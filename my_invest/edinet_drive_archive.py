from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from edinet_full_archive import (
    ArchiveDatabase,
    ArchivePaths,
    EdinetClient,
    JST,
    PAYLOAD_EXTENSIONS,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_ENV_FILE,
    download_payloads,
    load_api_key,
    now_iso,
    parse_payload_types,
    is_sqlite_busy_error,
    sha256_file,
)


DEFAULT_DRIVE_ROOT = Path(
    "/Users/satouryuuichi/Library/CloudStorage/"
    "GoogleDrive-dorankunsan8@gmail.com/マイドライブ/EDINET_2X_RESEARCH"
)
DEFAULT_STAGING_ROOT = Path(__file__).resolve().parent / "data" / "staging" / "edinet_drive"
DEFAULT_RCLONE_REMOTE: str | None = None
DEFAULT_RCLONE_BINARY = Path("/opt/homebrew/bin/rclone")
DEFAULT_RCLONE_CHUNK_SIZE = "32M"
DEFAULT_RCLONE_RETRIES = 5
DEFAULT_RCLONE_LOW_LEVEL_RETRIES = 10
DEFAULT_RCLONE_RETRIES_SLEEP = "5s"
DEFAULT_RCLONE_CONNECT_TIMEOUT = "15s"
DEFAULT_RCLONE_IO_TIMEOUT = "2m"

DRIVE_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_payloads_status_type_doc
ON payloads(status, payload_type, doc_id);

