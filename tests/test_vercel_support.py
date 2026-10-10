import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules import credentials, ocr_extractor
from modules.database import _postgres_sql, connect_database


def test_postgres_sql_translates_sqlite_schema_and_parameters():
    statement = _postgres_sql(
        "CREATE TABLE scans (id INTEGER PRIMARY KEY AUTOINCREMENT); "
        "SELECT * FROM scans WHERE username = ?"
    )
    assert "BIGSERIAL PRIMARY KEY" in statement
    assert "username = %s" in statement


def test_ocr_failure_is_returned_to_the_client(monkeypatch):
    monkeypatch.setattr(ocr_extractor, "_WINOCR_OK", False)
    monkeypatch.setattr(ocr_extractor, "_TESSERACT_OK", True)

    def fail_ocr(_image):
        raise RuntimeError("Tesseract executable not found")

    monkeypatch.setattr(ocr_extractor.pytesseract, "image_to_string", fail_ocr)
    result = ocr_extractor.OCRExtractor().extract(np.zeros((16, 16, 3), dtype=np.uint8))

    assert result["enabled"] is True
    assert result["error"] == "Tesseract executable not found"


def test_vercel_requires_persistent_database_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required on Vercel"):
        connect_database(str(tmp_path / "history.db"))

    with pytest.raises(credentials.AuthConfigError, match="DATABASE_URL is required on Vercel"):
        credentials.load_or_init_config()
