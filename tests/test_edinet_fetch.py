from __future__ import annotations

import zipfile

import pandas as pd
import pytest

from src.config import AppConfig
from src.data.fetch_edinet import is_valid_xbrl_zip, normalize_edinet_limit, select_edinet_codes


def test_normalize_edinet_limit_all_and_integer() -> None:
    assert normalize_edinet_limit("all") is None
    assert normalize_edinet_limit("ALL") is None
    assert normalize_edinet_limit("300") == 300
    assert normalize_edinet_limit(300) == 300


def test_normalize_edinet_limit_rejects_invalid_values() -> None:
    for value in ["", "zero", "0", -1]:
        with pytest.raises(ValueError):
            normalize_edinet_limit(value)


def test_select_edinet_codes_all_and_limited() -> None:
    source = pd.DataFrame({"code": ["1301", "1332", "7203"]})
    assert select_edinet_codes(source, "all") == ["1301", "1332", "7203"]
    assert select_edinet_codes(source, "2") == ["1301", "1332"]


def test_is_valid_xbrl_zip_detects_valid_and_invalid_cache(tmp_path) -> None:
    valid_zip = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid_zip, "w") as archive:
        archive.writestr("xbrl/sample.xbrl", "ok")

    empty_zip = tmp_path / "empty.zip"
    empty_zip.write_bytes(b"")

    non_zip = tmp_path / "not_zip.zip"
    non_zip.write_text("not a zip", encoding="utf-8")

    assert is_valid_xbrl_zip(valid_zip)
    assert not is_valid_xbrl_zip(empty_zip)
    assert not is_valid_xbrl_zip(non_zip)
    assert not is_valid_xbrl_zip(tmp_path / "missing.zip")


def test_config_accepts_edinet_limit_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDINET_LIMIT", "all")
    config = AppConfig.load()
    assert config.edinet_limit == "all"


def test_config_accepts_numeric_edinet_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDINET_LIMIT", "300")
    config = AppConfig.load()
    assert config.edinet_limit == "300"
