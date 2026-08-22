import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import run_edinet_drive_pipeline as pipeline


def fake_drive(tmp_path: Path):
    return SimpleNamespace(archive_root=tmp_path)


def test_drive_rejection_classifier_is_narrow() -> None:
    assert pipeline.is_drive_rejection("oauth2: invalid_client")
    assert pipeline.is_drive_rejection("oauth2: token has been expired or revoked")
    assert pipeline.is_drive_rejection(
        "googleapi: Error 403: permission denied, forbidden"
    )
    assert not pipeline.is_drive_rejection("dial tcp: DNS lookup timeout")
    assert not pipeline.is_drive_rejection("googleapi: Error 403: rateLimitExceeded")
    assert not pipeline.is_drive_rejection(
        "NOTICE: the shared client_id is being retired later in 2026"
    )


def test_drive_rejection_alert_is_deduplicated_and_rearmed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    drive = fake_drive(tmp_path)
    error = "oauth2: invalid_client"

    assert pipeline.notify_drive_rejection(drive, error)
    assert not pipeline.notify_drive_rejection(drive, error)
    assert len(calls) == 1

    state_path = pipeline.rejection_alert_path(drive)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["active"] is True
    assert error not in state_path.read_text(encoding="utf-8")
    assert state_path.stat().st_mode & 0o777 == 0o600

    pipeline.clear_drive_rejection_alert(drive)
    assert pipeline.notify_drive_rejection(drive, error)
    assert len(calls) == 2


def test_non_rejection_does_not_create_alert(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected")),
    )
    drive = fake_drive(tmp_path)
    assert not pipeline.notify_drive_rejection(drive, "network timeout")
    assert not pipeline.rejection_alert_path(drive).exists()


def test_failed_native_notification_is_retried(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    drive = fake_drive(tmp_path)

    assert pipeline.notify_drive_rejection(drive, "oauth2: invalid_client")
    assert pipeline.notify_drive_rejection(drive, "oauth2: invalid_client")
    assert len(calls) == 2
    state = json.loads(
        pipeline.rejection_alert_path(drive).read_text(encoding="utf-8")
    )
    assert state["active"] is True
    assert state["notified"] is False


def test_sqlite_error_is_classified_and_auto_recovered(
    tmp_path: Path,
    monkeypatch,
) -> None:
    attempts = []
    rollbacks = []
    fake_database = SimpleNamespace(
        connection=SimpleNamespace(rollback=lambda: rollbacks.append(True))
    )

    def operation():
        attempts.append(True)
        if len(attempts) == 1:
            raise sqlite3.OperationalError("database is locked")
        return "recovered"

    monkeypatch.setattr(pipeline.time, "sleep", lambda _: None)
    result = pipeline.run_with_auto_recovery(
        operation,
        database=fake_database,
        archive_root=tmp_path,
        source="test_downloader",
    )

    assert result == "recovered"
    assert len(attempts) == 2
    assert rollbacks == [True]
    health = json.loads(
        (tmp_path / "manifest" / pipeline.PIPELINE_HEALTH_FILE).read_text(
            encoding="utf-8"
        )
    )
    assert health["status"] == "healthy"
    assert health["last_event"]["category"] == "sqlite_write_contention"
    incidents = (
        tmp_path / "manifest" / pipeline.PIPELINE_INCIDENT_FILE
    ).read_text(encoding="utf-8")
    assert "database is locked" not in incidents
    assert len(incidents.splitlines()) == 2
