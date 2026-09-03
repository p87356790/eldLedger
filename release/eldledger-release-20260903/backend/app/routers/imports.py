from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.imports import (
    AutoCategoryRuleCreate,
    AutoCategoryRuleRead,
    AutoCategoryRuleUpdate,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    ImportProfileRead,
)
from app.security.deps import get_current_user
from app.services.accounting_service import AccountingError
from app.services.csv_import_service import CsvImportService

router = APIRouter(prefix="/import", tags=["import"])


def _service(db: Session = Depends(get_db)) -> CsvImportService:
    return CsvImportService(db)


@router.get("/profiles", response_model=list[ImportProfileRead])
def list_profiles(
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> list[ImportProfileRead]:
    try:
        return service.list_profiles(user)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    account_id: int = Form(...),
    organization_id: int | None = Form(default=None),
    profile_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> ImportPreviewResponse:
    payload = await file.read()
    filename = file.filename or "import.csv"
    try:
        return service.preview(
            user,
            file_bytes=payload,
            filename=filename,
            account_id=account_id,
            organization_id=organization_id,
            profile_id=profile_id,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/commit", response_model=ImportCommitResponse)
def commit_import(
    payload: ImportCommitRequest,
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> ImportCommitResponse:
    try:
        return service.commit(user, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/rules", response_model=list[AutoCategoryRuleRead])
def list_rules(
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> list[AutoCategoryRuleRead]:
    return service.list_rules(user)


@router.post("/rules", response_model=AutoCategoryRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: AutoCategoryRuleCreate,
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> AutoCategoryRuleRead:
    try:
        return service.create_rule(user, payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.patch("/rules/{rule_id}", response_model=AutoCategoryRuleRead)
def update_rule(
    rule_id: int,
    payload: AutoCategoryRuleUpdate,
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> AutoCategoryRuleRead:
    try:
        return service.update_rule(user, rule_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    service: CsvImportService = Depends(_service),
) -> None:
    try:
        service.delete_rule(user, rule_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
