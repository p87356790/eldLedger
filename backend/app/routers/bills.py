from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.accounting import AttachmentRead
from app.schemas.bills import BillCreate, BillPay, BillRead, BillUpdate
from app.security.deps import get_current_user
from app.services.accounting_service import AccountingError
from app.services.bill_service import BillService

router = APIRouter(prefix="/bills", tags=["bills"])


def _service(db: Session = Depends(get_db)) -> BillService:
    return BillService(db)


@router.get("", response_model=list[BillRead])
def list_bills(
    organization_id: int = Query(..., ge=1),
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> list[BillRead]:
    if user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 장부에는 접근할 수 없어요.")
    return [BillRead.model_validate(bill) for bill in service.list_bills(user)]


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: BillCreate,
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> BillRead:
    try:
        bill = service.create(user, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return BillRead.model_validate(bill)


@router.patch("/{bill_id}", response_model=BillRead)
def update_bill(
    bill_id: int,
    payload: BillUpdate,
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> BillRead:
    try:
        bill = service.update(user, bill_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return BillRead.model_validate(bill)


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(
    bill_id: int,
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> None:
    try:
        service.delete(user, bill_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{bill_id}/pay", response_model=BillRead)
def pay_bill(
    bill_id: int,
    payload: BillPay,
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> BillRead:
    try:
        bill = service.pay(user, bill_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return BillRead.model_validate(bill)


@router.post(
    "/{bill_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_bill_attachment(
    bill_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> AttachmentRead:
    content = await file.read()
    try:
        attachment = service.add_attachment(
            user,
            bill_id,
            original_filename=file.filename or "invoice",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return AttachmentRead.model_validate(attachment)


@router.delete("/{bill_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_bill_attachment(
    bill_id: int,
    attachment_id: int,
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> None:
    try:
        service.unlink_attachment(user, bill_id, attachment_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/{bill_id}/attachments/{attachment_id}", response_model=None)
def download_bill_attachment(
    bill_id: int,
    attachment_id: int,
    user: User = Depends(get_current_user),
    service: BillService = Depends(_service),
) -> FileResponse:
    try:
        attachment, path = service.get_attachment_file(user, bill_id, attachment_id)
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
