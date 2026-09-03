from datetime import date

from sqlalchemy.orm import Session

from app.models import Account, Organization
from app.models.enums import NORMAL_BALANCE_BY_TYPE, AccountType, PaymentInstrumentKind
from app.repositories.account_repository import AccountRepository
from app.schemas.wallets import (
    WalletAccountCreate,
    WalletAccountRead,
    WalletAccountUpdate,
    WalletBalanceAdjust,
)
from app.services.accounting_service import AccountingError, AccountingService
from app.services.ledger_service import LedgerService

KIND_PARENT_CODE: dict[PaymentInstrumentKind, str] = {
    PaymentInstrumentKind.CASH: "1100",
    PaymentInstrumentKind.BANK: "1200",
    PaymentInstrumentKind.CREDIT_CARD: "2100",
    PaymentInstrumentKind.LOAN: "2300",
    PaymentInstrumentKind.OTHER_ASSET: "1600",
}

KIND_ACCOUNT_TYPE: dict[PaymentInstrumentKind, AccountType] = {
    PaymentInstrumentKind.CASH: AccountType.ASSET,
    PaymentInstrumentKind.BANK: AccountType.ASSET,
    PaymentInstrumentKind.CREDIT_CARD: AccountType.LIABILITY,
    PaymentInstrumentKind.LOAN: AccountType.LIABILITY,
    PaymentInstrumentKind.OTHER_ASSET: AccountType.ASSET,
}

PAYMENT_KINDS = {
    PaymentInstrumentKind.CASH,
    PaymentInstrumentKind.BANK,
    PaymentInstrumentKind.CREDIT_CARD,
    PaymentInstrumentKind.LOAN,
}


