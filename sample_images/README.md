# sample_images/

No real photos are bundled with this project (intentionally — it's a
privacy tool, so we didn't want to ship other people's faces in it).

Drop your own test photos here to try the dashboard, or just use the
"Upload an image" button in the Streamlit app to pick a file from
anywhere on your machine.

For a quick sanity check with zero real photos needed, run:

```bash
python3 tests/test_pipeline.py
```

which generates a synthetic test image on the fly and runs it through
the full pipeline.
