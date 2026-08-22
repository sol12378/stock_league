from __future__ import annotations

import json
import zipfile
from datetime import date

from edinet_full_archive import (
    ArchiveDatabase,
    ArchivePaths,
    iter_dates,
    load_api_key,
    payload_types_for_document,
    sanitize_error,
    validate_payload,
)


def test_load_api_key_accepts_spaces_without_exposing_value(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EDINET_API_KEY = secret-value\n", encoding="utf-8")
    assert load_api_key(env_file) == "secret-value"


def test_payload_types_follow_flags() -> None:
    record = {
        "docTypeCode": "120",
        "legalStatus": "1",
        "disclosureStatus": "0",
        "pdfFlag": "1",
        "attachDocFlag": "0",
        "englishDocFlag": "1",
        "csvFlag": "1",
    }
    assert payload_types_for_document(record) == [1, 2, 4, 5]
    assert payload_types_for_document({**record, "legalStatus": "0"}) == []
    assert payload_types_for_document({**record, "disclosureStatus": "2"}) == []
    assert payload_types_for_document({**record, "docTypeCode": None}) == []


def test_iter_dates_is_inclusive() -> None:
    values = list(iter_dates(date(2025, 6, 29), date(2025, 7, 1)))
    assert values == [date(2025, 6, 29), date(2025, 6, 30), date(2025, 7, 1)]


def test_validate_payload_signatures(tmp_path) -> None:
    archive = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("sample.txt", "ok")
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    invalid = tmp_path / "invalid.zip"
    invalid.write_text("not zip", encoding="utf-8")
    assert validate_payload(archive, 1)[0]
    assert validate_payload(pdf, 2)[0]
    assert not validate_payload(invalid, 1)[0]


def test_ingest_day_creates_document_and_payload_plan(tmp_path) -> None:
    paths = ArchivePaths(tmp_path / "archive")
    database = ArchiveDatabase(paths.database)
    filing_date = date(2025, 6, 30)
    raw_path = paths.day(filing_date)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"processDateTime": "2025-06-30 12:00"},
        "results": [
            {
                "docID": "S100TEST",
                "submitDateTime": "2025-06-30 09:00",
                "docTypeCode": "120",
                "legalStatus": "1",
                "disclosureStatus": "0",
                "pdfFlag": "1",
                "attachDocFlag": "0",
                "englishDocFlag": "0",
                "csvFlag": "1",
            }
        ],
    }
    raw_path.write_text(json.dumps(payload), encoding="utf-8")
    assert database.ingest_day(filing_date, raw_path, payload, "test") == 1
    assert database.connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
    planned = database.connection.execute(
        "SELECT payload_type FROM payloads ORDER BY payload_type"
    ).fetchall()
    assert [row[0] for row in planned] == [1, 2, 5]
    database.close()


def test_sanitize_error_redacts_key() -> None:
    assert "secret" not in sanitize_error("url?Subscription-Key=secret", "secret")


def test_pending_payload_snapshot_closes_before_concurrent_write(tmp_path) -> None:
    paths = ArchivePaths(tmp_path / "archive")
    first = ArchiveDatabase(paths.database)
    filing_date = date(2025, 6, 30)
    raw_path = paths.day(filing_date)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {},
        "results": [
            {
                "docID": "S100LOCK",
                "submitDateTime": "2025-06-30 09:00",
                "docTypeCode": "120",
                "legalStatus": "1",
                "disclosureStatus": "0",
                "pdfFlag": "0",
                "attachDocFlag": "0",
                "englishDocFlag": "0",
                "csvFlag": "1",
            }
        ],
    }
    raw_path.write_text(json.dumps(payload), encoding="utf-8")
    first.ingest_day(filing_date, raw_path, payload, "test")
    second = ArchiveDatabase(paths.database)

    pending = first.pending_payloads({1}, limit=1)
    assert next(pending)["doc_id"] == "S100LOCK"
    second.set_payload_result("S100LOCK", 5, status="unavailable")
    first.set_payload_result("S100LOCK", 1, status="unavailable")

    statuses = first.connection.execute(
        "SELECT payload_type,status FROM payloads ORDER BY payload_type"
    ).fetchall()
    assert [(row[0], row[1]) for row in statuses] == [
        (1, "unavailable"),
        (5, "unavailable"),
    ]
    assert first.connection.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    second.close()
    first.close()
