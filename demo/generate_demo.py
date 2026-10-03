import os
import sys
import json
import cv2
import numpy as np
import piexif
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.scanner import PrivacyScanner
from modules.image_utils import draw_boxes, apply_redactions, blur_region
OUT_DIR = os.path.join(os.path.dirname(__file__), 'output')

def _old_blur_region(image_bgr, bbox, method='gaussian'):
    x, y, w, h = [int(v) for v in bbox]
    x, y = (max(0, x), max(0, y))
    x2, y2 = (min(image_bgr.shape[1], x + w), min(image_bgr.shape[0], y + h))
    if x2 <= x or y2 <= y:
        return image_bgr
    roi = image_bgr[y:y2, x:x2]
    if method == 'pixelate':
        hh, ww = roi.shape[:2]
        small = cv2.resize(roi, (max(1, ww // 12), max(1, hh // 12)))
        out = cv2.resize(small, (ww, hh), interpolation=cv2.INTER_NEAREST)
    else:
        out = cv2.GaussianBlur(roi, (51, 51), 30)
    image_bgr[y:y2, x:x2] = out
    return image_bgr

def build_scene(path):
    W, H = (1000, 650)
    img = np.full((H, W, 3), (200, 190, 175), dtype=np.uint8)
    cv2.rectangle(img, (0, 420), (W, H), (120, 130, 135), -1)
    cv2.rectangle(img, (540, 260), (960, 430), (60, 60, 180), -1)
    cv2.rectangle(img, (580, 200), (880, 270), (60, 60, 180), -1)
    cv2.rectangle(img, (610, 215), (840, 260), (210, 225, 235), -1)
    cv2.circle(img, (610, 430), 35, (25, 25, 25), -1)
    cv2.circle(img, (900, 430), 35, (25, 25, 25), -1)
    cv2.rectangle(img, (690, 400), (860, 440), (240, 240, 240), -1)
    cv2.rectangle(img, (690, 400), (860, 440), (0, 0, 0), 2)
    cv2.putText(img, 'MH12 AB 4521', (702, 428), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.ellipse(img, (230, 195), (42, 50), 0, 0, 360, (90, 70, 60), -1)
    pts = np.array([[165, 240], [295, 240], [320, 420], [140, 420]], np.int32)
    cv2.fillPoly(img, [pts], (40, 90, 140))
    card = (280, 90)
    card_x, card_y = (330, 300)
    cv2.rectangle(img, (card_x, card_y), (card_x + card[0], card_y + card[1]), (250, 248, 240), -1)
    cv2.rectangle(img, (card_x, card_y), (card_x + card[0], card_y + card[1]), (110, 110, 110), 2)
    cv2.putText(img, 'DRIVER LICENSE', (card_x + 14, card_y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (10, 10, 10), 2)
    cv2.putText(img, 'DOB: 04/12/1988', (card_x + 14, card_y + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 10, 10), 1)
    cv2.putText(img, 'contact@example.com', (card_x + 14, card_y + 78), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (10, 10, 10), 1)
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    gps_ifd = {piexif.GPSIFD.GPSLatitudeRef: 'N', piexif.GPSIFD.GPSLatitude: [(26, 1), (55, 1), (1200, 100)], piexif.GPSIFD.GPSLongitudeRef: 'E', piexif.GPSIFD.GPSLongitude: [(75, 1), (49, 1), (1800, 100)]}
    exif_dict = {'GPS': gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, path)
    return path

def make_zoom_comparison(image_bgr, boxes_with_titles, out_path):
    crops_old, crops_new = ([], [])
    target_h = 160
    for box, title in boxes_with_titles:
        x, y, w, h = [int(v) for v in box['bbox']]
        pad = int(max(w, h) * 0.6)
        cx1, cy1 = (max(0, x - pad), max(0, y - pad))
        cx2 = min(image_bgr.shape[1], x + w + pad)
        cy2 = min(image_bgr.shape[0], y + h + pad)
        old_full = _old_blur_region(image_bgr.copy(), box['bbox'], method='gaussian')
        new_full = blur_region(image_bgr.copy(), box['bbox'], method='auto', padding=0.15, feather=True)
        old_crop = old_full[cy1:cy2, cx1:cx2]
        new_crop = new_full[cy1:cy2, cx1:cx2]
        scale = target_h / old_crop.shape[0]
        old_crop = cv2.resize(old_crop, (int(old_crop.shape[1] * scale), target_h))
        new_crop = cv2.resize(new_crop, (int(new_crop.shape[1] * scale), target_h))
        cv2.putText(old_crop, title, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(new_crop, title, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        crops_old.append(old_crop)
        crops_new.append(new_crop)

    def hstack_padded(crops, gap=10):
        max_w = max((c.shape[1] for c in crops))
        padded = []
        for c in crops:
            pad_w = max_w - c.shape[1]
            padded.append(cv2.copyMakeBorder(c, 0, 0, 0, pad_w, cv2.BORDER_CONSTANT, value=(30, 30, 30)))
        row = padded[0]
        for c in padded[1:]:
            gapper = np.full((row.shape[0], gap, 3), 15, dtype=np.uint8)
            row = np.hstack([row, gapper, c])
        return row
    row_old = hstack_padded(crops_old)
    row_new = hstack_padded(crops_new)
    label_h = 28
    label_old = np.full((label_h, row_old.shape[1], 3), (40, 40, 40), dtype=np.uint8)
    cv2.putText(label_old, 'OLD (v1): hard edges, no safety padding, fixed strength', (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 255), 1, cv2.LINE_AA)
    label_new = np.full((label_h, row_new.shape[1], 3), (40, 40, 40), dtype=np.uint8)
    cv2.putText(label_new, 'NEW: auto method, padded + feathered, adaptive strength', (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 255, 180), 1, cv2.LINE_AA)
    gap = np.full((14, row_old.shape[1], 3), 15, dtype=np.uint8)
    composite = np.vstack([label_old, row_old, gap, label_new, row_new])
    cv2.imwrite(out_path, composite)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    scene_path = os.path.join(OUT_DIR, '01_original_scene.jpg')
    build_scene(scene_path)
    print(f'[1/4] Built demo scene -> {scene_path}')
    scanner = PrivacyScanner(enable_background_objects=False)
    result = scanner.scan(scene_path)
    detections = result['detections']
    risk = result['risk']
    print('\n--- Live detection results (genuine, not staged) ---')
    print(f'Plates found: {len(detections['plates'])} -> {detections['plates']}')
    print(f'Faces found:  {len(detections['faces'])}  (see demo/README.md for why)')
    print(f'OCR findings: {detections['ocr']['findings']}')
    print(f'GPS metadata: has_gps={detections['metadata']['has_gps']}')
    print(f'\nRisk score: {risk['score']}/100 ({risk['level']})')
    for b in risk['breakdown']:
        print(f'  - {b['category']}: {b['detail']} (+{b['points']})')
    print('\nSuggestions:')
    for s in risk['suggestions']:
        print(f'  - {s}')
    with open(os.path.join(OUT_DIR, 'risk_report.json'), 'w') as f:
        json.dump(result, f, indent=2, default=str)
    image_bgr = cv2.imread(scene_path)
    detected_path = os.path.join(OUT_DIR, '02_detected_risks.jpg')
    annotated = draw_boxes(image_bgr, detections['plates'], color=(0, 165, 255))
    if detections['ocr']['findings']:
        id_card_box = [{'type': 'id_document (text detected)', 'bbox': [330, 300, 280, 90]}]
        annotated = draw_boxes(annotated, id_card_box, color=(180, 0, 255))
    cv2.imwrite(detected_path, annotated)
    print(f'\n[2/4] Annotated detections -> {detected_path}')
    known_plate_center = (690 + 170 / 2, 400 + 40 / 2)

    def _center(b):
        x, y, w, h = b['bbox']
        return (x + w / 2, y + h / 2)

    def _dist(b):
        cx, cy = _center(b)
        return ((cx - known_plate_center[0]) ** 2 + (cy - known_plate_center[1]) ** 2) ** 0.5
    true_plate = min(detections['plates'], key=_dist) if detections['plates'] else None
    safe_path = os.path.join(OUT_DIR, '03_safe_image.jpg')
    id_card_box = {'type': 'id_document', 'bbox': [330, 300, 280, 90]}
    all_boxes = ([true_plate] if true_plate else []) + detections['faces'] + [id_card_box]
    safe_img = apply_redactions(image_bgr, all_boxes, method='auto', padding=0.15, feather=True)
    cv2.imwrite(safe_path, safe_img)
    print(f'[3/4] Safe (redacted) image -> {safe_path}')
    id_card_box = {'type': 'id_document', 'bbox': [330, 300, 280, 90]}
    compare_targets = [(true_plate, 'License plate')] if true_plate else []
    compare_targets.append((id_card_box, 'ID document'))
    compare_path = os.path.join(OUT_DIR, '04_old_vs_new_blur.jpg')
    make_zoom_comparison(image_bgr, compare_targets, compare_path)
    print(f'[4/4] Old-vs-new blur comparison -> {compare_path}')
    build_face_comparison(os.path.join(OUT_DIR, '05_face_blur_quality.jpg'))
    print(f'[5/5] Face-region blur comparison -> {os.path.join(OUT_DIR, '05_face_blur_quality.jpg')}')

def build_face_comparison(out_path):
    size = 500
    img = np.full((size, size, 3), (215, 205, 195), dtype=np.uint8)
    cx, cy = (size // 2, int(size * 0.46))
    fw, fh = (int(size * 0.22), int(size * 0.3))
    cv2.ellipse(img, (cx, cy), (fw, fh), 0, 0, 360, (110, 145, 195), -1)
    eye_dx = int(fw * 0.42)
    for ex in (cx - eye_dx, cx + eye_dx):
        cv2.circle(img, (ex, cy - int(fh * 0.15)), int(fh * 0.07), (40, 30, 20), -1)
    cv2.ellipse(img, (cx, cy + int(fh * 0.35)), (int(fw * 0.3), int(fh * 0.08)), 0, 0, 180, (80, 60, 100), -1)
    face_box = [cx - fw, cy - fh, fw * 2, fh * 2]
    old_full = _old_blur_region(img.copy(), face_box, method='gaussian')
    new_full = apply_redactions(img.copy(), [{'type': 'face', 'bbox': face_box}], method='auto', padding=0.15)

    def label(im, text, color):
        im = im.copy()
        cv2.rectangle(im, (0, 0), (im.shape[1], 26), (40, 40, 40), -1)
        cv2.putText(im, text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        return im
    old_labeled = label(old_full, 'OLD: hard edges, no padding', (180, 180, 255))
    new_labeled = label(new_full, 'NEW: auto -> gaussian+ellipse for faces', (180, 255, 180))
    gap = np.full((old_labeled.shape[0], 12, 3), 15, dtype=np.uint8)
    composite = np.hstack([old_labeled, gap, new_labeled])
    cv2.imwrite(out_path, composite)
if __name__ == '__main__':
    main()
