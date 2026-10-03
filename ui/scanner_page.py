"""
Comprehensive Multi-Aspect Privacy Scanner UI

Evaluates:
- Base detections: faces, license plates, OCR document text, minors, metadata, bg objects
- Aspect B: Visual Location Inference independent of GPS metadata
- Aspect A: Cross-session pattern recurrence risk
- Aspect C: Per-person consent gating compliance
- Aspect D: Cryptographically reversible redaction (AES-256-GCM) & permanent blurring
"""

import io
import os
import tempfile
import cv2
import numpy as np
import streamlit as st
from PIL import Image

from modules.image_utils import apply_redactions
from modules.scanner import PrivacyScanner
from modules.crypto_redaction import CryptoRedactor


def scanner_page():
    st.header("🛡️ Multi-Aspect AI Privacy Scanner")
    st.caption(
        "Evaluate image privacy across all five dimensions: individual identifiers, "
        "visual location clues, cross-session patterns, per-person consent status, and reversible encryption."
    )

    username = st.session_state.get("app_user", "default_user")

    # Upload and controls
    c_up, c_conf = st.columns([2, 1])

    with c_conf:
        st.subheader("⚙️ Scan Settings")
        target_scope = st.selectbox(
            "Intended Sharing Scope",
            ["social_media", "public", "internal_only", "commercial", "educational"],
            index=0,
            help="Consent policies evaluate compliance against this target distribution scope."
        )
        consent_policy = st.radio(
            "Consent Policy",
            ["STRICT", "ALLOW_UNKNOWN"],
            index=0,
            help="STRICT requires verified consent for every visible person. ALLOW_UNKNOWN permits unverified bystanders."
        )

    with c_up:
        uploaded = st.file_uploader(
            "Upload an image to scan (JPG, PNG, BMP)",
            type=["png", "jpg", "jpeg", "bmp"]
        )

    if uploaded is None:
        st.info("👆 Upload an image above to run a comprehensive multi-aspect privacy scan.")
        return

    # Load image
    image = Image.open(io.BytesIO(uploaded.getvalue())).convert("RGB")
    img_rgb = np.array(image)
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    suffix = os.path.splitext(uploaded.name)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name

    try:
        with st.spinner("Running holistic 5-aspect privacy audit..."):
            scanner = PrivacyScanner(enable_background_objects=True)
            result = scanner.scan_array(
                img_bgr,
                image_path=tmp_path,
                username=username,
                target_scope=target_scope,
                consent_policy=consent_policy,
                record_in_history=True
            )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    detections = result.get("detections", {})
    risk = result.get("risk", {})
    vis_loc = result.get("visual_location", {})
    consent = result.get("consent", {})
    pattern_risk = result.get("pattern_risk", {})

    # Top-Level Executive Dashboard
    st.markdown("---")
    st.subheader("📊 Holistic Risk Evaluation")

    score = risk.get("score", 0)
    level = risk.get("level", "Low")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Overall Risk Score", f"{score}/100", delta=level, delta_color="inverse" if score > 20 else "normal")
    m2.metric("Detected Faces", len(detections.get("faces", [])))
    m3.metric("License Plates", len(detections.get("plates", [])))

    vis_risk_str = "REVEALED" if vis_loc.get("has_visual_location_risk") else "CLEAN"
    m4.metric("Visual Location", vis_risk_str, delta="METADATA-INDEPENDENT", delta_color="inverse" if vis_loc.get("has_visual_location_risk") else "normal")

    consent_gate_str = consent.get("overall_decision", "APPROVED")
    m5.metric("Consent Gate", consent_gate_str, delta=f"{consent.get('faces_gated', 0)} Gated", delta_color="inverse" if not consent.get("can_share", True) else "normal")

    # Image preview + tabs
    col_img, col_tabs = st.columns([1, 1])

    # Annotated HUD visualization
    annotated_bgr = img_bgr.copy()
    h_img, w_img = annotated_bgr.shape[:2]

    # Draw plates in yellow
    for p in detections.get("plates", []):
        x, y, w, h = [int(v) for v in p['bbox']]
        cv2.rectangle(annotated_bgr, (x, y), (x + w, y + h), (0, 215, 255), 2)
        cv2.putText(annotated_bgr, "License Plate", (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 215, 255), 2)

    # Draw faces with consent status
    gated_boxes = consent.get("redaction_boxes", [])
    for fd in consent.get("face_decisions", []):
        x, y, w, h = [int(v) for v in fd['bbox']]
        can_share = fd.get('can_share', False)
        box_color = (0, 255, 0) if can_share else (0, 0, 255)
        status_lbl = f"{fd.get('name', 'Person')}: {fd.get('consent_status', 'UNKNOWN')}"
        cv2.rectangle(annotated_bgr, (x, y), (x + w, y + h), box_color, 2)
        cv2.putText(annotated_bgr, status_lbl, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

    annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)

    # Image preview + tabs
    col_img, col_tabs = st.columns([1, 1])

    with col_img:
        preview_tab1, preview_tab2 = st.tabs(["Original Upload", "🛡️ Detection Overlays (HUD)"])
        with preview_tab1:
            st.image(image, caption="Original Upload", use_container_width=True)
        with preview_tab2:
            st.image(annotated_rgb, caption="Privacy Scanner HUD (Green=Consenting, Red=Gated, Yellow=Plates)", use_container_width=True)

        if not consent.get("can_share", True):
            st.error(f"⛔ **SHARING GATE:** {consent.get('overall_decision')} — One or more individuals have not provided valid consent.")
        elif vis_loc.get("has_visual_location_risk"):
            st.warning("⚠️ **LOCATION LEAK:** Visual features reveal capture location even without GPS metadata.")
        else:
            st.success("✅ **CLEARED:** No critical privacy impediments detected.")

    with col_tabs:
        t_base, t_visloc, t_consent, t_pattern = st.tabs([
            "🔍 Base Findings",
            "📍 Visual Location",
            "👥 Consent Gating",
            "📈 Pattern Risk"
        ])

        with t_base:
            st.markdown("#### Primary Identifiers & Exposure")
            if risk.get("breakdown"):
                for item in risk.get("breakdown", []):
                    st.write(f"- **{item['category']}**: {item['detail']} *(+{item['points']} pts)*")
            else:
                st.write("No base privacy flags.")

            if risk.get("suggestions"):
                st.markdown("#### Remediation Suggestions")
                for s in risk.get("suggestions", []):
                    st.warning(s)

        with t_visloc:
            st.markdown("#### Aspect B: Pixel-Level Location Inference")
            st.caption("Analyzes storefronts, landmark text, street signs, and architectural cues directly from image pixels.")
            if vis_loc.get("has_visual_location_risk"):
                st.error(f"**Confidence:** {int(vis_loc.get('overall_confidence', 0)*100)}%")
                if vis_loc.get("location_bucket"):
                    st.write(f"**Inferred Location:** `{vis_loc.get('location_bucket')}`")

                findings = vis_loc.get("findings", [])
                for f in findings:
                    st.write(f"- `[{f.get('type')}]` {f.get('detail')}")

                if vis_loc.get("scene_labels"):
                    st.write(f"**Scene Type Cues:** {', '.join(vis_loc.get('scene_labels'))}")
            else:
                st.success("No visual location indicators detected in image pixels.")

        with t_consent:
            st.markdown("#### Aspect C: Per-Person Consent Verification")
            st.caption("Face embeddings matched against local encrypted consent registry.")
            st.write(f"**Evaluated Faces:** {consent.get('faces_evaluated', 0)}")
            st.write(f"**Passed:** {consent.get('faces_passed', 0)} | **Gated:** {consent.get('faces_gated', 0)}")

            for fd in consent.get("face_decisions", []):
                with st.expander(f"Face #{fd['face_index'] + 1}: {fd['name']} ({fd['consent_status']})", expanded=True):
                    st.write(f"- **Status:** `{fd['consent_status']}`")
                    st.write(f"- **Can Share:** `{'YES' if fd['can_share'] else 'NO'}`")
                    st.write(f"- **Reason:** {fd['reason']}")
                    if fd.get('similarity'):
                        st.write(f"- **Template Match Confidence:** {int(fd['similarity'] * 100)}%")

        with t_pattern:
            st.markdown("#### Aspect A: Cross-Session Routine Exposure")
            st.caption("Risk evaluated across historical scans over a rolling 30-day window.")
            p_score = pattern_risk.get("pattern_score", 0)
            p_level = pattern_risk.get("pattern_level", "None")
            st.write(f"**Accumulated Pattern Risk:** {p_score}/100 ({p_level})")

            pats = pattern_risk.get("patterns", [])
            if pats:
                for p in pats:
                    st.warning(f"- **[{p.get('severity', '').upper()}]** {p.get('detail')}")
            else:
                st.info("No recurring schedule or location patterns detected across your scan history.")

    # --- DEFENSE & REDACTION CONTROLS ---
    st.markdown("---")
    st.subheader("🛡️ Privacy Defense & Obscuration")

    tab_safepost, tab_perm, tab_crypto = st.tabs([
        "✨ Safe Post (Consent-Aware Auto Redact)",
        "Permanent Irreversible Redaction",
        "🔐 Cryptographically Reversible Redaction (Aspect D)"
    ])

    # Safe Post (FIG. 3: Consenting = untouched, Non-consenting = redacted)
    with tab_safepost:
        st.markdown("#### 🌟 1-Click Safe Post Generator (Aspect C & FIG. 3)")
        st.caption(
            "Automatically leaves consenting family/friends in full high quality while redacting only "
            "unrecognized bystanders, denied subjects, and vehicle license plates."
        )
        sp_c1, sp_c2 = st.columns(2)
        with sp_c1:
            sp_boxes = []
            # Only unconsented faces
            sp_boxes.extend(consent.get("redaction_boxes", []))
            # Plates
            sp_boxes.extend(detections.get("plates", []))

            st.write(f"- Unconsented / bystander faces to obscure: **{len(consent.get('redaction_boxes', []))}**")
            st.write(f"- Consenting faces preserved: **{consent.get('faces_passed', 0)}**")
            st.write(f"- License plates to obscure: **{len(detections.get('plates', []))}**")

            sp_style = st.selectbox("Safe Post Obscuration Method", ["pixelate", "blur", "solid_tile"], index=0, key="sp_style")
            sp_redacted_bgr = apply_redactions(img_bgr.copy(), sp_boxes, method=sp_style if sp_style != "solid_tile" else "blackout", padding=0.1)
            sp_redacted_rgb = cv2.cvtColor(sp_redacted_bgr, cv2.COLOR_BGR2RGB)

        with sp_c2:
            st.image(sp_redacted_rgb, caption="Safe Post Image (Ready for Social Media / Sharing)", use_container_width=True)
            sp_out = io.BytesIO()
            Image.fromarray(sp_redacted_rgb).save(sp_out, format="PNG")
            st.download_button(
                "🚀 Download Safe Post Image",
                data=sp_out.getvalue(),
                file_name=f"safepost_{uploaded.name.split('.')[0]}.png",
                mime="image/png",
                type="primary"
            )

    # Perm Redaction
    with tab_perm:
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            blur_faces = st.checkbox("Redact Faces", value=True)
            blur_plates = st.checkbox("Redact License Plates", value=True)
            blur_unconsented_only = st.checkbox("Only Redact Unconsented Faces", value=False)
            padding = st.slider("Padding around detected regions", 0.0, 0.35, 0.15, 0.05)

        boxes = []
        if blur_faces:
            if blur_unconsented_only:
                boxes.extend(consent.get("redaction_boxes", []))
            else:
                boxes.extend(detections.get("faces", []))
        if blur_plates:
            boxes.extend(detections.get("plates", []))

        redacted_bgr = apply_redactions(
            img_bgr.copy(),
            boxes,
            method="auto",
            padding=padding,
            feather=True
        )
        redacted_rgb = cv2.cvtColor(redacted_bgr, cv2.COLOR_BGR2RGB)

        with c_p2:
            st.image(redacted_rgb, caption="Permanently Redacted Image", use_container_width=True)
            output = io.BytesIO()
            Image.fromarray(redacted_rgb).save(output, format="PNG")
            st.download_button(
                "📥 Download Permanently Redacted Image",
                data=output.getvalue(),
                file_name=f"redacted_{uploaded.name}",
                mime="image/png"
            )

    # Cryptographic Reversible Redaction
    with tab_crypto:
        st.write(
            "Cryptographically seals original pixels with **AES-256-GCM** inside an authenticated PNG envelope. "
            "Public viewers only see neutral placeholders or blurred regions, with **zero statistical leakage**. "
            "The designated key holder can restore 100% bit-exact original quality anytime."
        )

        cr_col1, cr_col2 = st.columns(2)
        with cr_col1:
            crypto_pass = st.text_input("Enter Key / Passphrase for Restoration", type="password", value="MySecretPassphrase123!", key="scanner_crypto_pass")
            crypto_style = st.selectbox(
                "Obscuration Visual Filter",
                [
                    "neutral_placeholder (Claim D1/D2: Zero Statistical Leakage)",
                    "solid_tile (Opaque Uniform Slate)",
                    "pixelate (Adaptive Mosaic)",
                    "blur (Gaussian Blur)",
                    "blackout (Black Fill)"
                ],
                index=0,
                key="scanner_crypto_style"
            )
            selected_crypto_style = crypto_style.split(" ")[0]

            crypto_embed_mode = st.radio(
                "Carrier Format",
                ["PNG Metadata Chunk (Lossless, Bit-Exact)", "Steganographic Pixel LSB (Claim D3: In-Pixel Carrier)"],
                index=0,
                key="scanner_crypto_embed"
            )
            include_unconsented = st.checkbox("Lock Unconsented Faces", value=True)
            include_plates = st.checkbox("Lock License Plates", value=True)

        crypto_regions = []
        if include_unconsented:
            for b in consent.get("redaction_boxes", []):
                crypto_regions.append({'bbox': b, 'type': 'unconsented_face'})
            if not crypto_regions:
                for f in detections.get("faces", []):
                    crypto_regions.append({'bbox': f['bbox'], 'type': 'face'})
        if include_plates:
            for p in detections.get("plates", []):
                crypto_regions.append({'bbox': p['bbox'], 'type': 'plate'})

        if st.button("🔒 Generate PrivacyLock Protected PNG", type="primary"):
            redactor = CryptoRedactor()
            crypto_res = redactor.obscure_and_encrypt(
                image_bgr=img_bgr,
                regions=crypto_regions,
                passphrase=crypto_pass,
                blur_style=selected_crypto_style
            )
            use_stego = "Steganographic" in crypto_embed_mode
            embedded_png = redactor.export_embedded_png(
                crypto_res['obscured_image_bgr'],
                crypto_res['encrypted_envelope'],
                use_steganography=use_stego
            )

            with cr_col2:
                obscured_rgb = cv2.cvtColor(crypto_res['obscured_image_bgr'], cv2.COLOR_BGR2RGB)
                st.image(obscured_rgb, caption=f"PrivacyLock Output ({selected_crypto_style})", use_container_width=True)
                st.download_button(
                    "📥 Download PrivacyLock PNG Image",
                    data=embedded_png,
                    file_name=f"privacylock_{uploaded.name.split('.')[0]}.png",
                    mime="image/png"
                )
                st.success(f"Encrypted {crypto_res['regions_count']} region(s). Restore anytime in the Cryptographic Vault.")
