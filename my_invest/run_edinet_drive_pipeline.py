from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import sqlite3
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from edinet_drive_archive import (
    DEFAULT_DRIVE_ROOT,
    DEFAULT_RCLONE_BINARY,
    DEFAULT_RCLONE_CHUNK_SIZE,
    DEFAULT_RCLONE_LOW_LEVEL_RETRIES,
    DEFAULT_RCLONE_RETRIES,
    DEFAULT_STAGING_ROOT,
    DriveArchive,
)
from edinet_full_archive import (
    ArchiveDatabase,
    ArchivePaths,
    DEFAULT_ARCHIVE_ROOT,
    DEFAULT_ENV_FILE,
    EdinetClient,
    download_payloads,
    is_sqlite_busy_error,
    load_api_key,
)


TYPE_PRIORITY = [4, 5, 1, 3, 2]
DRIVE_REJECTION_ALERT_FILE = "drive_rejection_alert.json"
PIPELINE_HEALTH_FILE = "pipeline_health.json"
PIPELINE_INCIDENT_FILE = "pipeline_incidents.jsonl"
INCIDENT_LOCK = threading.Lock()


def classify_pipeline_error(exc: BaseException) -> dict[str, object]:
    message = str(exc)
    if is_sqlite_busy_error(exc):
        return {
            "category": "sqlite_write_contention",
            "cause": "concurrent downloader and Drive database writers",
            "action": "rollback_backoff_retry",
            "retryable": True,
        }
    if is_drive_rejection(message):
        return {
            "category": "drive_auth_rejection",
            "cause": "Google Drive rejected OAuth authentication or permission",
            "action": "notify_user_and_preserve_local_originals",
            "retryable": False,
        }
    lowered = message.lower()
    if "no space left" in lowered or "free space fell below" in lowered:
        return {
            "category": "disk_capacity",
            "cause": "local free space is below the safety reserve",
            "action": "pause_downloads_while_drive_drains",
            "retryable": True,
        }
    if any(token in lowered for token in ("timeout", "connection reset", "temporarily unavailable")):
        return {
            "category": "transient_network",
            "cause": "temporary API or network failure",
            "action": "bounded_backoff_retry",
            "retryable": True,
        }
    if "made no progress" in lowered:
        return {
            "category": "edinet_no_progress",
            "cause": "a complete EDINET batch returned no successful payloads",
            "action": "record_diagnostics_and_launchd_restart",
            "retryable": True,
        }
    return {
        "category": "unknown",
        "cause": "unclassified pipeline exception",
        "action": "record_diagnostics_and_launchd_restart",
        "retryable": False,
    }


