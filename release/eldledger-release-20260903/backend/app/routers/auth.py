from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.auth import AuthResponse, LoginRequest, LogoutRequest, RefreshRequest, TokenPair, UserRead
from app.security.deps import get_current_user
from app.services.accounting_service import AccountingError
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, service: AuthService = Depends(_service)) -> AuthResponse:
    try:
        return service.login(payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, service: AuthService = Depends(_service)) -> TokenPair:
    try:
        return service.refresh(payload.refresh_token)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_service),
) -> None:
    service.logout(user, payload.refresh_token)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
