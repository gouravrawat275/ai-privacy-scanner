import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from modules.scanner import PrivacyScanner
from modules.risk_analyzer import compute_risk
from modules.image_utils import blur_region, apply_redactions, draw_boxes, _expand_bbox, _redact_pixels
from modules.metadata_scanner import MetadataScanner


def make_synthetic_test_image(path):
    img = np.full((600, 900, 3), 230, dtype=np.uint8)
    cv2.ellipse(img, (200, 200), (70, 90), 0, 0, 360, (180, 170, 160), -1)
    cv2.circle(img, (175, 180), 8, (50, 50, 50), -1)
    cv2.circle(img, (225, 180), 8, (50, 50, 50), -1)
    cv2.ellipse(img, (200, 230), (25, 10), 0, 0, 180, (80, 60, 60), 2)
    cv2.rectangle(img, (500, 400), (700, 460), (240, 240, 240), -1)
    cv2.rectangle(img, (500, 400), (700, 460), (0, 0, 0), 2)
    cv2.putText(img, 'ABC-1234', (515, 440), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(img, 'DRIVER LICENSE', (450, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, 'DOB: 01/01/1990', (450, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, 'contact@example.com', (450, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.imwrite(path, img)
    return path


def test_full_pipeline_runs_without_crashing():
    test_img_path = os.path.join(os.path.dirname(__file__), '_synthetic_test.jpg')
    make_synthetic_test_image(test_img_path)
    scanner = PrivacyScanner(enable_background_objects=False)
    result = scanner.scan(test_img_path)
    assert 'detections' in result
    assert 'risk' in result
    assert isinstance(result['risk']['score'], int) or isinstance(result['risk']['score'], float)
    assert result['risk']['level'] in ('Low', 'Medium', 'High', 'Critical')
    assert 'faces' in result['detections']
    assert 'plates' in result['detections']
    assert 'ocr' in result['detections']
    print(f"[OK] Pipeline ran. Risk score={result['risk']['score']} level={result['risk']['level']}")
    print(f"[OK] OCR found text: {result['detections']['ocr']['raw_text'][:80]!r}")
    print(f"[OK] OCR findings: {result['detections']['ocr']['findings']}")
    os.remove(test_img_path)


def test_risk_engine_with_mock_detections():
    mock_detections = {
        'faces': [{'type': 'face', 'bbox': [0, 0, 10, 10]}],
        'plates': [{'type': 'plate', 'bbox': [0, 0, 10, 10]}],
        'child_flags': [{'flag_for_review': True, 'estimated_age_range': '(8-12)'}],
        'ocr': {'findings': [{'type': 'id_keyword', 'match': 'passport'}]},
        'metadata': {'has_gps': True},
        'background_objects': [],
    }
    risk = compute_risk(mock_detections)
    assert risk['score'] > 0
    assert risk['level'] in ('Low', 'Medium', 'High', 'Critical')
    assert len(risk['breakdown']) > 0
    assert any(('minor' in s.lower() for s in risk['suggestions']))
    print(f"[OK] Mock risk score={risk['score']} level={risk['level']}")
    print(f"[OK] Suggestions: {risk['suggestions']}")


def test_blur_and_draw_do_not_crash():
    img = np.full((300, 300, 3), 255, dtype=np.uint8)
    boxes = [{'type': 'face', 'bbox': [50, 50, 80, 80]}]
    for method in ('gaussian', 'pixelate', 'solid', 'auto'):
        out = blur_region(img.copy(), boxes[0]['bbox'], method=method)
        assert out.shape == img.shape
    drawn = draw_boxes(img.copy(), boxes)
    assert drawn.shape == img.shape
    print('[OK] Blur (all 4 methods)/draw all ran without crashing')


def test_redaction_padding_expands_coverage():
    bbox = [100, 100, 60, 60]
    img_shape = (300, 300, 3)
    x1, y1, x2, y2 = _expand_bbox(bbox, 0.0, img_shape)
    assert (x1, y1, x2, y2) == (100, 100, 160, 160)
    x1p, y1p, x2p, y2p = _expand_bbox(bbox, 0.15, img_shape)
    assert x1p < 100 and y1p < 100 and (x2p > 160) and (y2p > 160)
    print(f"[OK] padding=0.15 expands [100,100,160,160] -> [{x1p},{y1p},{x2p},{y2p}]")


def test_redaction_core_area_fully_obscured_even_with_feathering():
    bbox = [100, 100, 60, 60]
    img = np.full((300, 300, 3), 128, dtype=np.uint8)
    core = img[100:160, 100:160]
    for row in range(core.shape[0]):
        core[row, :] = 30 if row // 2 % 2 == 0 else 220
    img[100:160, 100:160] = core
    col = 130
    orig_jump = int(np.abs(np.diff(img[95:165, col, 0].astype(int))).max())
    out = blur_region(img.copy(), bbox, method='auto', padding=0.15, feather=True)
    new_jump = int(np.abs(np.diff(out[100:160, col, 0].astype(int))).max())
    assert new_jump < orig_jump * 0.5, 'fine detail inside the core detection area must be substantially destroyed'
    print(f"[OK] fine-detail row-to-row jump inside core box: {orig_jump} -> {new_jump} ({100 * (1 - new_jump / orig_jump):.0f}% reduction)")


def test_redaction_corners_fully_obscured_both_shapes():
    bbox = [100, 100, 60, 60]
    x1, y1, x2, y2 = (100, 100, 160, 160)

    def make_img():
        img = np.full((300, 300, 3), 128, dtype=np.uint8)
        core = img[91:169, 91:169]
        for row in range(core.shape[0]):
            core[row, :] = 30 if row // 2 % 2 == 0 else 220
        img[91:169, 91:169] = core
        return img

    def worst_corner_jump(out):
        inset = 2
        corners = [
            (y1 + inset, x1 + inset),
            (y1 + inset, x2 - inset - 1),
            (y2 - inset - 1, x1 + inset),
            (y2 - inset - 1, x2 - inset - 1),
        ]
        worst = 0
        for cy, cx in corners:
            patch = out[cy - 2:cy + 3, cx - 2:cx + 3, 0].astype(int)
            worst = max(worst, int(np.abs(np.diff(patch, axis=0)).max()))
        return worst

    for shape in ('rect', 'ellipse'):
        out = blur_region(make_img(), bbox, method='auto', padding=0.15, feather=True, shape=shape)
        worst = worst_corner_jump(out)
        assert worst < 30, f"shape={shape}: corner of the real detected box must be fully redacted (got jump={worst}/190)"
        print(f"[OK] shape={shape}: worst-case corner jump = {worst}/190 ({100 * worst / 190:.0f}% residual)")


def test_apply_redactions_uses_gaussian_for_faces_with_auto_method():
    img = np.full((300, 300, 3), 128, dtype=np.uint8)
    face_box = {'type': 'face', 'bbox': [100, 100, 60, 60]}
    plate_box = {'type': 'plate', 'bbox': [200, 200, 40, 20]}
    calls = []
    import modules.image_utils as iu

    orig_blur_region = iu.blur_region

    def spy(image_bgr, bbox, method='auto', **kwargs):
        calls.append({'method': method, 'shape': kwargs.get('shape')})
        return orig_blur_region(image_bgr, bbox, method=method, **kwargs)

    iu.blur_region = spy
    try:
        iu.apply_redactions(img, [face_box, plate_box], method='auto')
    finally:
        iu.blur_region = orig_blur_region
    face_call = next((c for c in calls if c['shape'] == 'ellipse'))
    plate_call = next((c for c in calls if c['shape'] == 'rect'))
    assert face_call['method'] == 'gaussian', 'faces must be routed to gaussian when the caller asked for auto'
    assert plate_call['method'] == 'auto', "non-face boxes must keep the caller's requested method unchanged"
    print(f"[OK] apply_redactions routing: face->{face_call['method']}/{face_call['shape']}, plate->{plate_call['method']}/{plate_call['shape']}")


def test_apply_redactions_accepts_coordinate_lists():
    import modules.image_utils as iu

    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    out = iu.apply_redactions(img, [[20, 20, 30, 30]], method='solid', padding=0, feather=False)

    assert np.all(out[20:50, 20:50] == 20)


def test_redaction_feathering_smooths_the_edge():
    bbox = [100, 100, 60, 60]
    x1p, y1p, x2p, y2p = _expand_bbox(bbox, 0.15, (300, 300, 3))

    def make_base():
        img = np.full((300, 300, 3), 128, dtype=np.uint8)
        img[y1p:y2p, x1p:x2p] = (250, 250, 250)
        return img

    hard = blur_region(make_base(), bbox, method='solid', padding=0.15, feather=False)
    soft = blur_region(make_base(), bbox, method='solid', padding=0.15, feather=True)
    row = (y1p + y2p) // 2
    window = slice(x2p - 5, x2p + 30)
    hard_strip = hard[row, window, 0].astype(int)
    soft_strip = soft[row, window, 0].astype(int)
    hard_width = int(np.sum(np.abs(np.diff(hard_strip)) > 3))
    soft_width = int(np.sum(np.abs(np.diff(soft_strip)) > 3))
    assert hard_width <= 1, 'a hard (unfeathered) cut should transition in a single pixel step'
    assert soft_width >= 5, 'a feathered edge should visibly spread the transition across several pixels'
    print(f"[OK] transition width: hard-cut={hard_width}px feathered={soft_width}px")


def test_redaction_strength_scales_with_region_size():
    small_roi = np.random.randint(0, 255, (30, 30, 3), dtype=np.uint8)
    large_roi = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
    small_out = _redact_pixels(small_roi, 'gaussian')
    large_out = _redact_pixels(large_roi, 'gaussian')
    assert small_out.std() < 60, 'small regions must still be strongly obscured'
    assert large_out.std() < 60, 'large regions must be JUST as strongly obscured, not left under-blurred'
    print(f"[OK] residual detail after redaction: small={small_out.std():.1f} large={large_out.std():.1f} (both well below raw ~73)")


def test_metadata_scanner_handles_no_exif():
    test_img_path = os.path.join(os.path.dirname(__file__), '_no_exif.png')
    cv2.imwrite(test_img_path, np.full((50, 50, 3), 255, dtype=np.uint8))
    result = MetadataScanner().scan(test_img_path)
    assert result['has_exif'] is False
    assert result['has_gps'] is False
    print('[OK] Metadata scanner handles images with no EXIF gracefully')
    os.remove(test_img_path)


if __name__ == '__main__':
    test_full_pipeline_runs_without_crashing()
    test_risk_engine_with_mock_detections()
    test_blur_and_draw_do_not_crash()
    test_redaction_padding_expands_coverage()
    test_redaction_core_area_fully_obscured_even_with_feathering()
    test_redaction_corners_fully_obscured_both_shapes()
    test_apply_redactions_uses_gaussian_for_faces_with_auto_method()
    test_redaction_feathering_smooths_the_edge()
    test_redaction_strength_scales_with_region_size()
    test_metadata_scanner_handles_no_exif()
    print('\nAll smoke tests passed.')
