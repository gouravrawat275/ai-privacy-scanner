import os
import cv2
import numpy as np
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
FACE_PROTO = os.path.join(MODEL_DIR, 'face_deploy.prototxt')
FACE_WEIGHTS = os.path.join(MODEL_DIR, 'face_res10_300x300_ssd.caffemodel')

class FaceDetector:

    def __init__(self):
        self.dnn_net = None
        if os.path.exists(FACE_PROTO) and os.path.exists(FACE_WEIGHTS):
            try:
                self.dnn_net = cv2.dnn.readNetFromCaffe(FACE_PROTO, FACE_WEIGHTS)
            except Exception as e:
                print(f'[FaceDetector] Found DNN model files but failed to load them ({e}). Falling back to the Haar cascade.')
        else:
            print('[FaceDetector] DNN face model not found in /models — using the bundled Haar cascade (works out of the box, but noticeably less robust on real photos). Run scripts/download_models.py to enable the DNN backend.')
        cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
        self.cascade = cv2.CascadeClassifier(cascade_path)
        if self.cascade.empty():
            raise RuntimeError(f'Could not load face cascade from {cascade_path}')

    def detect(self, image_bgr, conf_threshold=0.5):
        if self.dnn_net is not None:
            return self._detect_dnn(image_bgr, conf_threshold)
        return self._detect_haar(image_bgr)

    def _detect_dnn(self, image_bgr, conf_threshold):
        h, w = image_bgr.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(image_bgr, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        self.dnn_net.setInput(blob)
        detections = self.dnn_net.forward()
        results = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence < conf_threshold:
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = (max(0, x1), max(0, y1))
            x2, y2 = (min(w, x2), min(h, y2))
            if x2 > x1 and y2 > y1:
                results.append({'type': 'face', 'bbox': [int(x1), int(y1), int(x2 - x1), int(y2 - y1)], 'confidence': round(confidence, 3)})
        return results

    def _detect_haar(self, image_bgr):
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(40, 40))
        return [{'type': 'face', 'bbox': [int(x), int(y), int(w), int(h)], 'confidence': None} for x, y, w, h in faces]

class PlateDetector:

    def __init__(self):
        cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_russian_plate_number.xml')
        self.cascade = cv2.CascadeClassifier(cascade_path) if os.path.exists(cascade_path) else None
        if self.cascade is not None and self.cascade.empty():
            self.cascade = None

    def detect(self, image_bgr):
        results = []
        if self.cascade is not None:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            plates = self.cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=4, minSize=(60, 20))
            for x, y, w, h in plates:
                results.append({'type': 'plate', 'bbox': [int(x), int(y), int(w), int(h)], 'confidence': None})
        if not results:
            results.extend(self._contour_fallback(image_bgr))
        return results

    def _contour_fallback(self, image_bgr):
        raw_boxes = []
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.bilateralFilter(gray, 11, 17, 17), 30, 200)
        contours, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        img_area = image_bgr.shape[0] * image_bgr.shape[1]
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if h == 0:
                continue
            aspect = w / h
            area_ratio = w * h / img_area
            if 2.0 <= aspect <= 5.5 and 0.001 <= area_ratio <= 0.05:
                raw_boxes.append([int(x), int(y), int(w), int(h)])
        deduped = self._nms(raw_boxes, iou_threshold=0.3)
        return [{'type': 'plate_candidate', 'bbox': b, 'confidence': None} for b in deduped[:5]]

    @staticmethod
    def _nms(boxes, iou_threshold=0.3):
        if not boxes:
            return []

        def iou(a, b):
            ax1, ay1, aw, ah = a
            bx1, by1, bw, bh = b
            ax2, ay2 = (ax1 + aw, ay1 + ah)
            bx2, by2 = (bx1 + bw, by1 + bh)
            ix1, iy1 = (max(ax1, bx1), max(ay1, by1))
            ix2, iy2 = (min(ax2, bx2), min(ay2, by2))
            iw, ih = (max(0, ix2 - ix1), max(0, iy2 - iy1))
            inter = iw * ih
            union = aw * ah + bw * bh - inter
            return inter / union if union > 0 else 0
        boxes_sorted = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        kept = []
        for box in boxes_sorted:
            if all((iou(box, k) < iou_threshold for k in kept)):
                kept.append(box)
        return kept

class BackgroundObjectDetector:
    SENSITIVE_CLASSES = {'laptop', 'cell phone', 'tv', 'book', 'person', 'remote', 'keyboard'}

    def __init__(self, model_name='yolov8n.pt'):
        self.available = False
        self.model = None
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_name)
            self.available = True
        except Exception as e:
            print(f'[BackgroundObjectDetector] YOLO not available ({e}). Background object detection will be skipped. Run `pip install ultralytics` to enable it.')

    def detect(self, image_bgr):
        if not self.available:
            return []
        try:
            results = self.model(image_bgr, verbose=False)
        except Exception as e:
            print(f'[BackgroundObjectDetector] inference failed: {e}')
            return []
        findings = []
        for r in results:
            for box in r.boxes:
                cls_name = self.model.names[int(box.cls[0])]
                if cls_name in self.SENSITIVE_CLASSES:
                    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                    findings.append({'type': 'background_object', 'label': cls_name, 'bbox': [x1, y1, x2 - x1, y2 - y1], 'confidence': float(box.conf[0])})
        return findings
