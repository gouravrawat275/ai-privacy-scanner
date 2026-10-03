"""
Patent Architecture & Drawings Explorer

Presents the full Provisional Patent Application / Technical Disclosure Document,
interactive flow diagrams for FIG. 1, FIG. 2, FIG. 3, FIG. 4, and Aspect E,
and a claims-to-code traceability matrix.
"""

import streamlit as st


def patent_page():
    st.header("📜 Patent Architecture & Technical Disclosure")
    st.caption(
        "PROVISIONAL PATENT APPLICATION TECHNICAL DISCLOSURE: "
        "System and Methods for Predictive, Cross-Session, Consent-Aware, and Cryptographically Reversible Privacy Protection for Digital Photographs"
    )

    tab_overview, tab_diagrams, tab_claims, tab_benchmarks = st.tabs([
        "📋 Invention Summary",
        "📐 Drawings & Data Flows (FIG. 1 - 4)",
        "⚖️ Patent Claims Traceability",
        "⚡ Comparative Advantage Matrix"
    ])

    with tab_overview:
        st.subheader("Invention Field & Technical Gaps in Prior Art")
        st.markdown("""
        **Title:** *Predictive, Cross-Session, Consent-Aware, and Cryptographically Reversible Photo Privacy Protection System*

        **Field:** Digital image processing; computer vision; behavioral pattern analysis; applied cryptography; camera/capture-time systems.

        ---
        ### 🔍 The Five Foundational Gaps Addressed by this Invention:
        1. **Cross-Session Blindness (Aspect A):** Every prior-art system scores only a single image in isolation. None evaluate whether a *sequence* of otherwise benign photos, taken across days or weeks, reveals a habit, routine, or commute.
        2. **Metadata Reliance (Aspect B):** Prior-art systems detect location exposure solely via EXIF GPS tags. None address cases where metadata has been stripped by cameras, users, or social media platforms, yet visual landmarks or storefront signs still leak location.
        3. **Undifferentiated Face Detection (Aspect C):** Existing scanners treat every face identically. None distinguish a consenting family member or self-portrait from an unrecognized bystander or person who explicitly denied consent.
        4. **Irreversible or Insecure Redaction (Aspect D):** Gaussian blur and pixelation are susceptible to neural de-blurring reconstruction attacks and cannot be restored. This system introduces AES-256-GCM authenticated encryption of original pixel patches sealed in neutral placeholders.
        5. **Post-Hoc Capture Vulnerability (Aspect E):** All existing tools operate after the photo is already saved to disk. Aspect E shifts the intervention point to the live camera viewfinder *before* the shutter is actuated.
        """)

    with tab_diagrams:
        st.subheader("System Architecture & Process Flows")

        fig_choice = st.radio(
            "Select Drawing to Inspect",
            [
                "FIG. 1 — Aspect A: Cross-Session Pattern Risk Analysis",
                "FIG. 2 — Aspect B: Visual Location Inference Independent of Metadata",
                "FIG. 3 — Aspect C: Per-Person Consent Gating & Safe Post Flow",
                "FIG. 4 — Aspect D: Reversible Cryptographic Redaction vs Permanent Blur",
                "Aspect E — Pre-Capture Viewfinder HUD & Gated Shutter"
            ],
            index=0
        )

        if "FIG. 1" in fig_choice:
            st.markdown("### FIG. 1 — Aspect A Data-Flow Diagram")
            st.code("""
New Image ───────────► AI Privacy Scanner ───────────► Per-Image Findings ──┐
                                                                            │
                                                                            ▼
Local History Store (non-identifying attributes) ────────────────────► Pattern Risk Engine
  - Coarsened location grid (~1km cell)                                     │
  - Day-of-week & Time-of-day bucket                                        ▼
  - Recurring scene & background objects                           Pattern Risk Signal
  - NO image pixels, NO exact GPS, NO raw text                              │
                                                                            ▼
  ▲──────────────────────── Update after each scan ─────────────────────────┘
            """, language="text")
            st.info(
                "**Claim A1/A2 Grounding:** Stores coarsened geographic indicators and temporal buckets locally without "
                "retaining raw images or exact GPS, generating an additive secondary risk signal when recurring schedules emerge."
            )

        elif "FIG. 2" in fig_choice:
            st.markdown("### FIG. 2 — Aspect B Process Flow")
            st.code("""
Image Input ──┬──► Metadata Scanner ─────► GPS tag present? ──[YES]──► GPS-Based Finding
              │                                             └──[NO]───► (No metadata finding)
              │
              └──► Visual Location Inference (Parallel & Independent)
                     ├── Landmark Feature Matching (Local Reference DB)
                     ├── Storefront Sign & Street Name Regex (OCR Extracted)
                     └── Architectural & Environmental Cue Classifier
                                     │
                                     ▼
                     Visual Location-Risk Finding (Additive & Independent)
            """, language="text")
            st.info(
                "**Claim B1/B2 Grounding:** Operates directly on visual pixels, guaranteeing location exposure detection even when "
                "EXIF metadata was never recorded or has already been stripped by third-party platforms."
            )

        elif "FIG. 3" in fig_choice:
            st.markdown("### FIG. 3 — Aspect C Consent-Gating Flow")
            st.code("""
Image Input ──► Face Detection ──► Normalized Facial Embeddings (256-D)
                                                 │
                                                 ▼
                                   Compare against Consent Registry
                                     (Embedding ──► Consent Status)
                                                 │
                         ┌───────────────────────┴───────────────────────┐
                         ▼                                               ▼
                [Match: Consenting]                         [No Match / Non-Consenting]
                         │                                               │
                         ▼                                               ▼
             Allow in High Quality                          Trigger Safe Post Redaction
                ("Safe Post")                                 or Gated User Warning
            """, language="text")
            st.info(
                "**Claim C1/C2 Grounding:** Converts face detection into a per-individual consent-enforcement workflow. "
                "Withholds sharing actions when unconsented faces appear and offers 1-click Safe Post generation."
            )

        elif "FIG. 4" in fig_choice:
            st.markdown("### FIG. 4 — Aspect D Cryptographically Reversible Redaction")
            st.code("""
Flagged Region ──┬──► [Conventional Path] Blur / Pixelate (Not provably irreversible)
                 │
                 └──► [Inventive Path] AES-256-GCM Patch Encryption
                        ├── Extract pristine pixel patch & compress (zlib)
                        ├── Encrypt with key derived via PBKDF2 (100k rounds)
                        ├── Replace region with Opaque Visually Neutral Placeholder (Claim D2)
                        ├── Embed ciphertext in PNG metadata OR Steganographic LSB (Claim D3)
                        │
                        ▼
                 Single File Protected Output (Safe for Public Distribution)
                        │
                        ▼ (Later time, authorized party)
                 Recipient with Matching Passphrase/Key Decrypts & Restores 100% Bit-Exact
            """, language="text")
            st.info(
                "**Claim D1-D3 Grounding:** Neutral placeholder guarantees zero statistically recoverable information for "
                "unauthorized viewers, while the steganographically embedded ciphertext permits exact mathematical restoration."
            )

        else:
            st.markdown("### Aspect E — Pre-Capture Viewfinder HUD")
            st.code("""
Live Camera Viewfinder Feed ──► Fast Lightweight Detection Pipeline
                                  ├── Faces & Consent Status Lookup
                                  ├── Vehicle License Plate Recognition
                                  └── Sensitive Document & ID Keyword OCR
                                                 │
                                                 ▼
                               Pre-Capture Risk Threshold Evaluation
                                                 │
                         ┌───────────────────────┴───────────────────────┐
                         ▼                                               ▼
                [Risk Below Threshold]                          [Risk Above Threshold]
                         │                                               │
                         ▼                                               ▼
                Clear Shutter Indicator                     Real-Time Visual/Haptic Warning
                                                            + Actionable Reframing Guidance
                                                            + Shutter Protection Gate
            """, language="text")
            st.info(
                "**Claim E1/E2 Grounding:** Moves the point of intervention from post-hoc remediation to pre-capture prevention, "
                "warning the operator and suggesting physical reframing angles before the shutter control is pressed."
            )

    with tab_claims:
        st.subheader("Traceability Matrix: Patent Claims to Implementation")
        st.markdown("""
        | Claim | Title | Module Implementation | Automated Test Case | Status |
        | :--- | :--- | :--- | :--- | :--- |
        | **A1** | Cross-Session Non-Identifying Attributes | `modules/pattern_risk_engine.py:record_scan` | `tests/test_patent_aspects.py:test_aspect_a_cross_session_patterns` | ✅ Verified |
        | **A2** | Coarsened Location Indicator (~1km) | `modules/pattern_risk_engine.py:_coarsen_gps` | `tests/test_patent_aspects.py:test_aspect_a_cross_session_patterns` | ✅ Verified |
        | **B1** | Visual Location Inference (Landmark & OCR) | `modules/visual_location_inference.py:infer` | `tests/test_patent_aspects.py:test_aspect_b_visual_location_inference` | ✅ Verified |
        | **B2** | Functioning Independently of Stripped GPS | `modules/scanner.py:scan_array` | `tests/test_patent_aspects.py:test_aspect_b_visual_location_inference` | ✅ Verified |
        | **C1** | Per-Person Consent Gating & Embeddings | `modules/consent_registry.py:evaluate_image_consent` | `tests/test_patent_aspects.py:test_aspect_c_consent_gating` | ✅ Verified |
        | **C2** | Local Never-Transmitted Consent Storage | `modules/consent_registry.py` (Local SQLite) | `tests/test_patent_aspects.py:test_aspect_c_consent_gating` | ✅ Verified |
        | **D1** | AES-256-GCM Reversible Region Redaction | `modules/crypto_redaction.py:obscure_and_encrypt` | `tests/test_patent_aspects.py:test_aspect_d_cryptographic_reversible_redaction` | ✅ Verified |
        | **D2** | Neutral Placeholder (Zero Statistical Leakage) | `modules/crypto_redaction.py:neutral_placeholder` | `tests/test_patent_aspects.py:test_aspect_d_steganography_and_neutral_placeholder` | ✅ Verified |
        | **D3** | Steganographic Single-File Carrier | `modules/crypto_redaction.py:embed_steganographic` | `tests/test_patent_aspects.py:test_aspect_d_steganography_and_neutral_placeholder` | ✅ Verified |
        | **E1** | Pre-Capture Viewfinder Risk Evaluation | `ui/live_camera_page.py` & `api.py:/pre-capture/evaluate` | `tests/test_patent_aspects.py:test_aspect_e_pre_capture_risk_computation` | ✅ Verified |
        | **E2** | Pre-Capture Suggested Reframing Action | `ui/live_camera_page.py` | `tests/test_patent_aspects.py:test_aspect_e_pre_capture_risk_computation` | ✅ Verified |
        """)

    with tab_benchmarks:
        st.subheader("Prior Art Comparison & Competitive Advantages")
        st.markdown("""
        | Capability | Commercial Photo Tools | Academic Frameworks | Base System | **This Disclosed Invention** |
        | :--- | :--- | :--- | :--- | :--- |
        | **Temporal & Commute Pattern Analysis** | ❌ None (Single-image only) | ❌ None | ❌ None | **✅ Aspect A: 30-Day Multi-Image Routine Engine** |
        | **Pixel Location Inference (No GPS)** | ❌ Metadata Only | ⚠️ Cloud Only | ❌ Metadata Only | **✅ Aspect B: Offline Local Pixel & OCR Cues** |
        | **Per-Person Consent Gating** | ❌ Undifferentiated Faces | ❌ None | ❌ Undifferentiated | **✅ Aspect C: 256-D Local Face Registry & Safe Post** |
        | **Reversible Redaction Guarantee** | ❌ Permanent Blur Only | ⚠️ Fragile Watermarks | ❌ Permanent Blur | **✅ Aspect D: AES-256-GCM + Steganographic Carrier** |
        | **Pre-Capture Viewfinder HUD & Warnings** | ❌ Post-Capture Only | ❌ Post-Capture Only | ❌ Post-Capture Only | **✅ Aspect E: Pre-Capture Viewfinder Reframing HUD** |
        """)
