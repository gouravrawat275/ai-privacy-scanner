import json
import tempfile
import base64

import cv2
import numpy as np
import jwt
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from modules.scanner import PrivacyScanner
from modules.image_utils import apply_redactions
from modules.scan_history import log_scan, get_recent, get_stats
from modules.credentials import AuthConfigError, RegisterError, load_config, load_or_init_config, verify_password, register_user
from modules.api_auth import create_access_token, create_refresh_token, decode_token

# Patent modules
from modules.visual_location_inference import VisualLocationInference
from modules.pattern_risk_engine import PatternRiskEngine
from modules.consent_registry import ConsentRegistry
from modules.crypto_redaction import CryptoRedactor

app = FastAPI(
    title="AI Privacy Risk Scanner & Defense API",
    description="Full-spectrum multi-aspect privacy evaluation, visual location inference, cross-session patterns, consent gating, and reversible cryptographic redaction.",
    version="2.5.0"
)
_scanner = None
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(TokenResponse):
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: str
    first_name: str
    last_name: str
    password: str
    password_confirm: str


class SubjectRegisterRequest(BaseModel):
    name: str
    consent_status: str = "GRANTED"
    allowed_scopes: List[str] = ["public", "social_media", "internal_only"]
    valid_until: Optional[str] = None
    notes: Optional[str] = ""


class SubjectUpdateRequest(BaseModel):
    consent_status: str
    allowed_scopes: Optional[List[str]] = None
    valid_until: Optional[str] = None


class DecryptRestoreRequest(BaseModel):
    envelope: Dict[str, Any]
    passphrase: Optional[str] = None
    key_b64: Optional[str] = None


def get_scanner() -> PrivacyScanner:
    global _scanner
    if _scanner is None:
        _scanner = PrivacyScanner(enable_background_objects=True)
    return _scanner


def _scan_or_400(scanner: PrivacyScanner, tmp_path: str, username: str = "default_user"):
    try:
        return scanner.scan(tmp_path, username=username)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read that file as an image. Check the format (JPG/PNG/BMP) and that it isn't corrupted.",
        )


def _unauthorized(detail="Invalid or expired token"):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_username(token: str = Depends(oauth2_scheme)) -> str:
    try:
        config = load_or_init_config()
        return decode_token(token, config, expected_type="access")
    except AuthConfigError:
        raise
    except jwt.PyJWTError:
        raise _unauthorized()


@app.exception_handler(AuthConfigError)
async def auth_config_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/health")
def health():
    return {
        "status": "ok",
        "features": {
            "aspect_a_cross_session_patterns": True,
            "aspect_b_visual_location_inference": True,
            "aspect_c_consent_gating": True,
            "aspect_d_crypto_redaction": True,
            "aspect_e_pre_capture_evaluation": True
        }
    }


@app.post("/register", response_model=LoginResponse)
def register(body: RegisterRequest):
    config = load_or_init_config()
    try:
        email = register_user(config, body.first_name, body.last_name, body.email, body.password, body.password_confirm)
    except RegisterError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    config = load_or_init_config()
    return LoginResponse(
        access_token=create_access_token(email, config),
        refresh_token=create_refresh_token(email, config),
    )


