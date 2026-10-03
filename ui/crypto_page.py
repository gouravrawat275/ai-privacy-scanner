"""
Aspect D — Cryptographic Vault UI (Reversible Redaction)

Allows users to cryptographically obscure sensitive image regions using AES-256-GCM,
and later decrypt and restore the exact original pixel values using an authorized key or passphrase.
"""

import io
import json
import cv2
import numpy as np
import streamlit as st
from PIL import Image

from modules.crypto_redaction import CryptoRedactor
from modules.scanner import PrivacyScanner


def crypto_page():
    st.header("🔐 Cryptographic Vault & Reversible Redaction (Aspect D)")
    st.caption(
        "Unlike permanent irreversible blurring or pixelation, **cryptographically reversible redaction** "
        "obscures sensitive regions for public distribution while sealing the pristine original pixels inside an "
        "authenticated **AES-256-GCM** encrypted envelope. Only authorized key or passphrase holders can restore the original."
    )

    redactor = CryptoRedactor()

    tab_lock, tab_unlock = st.tabs(["🔒 Protect & Obscure Image", "🔓 Unlock & Restore Original Image"])

    # --- TAB 1: LOCK & ENCRYPT ---
    with tab_lock:
        st.subheader("Step 1: Upload Source Image")
        uploaded = st.file_uploader("Upload an image to cryptographically protect", type=["png", "jpg", "jpeg", "bmp"], key="crypto_upload")

        if uploaded is not None:
            raw_bytes = uploaded.getvalue()
            pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            img_rgb = np.array(pil_img)
            img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

            st.image(img_rgb, caption="Source Image", use_container_width=True)

            st.subheader("Step 2: Protection & Encryption Settings")
            c1, c2 = st.columns(2)
            with c1:
                key_mode = st.radio("Key Mechanism", ["Human Passphrase (PBKDF2)", "Generate Random 256-bit AES Key"])
                if key_mode == "Human Passphrase (PBKDF2)":
                    passphrase = st.text_input("Enter Secret Passphrase", type="password", value="MySecretPassword123!")
                    raw_key = None
                else:
                    passphrase = None
                    raw_key = redactor.generate_random_key()
                    st.text_input("Generated 256-bit Key (Save this!)", value=raw_key, disabled=True)

                embed_mode = st.radio(
                    "Payload Encapsulation Mechanism",
                    [
                        "PNG Metadata Chunk (Lossless, Bit-Exact Background)",
                        "Steganographic Pixel LSB (Claim D3: In-Pixel Invisible Carrier)",
                        "Standalone Envelope File (.json)"
                    ],
                    index=0,
                    help="Metadata chunk stores payload in PNG tEXt. Steganography embeds ciphertext bits directly into the image's low-order color bits."
                )

            with c2:
                blur_style = st.selectbox(
                    "Obscuration Visual Style",
                    [
                        "neutral_placeholder (Claim D1/D2: Zero Statistical Leakage)",
                        "solid_tile (Uniform Opaque Slate Tile)",
                        "pixelate (Adaptive Mosaic)",
                        "blur (Heavy Gaussian Blur)",
                        "blackout (Solid Black)"
                    ],
                    index=0
                )
                selected_style = blur_style.split(" ")[0]
                auto_detect = st.checkbox("Automatically Detect & Lock Faces & Plates", value=True)

            if st.button("🔒 Apply Cryptographic Privacy Lock", type="primary"):
                regions = []
                if auto_detect:
                    scanner = PrivacyScanner(enable_background_objects=False)
                    faces = scanner.face_detector.detect(img_bgr)
                    plates = scanner.plate_detector.detect(img_bgr)
                    for f in faces:
                        regions.append({'bbox': f['bbox'], 'type': 'face', 'label': 'Face'})
                    for p in plates:
                        regions.append({'bbox': p['bbox'], 'type': 'plate', 'label': 'Plate'})

                if not regions:
                    st.warning("No sensitive regions automatically detected. Locking center area as demonstration.")
                    h, w = img_bgr.shape[:2]
                    regions.append({'bbox': [w // 4, h // 4, w // 2, h // 2], 'type': 'custom', 'label': 'Center Box'})

                with st.spinner("Encrypting original pixels with AES-256-GCM..."):
                    crypto_result = redactor.obscure_and_encrypt(
                        image_bgr=img_bgr,
                        regions=regions,
                        passphrase=passphrase,
                        raw_key_b64=raw_key,
                        blur_style=selected_style
                    )

                    use_stego = "Steganographic" in embed_mode
                    # Export as embedded PNG
                    embedded_png = redactor.export_embedded_png(
                        crypto_result['obscured_image_bgr'],
                        crypto_result['encrypted_envelope'],
                        use_steganography=use_stego
                    )

                st.success(f"Successfully cryptographically locked {crypto_result['regions_count']} region(s) using {selected_style}!")

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    obscured_rgb = cv2.cvtColor(crypto_result['obscured_image_bgr'], cv2.COLOR_BGR2RGB)
                    st.image(obscured_rgb, caption=f"Obscured Public-Safe Output ({selected_style})", use_container_width=True)

                with col_res2:
                    st.markdown("### 📦 Download Protected Package")
                    st.write(
                        "The protected image below carries the AES-256-GCM encrypted envelope. "
                        f"Encapsulation mode: **{embed_mode.split('(')[0].strip()}**."
                    )
                    st.download_button(
                        "📥 Download PrivacyLock PNG Image",
                        data=embedded_png,
                        file_name=f"privacylock_{uploaded.name.split('.')[0]}.png",
                        mime="image/png"
                    )

                    envelope_json_str = json.dumps(crypto_result['encrypted_envelope'], indent=2)
                    st.download_button(
                        "📄 Download Cryptographic Envelope (.json)",
                        data=envelope_json_str,
                        file_name=f"privacylock_envelope_{uploaded.name.split('.')[0]}.json",
                        mime="application/json"
                    )

                    with st.expander("Inspect Encrypted Cryptographic Envelope"):
                        st.json(crypto_result['encrypted_envelope'])

    # --- TAB 2: UNLOCK & RESTORE ---
    with tab_unlock:
        st.subheader("Step 1: Upload Privacy-Locked Image")
        locked_file = st.file_uploader("Upload a PrivacyLock PNG (or obscured image + envelope)", type=["png", "jpg", "jpeg"], key="unlock_upload")

        if locked_file is not None:
            file_bytes = locked_file.getvalue()
            loaded_bgr, embedded_envelope = redactor.load_embedded_png(file_bytes)

            has_embedded = embedded_envelope is not None
            if has_embedded:
                st.success("✅ Valid PrivacyLock payload detected inside PNG metadata!")
            else:
                st.info("No embedded metadata found. You may manually paste the JSON cryptographic envelope below.")

            envelope_to_use = embedded_envelope
            if not has_embedded:
                env_text = st.text_area("Paste Encrypted Envelope JSON")
                if env_text:
                    try:
                        envelope_to_use = json.loads(env_text)
                    except Exception:
                        st.error("Invalid JSON string.")

            col_auth1, col_auth2 = st.columns(2)
            with col_auth1:
                unlock_pass = st.text_input("Decryption Passphrase", type="password", key="unlock_pass_input")
            with col_auth2:
                unlock_key = st.text_input("Or Raw 256-bit AES Key (Base64)", key="unlock_key_input")

            if st.button("🔓 Decrypt & Restore Original Pixels", type="primary"):
                if not envelope_to_use:
                    st.error("Missing cryptographic envelope.")
                elif not unlock_pass and not unlock_key:
                    st.error("Please enter the passphrase or secret key.")
                else:
                    with st.spinner("Authenticating AES-256-GCM ciphertext tag and restoring pixels..."):
                        success, restored_bgr, msg = redactor.decrypt_and_restore(
                            obscured_image_bgr=loaded_bgr,
                            envelope=envelope_to_use,
                            passphrase=unlock_pass if unlock_pass else None,
                            raw_key_b64=unlock_key if unlock_key else None
                        )

                    if success and restored_bgr is not None:
                        st.success(f"🎉 {msg}")
                        restored_rgb = cv2.cvtColor(restored_bgr, cv2.COLOR_BGR2RGB)
                        st.image(restored_rgb, caption="Restored Original Image (100% Bit-Exact)", use_container_width=True)

                        out_buf = io.BytesIO()
                        Image.fromarray(restored_rgb).save(out_buf, format="PNG")
                        st.download_button(
                            "📥 Download Restored Original Image",
                            data=out_buf.getvalue(),
                            file_name=f"restored_{locked_file.name}",
                            mime="image/png"
                        )
                    else:
                        st.error(f"❌ {msg}")
