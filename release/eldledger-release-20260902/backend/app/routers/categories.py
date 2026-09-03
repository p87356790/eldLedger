from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import TransactionType
from app.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryReorderRequest,
    CategoryUpdate,
    ChartAccountOption,
)
from app.services.accounting_service import AccountingError
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


def _service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db)


@router.get("", response_model=list[CategoryRead])
def list_categories(
    organization_id: int = Query(..., ge=1),
    transaction_type: TransactionType | None = None,
    include_hidden: bool = False,
    service: CategoryService = Depends(_service),
) -> list[CategoryRead]:
    try:
        return service.list_categories(
            organization_id,
            transaction_type=transaction_type,
            include_hidden=include_hidden,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/chart-options", response_model=list[ChartAccountOption])
def list_chart_options(
    organization_id: int = Query(..., ge=1),
    transaction_type: TransactionType = Query(...),
    service: CategoryService = Depends(_service),
) -> list[ChartAccountOption]:
    try:
        return service.list_chart_options(organization_id, transaction_type)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/reorder", response_model=list[CategoryRead])
def reorder_categories(
    payload: CategoryReorderRequest,
    service: CategoryService = Depends(_service),
) -> list[CategoryRead]:
    try:
        return service.reorder(payload.organization_id, payload.items)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.create_category(payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(
    category_id: int,
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.get_category(category_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.update_category(category_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{category_id}/deactivate", response_model=CategoryRead)
def deactivate_category(
    category_id: int,
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.deactivate_category(category_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    service: CategoryService = Depends(_service),
) -> None:
    try:
        service.delete_category(category_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