@app.post("/login", response_model=LoginResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    config = load_or_init_config()
    if not verify_password(form_data.username, form_data.password, config):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return LoginResponse(
        access_token=create_access_token(form_data.username, config),
        refresh_token=create_refresh_token(form_data.username, config),
    )


@app.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    config = load_or_init_config()
    try:
        username = decode_token(body.refresh_token, config, expected_type="refresh")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid or expired refresh token")
    return TokenResponse(access_token=create_access_token(username, config))


@app.post("/scan")
async def scan(
    file: UploadFile = File(...),
    target_scope: str = Form("social_media"),
    consent_policy: str = Form("STRICT"),
    username: str = Depends(get_current_username)
):
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        scanner = get_scanner()
        image_bgr = cv2.imread(tmp_path)
        if image_bgr is None:
            raise HTTPException(status_code=400, detail="Could not read uploaded image.")

        result = scanner.scan_array(
            image_bgr,
            image_path=tmp_path,
            username=username,
            target_scope=target_scope,
            consent_policy=consent_policy,
            record_in_history=True
        )
        log_scan(username, file.filename, result)
        return JSONResponse(content=json.loads(json.dumps(result, default=str)))
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


# --- Aspect B: Visual Location Inference Endpoint ---
@app.post("/visual-location")
async def visual_location_endpoint(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    scanner = get_scanner()
    ocr = scanner.ocr_extractor.extract(img_bgr)
    vis_loc = scanner.visual_location_inferrer.infer(img_bgr, ocr_result=ocr)
    return JSONResponse(content=vis_loc)


# --- Aspect A: Cross-Session Pattern Analysis Endpoints ---
@app.get("/patterns")
def get_user_patterns(username: str = Depends(get_current_username)):
    scanner = get_scanner()
    analysis = scanner.pattern_risk_engine.evaluate(username)
    history_summary = scanner.pattern_risk_engine.get_user_history_summary(username)
    return {
        "analysis": analysis,
        "history_summary": history_summary
    }


# --- Aspect C: Consent Gating Endpoints ---
@app.get("/consent/subjects")
def list_consent_subjects():
    scanner = get_scanner()
    return scanner.consent_registry.list_subjects()


@app.post("/consent/register")
async def register_consent_subject(
    name: str = Form(...),
    consent_status: str = Form("GRANTED"),
    allowed_scopes: str = Form("public,social_media,internal_only"),
    valid_until: Optional[str] = Form(None),
    notes: Optional[str] = Form(""),
    reference_face: Optional[UploadFile] = File(None)
):
    scanner = get_scanner()
    scopes = [s.strip() for s in allowed_scopes.split(",") if s.strip()]

    ref_bgr = None
    if reference_face:
        ref_bytes = await reference_face.read()
        nparr = np.frombuffer(ref_bytes, np.uint8)
        ref_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    subject_id = scanner.consent_registry.register_subject(
        name=name,
        consent_status=consent_status,
        allowed_scopes=scopes,
        valid_until=valid_until,
        notes=notes or "",
        reference_image_bgr=ref_bgr
    )
    return {"status": "created", "subject_id": subject_id, "name": name}


@app.put("/consent/subjects/{subject_id}")
def update_consent_subject(subject_id: str, body: SubjectUpdateRequest):
    scanner = get_scanner()
    ok = scanner.consent_registry.update_consent(
        subject_id=subject_id,
        consent_status=body.consent_status,
        allowed_scopes=body.allowed_scopes,
        valid_until=body.valid_until
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"status": "updated", "subject_id": subject_id}


@app.delete("/consent/subjects/{subject_id}")
def delete_consent_subject(subject_id: str):
    scanner = get_scanner()
    ok = scanner.consent_registry.delete_subject(subject_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"status": "deleted", "subject_id": subject_id}


# --- Aspect D: Cryptographically Reversible Redaction Endpoints ---
@app.post("/crypto/obscure")
async def crypto_obscure_endpoint(
    file: UploadFile = File(...),
    passphrase: Optional[str] = Form(None),
    blur_style: str = Form("pixelate"),
    auto_detect_regions: bool = Form(True),
    custom_boxes_json: Optional[str] = Form(None)
):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid image.")

    scanner = get_scanner()
    regions = []

    if auto_detect_regions:
        faces = scanner.face_detector.detect(image_bgr)
        plates = scanner.plate_detector.detect(image_bgr)
        for f in faces:
            regions.append({'bbox': f['bbox'], 'type': 'face', 'label': 'Face'})
        for p in plates:
            regions.append({'bbox': p['bbox'], 'type': 'plate', 'label': 'Plate'})

    if custom_boxes_json:
        try:
            custom_boxes = json.loads(custom_boxes_json)
            for b in custom_boxes:
                regions.append({'bbox': b, 'type': 'custom', 'label': 'Custom'})
        except Exception:
            pass

    redactor = scanner.crypto_redactor
    result = redactor.obscure_and_encrypt(
        image_bgr=image_bgr,
        regions=regions,
        passphrase=passphrase,
        blur_style=blur_style
    )

    # Return embedded PNG package as downloadable file
    embedded_png = redactor.export_embedded_png(
        result['obscured_image_bgr'],
        result['encrypted_envelope']
    )

    headers = {
        "X-Encrypted-Regions": str(result['regions_count']),
        "X-Key-Base64": result.get('key_b64') or "",
        "X-Salt-Base64": result.get('salt_b64') or "",
        "Content-Disposition": f'attachment; filename="privacy_locked_{os.path.splitext(file.filename)[0]}.png"'
    }
    return Response(content=embedded_png, media_type="image/png", headers=headers)


@app.post("/crypto/restore")
async def crypto_restore_endpoint(
    file: UploadFile = File(...),
    passphrase: Optional[str] = Form(None),
    key_b64: Optional[str] = Form(None),
    envelope_json: Optional[str] = Form(None)
):
    png_bytes = await file.read()
    redactor = CryptoRedactor()

    # Attempt to load envelope from PNG metadata first
    img_bgr, embedded_envelope = redactor.load_embedded_png(png_bytes)

    envelope = embedded_envelope
    if not envelope and envelope_json:
        try:
            envelope = json.loads(envelope_json)
        except Exception:
            pass

    if not envelope:
        raise HTTPException(status_code=400, detail="No cryptographic privacy envelope found in image or parameters.")

    success, restored_bgr, msg = redactor.decrypt_and_restore(
        obscured_image_bgr=img_bgr,
        envelope=envelope,
        passphrase=passphrase,
        raw_key_b64=key_b64
    )

    if not success or restored_bgr is None:
        raise HTTPException(status_code=400, detail=msg)

    ok, buf = cv2.imencode(".png", restored_bgr)
    return Response(content=buf.tobytes(), media_type="image/png")


# --- Aspect E: Pre-Capture Fast Evaluation Endpoint ---
@app.post("/pre-capture/evaluate")
async def pre_capture_evaluate(
    frame: UploadFile = File(...),
    target_scope: str = Form("social_media")
):
    """
    Lightweight, rapid evaluation intended for live camera viewfinders.
    Returns real-time risk scores, bounding boxes, and pre-capture warnings.
    """
    frame_bytes = await frame.read()
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise HTTPException(status_code=400, detail="Invalid frame.")

    scanner = get_scanner()
    faces = scanner.face_detector.detect(frame_bgr)
    plates = scanner.plate_detector.detect(frame_bgr)

    # Consent check
    consent_eval = scanner.consent_registry.evaluate_image_consent(
        image_bgr=frame_bgr,
        detected_faces=faces,
        target_scope=target_scope,
        policy="STRICT"
    )

    # Score calculation
    risk_score = min(100, len(faces) * 15 + len(plates) * 20 + (30 if not consent_eval['can_share'] else 0))
    risk_level = "Low" if risk_score <= 20 else ("Medium" if risk_score <= 50 else ("High" if risk_score <= 75 else "Critical"))

    alerts = []
    if plates:
        alerts.append("🚗 License plate visible in frame")
    if not consent_eval['can_share']:
        alerts.append("⛔ Unconsented face detected")
    if len(faces) > 3:
        alerts.append("👥 Crowd / multiple bystanders in frame")

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "faces_count": len(faces),
        "plates_count": len(plates),
        "can_share": consent_eval['can_share'],
        "alerts": alerts,
        "faces": faces,
        "plates": plates
    }


@app.post("/redact")
async def redact(
    file: UploadFile = File(...),
    method: str = Form("auto"),
    padding: float = Form(0.15),
    blur_faces: bool = Form(True),
    blur_plates: bool = Form(True),
    username: str = Depends(get_current_username),
):
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        scanner = get_scanner()
        result = _scan_or_400(scanner, tmp_path, username=username)
        log_scan(username, file.filename, result)

        image_bgr = cv2.imread(tmp_path)
        boxes = []
        if blur_faces:
            boxes += result["detections"]["faces"]
        if blur_plates:
            boxes += result["detections"]["plates"]

        image_bgr = apply_redactions(image_bgr, boxes, method=method, padding=padding)

        ok, buf = cv2.imencode(".jpg", image_bgr)
        if not ok:
            return JSONResponse(status_code=500, content={"error": "encoding failed"})

        headers = {"X-Risk-Score": str(result["risk"]["score"]), "X-Risk-Level": result["risk"]["level"]}
        return Response(content=buf.tobytes(), media_type="image/jpeg", headers=headers)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


@app.get("/history")
def history(limit: int = 50, username: str = Depends(get_current_username)):
    return {
        "stats": get_stats(username),
        "recent": get_recent(username, limit=min(limit, 200)),
    }
