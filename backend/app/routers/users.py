from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.auth import (
    AdminPasswordSet,
    AuditLogRead,
    FactoryResetRequest,
    LedgerResetResult,
    PasswordChange,
    ProfileUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security.deps import get_current_user, require_admin
from app.services.accounting_service import AccountingError
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])


def _service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get("/me", response_model=UserRead)
def read_me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_service),
) -> UserRead:
    try:
        return service.update_profile(user, payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_service),
) -> None:
    try:
        service.change_password(user, payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/me/login-history", response_model=list[AuditLogRead])
def my_login_history(
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_service),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AuditLogRead]:
    return [AuditLogRead.model_validate(item) for item in service.login_history(user, limit=limit)]


@router.get("", response_model=list[UserRead])
def list_users(
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> list[UserRead]:
    return service.list_users(actor)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> UserRead:
    try:
        return service.create_user(actor, payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_user_password(
    user_id: int,
    payload: AdminPasswordSet,
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> None:
    try:
        service.set_user_password(actor, user_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> UserRead:
    try:
        return service.update_user(actor, user_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{user_id}/reset-ledger", response_model=LedgerResetResult)
def reset_user_ledger_endpoint(
    user_id: int,
    payload: FactoryResetRequest,
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> LedgerResetResult:
    try:
        return service.reset_ledger(actor, payload, target_user_id=user_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: int,
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> UserRead:
    try:
        return service.deactivate_user(actor, user_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
