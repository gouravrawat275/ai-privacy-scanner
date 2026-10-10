import cv2
import numpy as np

def _expand_bbox(bbox, padding, img_shape):
    x, y, w, h = [float(v) for v in bbox]
    pad_x, pad_y = (w * padding, h * padding)
    x1 = max(0, int(round(x - pad_x)))
    y1 = max(0, int(round(y - pad_y)))
    x2 = min(img_shape[1], int(round(x + w + pad_x)))
    y2 = min(img_shape[0], int(round(y + h + pad_y)))
    return (x1, y1, x2, y2)

def _redact_pixels(roi, method='auto'):
    h, w = roi.shape[:2]
    if h == 0 or w == 0:
        return roi
    if method == 'solid':
        out = roi.copy()
        out[:] = (20, 20, 20)
        return out
    if method in ('pixelate', 'auto'):
        target_blocks = 10
        block_px = max(4, min(w, h) // target_blocks)
        small_w, small_h = (max(1, w // block_px), max(1, h // block_px))
        small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        out = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        out = cv2.addWeighted(out, 0.7, np.full_like(out, 128), 0.3, 0)
        if method == 'auto':
            k = max(3, block_px // 2 * 2 + 1)
            out = cv2.GaussianBlur(out, (k, k), block_px / 4)
        return out
    k = max(31, int(min(w, h) * 0.5))
    k = k if k % 2 == 1 else k + 1
    return cv2.GaussianBlur(roi, (k, k), k / 6)

def blur_region(image_bgr, bbox, method='auto', padding=0.15, feather=True, feather_margin=0.35, shape='rect'):
    img_h, img_w = image_bgr.shape[:2]
    core_x1, core_y1, core_x2, core_y2 = _expand_bbox(bbox, padding, image_bgr.shape)
    if core_x2 <= core_x1 or core_y2 <= core_y1:
        return image_bgr
    if not feather:
        roi = image_bgr[core_y1:core_y2, core_x1:core_x2]
        image_bgr[core_y1:core_y2, core_x1:core_x2] = _redact_pixels(roi, method)
        return image_bgr
    core_w, core_h = (core_x2 - core_x1, core_y2 - core_y1)
    fm_x, fm_y = (int(core_w * feather_margin), int(core_h * feather_margin))
    out_x1 = max(0, core_x1 - fm_x)
    out_y1 = max(0, core_y1 - fm_y)
    out_x2 = min(img_w, core_x2 + fm_x)
    out_y2 = min(img_h, core_y2 + fm_y)
    outer = image_bgr[out_y1:out_y2, out_x1:out_x2]
    if outer.size == 0:
        return image_bgr
    rel_x1, rel_y1 = (core_x1 - out_x1, core_y1 - out_y1)
    rel_x2, rel_y2 = (core_x2 - out_x1, core_y2 - out_y1)

    def _draw_shape(m):
        if shape == 'ellipse':
            cx, cy = ((rel_x1 + rel_x2) / 2, (rel_y1 + rel_y2) / 2)
            ax = max(1, int((rel_x2 - rel_x1) / 2 * 1.5))
            ay = max(1, int((rel_y2 - rel_y1) / 2 * 1.5))
            cv2.ellipse(m, (int(cx), int(cy)), (ax, ay), 0, 0, 360, 1.0, -1)
        else:
            cv2.rectangle(m, (rel_x1, rel_y1), (rel_x2, rel_y2), 1.0, -1)
        return m
    mask = _draw_shape(np.zeros(outer.shape[:2], dtype=np.float32))
    feather_px = max(3, int(min(outer.shape[0], outer.shape[1]) * 0.15))
    k = feather_px * 2 + 1
    mask = cv2.GaussianBlur(mask, (k, k), feather_px / 2)
    mask = _draw_shape(mask)
    mask = np.clip(mask, 0.0, 1.0)[..., None]
    redacted_outer = _redact_pixels(outer, method)
    blended = mask * redacted_outer.astype(np.float32) + (1 - mask) * outer.astype(np.float32)
    image_bgr[out_y1:out_y2, out_x1:out_x2] = blended.astype(np.uint8)
    return image_bgr

def apply_redactions(image_bgr, boxes, method='auto', padding=0.15, feather=True):
    out = image_bgr.copy()
    for box in boxes:
        if isinstance(box, dict):
            bbox = box['bbox']
            is_face = box.get('type') == 'face'
        else:
            bbox = box
            is_face = False
        shape = 'ellipse' if is_face else 'rect'
        box_method = 'gaussian' if is_face and method in ('auto', 'pixelate') else method
        out = blur_region(out, bbox, method=box_method, padding=padding, feather=feather, shape=shape)
    return out

def draw_boxes(image_bgr, detections, color=(0, 0, 255), thickness=2):
    img = image_bgr.copy()
    for d in detections:
        if isinstance(d, dict):
            bbox = d.get('bbox')
            label = d.get('label', d.get('type', ''))
        else:
            bbox = d
            label = ''
        if not bbox or len(bbox) < 4:
            continue
        x, y, w, h = [int(v) for v in bbox]
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)
        if label:
            cv2.putText(img, label, (x, max(15, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return img
