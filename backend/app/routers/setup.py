from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.auth import AuthResponse, FactoryResetRequest, SetupCreate, SetupStatus
from app.security.deps import require_admin
from app.services.accounting_service import AccountingError
from app.services.auth_service import AuthService

router = APIRouter(prefix="/setup", tags=["setup"])


def _service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get("", response_model=SetupStatus)
def setup_status(service: AuthService = Depends(_service)) -> SetupStatus:
    return service.setup_status()


@router.post("", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def complete_setup(payload: SetupCreate, service: AuthService = Depends(_service)) -> AuthResponse:
    try:
        return service.complete_setup(payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/reset", response_model=SetupStatus)
def factory_reset(
    payload: FactoryResetRequest,
    actor: User = Depends(require_admin),
    service: AuthService = Depends(_service),
) -> SetupStatus:
    try:
        return service.factory_reset(actor, payload)
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
