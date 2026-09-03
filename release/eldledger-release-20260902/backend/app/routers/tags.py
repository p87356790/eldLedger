from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.accounting import TransactionRead
from app.schemas.categories import TagCreate, TagRead, TagUpdate, TransactionTagsUpdate
from app.services.accounting_service import AccountingError
from app.services.tag_service import TagService

router = APIRouter(tags=["tags"])


def _service(db: Session = Depends(get_db)) -> TagService:
    return TagService(db)


@router.get("/tags", response_model=list[TagRead])
def list_tags(
    organization_id: int = Query(..., ge=1),
    service: TagService = Depends(_service),
) -> list[TagRead]:
    try:
        return service.list_tags(organization_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    service: TagService = Depends(_service),
) -> TagRead:
    try:
        return service.create_tag(payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.patch("/tags/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    service: TagService = Depends(_service),
) -> TagRead:
    try:
        return service.update_tag(tag_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    service: TagService = Depends(_service),
) -> None:
    try:
        service.delete_tag(tag_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.put("/transactions/{transaction_id}/tags", response_model=TransactionRead)
def set_transaction_tags(
    transaction_id: int,
    payload: TransactionTagsUpdate,
    service: TagService = Depends(_service),
) -> TransactionRead:
    try:
        return service.set_transaction_tags(transaction_id, payload.tag_ids)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
