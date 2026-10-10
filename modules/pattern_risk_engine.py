"""
Aspect A — Cross-Session Pattern Risk Analysis

Maintains a local, never-transmitted history of prior scan results and
detected attributes (approximate location bucket, day-of-week, time-of-day,
recurring background objects) across multiple images, and computes a
secondary risk signal when a new image, considered together with that
history, reveals a temporal or spatial pattern not apparent from any single
image alone.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone, timedelta
from collections import Counter

from modules.database import connect_database

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'pattern_history.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS pattern_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    location_bucket TEXT,
    day_of_week INTEGER,
    hour_bucket INTEGER,
    scene_labels TEXT,
    bg_object_labels TEXT,
    risk_score INTEGER,
    scan_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_ph_user ON pattern_history(username);
CREATE INDEX IF NOT EXISTS idx_ph_loc ON pattern_history(location_bucket);
CREATE INDEX IF NOT EXISTS idx_ph_time ON pattern_history(timestamp);
"""

# --- Location bucketing (coarsens GPS to ~1km grid cells) ---

def _coarsen_gps(lat, lon, precision=2):
    """Round lat/lon to `precision` decimal places (~1km at precision=2)."""
    return f"{round(lat, precision)},{round(lon, precision)}"


def _hour_bucket(hour):
    """Map hour (0-23) into a coarse time-of-day bucket."""
    if 5 <= hour < 9:
        return 0   # early morning
    elif 9 <= hour < 12:
        return 1   # morning
    elif 12 <= hour < 14:
        return 2   # midday
    elif 14 <= hour < 17:
        return 3   # afternoon
    elif 17 <= hour < 21:
        return 4   # evening
    else:
        return 5   # night


def _connect(path=None):
    target_path = path or DB_PATH
    conn = connect_database(target_path)
    conn.executescript(SCHEMA)
    return conn


