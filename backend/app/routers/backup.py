from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.backup import LedgerImportResult
from app.security.deps import get_current_user
from app.services.accounting_service import AccountingError
from app.services.backup_service import BackupService, LedgerConflictError

router = APIRouter(prefix="/backup", tags=["backup"])


def _service(db: Session = Depends(get_db)) -> BackupService:
    return BackupService(db)


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
    except LedgerConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
