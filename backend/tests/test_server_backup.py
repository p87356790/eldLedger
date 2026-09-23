import io
import os
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.init_db import seed_standard_data
from app.main import app
from app.models import Organization, User
from app.models.enums import UserRole
from app.schemas.backup import BackupFrequency, BackupScheduleState, BackupScheduleUpdate
from app.security.deps import get_current_user
from app.security.passwords import hash_password
from app.services.chart_template_service import ChartTemplateService
from app.services.server_backup_service import (
    ServerBackupService,
    next_run_at,
    resolve_backup_path,
    schedule_is_due,
)


def _org(db_session: Session) -> Organization:
    organization = db_session.scalar(select(Organization).order_by(Organization.id))
    assert organization is not None
    return organization


def test_daily_schedule_is_due_after_hour() -> None:
    state = BackupScheduleState(enabled=True, frequency=BackupFrequency.DAILY, hour=3)
    now = datetime(2026, 9, 15, 3, 0)
    assert schedule_is_due(state, now)
    assert not schedule_is_due(state, datetime(2026, 9, 15, 2, 59))
    state.last_run_at = datetime(2026, 9, 15, 3, 5)
    assert not schedule_is_due(state, now)
    state.last_run_at = datetime(2026, 9, 14, 3, 0)
    assert schedule_is_due(state, now)


def test_weekly_schedule_runs_on_selected_weekday() -> None:
    state = BackupScheduleState(enabled=True, frequency=BackupFrequency.WEEKLY, weekday=0, hour=3)
    monday = datetime(2026, 9, 14, 3, 0)
    tuesday = datetime(2026, 9, 15, 3, 0)
    assert schedule_is_due(state, monday)
    assert not schedule_is_due(state, tuesday)


def test_monthly_schedule_runs_on_selected_day() -> None:
    state = BackupScheduleState(enabled=True, frequency=BackupFrequency.MONTHLY, monthday=15, hour=3)
    assert schedule_is_due(state, datetime(2026, 9, 15, 3, 0))
    assert not schedule_is_due(state, datetime(2026, 9, 16, 3, 0))


def test_disabled_schedule_is_never_due() -> None:
    state = BackupScheduleState(enabled=False, frequency=BackupFrequency.DAILY, hour=0)
    assert not schedule_is_due(state, datetime(2026, 9, 15, 10, 0))


def test_next_run_is_today_when_catch_up_is_due() -> None:
    state = BackupScheduleState(enabled=True, frequency=BackupFrequency.DAILY, hour=3)
    nxt = next_run_at(state, datetime(2026, 9, 15, 10, 0))
    assert nxt == datetime(2026, 9, 15, 3, 0)


def test_next_run_is_today_before_hour() -> None:
    state = BackupScheduleState(enabled=True, frequency=BackupFrequency.DAILY, hour=3)
    nxt = next_run_at(state, datetime(2026, 9, 15, 2, 0))
    assert nxt == datetime(2026, 9, 15, 3, 0)


def test_next_run_skips_today_after_successful_run() -> None:
    state = BackupScheduleState(
        enabled=True,
        frequency=BackupFrequency.DAILY,
        hour=3,
        last_run_at=datetime(2026, 9, 15, 3, 5),
    )
    nxt = next_run_at(state, datetime(2026, 9, 15, 10, 0))
    assert nxt == datetime(2026, 9, 16, 3, 0)


def test_monthly_schedule_clamps_to_last_day() -> None:
    state = BackupScheduleState(enabled=True, frequency=BackupFrequency.MONTHLY, monthday=31, hour=3)
    assert schedule_is_due(state, datetime(2026, 2, 28, 3, 0))
    assert not schedule_is_due(state, datetime(2026, 2, 27, 3, 0))
    assert schedule_is_due(state, datetime(2026, 3, 31, 3, 0))


def test_create_list_download_and_purge(client: TestClient, db_session: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    database = tmp_path / "database"
    uploads = tmp_path / "uploads" / "2026-09"
    database.mkdir()
    uploads.mkdir(parents=True)
    sqlite3.connect(database / "eldledger.db").close()
    (uploads / "receipt.jpg").write_bytes(b"jpeg-bytes")

    created = client.post("/api/v1/backup/server/run")
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["filename"].startswith("eldledger-")
    assert body["filename"].endswith(".zip")
    assert body["purged_count"] == 0

    listed = client.get("/api/v1/backup/server/files")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["filename"] == body["filename"]

    downloaded = client.get(f"/api/v1/backup/server/files/{body['filename']}")
    assert downloaded.status_code == 200
    assert downloaded.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        names = archive.namelist()
        assert "database/eldledger.db" in names
    assert "uploads/2026-09/receipt.jpg" in names

    folder = tmp_path / "backups" / "eldledger-20260915-010203"
    (folder / "database").mkdir(parents=True)
    (folder / "database" / "eldledger.db").write_bytes(b"folder-db")
    listed = client.get("/api/v1/backup/server/files")
    names = {row["filename"] for row in listed.json()}
    assert "eldledger-20260915-010203" in names
    folder_download = client.get("/api/v1/backup/server/files/eldledger-20260915-010203")
    assert folder_download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(folder_download.content)) as archive:
        assert "database/eldledger.db" in archive.namelist()

    old = tmp_path / "backups" / "eldledger-20200101-000000.zip"
    old.write_bytes(b"PK\x03\x04old")
    old_time = (datetime.now() - timedelta(days=31)).timestamp()
    os.utime(old, (old_time, old_time))

    service = ServerBackupService(db_session)
    removed = service.purge_expired()
    assert removed == 1
    assert not old.exists()
    assert (tmp_path / "backups" / body["filename"]).exists()


