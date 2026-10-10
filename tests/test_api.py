import os
import sys
import numpy as np
import cv2
import pytest
from fastapi import UploadFile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api import health, register, login, pre_capture_evaluate, RegisterRequest
from modules import credentials
from fastapi.security import OAuth2PasswordRequestForm


def test_api_health():
    res = health()
    assert res['status'] == 'ok'
    assert res['features']['aspect_a_cross_session_patterns'] is True
    assert res['features']['aspect_b_visual_location_inference'] is True
    assert res['features']['aspect_c_consent_gating'] is True
    assert res['features']['aspect_d_crypto_redaction'] is True
    assert res['features']['aspect_e_pre_capture_evaluation'] is True


def test_api_register_and_login_flow(monkeypatch, tmp_path):
    config_path = tmp_path / "auth_config.yaml"
    monkeypatch.setattr(credentials, "CONFIG_PATH", str(config_path))

    # Register first user via API
    reg_req = RegisterRequest(
        first_name="Alice",
        last_name="Smith",
        email="alice@example.com",
        password="SecurePass123!",
        password_confirm="SecurePass123!"
    )
    reg_res = register(reg_req)
    assert reg_res.access_token is not None
    assert reg_res.refresh_token is not None

    # Login via API
    form = OAuth2PasswordRequestForm(
        grant_type="password",
        username="alice@example.com",
        password="SecurePass123!",
        scope="",
        client_id=None,
        client_secret=None
    )
    login_res = login(form)
    assert login_res.access_token is not None
    assert login_res.refresh_token is not None


@pytest.mark.anyio
async def test_api_pre_capture_evaluate():
    # Synthetic frame
    img = np.zeros((200, 300, 3), dtype=np.uint8)
    ok, buf = cv2.imencode('.jpg', img)
    assert ok

    import io
    upload_file = UploadFile(
        file=io.BytesIO(buf.tobytes()),
        filename="viewfinder.jpg"
    )

    res = await pre_capture_evaluate(frame=upload_file, target_scope="social_media")
    assert "risk_score" in res
    assert "risk_level" in res
    assert "can_share" in res
    assert res["risk_score"] >= 0
