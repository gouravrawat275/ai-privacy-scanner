"""
Aspect A — Cross-Session Pattern Intelligence UI

Evaluates privacy risk across a history of multiple images rather than a single image in isolation.
Detects temporal routines, repeating location buckets, recurring background objects,
and schedule exposure patterns.
"""

import json
import streamlit as st

from modules.pattern_risk_engine import PatternRiskEngine


def pattern_page():
    st.header("📈 Cross-Session Pattern Intelligence (Aspect A)")
    st.caption(
        "A single photograph may seem benign in isolation, but sharing multiple photos over time "
        "can inadvertently expose your daily schedule, habits, home/work locations, and social connections. "
        "This engine analyzes accumulated non-identifying scan history to flag emerging recurrence risks."
    )

    username = st.session_state.get("app_user", "default_user")
    engine = PatternRiskEngine()

    analysis = engine.evaluate(username)
    history = engine.get_history_summary(username, limit=30)

    # Top summary metrics
    col1, col2, col3, col4 = st.columns(4)
    pattern_score = analysis.get("pattern_score", 0)
    level = analysis.get("pattern_level", "None")

    col1.metric("Pattern Risk Score", f"{pattern_score}/100", delta=level, delta_color="inverse" if pattern_score > 25 else "normal")
    col2.metric("Images in 30-Day Window", analysis.get("total_scans_in_window", 0))
    col3.metric("Detected Correlated Patterns", len(analysis.get("patterns", [])))
    col4.metric("Risk Posture", "ELEVATED" if pattern_score > 25 else "HEALTHY")

    # Patterns alert box
    patterns = analysis.get("patterns", [])
    if patterns:
        st.subheader("⚠️ Detected Behavioral & Spatial Patterns")
        for p in patterns:
            severity = p.get("severity", "medium").upper()
            detail = p.get("detail", "")
            if severity == "HIGH":
                st.error(f"🔴 **[{severity}]** {detail}")
            elif severity == "MEDIUM":
                st.warning(f"🟡 **[{severity}]** {detail}")
            else:
                st.info(f"🔵 **[{severity}]** {detail}")

        st.info(
            "💡 **Adversary Risk Insight:** Adversaries aggregating your public posts can stitch these recurring "
            "temporal markers and locations together to build an accurate profile of your whereabouts and predictable routines."
        )
    else:
        st.success("✅ **No Pattern Leaks Detected:** Your recent photo history shows good spatial and temporal diversity.")

    # Simulation Lab for Patent Aspect A Testing
    with st.expander("🧪 Aspect A Interactive Simulation Lab (Test Routine Exposure Detection)", expanded=not bool(history)):
        st.write(
            "Patent Aspect A detects a class of privacy risk that is **invisible to any single-image scan**: "
            "temporal and spatial routines revealed by a sequence of otherwise benign, low-risk photos. "
            "Use the controls below to simulate a realistic sequence of daily photos."
        )
        sim_c1, sim_c2 = st.columns(2)
        with sim_c1:
            if st.button("🚗 Simulate 5-Day Morning Commute Routine", use_container_width=True):
                # Seed 5 scans at same coarsened location around 8:30 AM
                for day_offset in range(1, 6):
                    sim_scan = {
                        'detections': {
                            'metadata': {'has_gps': True, 'raw': {'GPSInfo': {'GPSLatitude': (40, 42, 46), 'GPSLatitudeRef': 'N', 'GPSLongitude': (74, 0, 22), 'GPSLongitudeRef': 'W'}}},
                            'background_objects': [{'label': 'car'}, {'label': 'traffic light'}],
                        },
                        'visual_location': {'location_bucket': '40.71,-74.01', 'scene_labels': ['transportation', 'commercial']},
                        'risk': {'score': 25}
                    }
                    engine.record_scan(username, sim_scan)
                st.success("Seeded 5 daily morning commute scans. Refreshing analysis...")
                st.rerun()

        with sim_c2:
            if st.button("🏫 Simulate School Drop-Off Routine (Repeat Time & Place)", use_container_width=True):
                for day_offset in range(1, 5):
                    sim_scan = {
                        'detections': {
                            'metadata': {'has_gps': False},
                            'background_objects': [{'label': 'backpack'}, {'label': 'bicycle'}],
                        },
                        'visual_location': {'location_bucket': 'Oakridge Elementary Zone', 'scene_labels': ['educational']},
                        'risk': {'score': 15}
                    }
                    engine.record_scan(username, sim_scan)
                st.success("Seeded 4 school drop-off scans. Refreshing analysis...")
                st.rerun()

    # History Table & Breakdown
    st.markdown("---")
    st.subheader(f"Accumulated Non-Identifying Metadata History ({len(history)} entries)")
    st.caption("Privacy Guarantee: Only coarsened coordinates (~1km grid) and non-identifying category tokens are stored locally. Raw image pixels are never retained.")

    if history:
        rows = []
        for h in history:
            scene_labels = json.loads(h.get('scene_labels', '[]')) if isinstance(h.get('scene_labels'), str) else []
            bg_labels = json.loads(h.get('bg_object_labels', '[]')) if isinstance(h.get('bg_object_labels'), str) else []

            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            dow = days[h.get('day_of_week', 0)] if 0 <= h.get('day_of_week', 0) < 7 else "N/A"

            hours = ["Early Morning (5-9)", "Morning (9-12)", "Midday (12-14)", "Afternoon (14-17)", "Evening (17-21)", "Night (21-5)"]
            hb = hours[h.get('hour_bucket', 0)] if 0 <= h.get('hour_bucket', 0) < 6 else "N/A"

            rows.append({
                "Timestamp": h.get("timestamp", "")[:19].replace("T", " "),
                "Day": dow,
                "Time Window": hb,
                "Coarse Location Bucket": h.get("location_bucket") or "Unknown / Stripped",
                "Scene Cues": ", ".join(scene_labels) if scene_labels else "-",
                "Objects": ", ".join(bg_labels) if bg_labels else "-",
                "Scan Risk": h.get("risk_score", 0)
            })

        st.table(rows)

        col_clear, col_space = st.columns([1, 4])
        with col_clear:
            if st.button("🗑️ Clear My Pattern History"):
                engine.clear_history(username)
                st.success("Pattern history purged.")
                st.rerun()
    else:
        st.info("No prior scan history recorded yet. Scans performed in the Scanner or Camera page will appear here.")
