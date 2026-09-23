from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import Scope, TransactionType
from app.schemas.accounting import (
    AccountRead,
    AttachmentRead,
    CategoryRead,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionRead,
    TransactionUpdate,
)
from app.security.deps import get_current_user
from app.models import User
from app.services.accounting_service import AccountingError
from app.services.transaction_service import TransactionService

router = APIRouter(tags=["transactions"])


def _service(db: Session = Depends(get_db)) -> TransactionService:
    return TransactionService(db)


@router.get("/accounts", response_model=list[AccountRead])
def list_accounts(
    organization_id: int = Query(..., ge=1),
    user: User = Depends(get_current_user),
    service: TransactionService = Depends(_service),
) -> list[AccountRead]:
    return [AccountRead.model_validate(account) for account in service.list_accounts(organization_id, owner_user_id=user.id)]


@router.get("/categories", response_model=list[CategoryRead])
def list_categories(
    organization_id: int = Query(..., ge=1),
    user: User = Depends(get_current_user),
    service: TransactionService = Depends(_service),
) -> list[CategoryRead]:
    return [CategoryRead.model_validate(category) for category in service.list_categories(organization_id, owner_user_id=user.id)]


@router.post("/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    service: TransactionService = Depends(_service),
    user: User = Depends(get_current_user),
) -> TransactionRead:
    try:
        transaction = service.create(payload, created_by_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return TransactionRead.model_validate(transaction)


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions(
    organization_id: int = Query(..., ge=1),
    transaction_type: TransactionType | None = None,
    scope: Scope | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: int | None = Query(default=None, ge=0),
    amount_max: int | None = Query(default=None, ge=0),
    payment_account_id: int | None = None,
    category_id: int | None = None,
    tag_id: int | None = None,
    memo: str | None = None,
    include_reversed: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    service: TransactionService = Depends(_service),
) -> TransactionListResponse:
    total, rows = service.list_transactions(
        organization_id=organization_id,
        transaction_type=transaction_type,
        scope=scope,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        payment_account_id=payment_account_id,
        category_id=category_id,
        tag_id=tag_id,
        memo=memo,
        created_by_user_id=user.id,
        include_reversed=include_reversed,
        offset=offset,
        limit=limit,
    )
    return TransactionListResponse(
        total=total,
        items=[TransactionRead.model_validate(row) for row in rows],
    )


@router.post("/transactions/duplicate-check", response_model=DuplicateCheckResponse)
def check_duplicate_transactions(
    payload: DuplicateCheckRequest,
    service: TransactionService = Depends(_service),
    user: User = Depends(get_current_user),
) -> DuplicateCheckResponse:
    try:
        matches = service.find_duplicates(payload, created_by_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return DuplicateCheckResponse(matches=[TransactionRead.model_validate(row) for row in matches])


@router.get("/transactions/{transaction_id}", response_model=TransactionRead)
def get_transaction(
    transaction_id: int,
    service: TransactionService = Depends(_service),
) -> TransactionRead:
    try:
        transaction = service.get(transaction_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return TransactionRead.model_validate(transaction)


@router.put("/transactions/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    service: TransactionService = Depends(_service),
) -> TransactionRead:
    try:
        transaction = service.update(transaction_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return TransactionRead.model_validate(transaction)


@router.delete("/transactions/{transaction_id}", response_model=TransactionRead)
def cancel_transaction(
    transaction_id: int,
    service: TransactionService = Depends(_service),
) -> TransactionRead:
    try:
        transaction = service.cancel(transaction_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return TransactionRead.model_validate(transaction)


@router.post(
    "/transactions/{transaction_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    transaction_id: int,
    file: UploadFile = File(...),
    service: TransactionService = Depends(_service),
) -> AttachmentRead:
    content = await file.read()
    try:
        attachment = service.add_attachment(
            transaction_id,
            original_filename=file.filename or "receipt",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return AttachmentRead.model_validate(attachment)


@router.get("/transactions/{transaction_id}/attachments/{attachment_id}", response_model=None)
def download_attachment(
    transaction_id: int,
    attachment_id: int,
    service: TransactionService = Depends(_service),
) -> FileResponse:
    try:
        attachment, path = service.get_attachment_file(transaction_id, attachment_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    quoted = quote(attachment.original_filename)
    return FileResponse(
        path=path,
        media_type=attachment.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quoted}",
            "X-Content-Type-Options": "nosniff",
        },
    )