def record_pipeline_health(
    archive_root: Path,
    *,
    source: str,
    classification: dict[str, object],
    recovered: bool,
    attempt: int,
) -> None:
    """Persist sanitized diagnostics; never write raw provider errors."""
    manifest = archive_root / "manifest"
    manifest.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source,
        **classification,
        "recovered": recovered,
        "attempt": attempt,
    }
    health = {
        "status": "healthy" if recovered else "recovering",
        "updated_at": event["timestamp"],
        "last_event": event,
    }
    health_path = manifest / PIPELINE_HEALTH_FILE
    incident_path = manifest / PIPELINE_INCIDENT_FILE
    with INCIDENT_LOCK:
        try:
            temporary = health_path.with_suffix(health_path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(health, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(0o600)
            temporary.replace(health_path)
            with incident_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            incident_path.chmod(0o600)
        except OSError:
            print(
                "pipeline_health_record_failed "
                + json.dumps(
                    {"source": source, "category": classification.get("category")},
                    ensure_ascii=False,
                ),
                flush=True,
            )


def run_with_auto_recovery(
    operation,
    *,
    database: ArchiveDatabase,
    archive_root: Path,
    source: str,
    attempts: int = 8,
):
    for attempt in range(1, attempts + 1):
        try:
            result = operation()
            if attempt > 1:
                record_pipeline_health(
                    archive_root,
                    source=source,
                    classification=classify_pipeline_error(
                        sqlite3.OperationalError("database is locked")
                    ),
                    recovered=True,
                    attempt=attempt,
                )
            return result
        except sqlite3.OperationalError as exc:
            if not is_sqlite_busy_error(exc) or attempt == attempts:
                raise
            database.connection.rollback()
            classification = classify_pipeline_error(exc)
            record_pipeline_health(
                archive_root,
                source=source,
                classification=classification,
                recovered=False,
                attempt=attempt,
            )
            delay = min(0.25 * (2 ** (attempt - 1)), 10.0)
            print(
                "pipeline_auto_recovery "
                + json.dumps(
                    {
                        "source": source,
                        **classification,
                        "attempt": attempt,
                        "delay_seconds": delay,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            time.sleep(delay)


def is_drive_rejection(error: str) -> bool:
    """Return true only for an actual Drive authentication/permission rejection."""
    message = error.lower()
    explicit_markers = (
        "invalid_client",
        "unauthorized_client",
        "invalid_grant",
        "access_denied",
        "oauth2: cannot fetch token",
        "token has been expired or revoked",
        "token has been revoked",
        "credentials are invalid",
        "insufficient authentication scopes",
        "client is unauthorized",
        "client_id is disabled",
    )
    if any(marker in message for marker in explicit_markers):
        return True

    authentication_context = (
        "googleapi" in message
        or "oauth" in message
        or "authentication" in message
        or "authorization" in message
    )
    if "401" in message and authentication_context:
        return True
    permission_markers = (
        "permission denied",
        "access denied",
        "forbidden",
        "insufficient permission",
        "not authorized",
    )
    return (
        "403" in message
        and authentication_context
        and any(marker in message for marker in permission_markers)
    )


def rejection_alert_path(drive: DriveArchive) -> Path:
    return drive.archive_root / "manifest" / DRIVE_REJECTION_ALERT_FILE


def notify_drive_rejection(drive: DriveArchive, error: str) -> bool:
    """Persist and show one native alert per uninterrupted rejection incident."""
    if not is_drive_rejection(error):
        return False

    state_path = rejection_alert_path(drive)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        state = {}
    if state.get("active") is True and state.get("notified") is True:
        return False

    # Never persist or display the provider's raw error because it may contain
    # OAuth details. The digest is sufficient for diagnostics and deduplication.
    state = {
        "active": True,
        "notified": False,
        "error_sha256": hashlib.sha256(error.encode("utf-8")).hexdigest(),
        "message": "Google Drive authentication or permission rejection",
    }
    temporary = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(state_path)

    script = (
        'display notification "Google DriveがEDINET同期を拒否しました。'
        'Codexで詳細を確認してください。" with title "EDINET Google Drive同期" '
        'sound name "Basso"'
    )
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        notified = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        notified = False
    state["notified"] = notified
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(state_path)
    print(
        "drive_rejection_alert "
        + json.dumps(
            {
                "notified": notified,
                "state_file": str(state_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return True


def clear_drive_rejection_alert(drive: DriveArchive) -> None:
    """Re-arm the alert after a later Drive request succeeds."""
    state_path = rejection_alert_path(drive)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return
    if state.get("active") is not True:
        return
    state["active"] = False
    temporary = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(state_path)


def find_drive_rejection(
    drive: DriveArchive,
    statuses: tuple[str, ...],
) -> str | None:
    placeholders = ",".join("?" for _ in statuses)
    rows = drive.database.connection.execute(
        f"""
        SELECT last_error FROM drive_shards
        WHERE status IN ({placeholders}) AND last_error IS NOT NULL
        ORDER BY rowid DESC LIMIT 100
        """,
        statuses,
    )
    for row in rows:
        error = str(row[0])
        if is_drive_rejection(error):
            return error
    return None


def scalar(database: ArchiveDatabase, sql: str, params: tuple = ()) -> int:
    return int(database.connection.execute(sql, params).fetchone()[0])


def cloud_tick(drive: DriveArchive) -> int:
    cloud = drive.confirm_cloud()
    cloud_rejection = None
    if int(cloud["waiting"]):
        cloud_rejection = find_drive_rejection(drive, ("verified",))
    if cloud_rejection:
        notify_drive_rejection(drive, cloud_rejection)
    elif int(cloud["confirmed"]):
        clear_drive_rejection_alert(drive)
    released = drive.release()
    waiting = scalar(
        drive.database,
        "SELECT COUNT(*) FROM drive_shards WHERE status IN ('uploaded','verified')",
    )
    print(
        "cloud_progress "
        + json.dumps(
            {"cloud": cloud, "released": released, "waiting_shards": waiting},
            ensure_ascii=False,
        ),
        flush=True,
    )
    return waiting


def service_drive(drive: DriveArchive, args: argparse.Namespace) -> dict[str, object]:
    # Confirm completed uploads first so they can never be requeued as stale.
    cloud_before = cloud_tick(drive)
    requeue = drive.requeue_stalled(args.requeue_stalled_minutes)
    pack = {"shards": 0, "files": 0, "bytes": 0}
    upload = {"uploaded": 0, "existing": 0, "errors": 0}
    verify = {"verified": 0, "errors": 0}
    # Drain already-packed shards first. Packing can be CPU/SQLite intensive,
    # so creating more shards while an upload backlog exists only delays the
    # cloud transfer and consumes additional local disk.
    while True:
        upload_backlog = scalar(
            drive.database,
            "SELECT COUNT(*) FROM drive_shards WHERE status IN ('packed','upload_error')",
        )
        if upload_backlog:
            packed = {"shards": 0, "files": 0, "bytes": 0}
        else:
            packed = drive.pack_available(
                None,
                args.target_gib,
                args.max_files_per_shard,
                10,
            )
        uploaded = drive.upload(10)
        upload_rejection = None
        if int(uploaded["errors"]):
            upload_rejection = find_drive_rejection(drive, ("upload_error",))
        if upload_rejection:
            notify_drive_rejection(drive, upload_rejection)
        elif int(uploaded["uploaded"]) + int(uploaded["existing"]):
            clear_drive_rejection_alert(drive)
        verified = drive.verify(10)
        for key in pack:
            pack[key] += int(packed[key])
        for key in upload:
            upload[key] += int(uploaded[key])
        for key in verify:
            verify[key] += int(verified[key])
        cloud_tick(drive)
        made_progress = (
            int(packed["shards"])
            + int(uploaded["uploaded"])
            + int(uploaded["existing"])
            + int(verified["verified"])
        )
        if made_progress == 0:
            break
    cloud_after = cloud_tick(drive)
    return {
        "cloud_before": cloud_before,
        "requeue": requeue,
        "pack": pack,
        "upload": upload,
        "verify": verify,
        "cloud_after": cloud_after,
    }


def wait_for_cloud(drive: DriveArchive, args: argparse.Namespace) -> None:
    while True:
        result = service_drive(drive, args)
        unsharded = scalar(
            drive.database,
            """
            SELECT COUNT(*) FROM payloads p
            LEFT JOIN drive_shard_members m
              ON m.doc_id=p.doc_id AND m.payload_type=p.payload_type
            WHERE p.status='ok' AND m.doc_id IS NULL
            """,
        )
        if int(result["cloud_after"]) == 0 and unsharded == 0:
            break
        time.sleep(args.poll_seconds)


def pending_for_type(database: ArchiveDatabase, payload_type: int) -> int:
    return scalar(
        database,
        """
        SELECT COUNT(*) FROM payloads
        WHERE payload_type=? AND status NOT IN ('ok','unavailable')
        """,
        (payload_type,),
    )


def drive_is_drained(drive: DriveArchive) -> bool:
    unfinished_shards = scalar(
        drive.database,
        """
        SELECT COUNT(*) FROM drive_shards
        WHERE status IN ('packed','upload_error','uploaded','verify_error','verified')
        """,
    )
    unsharded = scalar(
        drive.database,
        """
        SELECT COUNT(*) FROM payloads p
        LEFT JOIN drive_shard_members m
          ON m.doc_id=p.doc_id AND m.payload_type=p.payload_type
        WHERE p.status='ok' AND m.doc_id IS NULL
        """,
    )
    return unfinished_shards == 0 and unsharded == 0


def make_drive(
    database: ArchiveDatabase,
    archive_root: Path,
    args: argparse.Namespace,
) -> DriveArchive:
    return DriveArchive(
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


def parallel_drive_worker(
    paths: ArchivePaths,
    archive_root: Path,
    args: argparse.Namespace,
    stop_event: threading.Event,
    downloads_done: threading.Event,
    errors: list[BaseException],
) -> None:
    database = ArchiveDatabase(paths.database)
    drive = make_drive(database, archive_root, args)
    consecutive_lock_errors = 0
    try:
        while not stop_event.is_set():
            try:
                service_drive(drive, args)
                if consecutive_lock_errors:
                    record_pipeline_health(
                        archive_root,
                        source="drive_worker",
                        classification=classify_pipeline_error(
                            sqlite3.OperationalError("database is locked")
                        ),
                        recovered=True,
                        attempt=consecutive_lock_errors + 1,
                    )
                    consecutive_lock_errors = 0
            except sqlite3.OperationalError as exc:
                if not is_sqlite_busy_error(exc):
                    raise
                database.connection.rollback()
                consecutive_lock_errors += 1
                classification = classify_pipeline_error(exc)
                record_pipeline_health(
                    archive_root,
                    source="drive_worker",
                    classification=classification,
                    recovered=False,
                    attempt=consecutive_lock_errors,
                )
                delay = min(0.5 * (2 ** (consecutive_lock_errors - 1)), 30.0)
                print(
                    "pipeline_auto_recovery "
                    + json.dumps(
                        {
                            "source": "drive_worker",
                            **classification,
                            "attempt": consecutive_lock_errors,
                            "delay_seconds": delay,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                stop_event.wait(delay)
                continue
            if downloads_done.is_set() and drive_is_drained(drive):
                return
            stop_event.wait(args.poll_seconds)
    except BaseException as exc:
        errors.append(exc)
        stop_event.set()
    finally:
        database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resumable EDINET to Google Drive pipeline")
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--drive-root", type=Path, default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--rclone-remote", default="edinet_drive:")
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
    parser.add_argument("--batch-files", type=int, default=5000)
    parser.add_argument("--target-gib", type=float, default=8.0)
    parser.add_argument("--max-files-per-shard", type=int, default=10000)
    parser.add_argument("--reserve-gib", type=float, default=80.0)
    parser.add_argument("--interval", type=float, default=0.25)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument(
        "--parallel-drive",
        action="store_true",
        help="Upload to Drive concurrently with the single-stream EDINET downloader.",
    )
    parser.add_argument(
        "--requeue-stalled-minutes",
        type=float,
        default=120.0,
        help="Repack verified DriveFS uploads that lack a cloud ID after this age.",
    )
    parser.add_argument(
        "--minimum-free-gib",
        type=float,
        default=180.0,
        help="Pause new downloads below this free-space threshold while Drive catches up.",
    )
    args = parser.parse_args()

    archive_root = args.archive_root.resolve()
    paths = ArchivePaths(archive_root)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    lock_path = paths.database.parent / "drive_pipeline.lock"
    lock_file = lock_path.open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"pipeline_already_running lock={lock_path}", flush=True)
        return

    database = ArchiveDatabase(paths.database)
    drive = make_drive(database, archive_root, args)
    drive.validate_drive()
    # A full quick_check scans this multi-million-row database and delays every
    # launch. Validate the connection and required WAL/foreign-key modes here;
    # operational reads plus SQLite exceptions provide continuous corruption
    # detection without pausing collection at startup.
    database.connection.execute("SELECT 1").fetchone()
    journal_mode = database.connection.execute("PRAGMA journal_mode").fetchone()[0]
    foreign_keys = database.connection.execute("PRAGMA foreign_keys").fetchone()[0]
    if str(journal_mode).lower() != "wal" or int(foreign_keys) != 1:
        raise RuntimeError("SQLite startup mode validation failed")
    record_pipeline_health(
        archive_root,
        source="pipeline_startup",
        classification={
            "category": "startup_validation",
            "cause": "SQLite and Drive configuration checks completed",
            "action": "continue_pipeline",
            "retryable": True,
        },
        recovered=True,
        attempt=1,
    )
    key = load_api_key(args.env_file)
    client = EdinetClient(key, args.interval)
    stop_event = threading.Event()
    downloads_done = threading.Event()
    drive_errors: list[BaseException] = []
    drive_thread: threading.Thread | None = None
    try:
        # Local source bytes are retained until Google Drive independently reports
        # the uploaded object's exact byte size and MD5 checksum.
        cloud_tick(drive)
        if args.parallel_drive:
            drive_thread = threading.Thread(
                target=parallel_drive_worker,
                args=(
                    paths,
                    archive_root,
                    args,
                    stop_event,
                    downloads_done,
                    drive_errors,
                ),
                name="edinet-drive-uploader",
                daemon=True,
            )
            drive_thread.start()
        for payload_type in TYPE_PRIORITY:
            while True:
                # Service every payload type so stalled shards from an earlier
                # priority phase are never stranded while another type downloads.
                if drive_errors:
                    raise RuntimeError("parallel Drive worker stopped") from drive_errors[0]
                drive_result: dict[str, object]
                if args.parallel_drive:
                    drive_result = {"mode": "parallel"}
                else:
                    drive_result = service_drive(drive, args)

                before = pending_for_type(database, payload_type)
                if before == 0:
                    break

                free_gib = shutil.disk_usage(archive_root).free / 1024**3
                if free_gib < args.minimum_free_gib:
                    print(
                        f"buffer_full free_gib={free_gib:.2f} "
                        f"minimum_free_gib={args.minimum_free_gib:.2f}",
                        flush=True,
                    )
                    if args.parallel_drive:
                        while free_gib < args.minimum_free_gib:
                            if drive_errors:
                                raise RuntimeError(
                                    "parallel Drive worker stopped"
                                ) from drive_errors[0]
                            time.sleep(args.poll_seconds)
                            free_gib = shutil.disk_usage(archive_root).free / 1024**3
                    else:
                        wait_for_cloud(drive, args)

                before = pending_for_type(database, payload_type)
                download_result = run_with_auto_recovery(
                    lambda: download_payloads(
                        database,
                        paths,
                        client,
                        {payload_type},
                        args.batch_files,
                        args.reserve_gib,
                    ),
                    database=database,
                    archive_root=archive_root,
                    source="edinet_downloader",
                )
                print(
                    "batch_complete "
                    + json.dumps(
                        {
                            "payload_type": payload_type,
                            "pending_before": before,
                            "download": download_result,
                            "drive": drive_result,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                after = pending_for_type(database, payload_type)
                if after >= before and not download_result.get("ok"):
                    raise RuntimeError(
                        f"payload type {payload_type} made no progress; pending={after}"
                    )
        if args.parallel_drive:
            downloads_done.set()
            while drive_thread is not None and drive_thread.is_alive():
                drive_thread.join(timeout=args.poll_seconds)
                if drive_errors:
                    raise RuntimeError("parallel Drive worker stopped") from drive_errors[0]
        else:
            wait_for_cloud(drive, args)
        result = drive.audit(
            Path(__file__).resolve().parent
            / "outputs"
            / "edinet_full_archive"
            / "drive_archive_audit.json"
        )
        print("pipeline_complete " + json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as exc:
        record_pipeline_health(
            archive_root,
            source="pipeline_main",
            classification=classify_pipeline_error(exc),
            recovered=False,
            attempt=1,
        )
        notify_drive_rejection(drive, str(exc))
        raise
    finally:
        stop_event.set()
        if drive_thread is not None and drive_thread.is_alive():
            drive_thread.join(timeout=5)
        database.close()
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


if __name__ == "__main__":
    main()
