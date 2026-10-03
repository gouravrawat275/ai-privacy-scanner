import os
import cv2
AGE_BUCKETS = ['(0-2)', '(4-6)', '(8-12)', '(15-20)', '(25-32)', '(38-43)', '(48-53)', '(60-100)']
MINOR_BUCKETS = {'(0-2)', '(4-6)', '(8-12)', '(15-20)'}
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
PROTO = os.path.join(MODEL_DIR, 'age_deploy.prototxt')
WEIGHTS = os.path.join(MODEL_DIR, 'age_net.caffemodel')
MEAN_VALUES = (78.4263377603, 87.7689143744, 114.895847746)

class ChildSafetyDetector:

    def __init__(self):
        self.model_loaded = False
        self.net = None
        if os.path.exists(PROTO) and os.path.exists(WEIGHTS):
            try:
                self.net = cv2.dnn.readNetFromCaffe(PROTO, WEIGHTS)
                self.model_loaded = True
            except Exception as e:
                print(f'[ChildSafetyDetector] Found model files but failed to load them: {e}')
        else:
            print('[ChildSafetyDetector] Age-estimation model not found in /models. Run scripts/download_models.py to enable automated age brackets. Until then, every face is flagged for manual review.')

    def assess(self, image_bgr, face_bbox):
        x, y, w, h = [int(v) for v in face_bbox]
        x, y = (max(0, x), max(0, y))
        face_img = image_bgr[y:y + h, x:x + w]
        if face_img.size == 0:
            return {'status': 'unknown', 'reason': 'Face region was empty/invalid.', 'flag_for_review': True}
        if not self.model_loaded:
            return {'status': 'unknown', 'reason': 'Age-estimation model not installed — manually check this face for child safety.', 'flag_for_review': True}
        blob = cv2.dnn.blobFromImage(face_img, 1.0, (227, 227), MEAN_VALUES, swapRB=False)
        self.net.setInput(blob)
        preds = self.net.forward()
        idx = int(preds[0].argmax())
        bucket = AGE_BUCKETS[idx]
        confidence = float(preds[0][idx])
        is_possible_minor = bucket in MINOR_BUCKETS
        return {'status': 'possible_minor' if is_possible_minor else 'likely_adult', 'estimated_age_range': bucket, 'confidence': round(confidence, 3), 'flag_for_review': is_possible_minor, 'note': 'Automated estimate only — may be inaccurate. When in doubt, treat as a minor.'}
