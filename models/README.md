# models/

This folder is where the **optional** age-estimation model lives once
downloaded. It's intentionally empty in the repo (the model is ~44MB and
is fetched on demand, not bundled).

To enable automated age-bracket estimates for the Child Safety Detector:

```bash
python3 scripts/download_models.py
```

This fetches `age_deploy.prototxt` and `age_net.caffemodel` (the
standard Levi & Hassner age-classification CaffeNet) into this folder.

**Without these files, the app still works fully** — every detected face
is simply flagged as "please review manually for child safety" instead
of getting an automated age-bracket estimate. See the Child Safety
Detector section in the main README for why that's the deliberate,
cautious default.

If you're shipping this in a commercial product, verify the model's
license/provenance yourself before relying on the download script's
default source — it's provided as a dev-time convenience, not a
license guarantee.
