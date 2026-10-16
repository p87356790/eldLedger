from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Account, CardStatement, Transaction, TransactionItem, User
from app.models.enums import BillStatus, PaymentInstrumentKind, RecordStatus, Scope, TransactionType
from app.schemas.accounting import TransactionCreate
from app.schemas.card_statements import CardStatementLine, CardStatementPay, CardStatementRead, CardStatementUpdate
from app.services.accounting_service import AccountingError
from app.services.transaction_service import TransactionService


class CardStatementService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transactions = TransactionService(session)

    def list_statements(self, user: User) -> list[CardStatementRead]:
        self._sync(user)
        rows = list(
            self._session.scalars(
                select(CardStatement)
                .options(
                    selectinload(CardStatement.card_account),
                    selectinload(CardStatement.bank_account),
                )
                .where(CardStatement.organization_id == user.organization_id)
                .where(CardStatement.created_by_user_id == user.id)
            )
        )
        rows.sort(key=_sort_key)
        return [self._to_read(user, row) for row in rows]

    def update_amount(self, user: User, statement_id: int, payload: CardStatementUpdate) -> CardStatementRead:
        statement = self._require_own(user, statement_id)
        if statement.status != BillStatus.OPEN:
            raise AccountingError("이미 납부한 정산은 금액을 바꿀 수 없어요.")
        statement.amount = payload.amount
        statement.amount_locked = True
        self._session.flush()
        return self._to_read(user, statement)

    def pay(self, user: User, statement_id: int, payload: CardStatementPay) -> CardStatementRead:
        statement = self._require_own(user, statement_id)
        if statement.status != BillStatus.OPEN:
            raise AccountingError("이미 납부한 정산이에요.")
        bank_id = statement.bank_account_id
        if bank_id is None and statement.card_account.settlement_account_id is not None:
            bank_id = statement.card_account.settlement_account_id
        if bank_id is None:
            raise AccountingError("카드에 결제 계좌를 연결해 주세요.")
        bank = self._session.get(Account, bank_id)
        if bank is None or bank.owner_user_id != user.id or bank.instrument_kind != PaymentInstrumentKind.BANK:
            raise AccountingError("결제 계좌는 사용 중인 은행계좌여야 해요.")
        title = _title(statement.period_start, statement.card_account.name)
        transaction = self._transactions.create(
            TransactionCreate(
                organization_id=statement.organization_id,
                occurred_on=payload.occurred_on,
                transaction_type=TransactionType.TRANSFER,
                scope=Scope.PERSONAL,
                amount=int(statement.amount),
                merchant=title,
                memo=statement.card_account.name,
                payment_account_id=bank.id,
                transfer_account_id=statement.card_account_id,
            ),
            created_by_user_id=user.id,
        )
        statement.status = BillStatus.PAID
        statement.paid_on = payload.occurred_on
        statement.transaction_id = transaction.id
        statement.bank_account_id = bank.id
        self._session.flush()
        return self._to_read(user, statement)

    def _sync(self, user: User) -> None:
        cards = list(
            self._session.scalars(
                select(Account).where(
                    Account.organization_id == user.organization_id,
                    Account.owner_user_id == user.id,
                    Account.instrument_kind == PaymentInstrumentKind.CREDIT_CARD,
                )
            )
        )
        if not cards:
            return
        existing = {
            (row.card_account_id, row.period_start): row
            for row in self._session.scalars(
                select(CardStatement)
                .options(selectinload(CardStatement.transaction))
                .where(CardStatement.created_by_user_id == user.id)
            )
        }
        closed_before = date(date.today().year, date.today().month, 1)
        for card in cards:
            for period_start in self._usage_months(user, card.id, before=closed_before):
                period_end = _month_end(period_start)
                net = self._usage_net(user, card.id, period_start, period_end)
                current = existing.get((card.id, period_start))
                if current is None:
                    if net > 0:
                        self._session.add(
                            CardStatement(
                                organization_id=user.organization_id,
                                created_by_user_id=user.id,
                                card_account_id=card.id,
                                bank_account_id=card.settlement_account_id,
                                period_start=period_start,
                                period_end=period_end,
                                pay_on=_payment_date(period_start, card.card_payment_day or 1),
                                amount=net,
                                amount_locked=False,
                                status=BillStatus.OPEN,
                            )
                        )
                    continue
                if current.status == BillStatus.PAID:
                    paid = current.transaction
                    if paid is not None and paid.status != RecordStatus.REVERSED:
                        continue
                    current.status = BillStatus.OPEN
                    current.paid_on = None
                    current.transaction_id = None
                if current.amount_locked:
                    continue
                if net <= 0:
                    self._session.delete(current)
                    continue
                current.amount = net
        self._session.flush()

    def _usage_months(self, user: User, card_id: int, *, before: date) -> list[date]:
        dates = self._session.scalars(
            select(Transaction.occurred_on).where(
                Transaction.created_by_user_id == user.id,
                Transaction.payment_account_id == card_id,
                Transaction.status != RecordStatus.REVERSED,
                Transaction.transaction_type.in_((TransactionType.EXPENSE, TransactionType.INCOME)),
                Transaction.occurred_on < before,
            )
        )
        months = {date(day.year, day.month, 1) for day in dates}
        return sorted(months)

    def _usage_net(self, user: User, card_id: int, start: date, end: date) -> int:
        rows = self._usage_rows(user, card_id, start, end)
        total = 0
        for row in rows:
            if row.transaction_type == TransactionType.EXPENSE:
                total += int(row.amount)
            else:
                total -= int(row.amount)
        return total

    def _usage_rows(self, user: User, card_id: int, start: date, end: date) -> list[Transaction]:
        return list(
            self._session.scalars(
                select(Transaction)
                .options(selectinload(Transaction.items).selectinload(TransactionItem.category))
                .where(
                    Transaction.created_by_user_id == user.id,
                    Transaction.payment_account_id == card_id,
                    Transaction.status != RecordStatus.REVERSED,
                    Transaction.transaction_type.in_((TransactionType.EXPENSE, TransactionType.INCOME)),
                    Transaction.occurred_on >= start,
                    Transaction.occurred_on <= end,
                )
                .order_by(Transaction.occurred_on, Transaction.id)
            )
        )

    def _require_own(self, user: User, statement_id: int) -> CardStatement:
        statement = self._session.scalar(
            select(CardStatement)
            .options(
                selectinload(CardStatement.card_account),
                selectinload(CardStatement.bank_account),
                selectinload(CardStatement.transaction),
            )
            .where(CardStatement.id == statement_id)
            .where(CardStatement.created_by_user_id == user.id)
        )
        if statement is None:
            raise LookupError("카드 정산을 찾을 수 없어요.")
        return statement

    def _to_read(self, user: User, statement: CardStatement) -> CardStatementRead:
        card_name = statement.card_account.name if statement.card_account is not None else "카드"
        bank_name = statement.bank_account.name if statement.bank_account is not None else None
        lines = [
            CardStatementLine(
                transaction_id=row.id,
                occurred_on=row.occurred_on,
                label=_line_label(row),
                signed_amount=int(row.amount) if row.transaction_type == TransactionType.EXPENSE else -int(row.amount),
            )
            for row in self._usage_rows(user, statement.card_account_id, statement.period_start, statement.period_end)
        ]
        book_amount = sum(line.signed_amount for line in lines)
        return CardStatementRead(
            id=statement.id,
            card_account_id=statement.card_account_id,
            card_name=card_name,
            bank_account_id=statement.bank_account_id,
            bank_name=bank_name,
            title=_title(statement.period_start, card_name),
            period_start=statement.period_start,
            period_end=statement.period_end,
            pay_on=statement.pay_on,
            amount=int(statement.amount),
            book_amount=book_amount,
            amount_locked=statement.amount_locked,
            status=statement.status,
            paid_on=statement.paid_on,
            transaction_id=statement.transaction_id,
            lines=lines,
        )


def _month_end(period_start: date) -> date:
    return date(period_start.year, period_start.month, monthrange(period_start.year, period_start.month)[1])


def _payment_date(period_start: date, payment_day: int) -> date:
    year = period_start.year + (1 if period_start.month == 12 else 0)
    month = 1 if period_start.month == 12 else period_start.month + 1
    return date(year, month, payment_day)


def _title(period_start: date, card_name: str) -> str:
    return f"{period_start.month}월 {card_name} 정산"


def _line_label(transaction: Transaction) -> str:
    names: list[str] = []
    for item in transaction.items:
        if item.category is not None and item.category.name and item.category.name not in names:
            names.append(item.category.name)
    head = (transaction.merchant or transaction.memo or "").strip()
    cats = ", ".join(names)
    if head and cats:
        return f"{head} · {cats}"
    return head or cats or "카드 사용"


def _sort_key(statement: CardStatement) -> tuple[int, int, int]:
    if statement.status == BillStatus.OPEN:
        return (0, statement.pay_on.toordinal(), statement.id)
    paid = statement.paid_on or statement.pay_on
    return (1, -paid.toordinal(), -statement.id)
