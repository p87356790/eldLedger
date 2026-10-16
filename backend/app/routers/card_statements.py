from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.card_statements import CardStatementPay, CardStatementRead, CardStatementUpdate
from app.security.deps import get_current_user
from app.services.accounting_service import AccountingError
from app.services.card_statement_service import CardStatementService

router = APIRouter(prefix="/card-statements", tags=["card-statements"])


def _service(db: Session = Depends(get_db)) -> CardStatementService:
    return CardStatementService(db)


@router.get("", response_model=list[CardStatementRead])
def list_card_statements(
    organization_id: int = Query(..., ge=1),
    user: User = Depends(get_current_user),
    service: CardStatementService = Depends(_service),
) -> list[CardStatementRead]:
    if user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 장부에는 접근할 수 없어요.")
    return service.list_statements(user)


@router.patch("/{statement_id}", response_model=CardStatementRead)
def update_card_statement(
    statement_id: int,
    payload: CardStatementUpdate,
    user: User = Depends(get_current_user),
    service: CardStatementService = Depends(_service),
) -> CardStatementRead:
    try:
        return service.update_amount(user, statement_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{statement_id}/pay", response_model=CardStatementRead)
def pay_card_statement(
    statement_id: int,
    payload: CardStatementPay,
    user: User = Depends(get_current_user),
    service: CardStatementService = Depends(_service),
) -> CardStatementRead:
    try:
        return service.pay(user, statement_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
