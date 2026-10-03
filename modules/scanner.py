import cv2
import numpy as np
from typing import Dict, Any, Optional

from modules.detection_module import FaceDetector, PlateDetector, BackgroundObjectDetector
from modules.ocr_extractor import OCRExtractor
from modules.child_safety_detector import ChildSafetyDetector
from modules.metadata_scanner import MetadataScanner
from modules.risk_analyzer import compute_risk

# New modules implementing the 5 patent aspects
from modules.visual_location_inference import VisualLocationInferrer
from modules.pattern_risk_engine import PatternRiskEngine
from modules.consent_registry import ConsentRegistry
from modules.crypto_redaction import CryptoRedactor


class PrivacyScanner:
    """
    Comprehensive multi-aspect AI Privacy Scanner:
    - Base detections: faces, plates, sensitive OCR, minors, metadata, bg objects
    - Aspect A: Cross-session pattern risk analysis
    - Aspect B: Metadata-independent visual location inference
    - Aspect C: Per-person consent gating with facial embeddings
    - Aspect D: Cryptographically reversible redaction
    """

    def __init__(self, enable_background_objects=True):
        self.face_detector = FaceDetector()
        self.plate_detector = PlateDetector()
        self.ocr_extractor = OCRExtractor()
        self.child_safety = ChildSafetyDetector()
        self.metadata_scanner = MetadataScanner()
        self.object_detector = BackgroundObjectDetector() if enable_background_objects else None

        # Integrated patent engines
        self.visual_location_inferrer = VisualLocationInferrer(ocr_extractor=self.ocr_extractor)
        self.pattern_risk_engine = PatternRiskEngine()
        self.consent_registry = ConsentRegistry()
        self.crypto_redactor = CryptoRedactor()

    def scan_array(
        self,
        image_bgr: np.ndarray,
        image_path: Optional[str] = None,
        username: str = "default_user",
        target_scope: str = "social_media",
        consent_policy: str = "STRICT",
        record_in_history: bool = True
    ) -> Dict[str, Any]:
        """
        Scan an image array with all 5 privacy risk aspects.
        """
        # 1. Base detections
        faces = self.face_detector.detect(image_bgr)
        plates = self.plate_detector.detect(image_bgr)
        ocr = self.ocr_extractor.extract(image_bgr)
        child_flags = [self.child_safety.assess(image_bgr, f['bbox']) for f in faces]
        metadata = self.metadata_scanner.scan(image_path) if image_path else {'has_exif': False, 'has_gps': False, 'findings': []}
        bg_objects = self.object_detector.detect(image_bgr) if self.object_detector else []

        # 2. Aspect B: Visual Location Inference (independent of metadata)
        visual_location = self.visual_location_inferrer.infer(image_bgr, ocr_result=ocr)

        # 3. Aspect C: Per-person consent gating
        consent_evaluation = self.consent_registry.evaluate_image_consent(
            image_bgr=image_bgr,
            detected_faces=faces,
            target_scope=target_scope,
            policy=consent_policy
        )

        # 4. Aspect A: Cross-session pattern risk
        # First evaluate current pattern risk before/with this scan
        pre_pattern_risk = self.pattern_risk_engine.evaluate(username)

        detections = {
            'faces': faces,
            'plates': plates,
            'ocr': ocr,
            'child_flags': child_flags,
            'metadata': metadata,
            'background_objects': bg_objects,
            'visual_location': visual_location,
            'consent': consent_evaluation,
            'pattern_risk': pre_pattern_risk
        }

        # Compute comprehensive holistic risk score
        risk = compute_risk(detections)

        full_result = {
            'detections': detections,
            'risk': risk,
            'visual_location': visual_location,
            'consent': consent_evaluation,
            'pattern_risk': pre_pattern_risk,
            'image_shape': list(image_bgr.shape)
        }

        # Optionally record this scan into cross-session pattern history
        if record_in_history:
            try:
                scan_hash = self.pattern_risk_engine.record_scan(
                    username=username,
                    scan_result=full_result,
                    image_path=image_path
                )
                full_result['scan_hash'] = scan_hash
                # Refresh pattern risk after recording
                post_pattern_risk = self.pattern_risk_engine.evaluate(username)
                full_result['pattern_risk'] = post_pattern_risk
                detections['pattern_risk'] = post_pattern_risk
            except Exception as e:
                full_result['pattern_record_error'] = str(e)

        return full_result

    def scan(
        self,
        image_path: str,
        username: str = "default_user",
        target_scope: str = "social_media",
        consent_policy: str = "STRICT",
        record_in_history: bool = True
    ) -> Dict[str, Any]:
        """Read image from path and scan."""
        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            raise ValueError(f'Could not read image at {image_path}')
        return self.scan_array(
            image_bgr,
            image_path=image_path,
            username=username,
            target_scope=target_scope,
            consent_policy=consent_policy,
            record_in_history=record_in_history
        )
