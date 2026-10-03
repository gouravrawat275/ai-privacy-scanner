# data/

`scan_history.db` (SQLite) lands here after your first scan — created
automatically by `modules/scan_history.py`, nothing to set up.

It stores scan **metadata only**: timestamp, filename, risk score/level,
and finding counts. Never the image itself, never OCR text or any other
extracted content. Gitignored by default, same reasoning as
`auth_config.yaml` — this is per-install runtime state, not source.

Want to reset your history? Just delete the `.db` file; it'll be
recreated empty on the next scan.
