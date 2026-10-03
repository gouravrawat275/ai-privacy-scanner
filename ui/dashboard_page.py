"""
Enhanced Dashboard UI

Aggregates:
- Global scan history and privacy risk metrics
- Cross-session pattern risk overview
- Consent registry compliance summary
- Quick access to all privacy defense tools
"""

import streamlit as st

from modules.scan_history import get_recent, get_stats
from modules.pattern_risk_engine import PatternRiskEngine
from modules.consent_registry import ConsentRegistry


def dashboard_page():
    st.header("📊 Privacy Intelligence Dashboard")
    username = st.session_state.get("app_user")
    if not username:
        st.warning("Please log in to view your dashboard.")
        return

    # Gather data
    stats = get_stats(username)
    total = stats.get("total_scans", 0)
    avg = stats.get("avg_risk_score", 0)
    by_level = stats.get("by_level", {})

    pattern_engine = PatternRiskEngine()
    pattern_analysis = pattern_engine.evaluate(username)

    consent_reg = ConsentRegistry()
    subjects = consent_reg.list_subjects()

    # Top KPI Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Images Scanned", total)
    c2.metric("Mean Privacy Risk Score", f"{round(avg, 1)}/100")
    c3.metric("Cross-Session Pattern Risk", f"{pattern_analysis.get('pattern_score', 0)}/100", delta=pattern_analysis.get('pattern_level', 'None'))
    c4.metric("Enrolled Consent Subjects", len(subjects))

    st.markdown("---")

    # Risk level distribution
    col_chart, col_status = st.columns([1, 1])

    with col_chart:
        st.subheader("Risk Severity Breakdown")
        if by_level:
            for lvl, cnt in by_level.items():
                pct = int((cnt / max(1, total)) * 100)
                st.write(f"**{lvl}:** {cnt} scans ({pct}%)")
                st.progress(pct / 100.0)
        else:
            st.info("No scan history yet to compute distribution.")

    with col_status:
        st.subheader("Active Privacy Shield Status")
        st.write("✅ **Aspect A:** Cross-Session Pattern Engine active (30-day rolling window)")
        st.write("✅ **Aspect B:** Visual Location Inference active (pixel-level OCR & landmarks)")
        st.write(f"✅ **Aspect C:** Consent Gating active ({len(subjects)} registered profiles)")
        st.write("✅ **Aspect D:** Cryptographic Vault active (AES-256-GCM Reversible Redaction)")
        st.write("✅ **Aspect E:** Pre-Capture Viewfinder ready (real-time camera evaluation)")

    # Recent scans table
    st.markdown("---")
    st.subheader("Recent Image Scans")
    recent = get_recent(username, limit=15)
    if not recent:
        st.info("No scans yet. Navigate to the **Scanner** or **Live Camera** page to evaluate photographs.")
        return

    rows = []
    for scan in recent:
        rows.append({
            "Timestamp": scan.get("timestamp", "")[:19].replace("T", " "),
            "Image Filename": scan.get("filename", ""),
            "Risk Score": scan.get("risk_score", 0),
            "Risk Level": scan.get("risk_level", "Unknown"),
            "Faces Detected": scan.get("num_faces", 0),
        })

    st.table(rows)