class AccountService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = AccountRepository(session)
        self._accounting = AccountingService(session)
        self._ledger = LedgerService(session)

    def list_wallets(self, organization_id: int, *, include_hidden: bool = False) -> list[WalletAccountRead]:
        self._require_organization(organization_id)
        return [self._to_read(account) for account in self._repo.list_wallets(organization_id, include_hidden=include_hidden)]

    def get_wallet(self, account_id: int) -> WalletAccountRead:
        return self._to_read(self._require_wallet(account_id))

    def create_wallet(self, payload: WalletAccountCreate) -> WalletAccountRead:
        self._require_organization(payload.organization_id)
        if payload.currency != "KRW":
            raise AccountingError("지금은 원화(KRW)만 사용할 수 있어요.")
        parent = self._require_parent(payload.organization_id, payload.instrument_kind)
        if payload.instrument_kind == PaymentInstrumentKind.CREDIT_CARD:
            self._require_settlement_bank(payload.organization_id, payload.settlement_account_id)

        account = Account(
            organization_id=payload.organization_id,
            parent_id=parent.id,
            code=self._next_child_code(payload.organization_id, parent),
            name=payload.name.strip(),
            account_type=KIND_ACCOUNT_TYPE[payload.instrument_kind],
            normal_balance=NORMAL_BALANCE_BY_TYPE[KIND_ACCOUNT_TYPE[payload.instrument_kind]],
            is_postable=True,
            is_payment_method=payload.instrument_kind in PAYMENT_KINDS,
            is_system=False,
            is_active=True,
            sort_order=payload.sort_order or parent.sort_order,
            instrument_kind=payload.instrument_kind,
            currency="KRW",
            opening_balance=payload.opening_balance,
            institution=payload.institution.strip() if payload.institution else None,
            card_payment_day=payload.card_payment_day,
            settlement_account_id=payload.settlement_account_id,
        )
        self._session.add(account)
        self._session.flush()

        if payload.opening_balance > 0:
            occurred_on = payload.opening_on or date.today()
            self._accounting.post_capital_adjustment(
                organization_id=payload.organization_id,
                wallet=account,
                amount_delta=payload.opening_balance,
                occurred_on=occurred_on,
                description=f"시작 잔액: {account.name}",
            )
        return self._to_read(account)

    def update_wallet(self, account_id: int, payload: WalletAccountUpdate) -> WalletAccountRead:
        account = self._require_wallet(account_id)
        if payload.name is not None:
            account.name = payload.name.strip()
        if payload.institution is not None:
            account.institution = payload.institution.strip() or None
        if payload.sort_order is not None:
            account.sort_order = payload.sort_order
        if payload.is_active is not None:
            self._set_active(account, payload.is_active)
        if account.instrument_kind == PaymentInstrumentKind.CREDIT_CARD:
            if payload.card_payment_day is not None:
                account.card_payment_day = payload.card_payment_day
            if payload.settlement_account_id is not None:
                self._require_settlement_bank(account.organization_id, payload.settlement_account_id)
                if payload.settlement_account_id == account.id:
                    raise AccountingError("카드 결제 계좌는 다른 계좌여야 해요.")
                account.settlement_account_id = payload.settlement_account_id
        elif payload.card_payment_day is not None or payload.settlement_account_id is not None:
            raise AccountingError("결제일과 결제 계좌는 신용카드만 설정할 수 있습니다.")
        self._session.flush()
        return self._to_read(account)

    def deactivate_wallet(self, account_id: int) -> WalletAccountRead:
        account = self._require_wallet(account_id)
        self._set_active(account, False)
        self._session.flush()
        return self._to_read(account)

    def adjust_balance(self, account_id: int, payload: WalletBalanceAdjust) -> WalletAccountRead:
        account = self._require_wallet(account_id)
        if not account.is_active:
            raise AccountingError("숨긴 계좌는 잔액을 맞출 수 없어요.")
        book_balance = self._current_balance(account)
        delta = payload.actual_balance - book_balance
        if delta == 0:
            raise AccountingError("장부 잔액과 같아요. 맞출 금액이 없어요.")
        memo = payload.memo.strip() if payload.memo else None
        description = memo or f"잔액 맞추기: {account.name}"
        self._accounting.post_capital_adjustment(
            organization_id=account.organization_id,
            wallet=account,
            amount_delta=delta,
            occurred_on=payload.occurred_on,
            description=description,
        )
        return self._to_read(account)

    def _set_active(self, account: Account, is_active: bool) -> None:
        if not is_active and self._repo.referenced_as_settlement(account.id):
            raise AccountingError("카드 결제 계좌로 쓰이는 통장은 먼저 연결을 바꿔 주세요.")
        account.is_active = is_active

    def _require_organization(self, organization_id: int) -> Organization:
        organization = self._session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("조직을 찾을 수 없습니다.")
        return organization

    def _require_wallet(self, account_id: int) -> Account:
        account = self._repo.get(account_id)
        if account is None or account.instrument_kind is None:
            raise LookupError("자산/계좌를 찾을 수 없습니다.")
        return account

    def _require_parent(self, organization_id: int, kind: PaymentInstrumentKind) -> Account:
        parent = self._repo.get_by_code(organization_id, KIND_PARENT_CODE[kind])
        if parent is None:
            raise AccountingError("연결할 계정과목을 찾을 수 없습니다.")
        return parent

    def _require_settlement_bank(self, organization_id: int, settlement_account_id: int | None) -> Account:
        if settlement_account_id is None:
            raise AccountingError("카드는 결제 계좌를 선택해 주세요.")
        bank = self._repo.get(settlement_account_id)
        if (
            bank is None
            or bank.organization_id != organization_id
            or bank.instrument_kind != PaymentInstrumentKind.BANK
            or not bank.is_active
        ):
            raise AccountingError("결제 계좌는 사용 중인 은행계좌여야 해요.")
        return bank

    def _next_child_code(self, organization_id: int, parent: Account) -> str:
        used = self._repo.list_codes(organization_id)
        if parent.code.isdigit():
            base = int(parent.code)
            for offset in range(1, 1000):
                candidate = str(base + offset)
                if candidate not in used:
                    return candidate
        suffix = 1
        while True:
            candidate = f"{parent.code}-{suffix}"
            if candidate not in used:
                return candidate
            suffix += 1

    def _current_balance(self, account: Account) -> int:
        ledgers = self._ledger.account_ledgers(
            organization_id=account.organization_id,
            account_id=account.id,
        )
        if not ledgers:
            return 0
        return ledgers[0].closing_balance

    def _to_read(self, account: Account) -> WalletAccountRead:
        kind = account.instrument_kind
        if kind is None:
            raise LookupError("자산/계좌를 찾을 수 없습니다.")
        return WalletAccountRead(
            id=account.id,
            organization_id=account.organization_id,
            name=account.name,
            instrument_kind=kind,
            currency=account.currency,
            opening_balance=int(account.opening_balance),
            chart_code=account.code,
            sort_order=account.sort_order,
            is_active=account.is_active,
            is_system=account.is_system,
            institution=account.institution,
            card_payment_day=account.card_payment_day,
            settlement_account_id=account.settlement_account_id,
            current_balance=self._current_balance(account),
        )
