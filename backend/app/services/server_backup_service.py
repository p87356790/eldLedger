from __future__ import annotations

import calendar
import json
import logging
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, Setting
from app.schemas.backup import (
    BackupFrequency,
    BackupScheduleRead,
    BackupScheduleState,
    BackupScheduleUpdate,
    ServerBackupFile,
    ServerBackupRunResult,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

SETTING_KEY = "backup.schedule"
RETENTION_DAYS = 30
BACKUP_NAME_RE = re.compile(r"^eldledger-\d{8}-\d{6}(?:\.zip)?$")
_run_lock = threading.Lock()


class BackupInProgressError(Exception):
    """Another full backup is already running."""


def backups_dir() -> Path:
    path = Path(settings.data_dir) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def schedule_matches_day(state: BackupScheduleState, when: datetime) -> bool:
    if state.frequency is BackupFrequency.DAILY:
        return True
    if state.frequency is BackupFrequency.WEEKLY:
        return when.weekday() == state.weekday
    last_day = calendar.monthrange(when.year, when.month)[1]
    return when.day == min(state.monthday, last_day)


def schedule_is_due(state: BackupScheduleState, now: datetime) -> bool:
    if not state.enabled:
        return False
    if now.hour < state.hour:
        return False
    if not schedule_matches_day(state, now):
        return False
    if state.last_run_at is not None and state.last_run_at.date() == now.date():
        return False
    return True


def next_run_at(state: BackupScheduleState, now: datetime) -> datetime | None:
    if not state.enabled:
        return None
    today_slot = now.replace(hour=state.hour, minute=0, second=0, microsecond=0)
    if schedule_is_due(state, now):
        return today_slot
    already_ran_today = state.last_run_at is not None and state.last_run_at.date() == now.date()
    if now < today_slot and not already_ran_today:
        cursor = today_slot
    else:
        cursor = today_slot + timedelta(days=1)
    for _ in range(400):
        if schedule_matches_day(state, cursor):
            return cursor
        cursor += timedelta(days=1)
        cursor = cursor.replace(hour=state.hour, minute=0, second=0, microsecond=0)
    return None


def resolve_backup_path(filename: str) -> Path:
    if filename != Path(filename).name or not BACKUP_NAME_RE.fullmatch(filename):
        raise LookupError("백업 파일을 찾을 수 없어요.")
    root = backups_dir().resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root):
        raise LookupError("백업 파일을 찾을 수 없어요.")
    if not path.exists():
        raise LookupError("백업 파일을 찾을 수 없어요.")
    return path


def directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def zip_directory(source: Path, dest: Path) -> None:
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for child in source.rglob("*"):
            if child.is_file():
                archive.write(child, child.relative_to(source).as_posix())


