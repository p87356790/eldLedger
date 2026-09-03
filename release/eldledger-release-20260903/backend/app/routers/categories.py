from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.enums import TransactionType
from app.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryReorderRequest,
    CategoryUpdate,
    ChartAccountOption,
)
from app.security.deps import get_current_user
from app.services.accounting_service import AccountingError
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


def _service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(db)


def _require_org(user: User, organization_id: int) -> None:
    if user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 장부에는 접근할 수 없어요.")


@router.get("", response_model=list[CategoryRead])
def list_categories(
    organization_id: int = Query(..., ge=1),
    transaction_type: TransactionType | None = None,
    include_hidden: bool = False,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> list[CategoryRead]:
    _require_org(user, organization_id)
    try:
        return service.list_categories(
            organization_id,
            owner_user_id=user.id,
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
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> list[ChartAccountOption]:
    _require_org(user, organization_id)
    try:
        return service.list_chart_options(organization_id, transaction_type)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/reorder", response_model=list[CategoryRead])
def reorder_categories(
    payload: CategoryReorderRequest,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> list[CategoryRead]:
    _require_org(user, payload.organization_id)
    try:
        return service.reorder(payload.organization_id, payload.items, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    _require_org(user, payload.organization_id)
    try:
        return service.create_category(payload, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(
    category_id: int,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.get_category(category_id, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.update_category(category_id, payload, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{category_id}/deactivate", response_model=CategoryRead)
def deactivate_category(
    category_id: int,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> CategoryRead:
    try:
        return service.deactivate_category(category_id, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    user: User = Depends(get_current_user),
    service: CategoryService = Depends(_service),
) -> None:
    try:
        service.delete_category(category_id, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
