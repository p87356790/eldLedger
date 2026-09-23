from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.database import get_db
from app.models import User
from app.schemas.backup import (
    BackupScheduleRead,
    BackupScheduleUpdate,
    ConfigBundle,
    ConfigImportResult,
    LedgerImportResult,
    ServerBackupDeleteRequest,
    ServerBackupDeleteResult,
    ServerBackupFile,
    ServerBackupRunResult,
)
from app.security.deps import get_current_user, require_admin
from app.services.accounting_service import AccountingError
from app.services.backup_service import BackupService, LedgerConflictError, decode_backup_bytes
from app.services.journal_balance import UnbalancedJournalError
from app.services.server_backup_service import (
    BackupInProgressError,
    ServerBackupService,
    resolve_backup_path,
    zip_directory,
)

router = APIRouter(prefix="/backup", tags=["backup"])


def _service(db: Session = Depends(get_db)) -> BackupService:
    return BackupService(db)


def _server_backup(db: Session = Depends(get_db)) -> ServerBackupService:
    return ServerBackupService(db)


def _unlink(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def _import_http_error(error: Exception) -> HTTPException:
    if isinstance(error, LedgerConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, AccountingError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    if isinstance(error, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, UnbalancedJournalError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    if isinstance(error, IntegrityError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="연결된 거래·분개·규칙이 있어 가져오지 못했어요. 해당 계정 장부를 초기화한 뒤 다시 시도해 주세요.",
        )
    if isinstance(error, OperationalError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="데이터베이스에 쓰지 못했어요. 디스크 권한이나 용량을 확인해 주세요.",
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"가져오기에 실패했어요. ({error})",
    )


@router.get("/export")
def export_ledger(
    user: User = Depends(get_current_user),
    service: BackupService = Depends(_service),
) -> Response:
    payload = service.export_zip(user)
    filename = f"eldledger-backup-{date.today().isoformat()}.zip"
    quoted = quote(filename)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


@router.post("/import", response_model=LedgerImportResult)
async def import_ledger(
    replace: bool = Query(default=False),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: BackupService = Depends(_service),
) -> LedgerImportResult:
    payload = await file.read()
    try:
        return service.import_zip(user, payload, replace=replace)
    except Exception as error:
        raise _import_http_error(error) from error


@router.get("/config/export", response_model=ConfigBundle)
def export_config(
    user: User = Depends(get_current_user),
    service: BackupService = Depends(_service),
) -> ConfigBundle:
    return service.export_config(user)


@router.post("/config/import", response_model=ConfigImportResult)
async def import_config(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: BackupService = Depends(_service),
) -> ConfigImportResult:
    payload = await file.read()
    try:
        bundle = ConfigBundle.model_validate_json(decode_backup_bytes(payload))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자산/분류 설정 파일 형식이 올바르지 않아요.",
        ) from error
    try:
        return service.import_config(user, bundle)
    except Exception as error:
        raise _import_http_error(error) from error


@router.get("/server/settings", response_model=BackupScheduleRead)
def get_server_backup_settings(
    user: User = Depends(require_admin),
    service: ServerBackupService = Depends(_server_backup),
) -> BackupScheduleRead:
    return service.get_schedule(user.organization_id)


@router.put("/server/settings", response_model=BackupScheduleRead)
def update_server_backup_settings(
    payload: BackupScheduleUpdate,
    user: User = Depends(require_admin),
    service: ServerBackupService = Depends(_server_backup),
) -> BackupScheduleRead:
    return service.update_schedule(user.organization_id, payload)


@router.get("/server/files", response_model=list[ServerBackupFile])
def list_server_backups(
    _user: User = Depends(require_admin),
    service: ServerBackupService = Depends(_server_backup),
) -> list[ServerBackupFile]:
    return service.list_files()


@router.post("/server/run", response_model=ServerBackupRunResult)
def run_server_backup(
    user: User = Depends(require_admin),
    service: ServerBackupService = Depends(_server_backup),
) -> ServerBackupRunResult:
    try:
        return service.create_full_backup(user.organization_id, user_id=user.id)
    except BackupInProgressError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/server/files/delete", response_model=ServerBackupDeleteResult)
def delete_server_backups(
    payload: ServerBackupDeleteRequest,
    user: User = Depends(require_admin),
    service: ServerBackupService = Depends(_server_backup),
) -> ServerBackupDeleteResult:
    try:
        deleted = service.delete_files(payload.filenames, user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return ServerBackupDeleteResult(deleted=deleted)


@router.delete("/server/files/{filename}", response_model=ServerBackupDeleteResult)
def delete_server_backup(
    filename: str,
    user: User = Depends(require_admin),
    service: ServerBackupService = Depends(_server_backup),
) -> ServerBackupDeleteResult:
    try:
        deleted = service.delete_files([filename], user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return ServerBackupDeleteResult(deleted=deleted)


@router.get("/server/files/{filename}", response_model=None)
def download_server_backup(
    filename: str,
    _user: User = Depends(require_admin),
) -> FileResponse:
    try:
        path = resolve_backup_path(filename)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if path.is_file():
        quoted = quote(path.name)
        return FileResponse(
            path=path,
            media_type="application/zip",
            filename=path.name,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
        )
    handle = NamedTemporaryFile(suffix=".zip", delete=False)
    handle.close()
    zip_directory(path, Path(handle.name))
    download_name = f"{path.name}.zip"
    quoted = quote(download_name)
    return FileResponse(
        path=handle.name,
        media_type="application/zip",
        filename=download_name,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
        background=BackgroundTask(_unlink, handle.name),
    )
