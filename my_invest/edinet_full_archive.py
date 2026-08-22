from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urljoin, urlparse

import requests


API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
DEFAULT_ENV_FILE = Path("/Users/satouryuuichi/Desktop/product/hobby/stock_league/.env")
DEFAULT_ARCHIVE_ROOT = Path(__file__).resolve().parent / "data" / "raw" / "edinet_full"
DEFAULT_EXISTING_ROOT = Path(
    "/Users/satouryuuichi/Desktop/product/hobby/stock_league/data/raw/edinet"
)
DEFAULT_REPORT_DIR = Path(__file__).resolve().parent / "outputs" / "edinet_full_archive"
PAYLOAD_EXTENSIONS = {1: ".zip", 2: ".pdf", 3: ".zip", 4: ".zip", 5: ".zip"}
FLAG_FOR_PAYLOAD = {2: "pdfFlag", 3: "attachDocFlag", 4: "englishDocFlag", 5: "csvFlag"}
PUBLIC_DOWNLOAD_SUFFIXES = {".zip", ".xlsx", ".xls", ".pdf", ".csv"}
JST = timezone(timedelta(hours=9))
SQLITE_BUSY_TIMEOUT_MS = 30_000
SQLITE_WRITE_RETRIES = 8


def is_sqlite_busy_error(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS days (
    filing_date TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    result_count INTEGER NOT NULL,
    process_datetime TEXT,
    acquired_at TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    list_date TEXT NOT NULL,
    seq_number INTEGER,
    edinet_code TEXT,
    sec_code TEXT,
    jcn TEXT,
    filer_name TEXT,
    fund_code TEXT,
    ordinance_code TEXT,
    form_code TEXT,
    doc_type_code TEXT,
    period_start TEXT,
    period_end TEXT,
    submit_datetime TEXT,
    doc_description TEXT,
    issuer_edinet_code TEXT,
    subject_edinet_code TEXT,
    subsidiary_edinet_code TEXT,
    current_report_reason TEXT,
    parent_doc_id TEXT,
    operation_datetime TEXT,
    withdrawal_status TEXT,
    doc_info_edit_status TEXT,
    disclosure_status TEXT,
    xbrl_flag TEXT,
    pdf_flag TEXT,
    attach_doc_flag TEXT,
    english_doc_flag TEXT,
    csv_flag TEXT,
    legal_status TEXT,
    raw_record_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_submit_datetime ON documents(submit_datetime);
CREATE INDEX IF NOT EXISTS idx_documents_sec_code ON documents(sec_code);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type_code);
CREATE INDEX IF NOT EXISTS idx_documents_issuer ON documents(issuer_edinet_code);
CREATE INDEX IF NOT EXISTS idx_documents_subject ON documents(subject_edinet_code);

CREATE TABLE IF NOT EXISTS payloads (
    doc_id TEXT NOT NULL,
    payload_type INTEGER NOT NULL,
    path TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    content_type TEXT,
    byte_size INTEGER,
    sha256 TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    acquired_at TEXT,
    last_error TEXT,
    source TEXT NOT NULL DEFAULT 'api',
    PRIMARY KEY (doc_id, payload_type),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS public_assets (
    url TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    content_type TEXT,
    byte_size INTEGER,
    sha256 TEXT,
    acquired_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_link_or_copy(source: Path, destination: Path, mode: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size == source.stat().st_size:
        return "existing"
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    if mode == "reference":
        return "reference"
    if mode == "hardlink":
        try:
            os.link(source, temporary)
        except OSError:
            shutil.copy2(source, temporary)
    elif mode == "copy":
        shutil.copy2(source, temporary)
    else:
        raise ValueError(f"Unsupported import mode: {mode}")
    temporary.replace(destination)
    return mode


def load_api_key(env_file: Path) -> str:
    key = ""
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != "EDINET_API_KEY":
            continue
        key = value.strip()
        if len(key) >= 2 and key[0] == key[-1] and key[0] in {'"', "'"}:
            key = key[1:-1]
        break
    if not key:
        raise RuntimeError(
            f"EDINET_API_KEY is not configured in {env_file}. "
            "The key value is never written to logs."
        )
    return key


def iter_dates(start: date, end: date) -> Iterator[date]:
    if start > end:
        raise ValueError("start must be on or before end")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def payload_types_for_document(record: dict[str, Any]) -> list[int]:
    if not str(record.get("docTypeCode") or "").strip():
        return []
    legal_status = str(record.get("legalStatus") or "").strip()
    if legal_status and legal_status not in {"1", "2"}:
        return []
    if str(record.get("disclosureStatus") or "0") == "2":
        return []
    planned = [1]
    for payload_type, flag in FLAG_FOR_PAYLOAD.items():
        if str(record.get(flag) or "0") == "1":
            planned.append(payload_type)
    return planned


def validate_payload(path: Path, payload_type: int) -> tuple[bool, str]:
    if not path.exists() or path.stat().st_size == 0:
        return False, "missing_or_empty"
    if payload_type == 2:
        with path.open("rb") as handle:
            return (handle.read(5) == b"%PDF-", "invalid_pdf_signature")
    if not zipfile.is_zipfile(path):
        return False, "invalid_zip_signature"
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
        return (bad is None, f"corrupt_member:{bad}" if bad else "")
    except zipfile.BadZipFile:
        return False, "bad_zip"


def sanitize_error(message: str, api_key: str | None = None) -> str:
    clean = message
    if api_key:
        clean = clean.replace(api_key, "[REDACTED]")
    return clean[:1000]


@dataclass
class ArchivePaths:
    root: Path

    @property
    def database(self) -> Path:
        return self.root / "manifest" / "archive.sqlite3"

    def day(self, filing_date: date) -> Path:
        return (
            self.root
            / "daily_lists"
            / f"{filing_date:%Y}"
            / f"{filing_date:%m}"
            / f"documents_{filing_date:%Y-%m-%d}.json"
        )

    def payload(self, doc_id: str, payload_type: int) -> Path:
        return (
            self.root
            / "documents"
            / doc_id[:4]
            / doc_id
            / f"type{payload_type}{PAYLOAD_EXTENSIONS[payload_type]}"
        )

    def public_asset(self, url: str) -> Path:
        parsed = urlparse(url)
        clean_path = parsed.path.strip("/") or "index.html"
        return self.root / "public_assets" / parsed.netloc / clean_path


class ArchiveDatabase:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            path,
            timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def write_with_retry(
        self,
        operation,
        *,
        label: str,
        attempts: int = SQLITE_WRITE_RETRIES,
    ) -> Any:
        """Retry an idempotent SQLite write after rolling back a busy snapshot."""
        for attempt in range(1, attempts + 1):
            try:
                result = operation()
                self.connection.commit()
                if attempt > 1:
                    print(
                        "sqlite_auto_recovery "
                        + json.dumps(
                            {
                                "label": label,
                                "cause": "concurrent_writer_contention",
                                "action": "rollback_backoff_retry",
                                "recovered": True,
                                "attempt": attempt,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                return result
            except sqlite3.OperationalError as exc:
                if not is_sqlite_busy_error(exc) or attempt == attempts:
                    raise
                self.connection.rollback()
                delay = min(0.05 * (2 ** (attempt - 1)), 2.0)
                print(
                    "sqlite_auto_recovery "
                    + json.dumps(
                        {
                            "label": label,
                            "cause": "concurrent_writer_contention",
                            "action": "rollback_backoff_retry",
                            "recovered": False,
                            "attempt": attempt,
                            "delay_seconds": delay,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                time.sleep(delay)

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def run(self, command: str, details: dict[str, Any]) -> Iterator[int]:
        cursor = self.connection.execute(
            "INSERT INTO runs(command, started_at, status, details_json) VALUES (?, ?, ?, ?)",
            (command, now_iso(), "running", json.dumps(details, ensure_ascii=False)),
        )
        run_id = int(cursor.lastrowid)
        self.connection.commit()
        try:
            yield run_id
        except BaseException:
            self.connection.execute(
                "UPDATE runs SET finished_at=?, status=? WHERE run_id=?",
                (now_iso(), "failed", run_id),
            )
            self.connection.commit()
            raise
        else:
            self.connection.execute(
                "UPDATE runs SET finished_at=?, status=? WHERE run_id=?",
                (now_iso(), "completed", run_id),
            )
            self.connection.commit()

    def ingest_day(
        self,
        filing_date: date,
        raw_path: Path,
        payload: dict[str, Any],
        source: str,
    ) -> int:
        acquired = now_iso()
        results = payload.get("results") or []
        metadata = payload.get("metadata") or {}
        process_datetime = metadata.get("processDateTime")
        self.connection.execute(
            """
            INSERT INTO days(
                filing_date, path, sha256, byte_size, result_count,
                process_datetime, acquired_at, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filing_date) DO UPDATE SET
                path=excluded.path, sha256=excluded.sha256, byte_size=excluded.byte_size,
                result_count=excluded.result_count, process_datetime=excluded.process_datetime,
                acquired_at=excluded.acquired_at, source=excluded.source
            """,
            (
                filing_date.isoformat(),
                str(raw_path),
                sha256_file(raw_path),
                raw_path.stat().st_size,
                len(results),
                process_datetime,
                acquired,
                source,
            ),
        )
        for record in results:
            doc_id = str(record.get("docID") or "").strip()
            if not doc_id:
                continue
            values = (
                doc_id,
                filing_date.isoformat(),
                record.get("seqNumber"),
                record.get("edinetCode"),
                record.get("secCode"),
                record.get("JCN"),
                record.get("filerName"),
                record.get("fundCode"),
                record.get("ordinanceCode"),
                record.get("formCode"),
                record.get("docTypeCode"),
                record.get("periodStart"),
                record.get("periodEnd"),
                record.get("submitDateTime"),
                record.get("docDescription"),
                record.get("issuerEdinetCode"),
                record.get("subjectEdinetCode"),
                record.get("subsidiaryEdinetCode"),
                record.get("currentReportReason"),
                record.get("parentDocID"),
                record.get("opeDateTime"),
                record.get("withdrawalStatus"),
                record.get("docInfoEditStatus"),
                record.get("disclosureStatus"),
                record.get("xbrlFlag"),
                record.get("pdfFlag"),
                record.get("attachDocFlag"),
                record.get("englishDocFlag"),
                record.get("csvFlag"),
                record.get("legalStatus"),
                json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                acquired,
                acquired,
            )
            placeholders = ",".join("?" for _ in values)
            self.connection.execute(
                f"""
                INSERT INTO documents VALUES ({placeholders})
                ON CONFLICT(doc_id) DO UPDATE SET
                    list_date=excluded.list_date,
                    seq_number=excluded.seq_number,
                    raw_record_json=excluded.raw_record_json,
                    last_seen_at=excluded.last_seen_at,
                    withdrawal_status=excluded.withdrawal_status,
                    doc_info_edit_status=excluded.doc_info_edit_status,
                    disclosure_status=excluded.disclosure_status,
                    legal_status=excluded.legal_status
                """,
                values,
            )
            for payload_type in payload_types_for_document(record):
                endpoint = f"{API_BASE}/documents/{doc_id}?type={payload_type}"
                self.connection.execute(
                    """
                    INSERT INTO payloads(doc_id, payload_type, path, endpoint, status)
                    VALUES (?, ?, ?, ?, 'pending')
                    ON CONFLICT(doc_id, payload_type) DO NOTHING
                    """,
                    (doc_id, payload_type, "", endpoint),
                )
        self.connection.commit()
        return len(results)

    def pending_payloads(
        self,
        payload_types: set[int] | None = None,
        limit: int | None = None,
    ) -> Iterator[sqlite3.Row]:
        sql = """
            SELECT p.*, d.raw_record_json
            FROM payloads p JOIN documents d USING(doc_id)
            WHERE p.status NOT IN ('ok', 'unavailable')
        """
        params: list[Any] = []
        if payload_types:
            placeholders = ",".join("?" for _ in payload_types)
            sql += f" AND p.payload_type IN ({placeholders})"
            params.extend(sorted(payload_types))
        sql += " ORDER BY d.submit_datetime, p.doc_id, p.payload_type"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        # Fully materialize and close this read cursor before any payload write.
        # Otherwise a concurrent Drive commit can make this WAL snapshot
        # impossible to upgrade to a writer (SQLITE_BUSY_SNAPSHOT).
        cursor = self.connection.execute(sql, params)
        try:
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return iter(rows)

    def set_payload_result(
        self,
        doc_id: str,
        payload_type: int,
        **fields: Any,
    ) -> None:
        allowed = {
            "path",
            "status",
            "http_status",
            "content_type",
            "byte_size",
            "sha256",
            "attempts",
            "acquired_at",
            "last_error",
            "source",
        }
        selected = {key: value for key, value in fields.items() if key in allowed}
        assignments = ", ".join(f"{key}=?" for key in selected)
        values = list(selected.values()) + [doc_id, payload_type]
        self.write_with_retry(
            lambda: self.connection.execute(
                f"UPDATE payloads SET {assignments} WHERE doc_id=? AND payload_type=?",
                values,
            ),
            label="set_payload_result",
        )

    def reconcile_payload_plan(self) -> dict[str, int]:
        eligibility = """
            doc_type_code IS NOT NULL AND doc_type_code <> ''
            AND COALESCE(disclosure_status, '0') <> '2'
            AND (legal_status IS NULL OR legal_status = '' OR legal_status IN ('1', '2'))
        """
        before = self.connection.execute("SELECT COUNT(*) FROM payloads").fetchone()[0]
        deleted = self.connection.execute(
            f"""
            DELETE FROM payloads
            WHERE status <> 'ok' AND doc_id IN (
                SELECT doc_id FROM documents WHERE NOT ({eligibility})
            )
            """
        ).rowcount
        rules = {
            1: "1=1",
            2: "pdf_flag='1'",
            3: "attach_doc_flag='1'",
            4: "english_doc_flag='1'",
            5: "csv_flag='1'",
        }
        inserted = 0
        for payload_type, rule in rules.items():
            cursor = self.connection.execute(
                f"""
                INSERT OR IGNORE INTO payloads(
                    doc_id, payload_type, path, endpoint, status
                )
                SELECT
                    doc_id,
                    ?,
                    '',
                    ? || doc_id || '?type=' || ?,
                    'pending'
                FROM documents
                WHERE {eligibility} AND ({rule})
                """,
                (payload_type, f"{API_BASE}/documents/", payload_type),
            )
            inserted += cursor.rowcount
        self.connection.commit()
        after = self.connection.execute("SELECT COUNT(*) FROM payloads").fetchone()[0]
        return {"before": before, "deleted": deleted, "inserted": inserted, "after": after}


class EdinetClient:
    def __init__(self, api_key: str, interval: float, retries: int = 5):
        self.api_key = api_key
        self.interval = max(interval, 0.0)
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "EDINET-research-archive/1.0"})
        self.last_request_at = 0.0

    def _pace(self) -> None:
        wait = self.interval - (time.monotonic() - self.last_request_at)
        if wait > 0:
            time.sleep(wait)

    def request(self, url: str, params: dict[str, Any], *, stream: bool = False) -> requests.Response:
        safe_params = dict(params)
        request_params = dict(safe_params)
        request_params["Subscription-Key"] = self.api_key
        last_error = "request_failed"
        for attempt in range(1, self.retries + 1):
            self._pace()
            try:
                response = self.session.get(
                    url,
                    params=request_params,
                    timeout=(20, 180),
                    stream=stream,
                )
                self.last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_error = sanitize_error(type(exc).__name__, self.api_key)
                time.sleep(min(60.0, 2.0**attempt))
                continue
            if response.status_code == 429:
                response.close()
                time.sleep(min(120.0, 2.0**attempt))
                continue
            if response.status_code >= 500:
                response.close()
                time.sleep(min(60.0, 2.0**attempt))
                continue
            return response
        raise RuntimeError(last_error)

    def get_day(self, filing_date: date) -> dict[str, Any]:
        response = self.request(
            f"{API_BASE}/documents.json",
            {"date": filing_date.isoformat(), "type": 2},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"invalid_json_status_{response.status_code}") from exc
        finally:
            response.close()
        status = payload.get("StatusCode") or (payload.get("metadata") or {}).get("status")
        if str(status) == "401":
            raise RuntimeError("EDINET authentication failed (key value redacted)")
        if str(status) not in {"200", "None"} and "results" not in payload:
            raise RuntimeError(f"EDINET list error status={status}")
        return payload


def save_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    temporary.replace(path)


def import_existing(
    database: ArchiveDatabase,
    paths: ArchivePaths,
    existing_root: Path,
    mode: str,
) -> dict[str, int]:
    counts = {"days": 0, "documents": 0, "payloads": 0, "invalid": 0}
    list_dir = existing_root / "documents_json"
    for source in sorted(list_dir.glob("documents_*.json")):
        date_text = source.stem.removeprefix("documents_")
        try:
            filing_date = date.fromisoformat(date_text)
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError):
            counts["invalid"] += 1
            continue
        destination = paths.day(filing_date)
        if mode == "reference":
            destination = source
        else:
            atomic_link_or_copy(source, destination, mode)
        counts["documents"] += database.ingest_day(
            filing_date, destination, payload, f"existing:{mode}"
        )
        counts["days"] += 1

    xbrl_dir = existing_root / "xbrl"
    for source in sorted(xbrl_dir.glob("*.zip")):
        doc_id = source.stem
        exists = database.connection.execute(
            "SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)
        ).fetchone()
        if not exists:
            continue
        valid, reason = validate_payload(source, 1)
        if not valid:
            counts["invalid"] += 1
            continue
        destination = paths.payload(doc_id, 1)
        if mode == "reference":
            destination = source
        else:
            atomic_link_or_copy(source, destination, mode)
        database.connection.execute(
            """
            INSERT INTO payloads(
                doc_id, payload_type, path, endpoint, status, byte_size,
                sha256, acquired_at, source
            ) VALUES (?, 1, ?, ?, 'ok', ?, ?, ?, ?)
            ON CONFLICT(doc_id, payload_type) DO UPDATE SET
                path=excluded.path, status='ok', byte_size=excluded.byte_size,
                sha256=excluded.sha256, acquired_at=excluded.acquired_at,
                source=excluded.source, last_error=NULL
            """,
            (
                doc_id,
                str(destination),
                f"{API_BASE}/documents/{doc_id}?type=1",
                source.stat().st_size,
                sha256_file(source),
                now_iso(),
                f"existing:{mode}",
            ),
        )
        counts["payloads"] += 1
    database.connection.commit()
    return counts


def scan_days(
    database: ArchiveDatabase,
    paths: ArchivePaths,
    client: EdinetClient,
    start: date,
    end: date,
    refresh: bool,
) -> dict[str, int]:
    counts = {"requested": 0, "skipped": 0, "documents": 0, "errors": 0}
    for index, filing_date in enumerate(iter_dates(start, end), start=1):
        path = paths.day(filing_date)
        if path.exists() and not refresh:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                counts["documents"] += database.ingest_day(
                    filing_date, path, payload, "archive_cache"
                )
                counts["skipped"] += 1
                continue
            except (json.JSONDecodeError, OSError):
                pass
        try:
            payload = client.get_day(filing_date)
            save_json_atomic(payload, path)
            counts["documents"] += database.ingest_day(filing_date, path, payload, "api")
            counts["requested"] += 1
        except Exception as exc:
            counts["errors"] += 1
            print(
                f"scan_error date={filing_date.isoformat()} "
                f"error={sanitize_error(str(exc), client.api_key)}",
                file=sys.stderr,
                flush=True,
            )
        if index % 100 == 0:
            print(f"scan_progress days={index} documents={counts['documents']}", flush=True)
    return counts


def free_bytes(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free


def download_payloads(
    database: ArchiveDatabase,
    paths: ArchivePaths,
    client: EdinetClient,
    payload_types: set[int] | None,
    max_files: int | None,
    reserve_gib: float,
) -> dict[str, int]:
    counts = {"ok": 0, "errors": 0, "unavailable": 0, "existing": 0}
    reserve_bytes = int(reserve_gib * 1024**3)
    for row in database.pending_payloads(payload_types, max_files):
        if max_files is not None and sum(counts.values()) >= max_files:
            break
        if free_bytes(paths.root) < reserve_bytes:
            raise RuntimeError(f"free space fell below reserve_gib={reserve_gib}")
        doc_id = str(row["doc_id"])
        payload_type = int(row["payload_type"])
        destination = paths.payload(doc_id, payload_type)
        valid, _ = validate_payload(destination, payload_type)
        if valid:
            database.set_payload_result(
                doc_id,
                payload_type,
                path=str(destination),
                status="ok",
                byte_size=destination.stat().st_size,
                sha256=sha256_file(destination),
                acquired_at=now_iso(),
                source="archive_cache",
                last_error=None,
            )
            counts["existing"] += 1
            continue
        endpoint = f"{API_BASE}/documents/{doc_id}"
        attempts = int(row["attempts"] or 0) + 1
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.unlink(missing_ok=True)
        response: requests.Response | None = None
        try:
            response = client.request(endpoint, {"type": payload_type}, stream=True)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
            if content_type == "application/json":
                try:
                    error_payload = response.json()
                    status_code = str(
                        error_payload.get("StatusCode")
                        or (error_payload.get("metadata") or {}).get("status")
                        or response.status_code
                    )
                except ValueError:
                    status_code = str(response.status_code)
                status = "unavailable" if status_code in {"404", "400"} else "error"
                database.set_payload_result(
                    doc_id,
                    payload_type,
                    status=status,
                    http_status=response.status_code,
                    content_type=content_type,
                    attempts=attempts,
                    last_error=f"api_status={status_code}",
                )
                counts[status if status == "unavailable" else "errors"] += 1
                continue
            digest = hashlib.sha256()
            byte_size = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    digest.update(chunk)
                    byte_size += len(chunk)
            valid, reason = validate_payload(temporary, payload_type)
            if not valid:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(reason)
            temporary.replace(destination)
            database.set_payload_result(
                doc_id,
                payload_type,
                path=str(destination),
                status="ok",
                http_status=response.status_code,
                content_type=content_type,
                byte_size=byte_size,
                sha256=digest.hexdigest(),
                attempts=attempts,
                acquired_at=now_iso(),
                last_error=None,
                source="api",
            )
            counts["ok"] += 1
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            database.set_payload_result(
                doc_id,
                payload_type,
                status="error",
                attempts=attempts,
                last_error=sanitize_error(str(exc), client.api_key),
            )
            counts["errors"] += 1
        finally:
            if response is not None:
                response.close()
        completed = sum(counts.values())
        if completed % 100 == 0:
            print(f"download_progress files={completed} ok={counts['ok']}", flush=True)
    return counts


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def collect_links(html: str, base_url: str) -> list[str]:
    parser = LinkCollector()
    parser.feed(html)
    return [urljoin(base_url, link) for link in parser.links]


def download_public_assets(
    database: ArchiveDatabase,
    paths: ArchivePaths,
    interval: float,
) -> dict[str, int]:
    seed_pages = [
        "https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html",
        "https://www.fsa.go.jp/search/EDINET_Taxonomy_All.html",
    ]
    fixed_assets = [
        "https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf",
        "https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140327.xlsx",
        "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip",
        "https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Fundcode.zip",
    ]
    session = requests.Session()
    session.headers.update({"User-Agent": "EDINET-research-archive/1.0"})
    page_urls = list(seed_pages)
    asset_urls = set(fixed_assets)
    seen_pages: set[str] = set()
    while page_urls:
        page_url = page_urls.pop(0)
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        response = session.get(page_url, timeout=60)
        if response.status_code != 200:
            continue
        page_path = paths.public_asset(page_url)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(response.content)
        for link in collect_links(response.text, page_url):
            suffix = Path(urlparse(link).path).suffix.lower()
            if suffix in PUBLIC_DOWNLOAD_SUFFIXES:
                asset_urls.add(link)
            elif (
                "fsa.go.jp/search/20" in link
                and link.endswith(".html")
                and link not in seen_pages
            ):
                page_urls.append(link)
        time.sleep(interval)

    counts = {"ok": 0, "errors": 0, "existing": 0}
    for index, url in enumerate(sorted(asset_urls), start=1):
        response: requests.Response | None = None
        destination = paths.public_asset(url)
        if destination.exists() and destination.stat().st_size > 0:
            counts["existing"] += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.unlink(missing_ok=True)
        try:
            response = session.get(url, timeout=(20, 180), stream=True)
            if response.status_code != 200:
                raise RuntimeError(f"http_status={response.status_code}")
            digest = hashlib.sha256()
            size = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            temporary.replace(destination)
            database.connection.execute(
                """
                INSERT INTO public_assets(
                    url, path, status, http_status, content_type,
                    byte_size, sha256, acquired_at, last_error
                ) VALUES (?, ?, 'ok', ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(url) DO UPDATE SET
                    path=excluded.path, status='ok', http_status=excluded.http_status,
                    content_type=excluded.content_type, byte_size=excluded.byte_size,
                    sha256=excluded.sha256, acquired_at=excluded.acquired_at,
                    last_error=NULL
                """,
                (
                    url,
                    str(destination),
                    response.status_code,
                    response.headers.get("Content-Type"),
                    size,
                    digest.hexdigest(),
                    now_iso(),
                ),
            )
            database.connection.commit()
            counts["ok"] += 1
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            database.connection.execute(
                """
                INSERT INTO public_assets(url, path, status, last_error)
                VALUES (?, ?, 'error', ?)
                ON CONFLICT(url) DO UPDATE SET status='error', last_error=excluded.last_error
                """,
                (url, str(destination), sanitize_error(str(exc))),
            )
            database.connection.commit()
            counts["errors"] += 1
        finally:
            if response is not None:
                response.close()
        if index % 50 == 0:
            print(f"asset_progress files={index}", flush=True)
        time.sleep(interval)
    return counts


def audit(database: ArchiveDatabase, paths: ArchivePaths, report_dir: Path) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    connection = database.connection
    scalar = lambda sql: connection.execute(sql).fetchone()[0]
    by_type = [
        dict(row)
        for row in connection.execute(
            """
            SELECT doc_type_code, COUNT(*) AS documents
            FROM documents GROUP BY doc_type_code ORDER BY doc_type_code
            """
        )
    ]
    payload_status = [
        dict(row)
        for row in connection.execute(
            """
            SELECT payload_type, status, COUNT(*) AS files,
                   COALESCE(SUM(byte_size), 0) AS bytes
            FROM payloads GROUP BY payload_type, status
            ORDER BY payload_type, status
            """
        )
    ]
    summary = {
        "generated_at": now_iso(),
        "archive_root": str(paths.root),
        "day_count": scalar("SELECT COUNT(*) FROM days"),
        "first_day": scalar("SELECT MIN(filing_date) FROM days"),
        "last_day": scalar("SELECT MAX(filing_date) FROM days"),
        "document_count": scalar("SELECT COUNT(*) FROM documents"),
        "payload_rows": scalar("SELECT COUNT(*) FROM payloads"),
        "payload_ok": scalar("SELECT COUNT(*) FROM payloads WHERE status='ok'"),
        "payload_pending": scalar(
            "SELECT COUNT(*) FROM payloads WHERE status NOT IN ('ok', 'unavailable')"
        ),
        "payload_bytes": scalar(
            "SELECT COALESCE(SUM(byte_size), 0) FROM payloads WHERE status='ok'"
        ),
        "public_assets_ok": scalar(
            "SELECT COUNT(*) FROM public_assets WHERE status='ok'"
        ),
        "free_bytes": free_bytes(paths.root),
        "documents_by_type": by_type,
        "payload_status": payload_status,
    }
    (report_dir / "archive_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# EDINET全原本アーカイブ監査",
        "",
        f"生成日時: {summary['generated_at']}",
        "",
        "## 概要",
        "",
        f"- 日別一覧: {summary['day_count']:,}日（{summary['first_day']}～{summary['last_day']}）",
        f"- 書類: {summary['document_count']:,}件",
        f"- 取得対象ファイル: {summary['payload_rows']:,}件",
        f"- 原本取得済み: {summary['payload_ok']:,}件",
        f"- 未完了・要再試行: {summary['payload_pending']:,}件",
        f"- 原本容量: {summary['payload_bytes'] / 1024**3:,.2f} GiB",
        f"- 空き容量: {summary['free_bytes'] / 1024**3:,.2f} GiB",
        "",
        "## 形式別進捗",
        "",
        "| type | 状態 | 件数 | 容量GiB |",
        "|---:|---|---:|---:|",
    ]
    for row in payload_status:
        lines.append(
            f"| {row['payload_type']} | {row['status']} | {row['files']:,} | "
            f"{row['bytes'] / 1024**3:,.2f} |"
        )
    lines.extend(
        [
            "",
            "APIキーは環境変数からのみ読み込み、監査DB・ログ・URLへ保存していない。",
        ]
    )
    (report_dir / "archive_progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_payload_types(value: str) -> set[int] | None:
    if value.strip().lower() == "all":
        return None
    result = {int(part.strip()) for part in value.split(",") if part.strip()}
    if not result or not result.issubset(PAYLOAD_EXTENSIONS):
        raise ValueError("payload types must be all or comma-separated values from 1,2,3,4,5")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive all public EDINET originals safely.")
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--interval", type=float, default=0.35)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")

    import_parser = subparsers.add_parser("import-existing")
    import_parser.add_argument("--existing-root", type=Path, default=DEFAULT_EXISTING_ROOT)
    import_parser.add_argument("--mode", choices=["hardlink", "copy", "reference"], default="hardlink")

    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--start", type=date.fromisoformat, required=True)
    scan_parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    scan_parser.add_argument("--refresh", action="store_true")

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("--types", default="all")
    download_parser.add_argument("--max-files", type=int)
    download_parser.add_argument("--reserve-gib", type=float, default=60.0)

    subparsers.add_parser("assets")
    subparsers.add_parser("reconcile")

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = ArchivePaths(args.archive_root.resolve())
    paths.root.mkdir(parents=True, exist_ok=True)
    database = ArchiveDatabase(paths.database)
    details = {key: str(value) for key, value in vars(args).items() if key != "env_file"}
    try:
        with database.run(args.command, details):
            if args.command == "init":
                result: dict[str, Any] = {"database": str(paths.database)}
            elif args.command == "import-existing":
                result = import_existing(
                    database, paths, args.existing_root.resolve(), args.mode
                )
            elif args.command == "scan":
                key = load_api_key(args.env_file)
                client = EdinetClient(key, args.interval)
                result = scan_days(
                    database, paths, client, args.start, args.end, args.refresh
                )
            elif args.command == "download":
                key = load_api_key(args.env_file)
                client = EdinetClient(key, args.interval)
                result = download_payloads(
                    database,
                    paths,
                    client,
                    parse_payload_types(args.types),
                    args.max_files,
                    args.reserve_gib,
                )
            elif args.command == "assets":
                result = download_public_assets(database, paths, args.interval)
            elif args.command == "reconcile":
                result = database.reconcile_payload_plan()
            elif args.command == "audit":
                result = audit(database, paths, args.report_dir.resolve())
            else:
                raise AssertionError(args.command)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()