class ServerBackupService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditService(session)

    def get_schedule(self, organization_id: int, now: datetime | None = None) -> BackupScheduleRead:
        state = self._load_state(organization_id)
        moment = now or datetime.now()
        return BackupScheduleRead(
            **state.model_dump(),
            retention_days=RETENTION_DAYS,
            next_run_at=next_run_at(state, moment),
        )

    def update_schedule(self, organization_id: int, payload: BackupScheduleUpdate) -> BackupScheduleRead:
        state = self._load_state(organization_id)
        updated = BackupScheduleState(
            **payload.model_dump(),
            last_run_at=state.last_run_at,
            last_run_status=state.last_run_status,
            last_run_filename=state.last_run_filename,
            last_error=state.last_error,
        )
        self._save_state(organization_id, updated)
        return self.get_schedule(organization_id)

    def list_files(self) -> list[ServerBackupFile]:
        rows: list[ServerBackupFile] = []
        for child in backups_dir().iterdir():
            if not BACKUP_NAME_RE.fullmatch(child.name):
                continue
            if child.is_file() and child.suffix == ".zip":
                stat = child.stat()
                rows.append(
                    ServerBackupFile(
                        filename=child.name,
                        created_at=datetime.fromtimestamp(stat.st_mtime),
                        size_bytes=stat.st_size,
                        kind="zip",
                    )
                )
            elif child.is_dir():
                rows.append(
                    ServerBackupFile(
                        filename=child.name,
                        created_at=datetime.fromtimestamp(child.stat().st_mtime),
                        size_bytes=directory_size(child),
                        kind="directory",
                    )
                )
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows

    def delete_files(self, filenames: Sequence[str], *, user_id: int | None = None) -> list[str]:
        unique = list(dict.fromkeys(filenames))
        paths = [resolve_backup_path(name) for name in unique]
        deleted: list[str] = []
        for path in paths:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path)
            deleted.append(path.name)
        if deleted:
            self._audit.record(
                action="SERVER_BACKUP_DELETE",
                user_id=user_id,
                entity_type="backup",
                details=", ".join(deleted),
            )
        return deleted

    def create_full_backup(self, organization_id: int, user_id: int | None = None) -> ServerBackupRunResult:
        if not _run_lock.acquire(blocking=False):
            raise BackupInProgressError("이미 백업이 진행 중이에요.")
        try:
            try:
                result = self._write_archive()
            except Exception as error:
                self._record_run(organization_id, status="error", filename=None, error=str(error))
                raise
            purged = self.purge_expired()
            self._record_run(organization_id, status="ok", filename=result.filename, error=None)
            self._audit.record(
                action="SERVER_BACKUP",
                user_id=user_id,
                entity_type="backup",
                details=result.filename,
            )
            logger.info("서버 백업 완료: %s", result.filename)
            return ServerBackupRunResult(
                filename=result.filename,
                size_bytes=result.size_bytes,
                purged_count=purged,
            )
        finally:
            _run_lock.release()

    def run_if_due(self, now: datetime | None = None) -> ServerBackupRunResult | None:
        organization_id = self._session.scalar(select(Organization.id).order_by(Organization.id).limit(1))
        if organization_id is None:
            return None
        moment = now or datetime.now()
        try:
            purged = self.purge_expired()
            if purged:
                logger.info("만료 백업 %s개 삭제", purged)
        except Exception:
            logger.exception("만료 백업 삭제 실패")
        state = self._load_state(organization_id)
        if not schedule_is_due(state, moment):
            return None
        return self.create_full_backup(organization_id, user_id=None)

    def purge_expired(self, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now()) - timedelta(days=RETENTION_DAYS)
        removed = 0
        for child in backups_dir().iterdir():
            if not BACKUP_NAME_RE.fullmatch(child.name):
                continue
            stamp = datetime.fromtimestamp(child.stat().st_mtime)
            if stamp >= cutoff:
                continue
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                shutil.rmtree(child)
            removed += 1
        return removed

    def _write_archive(self) -> ServerBackupFile:
        dest = self._unique_zip_path()
        partial = dest.with_name(dest.name + ".partial")
        try:
            with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                self._add_database(archive)
                self._add_directory(archive, Path(settings.data_dir) / "uploads", "uploads")
            partial.replace(dest)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        stat = dest.stat()
        return ServerBackupFile(
            filename=dest.name,
            created_at=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=stat.st_size,
            kind="zip",
        )

    def _unique_zip_path(self) -> Path:
        root = backups_dir()
        for offset in range(10):
            stamp = (datetime.now() + timedelta(seconds=offset)).strftime("%Y%m%d-%H%M%S")
            dest = root / f"eldledger-{stamp}.zip"
            if not dest.exists() and not dest.with_name(dest.name + ".partial").exists():
                return dest
        raise RuntimeError("같은 시각의 백업 파일이 이미 있어요. 잠시 후 다시 시도해 주세요.")

    def _add_database(self, archive: zipfile.ZipFile) -> None:
        source = Path(settings.data_dir) / "database" / "eldledger.db"
        if not source.is_file():
            database_dir = Path(settings.data_dir) / "database"
            self._add_directory(archive, database_dir, "database")
            return
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
            snapshot = Path(handle.name)
        try:
            src_conn = sqlite3.connect(str(source))
            try:
                dst_conn = sqlite3.connect(str(snapshot))
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()
            finally:
                src_conn.close()
            archive.write(snapshot, "database/eldledger.db")
        finally:
            snapshot.unlink(missing_ok=True)

    def _add_directory(self, archive: zipfile.ZipFile, source: Path, prefix: str) -> None:
        if not source.is_dir():
            return
        for child in source.rglob("*"):
            if not child.is_file():
                continue
            if child.name.startswith("."):
                continue
            archive.write(child, f"{prefix}/{child.relative_to(source).as_posix()}")

    def _load_state(self, organization_id: int) -> BackupScheduleState:
        row = self._session.scalar(
            select(Setting).where(
                Setting.organization_id == organization_id,
                Setting.key == SETTING_KEY,
            )
        )
        if row is None or not row.value.strip():
            return BackupScheduleState()
        try:
            payload = json.loads(row.value)
            return BackupScheduleState.model_validate(payload)
        except (json.JSONDecodeError, ValueError):
            logger.warning("백업 설정 값이 올바르지 않아 기본값을 씁니다.")
            return BackupScheduleState()

    def _save_state(self, organization_id: int, state: BackupScheduleState) -> None:
        row = self._session.scalar(
            select(Setting).where(
                Setting.organization_id == organization_id,
                Setting.key == SETTING_KEY,
            )
        )
        encoded = json.dumps(state.model_dump(mode="json"), ensure_ascii=False)
        if row is None:
            self._session.add(Setting(organization_id=organization_id, key=SETTING_KEY, value=encoded))
        else:
            row.value = encoded
        self._session.flush()

    def _record_run(
        self,
        organization_id: int,
        *,
        status: str,
        filename: str | None,
        error: str | None,
    ) -> None:
        state = self._load_state(organization_id)
        state.last_run_at = datetime.now()
        state.last_run_status = status
        state.last_run_filename = filename
        state.last_error = error
        self._save_state(organization_id, state)
