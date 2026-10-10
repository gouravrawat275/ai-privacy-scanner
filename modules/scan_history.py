import os
import sqlite3
from datetime import datetime, timezone
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'scan_history.db')
SCHEMA = '\nCREATE TABLE IF NOT EXISTS scans (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,\n    timestamp TEXT NOT NULL,\n    username TEXT NOT NULL,\n    filename TEXT,\n    risk_score INTEGER,\n    risk_level TEXT,\n    num_faces INTEGER,\n    num_plates INTEGER,\n    num_ocr_findings INTEGER,\n    has_gps INTEGER,\n    possible_minor INTEGER\n)\n'

def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn

def log_scan(username, filename, result):
    detections = result['detections']
    risk = result['risk']
    conn = _connect()
    try:
        conn.execute('INSERT INTO scans\n               (timestamp, username, filename, risk_score, risk_level,\n                num_faces, num_plates, num_ocr_findings, has_gps, possible_minor)\n               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (datetime.now(timezone.utc).isoformat(timespec='seconds'), username, filename, int(risk['score']), risk['level'], len(detections.get('faces', [])), len(detections.get('plates', [])), len(detections.get('ocr', {}).get('findings', [])), int(bool(detections.get('metadata', {}).get('has_gps'))), int(any((c.get('flag_for_review') for c in detections.get('child_flags', []))))))
        conn.commit()
    finally:
        conn.close()

def get_recent(username, limit=50):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute('SELECT * FROM scans WHERE username = ? ORDER BY id DESC LIMIT ?', (username, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_stats(username):
    conn = _connect()
    try:
        total = conn.execute('SELECT COUNT(*) FROM scans WHERE username = ?', (username,)).fetchone()[0]
        avg_score = conn.execute('SELECT AVG(risk_score) FROM scans WHERE username = ?', (username,)).fetchone()[0] or 0
        by_level = dict(conn.execute('SELECT risk_level, COUNT(*) FROM scans WHERE username = ? GROUP BY risk_level', (username,)).fetchall())
        return {'total_scans': total, 'avg_risk_score': round(avg_score, 1), 'by_level': by_level}
    finally:
        conn.close()
