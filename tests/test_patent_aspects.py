import os
import sys
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.pattern_risk_engine import PatternRiskEngine
from modules.visual_location_inference import VisualLocationInference
from modules.consent_registry import ConsentRegistry, FaceEmbeddingExtractor
from modules.crypto_redaction import CryptoRedactor
from modules.scanner import PrivacyScanner
from modules.risk_analyzer import compute_risk


def test_aspect_a_cross_session_patterns():
    """Verify Aspect A: cross-session pattern risk detection."""
    test_db = os.path.join(os.path.dirname(__file__), '_test_pattern.db')
    if os.path.exists(test_db):
        os.remove(test_db)

    engine = PatternRiskEngine()
    engine.DB_PATH = test_db

    username = "test_routine_user"
    engine.clear_history(username)

    # Empty history
    res0 = engine.evaluate(username)
    assert res0['pattern_score'] == 0
    assert res0['pattern_level'] == 'None'

    # Accumulate 4 scans with identical recurring location & midday time
    for i in range(4):
        scan_mock = {
            'detections': {
                'metadata': {'has_gps': True, 'raw': {'GPSInfo': {'GPSLatitude': (40, 42, 46), 'GPSLatitudeRef': 'N', 'GPSLongitude': (74, 0, 22), 'GPSLongitudeRef': 'W'}}},
                'background_objects': [{'label': 'laptop'}],
            },
            'risk': {'score': 30}
        }
        engine.record_scan(username, scan_mock)

    res = engine.evaluate(username)
    assert res['total_scans_in_window'] >= 4
    assert res['pattern_score'] > 20
    assert len(res['patterns']) > 0
    # Clean up
    engine.clear_history(username)
    if os.path.exists(test_db):
        os.remove(test_db)


def test_aspect_b_visual_location_inference():
    """Verify Aspect B: visual location inference independent of metadata."""
    vli = VisualLocationInference()

    # Landmark matching
    mock_ocr = {
        'enabled': True,
        'raw_text': 'I am standing in front of the Taj Mahal in Agra right now!'
    }
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    res = vli.infer(dummy_img, ocr_result=mock_ocr)

    assert res['has_visual_location_risk'] is True
    assert res['location_revealed'] is True
    assert res['risk_score'] > 0
    assert any(f['type'] == 'landmark_match' for f in res['findings'])
    assert 'Taj Mahal' in res['location_bucket']

    # Address matching
    mock_ocr_addr = {
        'enabled': True,
        'raw_text': 'Visit us at 742 Evergreen Terrace near Starbucks coffee'
    }
    res_addr = vli.infer(dummy_img, ocr_result=mock_ocr_addr)
    assert res_addr['has_visual_location_risk'] is True
    types = [f['type'] for f in res_addr['findings']]
    assert 'address_detected' in types or 'business_name' in types


def test_aspect_c_consent_gating():
    """Verify Aspect C: per-person consent gating with facial embeddings."""
    test_db = os.path.join(os.path.dirname(__file__), '_test_consent.db')
    if os.path.exists(test_db):
        os.remove(test_db)

    registry = ConsentRegistry(db_path=test_db)

    # Register person with DENIED status
    ref_face = np.full((120, 120, 3), 180, dtype=np.uint8)
    sub_id = registry.register_subject(
        name="Bob Protestor",
        consent_status="DENIED",
        allowed_scopes=["internal_only"],
        reference_image_bgr=ref_face
    )
    assert sub_id is not None

    # Evaluate image with matching face
    test_face = ref_face.copy()
    eval_res = registry.evaluate_image_consent(
        image_bgr=test_face,
        detected_faces=[{'bbox': [0, 0, 120, 120]}],
        target_scope="social_media",
        policy="STRICT"
    )

    assert eval_res['can_share'] is False
    assert eval_res['overall_decision'] in ('PROHIBITED', 'GATED_REDACTION_REQUIRED')
    assert len(eval_res['redaction_boxes']) == 1

    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except PermissionError:
            pass


def test_aspect_d_cryptographic_reversible_redaction():
    """Verify Aspect D: AES-256-GCM reversible redaction and exact pixel restoration."""
    redactor = CryptoRedactor()

    # Create distinct pattern image with rich pixel variation
    img = np.zeros((150, 150, 3), dtype=np.uint8)
    for r in range(20, 70):
        img[r, 20:70] = [(r * 3) % 256, (r * 7) % 256, (r * 11) % 256]
    for r in range(80, 120):
        img[r, 80:120] = [(r * 5) % 256, (r * 9) % 256, (r * 13) % 256]

    regions = [
        {'bbox': [20, 20, 50, 50], 'type': 'face'},
        {'bbox': [80, 80, 40, 40], 'type': 'plate'}
    ]

    passphrase = "TopSecretPassphrase456!"

    # Obscure and encrypt
    res = redactor.obscure_and_encrypt(
        image_bgr=img,
        regions=regions,
        passphrase=passphrase,
        blur_style="pixelate"
    )

    obscured = res['obscured_image_bgr']
    assert not np.array_equal(img, obscured), "Obscured image must differ from original"

    # Export to embedded PNG and re-load
    png_bytes = redactor.export_embedded_png(obscured, res['encrypted_envelope'])
    loaded_bgr, loaded_envelope = redactor.load_embedded_png(png_bytes)
    assert loaded_envelope is not None

    # Restore with correct passphrase
    success, restored_bgr, msg = redactor.decrypt_and_restore(
        obscured_image_bgr=loaded_bgr,
        envelope=loaded_envelope,
        passphrase=passphrase
    )
    assert success is True
    assert restored_bgr is not None
    assert np.array_equal(img, restored_bgr), "Restored image must be 100% bit-exact to original"

    # Restoration with wrong passphrase must fail
    fail_success, fail_bgr, fail_msg = redactor.decrypt_and_restore(
        obscured_image_bgr=loaded_bgr,
        envelope=loaded_envelope,
        passphrase="WrongPassword!"
    )
    assert fail_success is False


