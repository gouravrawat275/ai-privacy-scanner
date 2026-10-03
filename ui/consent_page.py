"""
Aspect C — Per-Person Consent Registry UI

Allows individuals and organizations to manage recorded consent status, permitted scopes,
validity expiration dates, and facial embedding templates for identity matching.
"""

import io
from datetime import datetime, timedelta
import cv2
import numpy as np
import streamlit as st
from PIL import Image

from modules.consent_registry import ConsentRegistry


def consent_page():
    st.header("👥 Consent Registry & Gating (Aspect C)")
    st.caption(
        "Manage per-person consent status for image sharing. When an image is scanned, "
        "faces are matched against this registry using privacy-preserving facial embeddings to gate sharing "
        "or mandate automated redactions."
    )

    registry = ConsentRegistry()

    tab_subjects, tab_register, tab_audit = st.tabs(["Registered Individuals", "Register New Person", "Consent Policies & Scopes"])

    with tab_subjects:
        col_hdr1, col_hdr2 = st.columns([3, 2])
        with col_hdr1:
            st.subheader(f"Registered Subjects ({len(registry.list_subjects())})")
        with col_hdr2:
            if st.button("👥 Pre-load Demo Subject Profiles", use_container_width=True):
                # 1. Self - GRANTED
                registry.register_subject(
                    name="Alex Walker (Self)",
                    consent_status="GRANTED",
                    allowed_scopes=["public", "social_media", "internal_only", "commercial"],
                    notes="Primary account operator portrait"
                )
                # 2. Friend - GRANTED for social media
                registry.register_subject(
                    name="Dr. Sarah Chen (Colleague)",
                    consent_status="GRANTED",
                    allowed_scopes=["social_media", "internal_only"],
                    notes="Signed conference photo release"
                )
                # 3. Bystander - DENIED
                registry.register_subject(
                    name="Marcus Vance (Bystander)",
                    consent_status="DENIED",
                    allowed_scopes=["internal_only"],
                    notes="Explicitly requested not to appear in public social posts"
                )
                st.success("Pre-loaded 3 sample consent profiles!")
                st.rerun()

        subjects = registry.list_subjects()
        if not subjects:
            st.info("No individuals are currently registered in the consent database. Use the 'Pre-load Demo Subject Profiles' button above or 'Register New Person' tab to add records.")
        else:
            for s in subjects:
                status_icon = "🟢" if s['consent_status'] == "GRANTED" else ("🔴" if s['consent_status'] == "DENIED" else "🟡")
                with st.expander(f"{status_icon} {s['name']} — Status: {s['consent_status']}", expanded=False):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.write(f"**Subject ID:** `{s['subject_id']}`")
                        st.write(f"**Consent Status:** `{s['consent_status']}`")
                        st.write(f"**Allowed Scopes:** {', '.join(s['allowed_scopes']) if s['allowed_scopes'] else 'None'}")
                        if s.get('valid_until'):
                            st.write(f"**Valid Until:** `{s['valid_until']}`")
                        if s.get('notes'):
                            st.write(f"**Notes:** {s['notes']}")
                    with c2:
                        st.write(f"**Face Templates Enrolled:** {s.get('template_count', 0)}")
                        st.write(f"**Registered At:** {s.get('created_at', '')[:10]}")
                        st.write(f"**Last Updated:** {s.get('updated_at', '')[:10]}")

                    with c3:
                        st.write("**Quick Actions**")
                        new_status = st.selectbox(
                            "Update Status",
                            ["GRANTED", "DENIED", "RESTRICTED", "REVOKED", "EXPIRED"],
                            index=["GRANTED", "DENIED", "RESTRICTED", "REVOKED", "EXPIRED"].index(s['consent_status']),
                            key=f"status_select_{s['subject_id']}"
                        )
                        if st.button("Apply Status", key=f"apply_{s['subject_id']}"):
                            registry.update_consent(s['subject_id'], new_status)
                            st.success(f"Updated {s['name']} to {new_status}")
                            st.rerun()

                        if st.button("🗑️ Delete", key=f"del_{s['subject_id']}"):
                            registry.delete_subject(s['subject_id'])
                            st.warning(f"Deleted {s['name']}")
                            st.rerun()

    with tab_register:
        st.subheader("Enroll New Subject")
        with st.form("register_subject_form"):
            name = st.text_input("Full Name / Alias", placeholder="e.g. Jane Doe")
            status = st.selectbox("Initial Consent Status", ["GRANTED", "DENIED", "RESTRICTED", "REVOKED"])

            scopes = st.multiselect(
                "Permitted Scopes",
                ["public", "social_media", "internal_only", "commercial", "educational"],
                default=["public", "social_media", "internal_only"]
            )

            has_expiry = st.checkbox("Set Consent Expiration Date", value=False)
            valid_until_str = None
            if has_expiry:
                exp_date = st.date_input("Expires on", value=datetime.today() + timedelta(days=365))
                valid_until_str = exp_date.isoformat()

            notes = st.text_area("Notes / Purpose of Consent", placeholder="e.g. Employee portrait release for Q4 2026")

            uploaded_face = st.file_uploader(
                "Reference Face Image (Recommended for facial recognition matching)",
                type=["png", "jpg", "jpeg"]
            )

            submit_btn = st.form_submit_button("Register Subject")

            if submit_btn:
                if not name.strip():
                    st.error("Please provide a name or alias.")
                else:
                    ref_bgr = None
                    if uploaded_face is not None:
                        pil_img = Image.open(io.BytesIO(uploaded_face.getvalue())).convert("RGB")
                        ref_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

                    sub_id = registry.register_subject(
                        name=name.strip(),
                        consent_status=status,
                        allowed_scopes=scopes,
                        valid_until=valid_until_str,
                        notes=notes,
                        reference_image_bgr=ref_bgr
                    )
                    st.success(f"Successfully registered '{name}' with ID `{sub_id}`!")
                    st.rerun()

    with tab_audit:
        st.subheader("Consent Policy & Gating Architecture")
        st.markdown("""
        ### How Per-Person Consent Gating Works:
        1. **Facial Feature Extraction:** When a photograph is scanned, each detected face is converted into a privacy-preserving normalized 256-dimensional feature vector.
        2. **Registry Lookup:** Vectors are compared against enrolled templates using cosine similarity (`threshold >= 0.65`).
        3. **Policy Evaluation:**
           - **GRANTED:** The individual permits sharing across the specified scopes.
           - **DENIED:** Hard block. Image sharing is marked **PROHIBITED** or the face is strictly redacted.
           - **RESTRICTED:** Permitted only if the current sharing scope (e.g. `internal_only`) matches permitted scopes.
           - **EXPIRED / REVOKED:** Treated as unconsented; face requires redaction before distribution.
           - **UNKNOWN / UNREGISTERED:** Handled according to operator policy (`STRICT` mode flags for redaction; `ALLOW_UNKNOWN` permits bystanders).
        """)
