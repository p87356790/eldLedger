from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.wallets import (
    WalletAccountCreate,
    WalletAccountRead,
    WalletAccountUpdate,
    WalletBalanceAdjust,
)
from app.services.account_service import AccountService
from app.services.accounting_service import AccountingError

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _service(db: Session = Depends(get_db)) -> AccountService:
    return AccountService(db)


@router.get("", response_model=list[WalletAccountRead])
def list_wallet_accounts(
    organization_id: int = Query(..., ge=1),
    include_hidden: bool = False,
    service: AccountService = Depends(_service),
) -> list[WalletAccountRead]:
    try:
        return service.list_wallets(organization_id, include_hidden=include_hidden)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("", response_model=WalletAccountRead, status_code=status.HTTP_201_CREATED)
def create_wallet_account(
    payload: WalletAccountCreate,
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.create_wallet(payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/{account_id}", response_model=WalletAccountRead)
def get_wallet_account(
    account_id: int,
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.get_wallet(account_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/{account_id}", response_model=WalletAccountRead)
def update_wallet_account(
    account_id: int,
    payload: WalletAccountUpdate,
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.update_wallet(account_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{account_id}/deactivate", response_model=WalletAccountRead)
def deactivate_wallet_account(
    account_id: int,
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.deactivate_wallet(account_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/{account_id}/adjust-balance", response_model=WalletAccountRead)
def adjust_wallet_balance(
    account_id: int,
    payload: WalletBalanceAdjust,
    service: AccountService = Depends(_service),
) -> WalletAccountRead:
    try:
        return service.adjust_balance(account_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except AccountingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