class PatternRiskEngine:
    """Evaluates accumulated scan history for recurrence patterns."""

    DB_PATH = DB_PATH

    # Thresholds
    LOCATION_REPEAT_THRESHOLD = 3      # same location bucket seen >= N times
    TIME_PATTERN_THRESHOLD = 3          # same day+hour bucket >= N times
    ROUTINE_WINDOW_DAYS = 30            # look back N days
    OBJECT_REPEAT_THRESHOLD = 4         # same bg object type >= N times

    def __init__(self, db_path=None):
        self.db_path = db_path or getattr(self, 'DB_PATH', DB_PATH)

    def _get_connection(self):
        target = getattr(self, 'db_path', None) or getattr(self, 'DB_PATH', DB_PATH)
        return _connect(target)

    def record_scan(self, username, scan_result, image_path=None):
        """Extract non-identifying attributes and append to history."""
        detections = scan_result.get('detections', {})
        meta = detections.get('metadata', {})

        # Coarsen location if GPS is available
        location_bucket = None
        raw = meta.get('raw', {})
        gps_info = raw.get('GPSInfo', {})
        if gps_info and meta.get('has_gps'):
            try:
                lat = self._dms_to_decimal(gps_info.get('GPSLatitude', ()), gps_info.get('GPSLatitudeRef', 'N'))
                lon = self._dms_to_decimal(gps_info.get('GPSLongitude', ()), gps_info.get('GPSLongitudeRef', 'E'))
                if lat is not None and lon is not None:
                    location_bucket = _coarsen_gps(lat, lon)
            except Exception:
                pass

        # Also accept visual-location inference results
        visual_loc = scan_result.get('visual_location', {})
        if not location_bucket and visual_loc.get('location_bucket'):
            location_bucket = visual_loc['location_bucket']

        now = datetime.now(timezone.utc)
        day_of_week = now.weekday()
        hour_bkt = _hour_bucket(now.hour)

        # Scene / background object labels
        bg_objects = detections.get('background_objects', [])
        bg_labels = sorted({o.get('label', '') for o in bg_objects if o.get('label')})

        # Scene-type labels from visual location inference
        scene_labels = visual_loc.get('scene_labels', [])

        scan_hash = hashlib.sha256(
            f"{username}:{now.isoformat()}:{location_bucket}".encode()
        ).hexdigest()[:16]

        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT INTO pattern_history
                   (username, timestamp, location_bucket, day_of_week,
                    hour_bucket, scene_labels, bg_object_labels,
                    risk_score, scan_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (username, now.isoformat(timespec='seconds'),
                 location_bucket, day_of_week, hour_bkt,
                 json.dumps(scene_labels), json.dumps(bg_labels),
                 int(scan_result.get('risk', {}).get('score', 0)),
                 scan_hash)
            )
            conn.commit()
        finally:
            conn.close()

        return scan_hash

    def evaluate(self, username):
        """
        Evaluate accumulated history for the user and return a pattern-risk
        result containing detected patterns and an aggregate signal.
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=self.ROUTINE_WINDOW_DAYS)).isoformat()
            rows = conn.execute(
                "SELECT * FROM pattern_history WHERE username = ? AND timestamp >= ? ORDER BY timestamp DESC",
                (username, cutoff)
            ).fetchall()
        finally:
            conn.close()

        if len(rows) < 2:
            return self._empty_result()

        patterns = []
        pattern_score = 0

        # --- 1. Location recurrence ---
        loc_counter = Counter()
        loc_entries = {}
        for r in rows:
            loc = r['location_bucket']
            if loc:
                loc_counter[loc] += 1
                loc_entries.setdefault(loc, []).append(r['timestamp'])
        for loc, count in loc_counter.items():
            if count >= self.LOCATION_REPEAT_THRESHOLD:
                patterns.append({
                    'type': 'location_recurrence',
                    'detail': f"Same approximate location appeared in {count} images over the past {self.ROUTINE_WINDOW_DAYS} days",
                    'location_bucket': loc,
                    'count': count,
                    'dates': loc_entries[loc][:5],
                    'severity': 'high' if count >= 5 else 'medium',
                })
                pattern_score += min(25, count * 5)

        # --- 2. Temporal routine detection (same day+hour repeats) ---
        time_counter = Counter()
        time_entries = {}
        for r in rows:
            key = (r['day_of_week'], r['hour_bucket'])
            time_counter[key] += 1
            time_entries.setdefault(key, []).append(r['timestamp'])
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hour_labels = ['early morning', 'morning', 'midday', 'afternoon', 'evening', 'night']
        for (dow, hb), count in time_counter.items():
            if count >= self.TIME_PATTERN_THRESHOLD:
                patterns.append({
                    'type': 'temporal_routine',
                    'detail': f"Images consistently taken on {day_names[dow]}s during {hour_labels[hb]} "
                              f"({count} occurrences)",
                    'day_of_week': dow,
                    'hour_bucket': hb,
                    'count': count,
                    'dates': time_entries[(dow, hb)][:5],
                    'severity': 'medium',
                })
                pattern_score += min(20, count * 4)

        # --- 3. Combined location + time = commute/routine ---
        loc_time_counter = Counter()
        for r in rows:
            if r['location_bucket']:
                key = (r['location_bucket'], r['day_of_week'], r['hour_bucket'])
                loc_time_counter[key] += 1
        for (loc, dow, hb), count in loc_time_counter.items():
            if count >= 2:
                patterns.append({
                    'type': 'routine_detected',
                    'detail': f"Routine detected: Same location on {day_names[dow]}s at {hour_labels[hb]} "
                              f"({count} times). This could reveal a commute, school drop-off, or regular habit.",
                    'location_bucket': loc,
                    'day_of_week': dow,
                    'hour_bucket': hb,
                    'count': count,
                    'severity': 'high',
                })
                pattern_score += min(30, count * 10)

        # --- 4. Recurring background objects ---
        all_obj_labels = []
        for r in rows:
            try:
                labels = json.loads(r['bg_object_labels'] or '[]')
                all_obj_labels.extend(labels)
            except (json.JSONDecodeError, TypeError):
                pass
        obj_counter = Counter(all_obj_labels)
        for label, count in obj_counter.items():
            if count >= self.OBJECT_REPEAT_THRESHOLD:
                patterns.append({
                    'type': 'recurring_object',
                    'detail': f"'{label}' appears in {count} recent images — "
                              f"this recurring element could help identify your environment",
                    'label': label,
                    'count': count,
                    'severity': 'low',
                })
                pattern_score += min(10, count * 2)

        pattern_score = min(pattern_score, 100)
        level = self._level_for(pattern_score)

        return {
            'pattern_score': pattern_score,
            'pattern_level': level,
            'risk_level': level.upper(),
            'patterns': patterns,
            'detected_patterns': patterns,
            'total_scans_in_window': len(rows),
            'window_days': self.ROUTINE_WINDOW_DAYS,
            'explanation': self._explain(patterns) if patterns else "No cross-session patterns detected.",
        }

    def get_history_summary(self, username, limit=20):
        """Return recent history entries (no image data, just attributes)."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, timestamp, location_bucket, day_of_week, hour_bucket, "
                "scene_labels, bg_object_labels, risk_score "
                "FROM pattern_history WHERE username = ? ORDER BY id DESC LIMIT ?",
                (username, limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    get_user_history_summary = get_history_summary

    def clear_history(self, username):
        """Allow user to clear their pattern history."""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM pattern_history WHERE username = ?", (username,))
            conn.commit()
        finally:
            conn.close()

    # --- Helpers ---

    @staticmethod
    def _dms_to_decimal(dms_tuple, ref):
        """Convert EXIF DMS GPS coordinates to decimal degrees."""
        if not dms_tuple or len(dms_tuple) < 3:
            return None
        try:
            d = float(dms_tuple[0])
            m = float(dms_tuple[1])
            s = float(dms_tuple[2])
            decimal = d + m / 60.0 + s / 3600.0
            if ref in ('S', 'W'):
                decimal = -decimal
            return decimal
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _level_for(score):
        if score <= 10:
            return 'None'
        elif score <= 25:
            return 'Low'
        elif score <= 50:
            return 'Medium'
        elif score <= 75:
            return 'High'
        return 'Critical'

    @staticmethod
    def _explain(patterns):
        """Generate a human-readable explanation of detected patterns."""
        lines = ["⚠️ Cross-session pattern analysis found the following:"]
        for i, p in enumerate(patterns, 1):
            lines.append(f"  {i}. [{p['severity'].upper()}] {p['detail']}")
        lines.append("")
        lines.append("These patterns, while each image may be individually low-risk, "
                      "could collectively reveal your routine, location, or habits.")
        return "\n".join(lines)

    @staticmethod
    def _empty_result():
        return {
            'pattern_score': 0,
            'pattern_level': 'None',
            'patterns': [],
            'total_scans_in_window': 0,
            'window_days': 30,
            'explanation': "Not enough scan history to detect patterns yet.",
        }
