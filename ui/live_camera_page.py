"""
Aspect E — Pre-Capture Privacy Risk Evaluation UI

Evaluates and communicates privacy risk to a device operator prior to image capture
rather than afterward. Provides a live camera viewfinder, pre-capture HUD metrics,
bounding box overlays, real-time consent checks, and actionable guidance to help
operators adjust framing, angle, or distance before taking a photo.
"""

import io
import os
import cv2
import numpy as np
import streamlit as st
from PIL import Image

from modules.scanner import PrivacyScanner
from modules.image_utils import apply_redactions
from modules.crypto_redaction import CryptoRedactor


def _create_synthetic_scene(scenario_type: str, shift_x: int = 0) -> np.ndarray:
    """Create a realistic pre-capture viewfinder frame for simulation testing."""
    W, H = 800, 500
    img = np.full((H, W, 3), (215, 220, 225), dtype=np.uint8)

    # Sky & Ground
    cv2.rectangle(img, (0, 0), (W, 250), (235, 215, 180), -1)  # Soft blue/sky
    cv2.rectangle(img, (0, 250), (W, H), (140, 145, 150), -1)  # Pavement

    if scenario_type == "street_plate":
        # Vehicle on the right that shifts out when panned left
        car_x = int(450 - shift_x)
        if car_x < W and car_x + 300 > 0:
            # Car body
            cv2.rectangle(img, (car_x, 220), (car_x + 300, 360), (40, 40, 160), -1)
            cv2.rectangle(img, (car_x + 40, 170), (car_x + 240, 220), (50, 50, 170), -1)
            # Wheels
            cv2.circle(img, (car_x + 60, 360), 28, (30, 30, 30), -1)
            cv2.circle(img, (car_x + 240, 360), 28, (30, 30, 30), -1)
            # License plate
            plate_x = car_x + 90
            cv2.rectangle(img, (plate_x, 300), (plate_x + 130, 335), (250, 250, 250), -1)
            cv2.rectangle(img, (plate_x, 300), (plate_x + 130, 335), (0, 0, 0), 2)
            cv2.putText(img, "MH12 AB 4521", (plate_x + 6, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

        # Subject standing in center
        cv2.circle(img, (200, 180), 30, (80, 70, 60), -1)
        cv2.rectangle(img, (160, 210), (240, 380), (120, 60, 50), -1)

    elif scenario_type == "bystander_storefront":
        # Storefront building in background
        cv2.rectangle(img, (0, 60), (W, 280), (190, 180, 170), -1)
        cv2.rectangle(img, (40, 80), (340, 140), (20, 70, 30), -1)
        cv2.putText(img, "STARBUCKS COFFEE", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (250, 250, 250), 2)
        cv2.putText(img, "742 Evergreen Terrace", (55, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1)

        # Bystander on side that can be reframed out
        bystander_x = int(620 + shift_x)
        if 0 < bystander_x < W - 50:
            cv2.circle(img, (bystander_x, 190), 26, (90, 80, 70), -1)
            cv2.rectangle(img, (bystander_x - 30, 216), (bystander_x + 30, 380), (50, 80, 120), -1)

        # Main subject
        cv2.circle(img, (280, 200), 35, (70, 60, 50), -1)
        cv2.rectangle(img, (230, 235), (330, 420), (130, 70, 60), -1)

    elif scenario_type == "desk_document":
        # Tabletop
        cv2.rectangle(img, (0, 100), (W, H), (160, 130, 100), -1)
        # ID Card on desk that can be reframed out
        doc_x = int(120 - shift_x)
        if doc_x > -150 and doc_x < W:
            cv2.rectangle(img, (doc_x, 260), (doc_x + 220, 380), (250, 250, 245), -1)
            cv2.rectangle(img, (doc_x, 260), (doc_x + 220, 380), (100, 100, 100), 2)
            cv2.putText(img, "DRIVER LICENSE", (doc_x + 10, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2)
            cv2.putText(img, "DOB: 05/18/1992", (doc_x + 10, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (20, 20, 20), 1)
            cv2.putText(img, "SSN: 123-45-6789", (doc_x + 10, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (20, 20, 20), 1)

        # Laptop on desk
        cv2.rectangle(img, (400, 180), (680, 360), (45, 45, 50), -1)
        cv2.rectangle(img, (415, 195), (665, 335), (180, 200, 220), -1)

    else:  # "clean_portrait"
        # Scenic background
        cv2.rectangle(img, (0, 0), (W, 280), (180, 210, 230), -1)
        cv2.rectangle(img, (0, 280), (W, H), (80, 150, 80), -1)
        # Consenting person in center
        cv2.circle(img, (400, 180), 40, (75, 65, 55), -1)
        cv2.rectangle(img, (340, 220), (460, 440), (40, 100, 160), -1)

    return img


def live_camera_page():
    st.header("📸 Pre-Capture Privacy Guard (Aspect E)")
    st.caption(
        "Evaluate privacy risks in real-time **before** capturing or saving a photograph. "
        "Provides live HUD metrics, bounding box overlays, real-time consent checks, and actionable reframing guidance."
    )

    scanner = PrivacyScanner(enable_background_objects=True)

    col_viewfinder, col_policy = st.columns([2, 1])

    with col_policy:
        st.subheader("🛡️ Pre-Capture Policy")
        target_scope = st.selectbox(
            "Intended Sharing Scope",
            ["social_media", "public", "internal_only", "commercial"],
            index=0,
            help="Pre-capture policy evaluates consent against this intended distribution."
        )
        strict_consent = st.checkbox(
            "Enforce Strict Consent Gating",
            value=True,
            help="Flags any unknown face as requiring consent before capture."
        )
        auto_crypto_lock = st.checkbox(
            "Auto-apply Reversible Crypto Lock on capture",
            value=False,
            help="If enabled, newly captured photos are automatically protected with AES-256-GCM."
        )
        if auto_crypto_lock:
            passphrase = st.text_input("Protection Passphrase", value="pre-capture-secret", type="password")
        else:
            passphrase = None

        viewfinder_source = st.radio(
            "Viewfinder Video Feed Source",
            [
                "🧪 Pre-Capture Simulation Lab (Test Scenarios)",
                "📸 Hardware Camera (Live Webcam)",
                "📁 Upload Custom Viewfinder Frame"
            ],
            index=0
        )

    frame_bgr = None

    with col_viewfinder:
        st.subheader("Live Viewfinder Feed")

        if viewfinder_source == "📸 Hardware Camera (Live Webcam)":
            camera_photo = st.camera_input("Aim camera at subject to evaluate framing risks:")
            if camera_photo is not None:
                raw_bytes = camera_photo.getvalue()
                pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
                frame_rgb = np.array(pil_img)
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        elif viewfinder_source == "🧪 Pre-Capture Simulation Lab (Test Scenarios)":
            sim_col1, sim_col2 = st.columns([1, 1])
            with sim_col1:
                scenario = st.selectbox(
                    "Select Viewfinder Scenario",
                    [
                        "Vehicle License Plate & Bystander (Street View)",
                        "Storefront Text & Address Marker (Visual Location)",
                        "Desk Workspace with ID Document / SSN",
                        "Clean Framing with Consenting Subject"
                    ]
                )
            with sim_col2:
                reframe_angle = st.slider(
                    "🔄 Camera Reframing Tilt / Pan Angle",
                    min_value=0,
                    max_value=60,
                    value=0,
                    step=5,
                    help="Adjust camera angle to simulate reframing away from sensitive elements in real-time."
                )

            scenario_map = {
                "Vehicle License Plate & Bystander (Street View)": "street_plate",
                "Storefront Text & Address Marker (Visual Location)": "bystander_storefront",
                "Desk Workspace with ID Document / SSN": "desk_document",
                "Clean Framing with Consenting Subject": "clean_portrait"
            }
            # Shift pixels proportional to tilt angle to simulate physical camera panning
            shift_px = int(reframe_angle * 6.5)
            frame_bgr = _create_synthetic_scene(scenario_map[scenario], shift_x=shift_px)

        else:
            uploaded_frame = st.file_uploader("Upload a frame to test pre-capture evaluation", type=["jpg", "jpeg", "png", "bmp"])
            if uploaded_frame is not None:
                pil_img = Image.open(io.BytesIO(uploaded_frame.getvalue())).convert("RGB")
                frame_rgb = np.array(pil_img)
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    # If a viewfinder frame is active
    if frame_bgr is not None:
        # Run fast pre-capture scan
        with st.spinner("Analyzing pre-capture viewfinder frame..."):
            faces = scanner.face_detector.detect(frame_bgr)
            plates = scanner.plate_detector.detect(frame_bgr)
            ocr = scanner.ocr_extractor.extract(frame_bgr)

            consent_eval = scanner.consent_registry.evaluate_image_consent(
                image_bgr=frame_bgr,
                detected_faces=faces,
                target_scope=target_scope,
                policy="STRICT" if strict_consent else "ALLOW_UNKNOWN"
            )

            vis_loc = scanner.visual_location_inferrer.infer(frame_bgr, ocr_result=ocr)

            # Compute pre-capture risk score
            base_score = len(faces) * 15 + len(plates) * 25
            if not consent_eval['can_share']:
                base_score += 30
            if vis_loc.get('has_visual_location_risk'):
                base_score += 25
            if any(f.get('type') in ('id_keyword', 'ssn_like', 'credit_card_like', 'passport_like') for f in ocr.get('findings', [])):
                base_score += 35

            pre_risk_score = min(100, base_score)
            risk_level = "Low" if pre_risk_score <= 15 else ("Medium" if pre_risk_score <= 45 else ("High" if pre_risk_score <= 75 else "Critical"))

        # Render HUD Dashboard
        st.markdown("---")
        st.subheader("⚡ Live Pre-Capture HUD Analysis (Aspect E)")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pre-Capture Risk", f"{pre_risk_score}/100", delta=risk_level, delta_color="inverse" if pre_risk_score > 20 else "normal")
        m2.metric("Detected Faces", len(faces))
        m3.metric("License Plates", len(plates))
        consent_status_str = "APPROVED" if consent_eval['can_share'] else "GATED"
        m4.metric("Consent Gate", consent_status_str, delta="OK" if consent_eval['can_share'] else "BLOCKED", delta_color="normal" if consent_eval['can_share'] else "inverse")

        # Actionable Pre-Capture Recommendations (Patent Claim E2)
        st.markdown("### 💡 Recommended Operator Actions Before Capture (Patent Claim E2)")
        recs = []
        if plates:
            recs.append("🚗 **Vehicle In Frame:** Legible license plate detected. *Action: Tilt camera up 10° or step left to exclude vehicle registration.*")
        if not consent_eval['can_share']:
            denied_faces = [d for d in consent_eval['face_decisions'] if d.get('consent_status') == 'DENIED']
            if denied_faces:
                recs.append(f"⛔ **Explicit Denial:** {denied_faces[0]['name']} has explicitly denied photo consent. *Action: Do not photograph or ensure face is fully excluded from frame.*")
            else:
                recs.append(f"⚠️ **Consent Gating:** {consent_eval['faces_gated']} face(s) lack registered consent for '{target_scope}'. *Action: Ask for verbal consent or use Safe Capture below to auto-obscure them.*")
        if vis_loc.get('has_visual_location_risk'):
            recs.append("📍 **Visual Location Clues:** Storefront, landmark text, or street sign visible in background. *Action: Angle viewfinder away from identifying exterior signage.*")
        if any(f.get('type') in ('id_keyword', 'ssn_like', 'credit_card_like') for f in ocr.get('findings', [])):
            recs.append("📄 **Sensitive Documents Detected:** Identity document or numeric pattern visible on desk. *Action: Remove paperwork from field of view before shooting.*")

        if not recs:
            st.success("✅ **FRAME CLEARED TO CAPTURE:** Zero privacy risk indicators detected. You can safely press the shutter button.")
        else:
            for r in recs:
                st.warning(r)

        # Annotated HUD overlay preview
        hud_bgr = frame_bgr.copy()
        # Draw faces
        for f in faces:
            x, y, w, h = [int(v) for v in f['bbox']]
            cv2.rectangle(hud_bgr, (x, y), (x + w, y + h), (0, 165, 255), 2)
            cv2.putText(hud_bgr, "Face", (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

        # Draw plates
        for p in plates:
            x, y, w, h = [int(v) for v in p['bbox']]
            cv2.rectangle(hud_bgr, (x, y), (x + w, y + h), (0, 215, 255), 2)
            cv2.putText(hud_bgr, "License Plate", (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 255), 2)

        # Draw consent tags
        for fd in consent_eval['face_decisions']:
            x, y, w, h = [int(v) for v in fd['bbox']]
            status = fd['consent_status']
            color = (0, 255, 0) if fd['can_share'] else (0, 0, 255)
            tag = f"{fd['name']}: {status}"
            cv2.putText(hud_bgr, tag, (x, min(hud_bgr.shape[0] - 5, y + h + 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

        hud_rgb = cv2.cvtColor(hud_bgr, cv2.COLOR_BGR2RGB)

        c1, c2 = st.columns(2)
        with c1:
            st.image(hud_rgb, caption="Pre-Capture Viewfinder HUD (Live Risk Overlays)", use_container_width=True)

        with c2:
            st.subheader("🛡️ Pre-Capture Shutter Actions")
            st.write(
                "Apply instant pre-capture protections before saving the image to disk or sharing to social media."
            )

            action = st.radio(
                "Shutter Actuation Action",
                [
                    "🔒 Reversible Cryptographic Lock (AES-256-GCM - Aspect D)",
                    "✨ Safe Post Redaction (Leaves Consenting Untouched - Aspect C)",
                    "📸 Raw Shutter Capture"
                ]
            )

            if action == "🔒 Reversible Cryptographic Lock (AES-256-GCM - Aspect D)":
                regions_to_lock = [{'bbox': f['bbox'], 'type': 'face'} for f in faces] + [{'bbox': p['bbox'], 'type': 'plate'} for p in plates]
                if not regions_to_lock:
                    h_f, w_f = frame_bgr.shape[:2]
                    regions_to_lock = [{'bbox': [w_f // 4, h_f // 4, w_f // 2, h_f // 2], 'type': 'custom'}]

                redactor = CryptoRedactor()
                crypto_res = redactor.obscure_and_encrypt(
                    image_bgr=frame_bgr,
                    regions=regions_to_lock,
                    passphrase=passphrase or "pre-capture-secret",
                    blur_style="neutral_placeholder"
                )
                safe_png = redactor.export_embedded_png(crypto_res['obscured_image_bgr'], crypto_res['encrypted_envelope'])
                st.download_button(
                    "💾 Actuate Shutter: Save Privacy-Locked PNG",
                    data=safe_png,
                    file_name="pre_capture_privacy_locked.png",
                    mime="image/png",
                    type="primary"
                )
                st.info(f"Protected {len(regions_to_lock)} regions with AES-256-GCM. Original pixels can be restored in the Cryptographic Vault.")

            elif action == "✨ Safe Post Redaction (Leaves Consenting Untouched - Aspect C)":
                redact_boxes = consent_eval.get("redaction_boxes", []) + plates
                redacted_bgr = apply_redactions(frame_bgr.copy(), redact_boxes, method="pixelate", padding=0.1)
                redacted_rgb = cv2.cvtColor(redacted_bgr, cv2.COLOR_BGR2RGB)
                out_buf = io.BytesIO()
                Image.fromarray(redacted_rgb).save(out_buf, format="PNG")
                st.download_button(
                    "💾 Actuate Shutter: Save Safe Post Photo",
                    data=out_buf.getvalue(),
                    file_name="pre_capture_safepost.png",
                    mime="image/png",
                    type="primary"
                )
            else:
                out_buf = io.BytesIO()
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                Image.fromarray(frame_rgb).save(out_buf, format="JPEG")
                st.download_button(
                    "💾 Actuate Shutter: Save Raw Photo",
                    data=out_buf.getvalue(),
                    file_name="captured_raw.jpg",
                    mime="image/jpeg"
                )

