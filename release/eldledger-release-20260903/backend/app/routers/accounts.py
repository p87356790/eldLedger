from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.wallets import (
    WalletAccountCreate,
    WalletAccountRead,
    WalletAccountUpdate,
    WalletBalanceAdjust,
)
from app.security.deps import get_current_user
from app.services.account_service import AccountService
from app.services.accounting_service import AccountingError

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _service(db: Session = Depends(get_db)) -> AccountService:
    return AccountService(db)


def _require_org(user: User, organization_id: int) -> None:
    if user.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 장부에는 접근할 수 없어요.")


@router.get("", response_model=list[WalletAccountRead])
def list_wallet_accounts(
    organization_id: int = Query(..., ge=1),
    include_hidden: bool = False,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(_service),
) -> list[WalletAccountRead]:
    _require_org(user, organization_id)
    try:
        return service.list_wallets(organization_id, owner_user_id=user.id, include_hidden=include_hidden)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("", response_model=WalletAccountRead, status_code=status.HTTP_201_CREATED)
def create_wallet_account(
    payload: WalletAccountCreate,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    _require_org(user, payload.organization_id)
    try:
        return service.create_wallet(payload, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/{account_id}", response_model=WalletAccountRead)
def get_wallet_account(
    account_id: int,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.get_wallet(account_id, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/{account_id}", response_model=WalletAccountRead)
def update_wallet_account(
    account_id: int,
    payload: WalletAccountUpdate,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.update_wallet(account_id, payload, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{account_id}/deactivate", response_model=WalletAccountRead)
def deactivate_wallet_account(
    account_id: int,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.deactivate_wallet(account_id, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{account_id}/adjust-balance", response_model=WalletAccountRead)
def adjust_wallet_balance(
    account_id: int,
    payload: WalletBalanceAdjust,
    user: User = Depends(get_current_user),
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.adjust_balance(account_id, payload, owner_user_id=user.id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