def test_aspect_d_steganography_and_neutral_placeholder():
    """Verify Aspect D (Claims D1-D3): Steganographic LSB payload embedding and neutral placeholder."""
    redactor = CryptoRedactor()

    # Image with enough dimensions to hold stego payload
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    for r in range(40, 100):
        img[r, 40:100] = [120, 180, 240]

    regions = [{'bbox': [40, 40, 60, 60], 'type': 'face'}]
    passphrase = "StegoSecretPassphrase789!"

    # Test neutral placeholder obscuration style (Claim D1/D2)
    res = redactor.obscure_and_encrypt(
        image_bgr=img,
        regions=regions,
        passphrase=passphrase,
        blur_style="neutral_placeholder"
    )
    obscured = res['obscured_image_bgr']
    assert not np.array_equal(img[40:100, 40:100], obscured[40:100, 40:100])

    # Test steganographic LSB embedding (Claim D3)
    stego_img = redactor.embed_steganographic(obscured, res['encrypted_envelope'])
    extracted_envelope = redactor.extract_steganographic(stego_img)
    assert extracted_envelope is not None
    assert extracted_envelope['format'] == 'PRIVACY_LOCK_V1'

    # Decrypt from stego-extracted envelope
    success, restored_bgr, msg = redactor.decrypt_and_restore(
        obscured_image_bgr=stego_img,
        envelope=extracted_envelope,
        passphrase=passphrase
    )
    assert success is True
    # The redacted patch [40:100, 40:100] must be 100% bit-exact restored
    assert np.array_equal(img[40:100, 40:100], restored_bgr[40:100, 40:100])


def test_aspect_e_pre_capture_risk_computation():
    """Verify Aspect E: pre-capture real-time risk evaluation."""
    detections = {
        'faces': [{'bbox': [10, 10, 50, 50]}],
        'plates': [{'bbox': [60, 60, 30, 15]}],
        'visual_location': {'has_visual_location_risk': True, 'location_revealed': True, 'risk_score': 35},
        'consent': {'can_share': False, 'faces_gated': 1, 'overall_decision': 'GATED_REDACTION_REQUIRED'},
        'pattern_risk': {'risk_level': 'HIGH'},
        'child_flags': [],
        'ocr': {'findings': []},
        'metadata': {'has_gps': False},
        'background_objects': []
    }

    risk = compute_risk(detections)
    assert risk['score'] > 40
    assert any(b['category'] == 'Visual Location' for b in risk['breakdown'])
    assert any(b['category'] == 'Consent Gating' for b in risk['breakdown'])
    assert any(b['category'] == 'Cross-Session Pattern' for b in risk['breakdown'])


def test_aspect_c_consent_expiration_handling():
    """Verify Aspect C correctly identifies expired consent dates even when date strings are timezone-naive."""
    test_db = os.path.join(os.path.dirname(__file__), '_test_consent_exp.db')
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    registry = ConsentRegistry(db_path=test_db)
    ref_face = np.full((80, 80, 3), 120, dtype=np.uint8)
    sub_id = registry.register_subject(
        name="Expired Subject",
        consent_status="GRANTED",
        valid_until="2020-01-01",  # clearly in the past, timezone-naive
        reference_image_bgr=ref_face
    )
    assert sub_id is not None

    eval_res = registry.evaluate_image_consent(
        image_bgr=ref_face,
        detected_faces=[{'bbox': [0, 0, 80, 80]}],
        target_scope="social_media",
        policy="STRICT"
    )
    assert eval_res['can_share'] is False
    assert eval_res['face_decisions'][0]['consent_status'] == 'EXPIRED'
    assert eval_res['faces_gated'] == 1

    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass


def test_aspect_a_custom_db_path():
    """Verify PatternRiskEngine writes to the custom db path provided."""
    test_db = os.path.join(os.path.dirname(__file__), '_test_custom_engine.db')
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    engine = PatternRiskEngine(db_path=test_db)
    assert engine.db_path == test_db
    engine.record_scan("user_x", {'detections': {}, 'risk': {'score': 10}})
    assert os.path.exists(test_db)
    history = engine.get_history_summary("user_x")
    assert len(history) == 1

    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass


def test_risk_analyzer_pattern_medium_and_visual_location():
    """Verify compute_risk correctly maps MEDIUM pattern risk and extracts landmark names from findings."""
    detections = {
        'faces': [],
        'plates': [],
        'visual_location': {
            'has_visual_location_risk': True,
            'location_revealed': True,
            'risk_score': 30,
            'findings': [
                {'type': 'landmark_match', 'inferred_location': 'Agra, India (Taj Mahal)', 'detail': 'Taj Mahal detected'},
                {'type': 'address_detected', 'detail': 'Main St'}
            ]
        },
        'pattern_risk': {
            'risk_level': 'MEDIUM',
            'detected_patterns': [{'detail': 'Same location on Mondays'}]
        }
    }
    risk = compute_risk(detections)
    assert risk['score'] > 20
    vis_breakdown = next(b for b in risk['breakdown'] if b['category'] == 'Visual Location')
    assert 'Taj Mahal' in vis_breakdown['detail']
    pat_breakdown = next(b for b in risk['breakdown'] if b['category'] == 'Cross-Session Pattern')
    assert 'MEDIUM' in pat_breakdown['detail']