CREATE TABLE IF NOT EXISTS drive_shards (
    shard_id TEXT PRIMARY KEY,
    payload_type INTEGER NOT NULL,
    submit_month TEXT NOT NULL,
    part_number INTEGER NOT NULL,
    filename TEXT NOT NULL UNIQUE,
    local_path TEXT,
    remote_relative_path TEXT NOT NULL,
    status TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    md5 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    uploaded_at TEXT,
    verified_at TEXT,
    released_at TEXT,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_drive_shards_status
ON drive_shards(status, payload_type, submit_month);

CREATE TABLE IF NOT EXISTS drive_shard_members (
    shard_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    payload_type INTEGER NOT NULL,
    archive_path TEXT NOT NULL,
    original_path TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (doc_id, payload_type),
    FOREIGN KEY (shard_id) REFERENCES drive_shards(shard_id)
);

CREATE INDEX IF NOT EXISTS idx_drive_members_shard
ON drive_shard_members(shard_id);
"""


def file_hashes(path: Path) -> tuple[str, str, int]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
            size += len(chunk)
    return sha256.hexdigest(), md5.hexdigest(), size


def ensure_within(path: Path, root: Path) -> None:
    path.resolve().relative_to(root.resolve())


@dataclass
class Member:
    doc_id: str
    payload_type: int
    original_path: Path
    archive_path: str
    byte_size: int
    sha256: str
    submit_month: str


class DriveArchive:
    def __init__(
        self,
        database: ArchiveDatabase,
        archive_root: Path,
        staging_root: Path,
        drive_root: Path,
        rclone_remote: str | None = DEFAULT_RCLONE_REMOTE,
        rclone_binary: Path = DEFAULT_RCLONE_BINARY,
        rclone_workers: int = 4,
        rclone_chunk_size: str = DEFAULT_RCLONE_CHUNK_SIZE,
        rclone_retries: int = DEFAULT_RCLONE_RETRIES,
        rclone_low_level_retries: int = DEFAULT_RCLONE_LOW_LEVEL_RETRIES,
        rclone_retries_sleep: str = DEFAULT_RCLONE_RETRIES_SLEEP,
        rclone_connect_timeout: str = DEFAULT_RCLONE_CONNECT_TIMEOUT,
        rclone_io_timeout: str = DEFAULT_RCLONE_IO_TIMEOUT,
    ) -> None:
        self.database = database
        self.connection = database.connection
        self.connection.executescript(DRIVE_SCHEMA)
        self.connection.commit()
        self.archive_root = archive_root.resolve()
        self.staging_root = staging_root.resolve()
        self.drive_root = drive_root.resolve()
        self.rclone_remote = rclone_remote.rstrip(":") + ":" if rclone_remote else None
        self.rclone_binary = rclone_binary
        self.rclone_workers = max(1, rclone_workers)
        self.rclone_chunk_size = rclone_chunk_size
        self.rclone_retries = max(1, rclone_retries)
        self.rclone_low_level_retries = max(1, rclone_low_level_retries)
        self.rclone_retries_sleep = rclone_retries_sleep
        self.rclone_connect_timeout = rclone_connect_timeout
        self.rclone_io_timeout = rclone_io_timeout
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def validate_drive(self) -> None:
        if self.rclone_remote:
            if not self.rclone_binary.is_file():
                raise RuntimeError(f"rclone binary is unavailable: {self.rclone_binary}")
            return
        expected = "GoogleDrive-dorankunsan8@gmail.com"
        if expected not in str(self.drive_root):
            raise RuntimeError("Drive root does not target the approved Google account")
        if not self.drive_root.exists():
            raise RuntimeError(f"Drive root is unavailable: {self.drive_root}")
        test_parent = self.drive_root / "00_control"
        if not test_parent.exists():
            raise RuntimeError(f"Drive control directory is unavailable: {test_parent}")

    @staticmethod
    def cloud_item_id(path: Path) -> bytes | None:
        result = subprocess.run(
            ["xattr", "-p", "com.google.drivefs.item-id#S", str(path)],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    def rclone_path(self, relative_path: str) -> str:
        if not self.rclone_remote:
            raise RuntimeError("rclone remote is not configured")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe remote path: {relative_path}")
        return self.rclone_remote + relative.as_posix().lstrip("/")

    def run_rclone(
        self,
        arguments: list[str],
        *,
        check: bool = True,
        timeout: int = 1800,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(self.rclone_binary), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            message = (result.stderr or result.stdout or "rclone command failed").strip()
            raise RuntimeError(message[-1000:])
        return result

    def rclone_metadata(self, relative_path: str) -> dict[str, Any] | None:
        """Return cloud metadata without downloading file content."""
        result = self.run_rclone(
            [
                "lsjson",
                self.rclone_path(relative_path),
                "--stat",
                "--hash",
                "--no-modtime",
            ],
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            combined = (result.stderr + "\n" + result.stdout).lower()
            if "not found" in combined or "directory not found" in combined:
                return None
            raise RuntimeError((result.stderr or result.stdout).strip()[-1000:])
        payload = json.loads(result.stdout)
        if isinstance(payload, list):
            if not payload:
                return None
            payload = payload[0]
        if not isinstance(payload, dict):
            raise RuntimeError("unexpected rclone metadata response")
        return payload

    @staticmethod
    def metadata_md5(metadata: dict[str, Any]) -> str:
        hashes = metadata.get("Hashes") or {}
        return str(hashes.get("MD5") or hashes.get("md5") or "").lower()

    def cloud_metadata_matches(self, row: sqlite3.Row) -> bool:
        metadata = self.rclone_metadata(str(row["remote_relative_path"]))
        if metadata is None:
            return False
        return (
            int(metadata.get("Size", -1)) == int(row["byte_size"])
            and self.metadata_md5(metadata) == str(row["md5"]).lower()
        )

    def upload_rclone(self, max_shards: int | None = None) -> dict[str, int]:
        """Upload independent shards concurrently; commit SQLite in this thread."""
        rows = list(self.shard_rows(["packed", "upload_error"]))
        if max_shards is not None:
            rows = rows[:max_shards]
        counts = {"uploaded": 0, "existing": 0, "errors": 0}

        def transfer(row: sqlite3.Row) -> str:
            local_path = Path(str(row["local_path"]))
            local_sha, local_md5, local_size = file_hashes(local_path)
            if (
                local_sha != row["sha256"]
                or local_md5 != row["md5"]
                or local_size != row["byte_size"]
            ):
                raise RuntimeError("local shard hash mismatch before upload")
            if self.cloud_metadata_matches(row):
                return "existing"
            self.run_rclone(
                [
                    "copyto",
                    str(local_path),
                    self.rclone_path(str(row["remote_relative_path"])),
                    "--drive-chunk-size",
                    self.rclone_chunk_size,
                    "--transfers",
                    "1",
                    "--checkers",
                    "1",
                    "--retries",
                    str(self.rclone_retries),
                    "--low-level-retries",
                    str(self.rclone_low_level_retries),
                    "--retries-sleep",
                    self.rclone_retries_sleep,
                    "--contimeout",
                    self.rclone_connect_timeout,
                    "--timeout",
                    self.rclone_io_timeout,
                    "--stats",
                    "30s",
                    "--stats-one-line",
                ],
            )
            if not self.cloud_metadata_matches(row):
                raise RuntimeError("Google Drive size/MD5 mismatch after upload")
            return "uploaded"

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.rclone_workers, max(1, len(rows)))
        ) as executor:
            futures = {executor.submit(transfer, row): row for row in rows}
            for future in concurrent.futures.as_completed(futures):
                row = futures[future]
                try:
                    outcome = future.result()
                    self.connection.execute(
                        """
                        UPDATE drive_shards SET status='uploaded', uploaded_at=?,
                            last_error=NULL WHERE shard_id=?
                        """,
                        (now_iso(), row["shard_id"]),
                    )
                    self.connection.commit()
                    counts[outcome] += 1
                    print(
                        f"rclone_upload_progress outcome={outcome} "
                        f"completed={counts['uploaded'] + counts['existing']} "
                        f"remote={row['remote_relative_path']}",
                        flush=True,
                    )
                except Exception as exc:
                    self.connection.execute(
                        "UPDATE drive_shards SET status='upload_error', last_error=? WHERE shard_id=?",
                        (str(exc)[:1000], row["shard_id"]),
                    )
                    self.connection.commit()
                    counts["errors"] += 1
        return counts

    def candidate_groups(self, payload_types: set[int] | None) -> list[tuple[int, str]]:
        sql = """
            SELECT p.payload_type,
                   substr(COALESCE(d.submit_datetime, d.list_date), 1, 7) AS submit_month
            FROM payloads p
            JOIN documents d USING(doc_id)
            LEFT JOIN drive_shard_members m
              ON m.doc_id=p.doc_id AND m.payload_type=p.payload_type
            WHERE p.status='ok' AND m.doc_id IS NULL
        """
        params: list[Any] = []
        if payload_types:
            placeholders = ",".join("?" for _ in payload_types)
            sql += f" AND p.payload_type IN ({placeholders})"
            params.extend(sorted(payload_types))
        sql += " GROUP BY p.payload_type, submit_month ORDER BY p.payload_type, submit_month"
        return [(int(row[0]), str(row[1] or "unknown")) for row in self.connection.execute(sql, params)]

    def members_for_group(
        self,
        payload_type: int,
        submit_month: str,
        target_bytes: int,
        max_files: int,
    ) -> list[Member]:
        rows = self.connection.execute(
            """
            SELECT p.doc_id, p.payload_type, p.path, p.byte_size, p.sha256,
                   substr(COALESCE(d.submit_datetime, d.list_date), 1, 7) AS submit_month
            FROM payloads p
            JOIN documents d USING(doc_id)
            LEFT JOIN drive_shard_members m
              ON m.doc_id=p.doc_id AND m.payload_type=p.payload_type
            WHERE p.status='ok' AND m.doc_id IS NULL
              AND p.payload_type=?
              AND substr(COALESCE(d.submit_datetime, d.list_date), 1, 7)=?
            ORDER BY d.submit_datetime, p.doc_id
            """,
            (payload_type, submit_month),
        )
        selected: list[Member] = []
        selected_bytes = 0
        for row in rows:
            path = Path(str(row["path"]))
            if not path.is_file():
                continue
            size = int(row["byte_size"] or path.stat().st_size)
            digest = str(row["sha256"] or "")
            if not digest:
                digest = sha256_file(path)
            if selected and (selected_bytes + size > target_bytes or len(selected) >= max_files):
                break
            archive_path = f"payloads/{row['doc_id']}/type{payload_type}{PAYLOAD_EXTENSIONS[payload_type]}"
            selected.append(
                Member(
                    doc_id=str(row["doc_id"]),
                    payload_type=payload_type,
                    original_path=path,
                    archive_path=archive_path,
                    byte_size=size,
                    sha256=digest,
                    submit_month=submit_month,
                )
            )
            selected_bytes += size
        return selected

    def next_part_number(self, payload_type: int, submit_month: str) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(MAX(part_number), 0) + 1
            FROM drive_shards WHERE payload_type=? AND submit_month=?
            """,
            (payload_type, submit_month),
        ).fetchone()
        return int(row[0])

    def pack_members(self, members: list[Member]) -> dict[str, Any]:
        if not members:
            raise ValueError("members must not be empty")
        payload_type = members[0].payload_type
        submit_month = members[0].submit_month
        part_number = self.next_part_number(payload_type, submit_month)
        month_token = submit_month.replace("-", "_")
        base = f"edinet_type{payload_type}_{month_token}_part{part_number:04d}"
        temporary = self.staging_root / f"{base}.tar.part"
        temporary.unlink(missing_ok=True)
        manifest_lines = []
        for member in members:
            manifest_lines.append(
                json.dumps(
                    {
                        "doc_id": member.doc_id,
                        "payload_type": member.payload_type,
                        "archive_path": member.archive_path,
                        "byte_size": member.byte_size,
                        "sha256": member.sha256,
                        "submit_month": member.submit_month,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        manifest_bytes = ("\n".join(manifest_lines) + "\n").encode("utf-8")
        with tarfile.open(temporary, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for member in members:
                archive.add(member.original_path, arcname=member.archive_path, recursive=False)
            info = tarfile.TarInfo("_manifest/members.jsonl")
            info.size = len(manifest_bytes)
            info.mtime = int(time.time())
            archive.addfile(info, io.BytesIO(manifest_bytes))
        sha256, md5, size = file_hashes(temporary)
        filename = f"{base}_{sha256[:12]}.tar"
        final_path = self.staging_root / filename
        temporary.replace(final_path)
        remote_relative = (
            Path("10_bronze")
            / "payload_shards"
            / f"type{payload_type}"
            / submit_month
            / filename
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO drive_shards(
                    shard_id, payload_type, submit_month, part_number, filename,
                    local_path, remote_relative_path, status, file_count,
                    byte_size, sha256, md5, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'packed', ?, ?, ?, ?, ?)
                """,
                (
                    sha256,
                    payload_type,
                    submit_month,
                    part_number,
                    filename,
                    str(final_path),
                    str(remote_relative),
                    len(members),
                    size,
                    sha256,
                    md5,
                    now_iso(),
                ),
            )
            self.connection.executemany(
                """
                INSERT INTO drive_shard_members(
                    shard_id, doc_id, payload_type, archive_path,
                    original_path, byte_size, sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        sha256,
                        member.doc_id,
                        member.payload_type,
                        member.archive_path,
                        str(member.original_path),
                        member.byte_size,
                        member.sha256,
                    )
                    for member in members
                ],
            )
        return {
            "shard_id": sha256,
            "filename": filename,
            "files": len(members),
            "bytes": size,
        }

    def pack_available(
        self,
        payload_types: set[int] | None,
        target_gib: float,
        max_files: int,
        max_shards: int | None,
    ) -> dict[str, int]:
        counts = {"shards": 0, "files": 0, "bytes": 0}
        target_bytes = int(target_gib * 1024**3)
        while True:
            groups = self.candidate_groups(payload_types)
            if not groups or (max_shards is not None and counts["shards"] >= max_shards):
                break
            payload_type, submit_month = groups[0]
            members = self.members_for_group(payload_type, submit_month, target_bytes, max_files)
            if not members:
                raise RuntimeError(
                    f"no local files found for type={payload_type} month={submit_month}"
                )
            result = self.pack_members(members)
            counts["shards"] += 1
            counts["files"] += int(result["files"])
            counts["bytes"] += int(result["bytes"])
            print(
                f"pack_progress shards={counts['shards']} files={counts['files']} "
                f"gib={counts['bytes'] / 1024**3:.2f}",
                flush=True,
            )
        return counts

    def pack_control_snapshot(self) -> dict[str, Any]:
        snapshot_token = datetime.now(JST).strftime("%Y%m%dT%H%M%S")
        base = f"edinet_control_snapshot_{snapshot_token}"
        temporary = self.staging_root / f"{base}.tar.part"
        temporary.unlink(missing_ok=True)
        snapshot_db = self.staging_root / f"archive_{snapshot_token}.sqlite3"
        snapshot_db.unlink(missing_ok=True)
        snapshot_connection = sqlite3.connect(snapshot_db)
        try:
            self.connection.backup(snapshot_connection)
        finally:
            snapshot_connection.close()
        project_root = Path(__file__).resolve().parent
        sources = [
            (self.archive_root / "daily_lists", "daily_lists"),
            (self.archive_root / "public_assets", "public_assets"),
            (snapshot_db, "manifest/archive.sqlite3"),
            (project_root / "EDINET_ARCHIVE_README.md", "control/EDINET_ARCHIVE_README.md"),
            (project_root / "edinet_full_archive.py", "control/edinet_full_archive.py"),
            (project_root / "edinet_drive_archive.py", "control/edinet_drive_archive.py"),
            (
                project_root / "outputs" / "double_stock_research_master_plan_20260818.md",
                "control/double_stock_research_master_plan_20260818.md",
            ),
            (
                project_root / "outputs" / "google_drive_edinet_archive_plan_20260818.md",
                "control/google_drive_edinet_archive_plan_20260818.md",
            ),
            (
                project_root / "outputs" / "edinet_full_archive",
                "control/edinet_full_archive_reports",
            ),
        ]
        included_files = 0
        with tarfile.open(temporary, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for source, arcname in sources:
                if not source.exists():
                    continue
                if source.is_dir():
                    included_files += sum(1 for child in source.rglob("*") if child.is_file())
                else:
                    included_files += 1
                archive.add(source, arcname=arcname, recursive=True)
        snapshot_db.unlink(missing_ok=True)
        sha256, md5, size = file_hashes(temporary)
        filename = f"{base}_{sha256[:12]}.tar"
        final_path = self.staging_root / filename
        temporary.replace(final_path)
        remote_relative = Path("10_bronze") / "control_snapshots" / filename
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO drive_shards(
                    shard_id, payload_type, submit_month, part_number, filename,
                    local_path, remote_relative_path, status, file_count,
                    byte_size, sha256, md5, created_at
                ) VALUES (?, 0, ?, 1, ?, ?, ?, 'packed', ?, ?, ?, ?, ?)
                """,
                (
                    sha256,
                    snapshot_token,
                    filename,
                    str(final_path),
                    str(remote_relative),
                    included_files,
                    size,
                    sha256,
                    md5,
                    now_iso(),
                ),
            )
        return {
            "shard_id": sha256,
            "filename": filename,
            "files": included_files,
            "bytes": size,
        }

    def shard_rows(self, statuses: Iterable[str]) -> Iterator[sqlite3.Row]:
        statuses = list(statuses)
        placeholders = ",".join("?" for _ in statuses)
        cursor = self.connection.execute(
            f"""
            SELECT * FROM drive_shards WHERE status IN ({placeholders})
            ORDER BY payload_type, submit_month, part_number
            """,
            statuses,
        )
        try:
            rows = cursor.fetchall()
        finally:
            cursor.close()
        # Drive operations can take minutes. Never retain a WAL read snapshot
        # while the downloader commits on its own connection.
        return iter(rows)

    def upload(self, max_shards: int | None = None) -> dict[str, int]:
        self.validate_drive()
        if self.rclone_remote:
            return self.upload_rclone(max_shards)
        counts = {"uploaded": 0, "existing": 0, "errors": 0}
        for row in self.shard_rows(["packed", "upload_error"]):
            if max_shards is not None and sum(counts.values()) >= max_shards:
                break
            local_path = Path(str(row["local_path"]))
            remote_path = self.drive_root / str(row["remote_relative_path"])
            remote_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = remote_path.with_suffix(remote_path.suffix + ".uploading")
            try:
                if remote_path.exists():
                    remote_sha, remote_md5, remote_size = file_hashes(remote_path)
                    if (
                        remote_sha == row["sha256"]
                        and remote_md5 == row["md5"]
                        and remote_size == row["byte_size"]
                    ):
                        self.connection.execute(
                            """
                            UPDATE drive_shards SET status='uploaded', uploaded_at=?,
                                last_error=NULL WHERE shard_id=?
                            """,
                            (now_iso(), row["shard_id"]),
                        )
                        self.connection.commit()
                        counts["existing"] += 1
                        continue
                    raise RuntimeError("remote filename exists with different content")
                temporary.unlink(missing_ok=True)
                shutil.copyfile(local_path, temporary)
                remote_sha, remote_md5, remote_size = file_hashes(temporary)
                if (
                    remote_sha != row["sha256"]
                    or remote_md5 != row["md5"]
                    or remote_size != row["byte_size"]
                ):
                    raise RuntimeError("remote staging hash mismatch")
                temporary.replace(remote_path)
                self.connection.execute(
                    """
                    UPDATE drive_shards SET status='uploaded', uploaded_at=?,
                        last_error=NULL WHERE shard_id=?
                    """,
                    (now_iso(), row["shard_id"]),
                )
                self.connection.commit()
                counts["uploaded"] += 1
                print(
                    f"upload_progress files={counts['uploaded']} "
                    f"remote={row['remote_relative_path']}",
                    flush=True,
                )
            except Exception as exc:
                self.connection.execute(
                    "UPDATE drive_shards SET status='upload_error', last_error=? WHERE shard_id=?",
                    (str(exc)[:1000], row["shard_id"]),
                )
                self.connection.commit()
                counts["errors"] += 1
            finally:
                temporary.unlink(missing_ok=True)
        return counts

    def verify(self, max_shards: int | None = None) -> dict[str, int]:
        self.validate_drive()
        counts = {"verified": 0, "errors": 0}
        for row in self.shard_rows(["uploaded", "verify_error"]):
            if max_shards is not None and sum(counts.values()) >= max_shards:
                break
            remote_path = self.drive_root / str(row["remote_relative_path"])
            verification_path = (
                Path(str(row["local_path"])) if self.rclone_remote else remote_path
            )
            try:
                remote_sha, remote_md5, remote_size = file_hashes(verification_path)
                if (
                    remote_sha != row["sha256"]
                    or remote_md5 != row["md5"]
                    or remote_size != row["byte_size"]
                ):
                    raise RuntimeError("remote shard hash mismatch")
                expected = {
                    str(member["archive_path"]): (int(member["byte_size"]), str(member["sha256"]))
                    for member in self.connection.execute(
                        """
                        SELECT archive_path, byte_size, sha256
                        FROM drive_shard_members WHERE shard_id=?
                        """,
                        (row["shard_id"],),
                    )
                }
                # Payload shards have member-level validation. Control snapshot
                # chunks have no members and are validated by their whole-file
                # SHA-256/MD5/size, allowing exact reassembly from the manifest.
                if expected:
                    with tarfile.open(verification_path, mode="r") as archive:
                        for archive_path, (expected_size, expected_sha) in expected.items():
                            extracted = archive.extractfile(archive_path)
                            if extracted is None:
                                raise RuntimeError(f"missing tar member: {archive_path}")
                            digest = hashlib.sha256()
                            size = 0
                            for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                                digest.update(chunk)
                                size += len(chunk)
                            if size != expected_size or digest.hexdigest() != expected_sha:
                                raise RuntimeError(f"tar member mismatch: {archive_path}")
                self.connection.execute(
                    """
                    UPDATE drive_shards SET status='verified', verified_at=?,
                        last_error=NULL WHERE shard_id=?
                    """,
                    (now_iso(), row["shard_id"]),
                )
                self.connection.commit()
                counts["verified"] += 1
                print(f"verify_progress shards={counts['verified']}", flush=True)
            except Exception as exc:
                self.connection.execute(
                    "UPDATE drive_shards SET status='verify_error', last_error=? WHERE shard_id=?",
                    (str(exc)[:1000], row["shard_id"]),
                )
                self.connection.commit()
                counts["errors"] += 1
        return counts

    def confirm_cloud(self, max_shards: int | None = None) -> dict[str, int]:
        self.validate_drive()
        counts = {"confirmed": 0, "waiting": 0, "missing": 0}
        for row in self.shard_rows(["verified"]):
            if max_shards is not None and sum(counts.values()) >= max_shards:
                break
            remote_path = self.drive_root / str(row["remote_relative_path"])
            if self.rclone_remote:
                try:
                    metadata = self.rclone_metadata(str(row["remote_relative_path"]))
                    if metadata is None:
                        counts["missing"] += 1
                        continue
                    if (
                        int(metadata.get("Size", -1)) != int(row["byte_size"])
                        or self.metadata_md5(metadata) != str(row["md5"]).lower()
                    ):
                        self.connection.execute(
                            "UPDATE drive_shards SET last_error=? WHERE shard_id=?",
                            ("cloud size/MD5 mismatch", row["shard_id"]),
                        )
                        self.connection.commit()
                        counts["waiting"] += 1
                        continue
                    self.connection.execute(
                        """
                        UPDATE drive_shards SET status='cloud_verified', last_error=NULL
                        WHERE shard_id=?
                        """,
                        (row["shard_id"],),
                    )
                    self.connection.commit()
                    counts["confirmed"] += 1
                except Exception as exc:
                    self.connection.execute(
                        "UPDATE drive_shards SET last_error=? WHERE shard_id=?",
                        (f"cloud_check_failed: {str(exc)[:900]}", row["shard_id"]),
                    )
                    self.connection.commit()
                    counts["waiting"] += 1
                continue
            if not remote_path.exists():
                counts["missing"] += 1
                continue
            if self.cloud_item_id(remote_path):
                self.connection.execute(
                    """
                    UPDATE drive_shards SET status='cloud_verified', last_error=NULL
                    WHERE shard_id=?
                    """,
                    (row["shard_id"],),
                )
                self.connection.commit()
                counts["confirmed"] += 1
            else:
                counts["waiting"] += 1
        return counts

    def requeue_stalled(
        self,
        min_age_minutes: float,
        max_shards: int | None = None,
        control_chunk_mib: float = 64.0,
    ) -> dict[str, int]:
        """Requeue DriveFS uploads that never received a cloud item ID.

        Every original member is revalidated before generated shard copies are
        removed. A cloud item ID is checked again immediately before removal so
        a completed upload is never requeued deliberately.
        """
        counts = {
            "requeued": 0,
            "files": 0,
            "bytes": 0,
            "not_stale": 0,
            "cloud_ready": 0,
            "control_parts": 0,
            "errors": 0,
        }
        cutoff = datetime.now(JST).timestamp() - max(min_age_minutes, 0.0) * 60.0
        for row in self.shard_rows(["verified"]):
            if max_shards is not None and counts["requeued"] >= max_shards:
                break
            verified_at = str(row["verified_at"] or "")
            try:
                verified_timestamp = datetime.fromisoformat(verified_at).timestamp()
            except ValueError:
                verified_timestamp = 0.0
            if verified_timestamp > cutoff:
                counts["not_stale"] += 1
                continue

            if self.rclone_remote:
                try:
                    if self.cloud_metadata_matches(row):
                        self.connection.execute(
                            """
                            UPDATE drive_shards SET status='cloud_verified', last_error=NULL
                            WHERE shard_id=?
                            """,
                            (row["shard_id"],),
                        )
                        self.connection.commit()
                        counts["cloud_ready"] += 1
                        continue
                    local_shard = Path(str(row["local_path"]))
                    if local_shard.is_file():
                        local_sha, local_md5, local_size = file_hashes(local_shard)
                        if (
                            local_sha != str(row["sha256"])
                            or local_md5 != str(row["md5"])
                            or local_size != int(row["byte_size"])
                        ):
                            raise RuntimeError("stalled local shard hash mismatch")
                        self.connection.execute(
                            """
                            UPDATE drive_shards
                            SET status='packed', uploaded_at=NULL, verified_at=NULL,
                                last_error='retry_via_rclone'
                            WHERE shard_id=?
                            """,
                            (row["shard_id"],),
                        )
                        self.connection.commit()
                        counts["requeued"] += 1
                        counts["bytes"] += int(row["byte_size"])
                        continue
                    # Fall through to the original-preserving rebuild path when
                    # a previous DriveFS attempt no longer has a staging shard.
                except Exception as exc:
                    self.connection.execute(
                        "UPDATE drive_shards SET last_error=? WHERE shard_id=?",
                        (f"rclone_requeue_failed: {str(exc)[:900]}", row["shard_id"]),
                    )
                    self.connection.commit()
                    counts["errors"] += 1
                    continue

            remote_path = self.drive_root / str(row["remote_relative_path"])
            if remote_path.exists() and self.cloud_item_id(remote_path):
                counts["cloud_ready"] += 1
                continue

            members = list(
                self.connection.execute(
                    "SELECT * FROM drive_shard_members WHERE shard_id=?",
                    (row["shard_id"],),
                )
            )
            try:
                if not members:
                    if int(row["payload_type"]) != 0:
                        raise RuntimeError("stalled payload shard has no members")
                    filename = str(row["filename"])
                    if filename.endswith((".chunk", ".parts_manifest.json")):
                        local_shard = Path(str(row["local_path"]))
                        ensure_within(local_shard, self.staging_root)
                        if not local_shard.is_file():
                            raise RuntimeError(f"missing control part: {local_shard}")
                        part_sha, part_md5, part_size = file_hashes(local_shard)
                        if (
                            part_sha != str(row["sha256"])
                            or part_md5 != str(row["md5"])
                            or part_size != int(row["byte_size"])
                        ):
                            raise RuntimeError("control part hash mismatch")
                        if remote_path.exists() and self.cloud_item_id(remote_path):
                            counts["cloud_ready"] += 1
                            continue
                        ensure_within(remote_path, self.drive_root)
                        remote_path.unlink(missing_ok=True)
                        self.connection.execute(
                            """
                            UPDATE drive_shards
                            SET status='packed', uploaded_at=NULL, verified_at=NULL,
                                last_error='retry_after_drivefs_restart'
                            WHERE shard_id=?
                            """,
                            (row["shard_id"],),
                        )
                        self.connection.commit()
                        counts["requeued"] += 1
                        counts["bytes"] += int(row["byte_size"])
                        continue
                    split_result = self.split_stalled_control_shard(
                        row,
                        max(1, int(control_chunk_mib * 1024**2)),
                    )
                    if not split_result:
                        counts["cloud_ready"] += 1
                        continue
                    counts["requeued"] += 1
                    counts["bytes"] += int(row["byte_size"])
                    counts["control_parts"] += int(split_result["parts"])
                    print(
                        f"requeue_control parts={split_result['parts']} "
                        f"gib={int(row['byte_size']) / 1024**3:.2f}",
                        flush=True,
                    )
                    continue
                for member in members:
                    original = Path(str(member["original_path"]))
                    ensure_within(original, self.archive_root / "documents")
                    if not original.is_file():
                        raise RuntimeError(f"missing original: {original}")
                    if original.stat().st_size != int(member["byte_size"]):
                        raise RuntimeError(f"original size mismatch: {original}")
                    if sha256_file(original) != str(member["sha256"]):
                        raise RuntimeError(f"original hash mismatch: {original}")

                # Recheck after hashing because DriveFS may have completed meanwhile.
                if remote_path.exists() and self.cloud_item_id(remote_path):
                    counts["cloud_ready"] += 1
                    continue
                ensure_within(remote_path, self.drive_root)
                remote_path.unlink(missing_ok=True)

                local_shard = Path(str(row["local_path"]))
                if local_shard.exists():
                    ensure_within(local_shard, self.staging_root)
                    local_shard.unlink()
                with self.connection:
                    self.connection.execute(
                        "DELETE FROM drive_shard_members WHERE shard_id=?",
                        (row["shard_id"],),
                    )
                    self.connection.execute(
                        """
                        UPDATE drive_shards
                        SET status='superseded', local_path=NULL,
                            last_error='requeued_after_drivefs_timeout'
                        WHERE shard_id=?
                        """,
                        (row["shard_id"],),
                    )
                counts["requeued"] += 1
                counts["files"] += len(members)
                counts["bytes"] += int(row["byte_size"])
                print(
                    f"requeue_progress shards={counts['requeued']} "
                    f"files={counts['files']} gib={counts['bytes'] / 1024**3:.2f}",
                    flush=True,
                )
            except Exception as exc:
                self.connection.execute(
                    "UPDATE drive_shards SET last_error=? WHERE shard_id=?",
                    (f"requeue_failed: {str(exc)[:900]}", row["shard_id"]),
                )
                self.connection.commit()
                counts["errors"] += 1
        return counts

    def split_stalled_control_shard(
        self,
        row: sqlite3.Row,
        chunk_bytes: int,
    ) -> dict[str, int] | None:
        """Split a stalled control tar into independently uploadable chunks."""
        local_shard = Path(str(row["local_path"]))
        ensure_within(local_shard, self.staging_root)
        if not local_shard.is_file():
            raise RuntimeError(f"missing control snapshot: {local_shard}")
        sha256, md5, size = file_hashes(local_shard)
        if (
            sha256 != str(row["sha256"])
            or md5 != str(row["md5"])
            or size != int(row["byte_size"])
        ):
            raise RuntimeError("control snapshot hash mismatch")

        remote_path = self.drive_root / str(row["remote_relative_path"])
        if remote_path.exists() and self.cloud_item_id(remote_path):
            return None

        generated: list[dict[str, Any]] = []
        stem = str(row["filename"])
        with local_shard.open("rb") as source:
            index = 0
            while True:
                block = source.read(chunk_bytes)
                if not block:
                    break
                index += 1
                digest = hashlib.sha256(block).hexdigest()
                chunk_name = f"{stem}.part{index:04d}_{digest[:12]}.chunk"
                chunk_path = self.staging_root / chunk_name
                temporary = chunk_path.with_suffix(chunk_path.suffix + ".part")
                temporary.unlink(missing_ok=True)
                temporary.write_bytes(block)
                temporary.replace(chunk_path)
                chunk_sha, chunk_md5, chunk_size = file_hashes(chunk_path)
                generated.append(
                    {
                        "filename": chunk_name,
                        "path": chunk_path,
                        "sha256": chunk_sha,
                        "md5": chunk_md5,
                        "bytes": chunk_size,
                        "order": index,
                    }
                )

        manifest_payload = {
            "format": "edinet-control-snapshot-parts-v1",
            "original_filename": row["filename"],
            "original_sha256": row["sha256"],
            "original_md5": row["md5"],
            "original_bytes": int(row["byte_size"]),
            "parts": [
                {
                    "order": item["order"],
                    "filename": item["filename"],
                    "byte_size": item["bytes"],
                    "sha256": item["sha256"],
                    "md5": item["md5"],
                }
                for item in generated
            ],
        }
        manifest_name = f"{stem}.parts_manifest.json"
        manifest_path = self.staging_root / manifest_name
        manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_sha, manifest_md5, manifest_size = file_hashes(manifest_path)
        generated.append(
            {
                "filename": manifest_name,
                "path": manifest_path,
                "sha256": manifest_sha,
                "md5": manifest_md5,
                "bytes": manifest_size,
                "order": len(generated) + 1,
            }
        )

        # DriveFS may finish while the local split is being built.
        if remote_path.exists() and self.cloud_item_id(remote_path):
            for item in generated:
                Path(item["path"]).unlink(missing_ok=True)
            return None
        ensure_within(remote_path, self.drive_root)
        remote_path.unlink(missing_ok=True)

        remote_parent = Path(str(row["remote_relative_path"])).parent / f"{stem}.parts"
        part_number = self.next_part_number(0, str(row["submit_month"]))
        with self.connection:
            for offset, item in enumerate(generated):
                self.connection.execute(
                    """
                    INSERT INTO drive_shards(
                        shard_id, payload_type, submit_month, part_number, filename,
                        local_path, remote_relative_path, status, file_count,
                        byte_size, sha256, md5, created_at
                    ) VALUES (?, 0, ?, ?, ?, ?, ?, 'packed', 0, ?, ?, ?, ?)
                    """,
                    (
                        hashlib.sha256(
                            (
                                str(row["shard_id"])
                                + ":"
                                + str(item["filename"])
                            ).encode("utf-8")
                        ).hexdigest(),
                        row["submit_month"],
                        part_number + offset,
                        item["filename"],
                        str(item["path"]),
                        str(remote_parent / str(item["filename"])),
                        item["bytes"],
                        item["sha256"],
                        item["md5"],
                        now_iso(),
                    ),
                )
            self.connection.execute(
                """
                UPDATE drive_shards
                SET status='superseded', local_path=NULL,
                    last_error='split_after_drivefs_timeout'
                WHERE shard_id=?
                """,
                (row["shard_id"],),
            )
        local_shard.unlink(missing_ok=True)
        return {"parts": len(generated), "bytes": size}

    def release(self, max_shards: int | None = None) -> dict[str, int]:
        counts = {"shards": 0, "files": 0, "bytes": 0}
        for row in self.shard_rows(["cloud_verified"]):
            if max_shards is not None and counts["shards"] >= max_shards:
                break
            members = list(
                self.connection.execute(
                    "SELECT * FROM drive_shard_members WHERE shard_id=?",
                    (row["shard_id"],),
                )
            )
            with self.connection:
                for member in members:
                    original = Path(str(member["original_path"]))
                    ensure_within(original, self.archive_root / "documents")
                    if original.exists():
                        original.unlink()
                    remote_uri = (
                        f"gdrive:{row['remote_relative_path']}#{member['archive_path']}"
                    )
                    self.connection.execute(
                        """
                        UPDATE payloads SET path=?, source='google_drive_shard'
                        WHERE doc_id=? AND payload_type=?
                        """,
                        (remote_uri, member["doc_id"], member["payload_type"]),
                    )
                    counts["files"] += 1
                    counts["bytes"] += int(member["byte_size"])
                local_shard = Path(str(row["local_path"]))
                ensure_within(local_shard, self.staging_root)
                local_shard.unlink(missing_ok=True)
                self.connection.execute(
                    """
                    UPDATE drive_shards SET status='released', released_at=?, local_path=NULL
                    WHERE shard_id=?
                    """,
                    (now_iso(), row["shard_id"]),
                )
            counts["shards"] += 1
        return counts

    def audit(self, output: Path) -> dict[str, Any]:
        scalar = lambda sql: self.connection.execute(sql).fetchone()[0]
        summary = {
            "generated_at": now_iso(),
            "drive_root": str(self.drive_root),
            "shards": scalar("SELECT COUNT(*) FROM drive_shards"),
            "verified_or_released": scalar(
                "SELECT COUNT(*) FROM drive_shards "
                "WHERE status IN ('verified','cloud_verified','released')"
            ),
            "remote_bytes": scalar(
                "SELECT COALESCE(SUM(byte_size),0) FROM drive_shards "
                "WHERE status IN ('uploaded','verified','cloud_verified','released')"
            ),
            "remote_members": scalar("SELECT COUNT(*) FROM drive_shard_members"),
            "payload_pending": scalar(
                "SELECT COUNT(*) FROM payloads WHERE status NOT IN ('ok','unavailable')"
            ),
            "payload_on_drive": scalar(
                "SELECT COUNT(*) FROM payloads WHERE source='google_drive_shard'"
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shard and verify EDINET originals on Google Drive")
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--drive-root", type=Path, default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--rclone-remote")
    parser.add_argument("--rclone-binary", type=Path, default=DEFAULT_RCLONE_BINARY)
    parser.add_argument("--rclone-workers", type=int, default=4)
    parser.add_argument("--rclone-chunk-size", default=DEFAULT_RCLONE_CHUNK_SIZE)
    parser.add_argument("--rclone-retries", type=int, default=DEFAULT_RCLONE_RETRIES)
    parser.add_argument(
        "--rclone-low-level-retries",
        type=int,
        default=DEFAULT_RCLONE_LOW_LEVEL_RETRIES,
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--interval", type=float, default=0.25)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    pack = sub.add_parser("pack")
    pack.add_argument("--types", default="all")
    pack.add_argument("--target-gib", type=float, default=8.0)
    pack.add_argument("--max-files", type=int, default=10000)
    pack.add_argument("--max-shards", type=int)
    sub.add_parser("pack-control")
    upload = sub.add_parser("upload")
    upload.add_argument("--max-shards", type=int)
    verify = sub.add_parser("verify")
    verify.add_argument("--max-shards", type=int)
    confirm = sub.add_parser("confirm-cloud")
    confirm.add_argument("--max-shards", type=int)
    requeue = sub.add_parser("requeue-stalled")
    requeue.add_argument("--min-age-minutes", type=float, default=120.0)
    requeue.add_argument("--max-shards", type=int)
    requeue.add_argument("--control-chunk-mib", type=float, default=64.0)
    release = sub.add_parser("release")
    release.add_argument("--max-shards", type=int)
    download = sub.add_parser("download-batch")
    download.add_argument("--types", required=True)
    download.add_argument("--max-files", type=int, default=5000)
    download.add_argument("--reserve-gib", type=float, default=80.0)
    audit = sub.add_parser("audit")
    audit.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent
        / "outputs"
        / "edinet_full_archive"
        / "drive_archive_audit.json",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    archive_root = args.archive_root.resolve()
    database = ArchiveDatabase(ArchivePaths(archive_root).database)
    drive = DriveArchive(
        database,
        archive_root,
        args.staging_root.resolve(),
        args.drive_root.resolve(),
        args.rclone_remote,
        args.rclone_binary,
        args.rclone_workers,
        args.rclone_chunk_size,
        args.rclone_retries,
        args.rclone_low_level_retries,
    )
    try:
        if args.command == "init":
            drive.validate_drive()
            result: dict[str, Any] = {"drive_root": str(drive.drive_root), "status": "ready"}
        elif args.command == "pack":
            result = drive.pack_available(
                parse_payload_types(args.types),
                args.target_gib,
                args.max_files,
                args.max_shards,
            )
        elif args.command == "pack-control":
            result = drive.pack_control_snapshot()
        elif args.command == "upload":
            result = drive.upload(args.max_shards)
        elif args.command == "verify":
            result = drive.verify(args.max_shards)
        elif args.command == "confirm-cloud":
            result = drive.confirm_cloud(args.max_shards)
        elif args.command == "requeue-stalled":
            result = drive.requeue_stalled(
                args.min_age_minutes,
                args.max_shards,
                args.control_chunk_mib,
            )
        elif args.command == "release":
            result = drive.release(args.max_shards)
        elif args.command == "download-batch":
            key = load_api_key(args.env_file)
            client = EdinetClient(key, args.interval)
            result = download_payloads(
                database,
                ArchivePaths(archive_root),
                client,
                parse_payload_types(args.types),
                args.max_files,
                args.reserve_gib,
            )
        elif args.command == "audit":
            result = drive.audit(args.output.resolve())
        else:
            raise AssertionError(args.command)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()