def test_delete_server_backup_files(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    backups = tmp_path / "backups"
    backups.mkdir()
    first = backups / "eldledger-20260921-010203.zip"
    second = backups / "eldledger-20260921-040506.zip"
    folder = backups / "eldledger-20260915-010203"
    first.write_bytes(b"PK\x03\x04one")
    second.write_bytes(b"PK\x03\x04two")
    (folder / "database").mkdir(parents=True)
    (folder / "database" / "eldledger.db").write_bytes(b"folder-db")

    single = client.delete("/api/v1/backup/server/files/eldledger-20260921-010203.zip")
    assert single.status_code == 200, single.text
    assert single.json()["deleted"] == ["eldledger-20260921-010203.zip"]
    assert not first.exists()
    assert second.exists()

    bulk = client.post(
        "/api/v1/backup/server/files/delete",
        json={"filenames": ["eldledger-20260921-040506.zip", "eldledger-20260915-010203"]},
    )
    assert bulk.status_code == 200, bulk.text
    assert set(bulk.json()["deleted"]) == {"eldledger-20260921-040506.zip", "eldledger-20260915-010203"}
    assert not second.exists()
    assert not folder.exists()
    assert client.get("/api/v1/backup/server/files").json() == []

    missing = client.delete("/api/v1/backup/server/files/eldledger-20200101-000000.zip")
    assert missing.status_code == 404
    traversal = client.post("/api/v1/backup/server/files/delete", json={"filenames": ["../secret.zip"]})
    assert traversal.status_code == 404


def test_settings_round_trip(client: TestClient) -> None:
    response = client.put(
        "/api/v1/backup/server/settings",
        json={"enabled": True, "frequency": "weekly", "weekday": 0, "monthday": 1, "hour": 4},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    assert body["frequency"] == "weekly"
    assert body["weekday"] == 0
    assert body["hour"] == 4
    assert body["retention_days"] == 30
    assert body["next_run_at"] is not None

    loaded = client.get("/api/v1/backup/server/settings")
    assert loaded.status_code == 200
    assert loaded.json()["frequency"] == "weekly"

    monthly = client.put(
        "/api/v1/backup/server/settings",
        json={"enabled": True, "frequency": "monthly", "weekday": 0, "monthday": 31, "hour": 4},
    )
    assert monthly.status_code == 200, monthly.text
    assert monthly.json()["monthday"] == 31
    assert monthly.json()["frequency"] == "monthly"


def test_download_rejects_unknown_and_traversal(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    (tmp_path / "backups").mkdir()
    missing = client.get("/api/v1/backup/server/files/eldledger-20200101-000000.zip")
    assert missing.status_code == 404
    traversal = client.get("/api/v1/backup/server/files/..%2Feldledger.db")
    assert traversal.status_code == 404
    try:
        resolve_backup_path("../secret.zip")
        assert False, "expected LookupError"
    except LookupError:
        pass


def test_server_backup_requires_admin(client: TestClient, db_session: Session) -> None:
    organization = _org(db_session)
    member = User(
        organization_id=organization.id,
        username="member",
        email="member@eldledger.local",
        hashed_password=hash_password("test-pass-1"),
        display_name="일반",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(member)
    db_session.flush()
    ChartTemplateService(db_session).provision_user_ledger(member)
    db_session.flush()

    def override_member() -> User:
        loaded = db_session.get(User, member.id)
        assert loaded is not None
        return loaded

    app.dependency_overrides[get_current_user] = override_member
    try:
        assert client.get("/api/v1/backup/server/settings").status_code == 403
        assert client.get("/api/v1/backup/server/files").status_code == 403
        assert client.post("/api/v1/backup/server/run").status_code == 403
        assert client.delete("/api/v1/backup/server/files/eldledger-20260921-010203.zip").status_code == 403
        assert client.post("/api/v1/backup/server/files/delete", json={"filenames": ["eldledger-20260921-010203.zip"]}).status_code == 403
    finally:
        admin = db_session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None

        def override_admin() -> User:
            loaded = db_session.get(User, admin.id)
            assert loaded is not None
            return loaded

        app.dependency_overrides[get_current_user] = override_admin


def test_run_if_due_creates_backup_once(db_session: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    (tmp_path / "database").mkdir()
    sqlite3.connect(tmp_path / "database" / "eldledger.db").close()
    organization = seed_standard_data(db_session)
    db_session.flush()
    service = ServerBackupService(db_session)
    service.update_schedule(
        organization.id,
        BackupScheduleUpdate(enabled=True, frequency=BackupFrequency.DAILY, hour=0),
    )
    now = datetime.now().replace(hour=1, minute=0, second=0, microsecond=0)
    first = service.run_if_due(now=now)
    assert first is not None
    second = service.run_if_due(now=now)
    assert second is None
