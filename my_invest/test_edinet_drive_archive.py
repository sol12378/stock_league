import hashlib
import sqlite3
import tarfile
from pathlib import Path
from types import SimpleNamespace

from edinet_drive_archive import DriveArchive, file_hashes
from edinet_full_archive import API_BASE, ArchiveDatabase


def insert_payload(database: ArchiveDatabase, path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    database.connection.execute(
        """
        INSERT INTO documents(
            doc_id, list_date, doc_type_code, submit_datetime,
            raw_record_json, first_seen_at, last_seen_at
        ) VALUES ('S100TEST', '2025-06-30', '120', '2025-06-30 12:00', '{}', 'x', 'x')
        """
    )
    database.connection.execute(
        """
        INSERT INTO payloads(
            doc_id, payload_type, path, endpoint, status,
            byte_size, sha256, acquired_at, source
        ) VALUES ('S100TEST', 1, ?, ?, 'ok', ?, ?, 'x', 'api')
        """,
        (str(path), f"{API_BASE}/documents/S100TEST?type=1", len(content), digest),
    )
    database.connection.commit()


def test_pack_upload_verify_release(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    source = archive_root / "documents" / "S100" / "S100TEST" / "type1.zip"
    insert_content = b"original-edinet-bytes"
    database = ArchiveDatabase(archive_root / "manifest" / "archive.sqlite3")
    insert_payload(database, source, insert_content)
    drive_root = (
        tmp_path
        / "GoogleDrive-dorankunsan8@gmail.com"
        / "MyDrive"
        / "EDINET_2X_RESEARCH"
    )
    (drive_root / "00_control").mkdir(parents=True)
    drive = DriveArchive(database, archive_root, tmp_path / "staging", drive_root)

    packed = drive.pack_available({1}, target_gib=0.001, max_files=10, max_shards=1)
    assert packed["files"] == 1
    shard = database.connection.execute("SELECT * FROM drive_shards").fetchone()
    with tarfile.open(shard["local_path"], "r") as archive:
        assert archive.extractfile("payloads/S100TEST/type1.zip").read() == insert_content

    assert drive.upload() == {"uploaded": 1, "existing": 0, "errors": 0}
    assert drive.verify() == {"verified": 1, "errors": 0}
    database.connection.execute("UPDATE drive_shards SET status='cloud_verified'")
    database.connection.commit()
    released = drive.release()
    assert released["files"] == 1
    assert not source.exists()
    payload = database.connection.execute(
        "SELECT path, source, sha256 FROM payloads WHERE doc_id='S100TEST' AND payload_type=1"
    ).fetchone()
    assert payload["path"].startswith("gdrive:")
    assert payload["source"] == "google_drive_shard"
    assert payload["sha256"] == hashlib.sha256(insert_content).hexdigest()
    database.close()


def test_requeue_stalled_preserves_original_and_removes_generated_copies(
    tmp_path: Path,
) -> None:
    archive_root = tmp_path / "archive"
    source = archive_root / "documents" / "S100" / "S100TEST" / "type1.zip"
    insert_content = b"original-edinet-bytes"
    database = ArchiveDatabase(archive_root / "manifest" / "archive.sqlite3")
    insert_payload(database, source, insert_content)
    drive_root = (
        tmp_path
        / "GoogleDrive-dorankunsan8@gmail.com"
        / "MyDrive"
        / "EDINET_2X_RESEARCH"
    )
    (drive_root / "00_control").mkdir(parents=True)
    staging_root = tmp_path / "staging"
    drive = DriveArchive(database, archive_root, staging_root, drive_root)

    drive.pack_available({1}, target_gib=0.001, max_files=10, max_shards=1)
    drive.upload()
    drive.verify()
    shard = database.connection.execute("SELECT * FROM drive_shards").fetchone()
    local_shard = Path(shard["local_path"])
    remote_shard = drive_root / shard["remote_relative_path"]

    result = drive.requeue_stalled(min_age_minutes=0)

    assert result["requeued"] == 1
    assert result["files"] == 1
    assert source.read_bytes() == insert_content
    assert not local_shard.exists()
    assert not remote_shard.exists()
    status = database.connection.execute(
        "SELECT status FROM drive_shards WHERE shard_id=?", (shard["shard_id"],)
    ).fetchone()[0]
    assert status == "superseded"
    assert database.connection.execute(
        "SELECT COUNT(*) FROM drive_shard_members"
    ).fetchone()[0] == 0
    database.close()


def test_stalled_control_snapshot_is_split_and_each_part_verifies(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    database = ArchiveDatabase(archive_root / "manifest" / "archive.sqlite3")
    staging_root = tmp_path / "staging"
    staging_root.mkdir(parents=True)
    drive_root = (
        tmp_path
        / "GoogleDrive-dorankunsan8@gmail.com"
        / "MyDrive"
        / "EDINET_2X_RESEARCH"
    )
    (drive_root / "00_control").mkdir(parents=True)
    drive = DriveArchive(database, archive_root, staging_root, drive_root)

    local = staging_root / "control.tar"
    local.write_bytes(b"0123456789" * 3)
    sha256, md5, size = file_hashes(local)
    relative = Path("10_bronze/control_snapshots/control.tar")
    remote = drive_root / relative
    remote.parent.mkdir(parents=True)
    remote.write_bytes(local.read_bytes())
    database.connection.execute(
        """
        INSERT INTO drive_shards(
            shard_id, payload_type, submit_month, part_number, filename,
            local_path, remote_relative_path, status, file_count,
            byte_size, sha256, md5, created_at, uploaded_at, verified_at
        ) VALUES (?, 0, 'snapshot', 1, 'control.tar', ?, ?, 'verified', 0,
                  ?, ?, ?, 'x', 'x', '2000-01-01T00:00:00+00:00')
        """,
        (sha256, str(local), str(relative), size, sha256, md5),
    )
    database.connection.commit()

    result = drive.requeue_stalled(
        min_age_minutes=0,
        control_chunk_mib=10 / 1024**2,
    )

    assert result["requeued"] == 1, (
        result,
        database.connection.execute(
            "SELECT last_error FROM drive_shards WHERE shard_id=?", (sha256,)
        ).fetchone()[0],
    )
    assert result["control_parts"] == 4  # Three chunks plus reassembly manifest.
    assert not local.exists()
    assert not remote.exists()
    assert database.connection.execute(
        "SELECT status FROM drive_shards WHERE shard_id=?", (sha256,)
    ).fetchone()[0] == "superseded"
    assert database.connection.execute(
        "SELECT COUNT(*) FROM drive_shards WHERE status='packed'"
    ).fetchone()[0] == 4
    assert drive.upload()["uploaded"] == 4
    assert drive.verify()["verified"] == 4
    retry = drive.requeue_stalled(min_age_minutes=0)
    assert retry["requeued"] == 4
    assert retry["control_parts"] == 0
    assert database.connection.execute(
        "SELECT COUNT(*) FROM drive_shards"
    ).fetchone()[0] == 5
    assert database.connection.execute(
        "SELECT COUNT(*) FROM drive_shards WHERE status='packed'"
    ).fetchone()[0] == 4
    database.close()


def test_rclone_upload_requires_cloud_md5_before_release(
    tmp_path: Path,
    monkeypatch,
) -> None:
    archive_root = tmp_path / "archive"
    source = archive_root / "documents" / "S100" / "S100TEST" / "type1.zip"
    insert_content = b"original-edinet-bytes-for-rclone"
    database = ArchiveDatabase(archive_root / "manifest" / "archive.sqlite3")
    insert_payload(database, source, insert_content)
    drive = DriveArchive(
        database,
        archive_root,
        tmp_path / "staging",
        tmp_path / "unused-drivefs",
        rclone_remote="edinet_drive:",
        rclone_binary=Path("/usr/bin/true"),
    )
    drive.pack_available({1}, target_gib=0.001, max_files=10, max_shards=1)
    shard = database.connection.execute("SELECT * FROM drive_shards").fetchone()
    cloud = {"exists": False}

    def fake_metadata(relative_path: str):
        assert relative_path == shard["remote_relative_path"]
        if not cloud["exists"]:
            return None
        return {"Size": shard["byte_size"], "Hashes": {"MD5": shard["md5"]}}

    rclone_calls = []

    def fake_run(arguments, **kwargs):
        rclone_calls.append(arguments)
        assert arguments[0] == "copyto"
        assert arguments[2] == "edinet_drive:" + shard["remote_relative_path"]
        cloud["exists"] = True
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(drive, "rclone_metadata", fake_metadata)
    monkeypatch.setattr(drive, "run_rclone", fake_run)

    assert drive.upload() == {"uploaded": 1, "existing": 0, "errors": 0}
    upload_arguments = rclone_calls[0]
    assert upload_arguments[upload_arguments.index("--drive-chunk-size") + 1] == "32M"
    assert upload_arguments[upload_arguments.index("--retries") + 1] == "5"
    assert upload_arguments[upload_arguments.index("--low-level-retries") + 1] == "10"
    assert source.exists(), "original must remain before cloud verification"
    assert drive.verify() == {"verified": 1, "errors": 0}
    assert drive.confirm_cloud() == {"confirmed": 1, "waiting": 0, "missing": 0}
    assert drive.release()["files"] == 1
    assert not source.exists()
    database.close()
