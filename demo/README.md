# demo/

Run `python3 demo/generate_demo.py` to regenerate everything in
`output/` from scratch. No real people's photos are used — every image
here is drawn programmatically.

## What's genuinely live vs. what's illustrated

| Output | How it was produced |
|---|---|
| `01_original_scene.jpg` | A synthetic "photo" someone might post: a car, a visible plate, a person holding up a driver's license, with real GPS EXIF data embedded. |
| `02_detected_risks.jpg` | **Live detection** — the actual `PrivacyScanner` pipeline run against the scene above. The plate cascade fires 3 times: 1 genuine hit on the real plate, and 2 false positives (windshield, card edge). That's realistic Haar cascade behavior on a busy scene, kept in on purpose rather than cleaned up — it's exactly why the dashboard shows a checkbox per detected region instead of blurring everything automatically. |
| `03_safe_image.jpg` | The redacted export, using the true plate match + the ID card region + the improved `auto` redaction method. |
| `04_old_vs_new_blur.jpg` | Zoomed comparison of the *old* (v1) vs *new* redaction code on the same live-detected regions. |
| `05_face_blur_quality.jpg` | **Not live detection.** Neither detector backend confidently fires on synthetic/vector art at the app's default threshold — verified for both, not assumed. The Haar cascade needs real photographic texture and doesn't respond to flat vector shading at all; the optional DNN backend (see `scripts/download_models.py`) gets *closer* (0.43 confidence on a shaded synthetic portrait) but still stays under the 0.5 default threshold. On a **real** photo the gap is stark and was measured directly during development: on a real (somewhat blurry) test photo, the Haar cascade found 0 faces while the DNN backend found 1 at 79% confidence, correctly located — that photo isn't included here (this project doesn't bundle real people's photos), but the finding is what motivated adding the DNN backend at all. Since this project intentionally doesn't use real people's photos, this image instead manually marks a face-shaped region on a synthetic portrait to show the redaction code's output quality. On a real uploaded photo, `FaceDetector` finds the box automatically (using whichever backend is available) and the identical redaction function runs on it — no manual step. |

## Why `05` matters despite not being "live"

Building it caught two real bugs, not just one:

1. The *original* fixed-strength blur left eyes and mouth faintly
   visible as darker patches once the region got large enough, because
   a single fixed kernel size doesn't scale to the region it's
   covering. Fixed by scaling strength to region size — regression test:
   `test_redaction_strength_scales_with_region_size`.
2. A later pass added elliptical feathering for faces (a rectangle over
   a round face looks wrong) and found the ellipse mask's own corners
   were measurably less redacted than its edges — a Gaussian blur softens
   a shape's own corners faster than its edge midpoints. Fixed by
   re-asserting the shape at full strength after the blur, not just
   drawing it once beforehand — regression test:
   `test_redaction_corners_fully_obscured_both_shapes`. That same pass
   also found the ellipse doesn't render as an oval at all against
   pixelated content specifically (see `modules/image_utils.py`'s module
   docstring for why), which is why faces route to `gaussian` even when
   you asked for `auto` — regression test:
   `test_apply_redactions_uses_gaussian_for_faces_with_auto_method`.

The *current* version fully flattens facial structure regardless of
region size, and renders as a clean oval rather than a box.
