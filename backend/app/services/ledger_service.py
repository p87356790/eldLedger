from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Account, JournalEntry, JournalLine, Transaction, TransactionItem
from app.models.enums import AccountType, NormalBalance, RecordStatus, Scope, TransactionType
from app.schemas.reports import (
    AccountLedger,
    AccountLedgerLine,
    JournalBookEntry,
    JournalBookLine,
    TransactionLedgerRow,
    TrialBalanceResponse,
    TrialBalanceRow,
)


@dataclass(frozen=True)
class LedgerLine:
    occurred_on: date
    journal_entry_id: int
    transaction_id: int | None
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    normal_balance: NormalBalance
    description: str | None
    debit_amount: int
    credit_amount: int


class LedgerService:
    """Builds ledgers and the trial balance from confirmed journal lines."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def collect_lines(
        self,
        *,
        organization_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: int | None = None,
        business_only: bool = False,
    ) -> list[LedgerLine]:
        stmt = (
            select(JournalLine, JournalEntry, Account, Transaction, TransactionItem)
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(Account, JournalLine.account_id == Account.id)
            .outerjoin(Transaction, JournalEntry.transaction_id == Transaction.id)
            .outerjoin(TransactionItem, JournalLine.transaction_item_id == TransactionItem.id)
            .where(JournalEntry.organization_id == organization_id)
            .where(JournalEntry.status == RecordStatus.CONFIRMED)
            .order_by(JournalEntry.occurred_on, JournalEntry.id, JournalLine.line_no, JournalLine.id)
        )
        if date_from is not None:
            stmt = stmt.where(JournalEntry.occurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(JournalEntry.occurred_on <= date_to)
        if account_id is not None:
            stmt = stmt.where(JournalLine.account_id == account_id)

        rows = self._session.execute(stmt).all()
        business_totals = self._business_item_totals(
            {transaction.id for _line, _entry, _account, transaction, _item in rows if transaction is not None}
        )

        lines: list[LedgerLine] = []
        for line, entry, account, transaction, item in rows:
            adjusted = self._adjust_line(
                line=line,
                transaction=transaction,
                item=item,
                business_only=business_only,
                business_totals=business_totals,
            )
            if adjusted is None:
                continue
            debit_amount, credit_amount = adjusted
            lines.append(
                LedgerLine(
                    occurred_on=entry.occurred_on,
                    journal_entry_id=entry.id,
                    transaction_id=entry.transaction_id,
                    account_id=account.id,
                    account_code=account.code,
                    account_name=account.name,
                    account_type=account.account_type,
                    normal_balance=account.normal_balance,
                    description=line.memo or entry.description,
                    debit_amount=debit_amount,
                    credit_amount=credit_amount,
                )
            )
        return lines

    def transaction_ledger(
        self,
        *,
        organization_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: int | None = None,
        business_only: bool = False,
    ) -> list[TransactionLedgerRow]:
        return [
            TransactionLedgerRow(
                occurred_on=line.occurred_on,
                account_code=line.account_code,
                account_name=line.account_name,
                description=line.description,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                journal_entry_id=line.journal_entry_id,
                transaction_id=line.transaction_id,
            )
            for line in self.collect_lines(
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
                account_id=account_id,
                business_only=business_only,
            )
        ]

    def journal_book(
        self,
        *,
        organization_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: int | None = None,
        business_only: bool = False,
    ) -> list[JournalBookEntry]:
        grouped: dict[int, list[LedgerLine]] = defaultdict(list)
        for line in self.collect_lines(
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            account_id=account_id,
            business_only=business_only,
        ):
            grouped[line.journal_entry_id].append(line)

        books: list[JournalBookEntry] = []
        for entry_id, entry_lines in grouped.items():
            first = entry_lines[0]
            debit_total = sum(line.debit_amount for line in entry_lines)
            credit_total = sum(line.credit_amount for line in entry_lines)
            if debit_total == 0 and credit_total == 0:
                continue
            books.append(
                JournalBookEntry(
                    journal_entry_id=entry_id,
                    occurred_on=first.occurred_on,
                    description=first.description,
                    transaction_id=first.transaction_id,
                    debit_total=debit_total,
                    credit_total=credit_total,
                    lines=[
                        JournalBookLine(
                            account_code=line.account_code,
                            account_name=line.account_name,
                            debit_amount=line.debit_amount,
                            credit_amount=line.credit_amount,
                            memo=line.description,
                        )
                        for line in entry_lines
                    ],
                )
            )
        books.sort(key=lambda entry: (entry.occurred_on, entry.journal_entry_id))
        return books

    def account_ledgers(
        self,
        *,
        organization_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: int | None = None,
        business_only: bool = False,
    ) -> list[AccountLedger]:
        grouped: dict[int, list[LedgerLine]] = defaultdict(list)
        for line in self.collect_lines(
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            account_id=account_id,
            business_only=business_only,
        ):
            grouped[line.account_id].append(line)

        ledgers: list[AccountLedger] = []
        for account_id, account_lines in grouped.items():
            first = account_lines[0]
            running = 0
            ledger_lines: list[AccountLedgerLine] = []
            for line in account_lines:
                if first.normal_balance == NormalBalance.DEBIT:
                    running += line.debit_amount - line.credit_amount
                else:
                    running += line.credit_amount - line.debit_amount
                ledger_lines.append(
                    AccountLedgerLine(
                        occurred_on=line.occurred_on,
                        description=line.description,
                        debit_amount=line.debit_amount,
                        credit_amount=line.credit_amount,
                        balance=running,
                        journal_entry_id=line.journal_entry_id,
                    )
                )
            ledgers.append(
                AccountLedger(
                    account_id=account_id,
                    account_code=first.account_code,
                    account_name=first.account_name,
                    account_type=first.account_type,
                    normal_balance=first.normal_balance,
                    debit_total=sum(line.debit_amount for line in account_lines),
                    credit_total=sum(line.credit_amount for line in account_lines),
                    closing_balance=running,
                    lines=ledger_lines,
                )
            )
        ledgers.sort(key=lambda ledger: ledger.account_code)
        return ledgers

    def trial_balance(
        self,
        *,
        organization_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: int | None = None,
        business_only: bool = False,
    ) -> TrialBalanceResponse:
        totals: dict[int, TrialBalanceRow] = {}
        for line in self.collect_lines(
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            account_id=account_id,
            business_only=business_only,
        ):
            row = totals.get(line.account_id)
            if row is None:
                row = TrialBalanceRow(
                    account_id=line.account_id,
                    account_code=line.account_code,
                    account_name=line.account_name,
                    account_type=line.account_type,
                    debit_total=0,
                    credit_total=0,
                )
            totals[line.account_id] = TrialBalanceRow(
                account_id=row.account_id,
                account_code=row.account_code,
                account_name=row.account_name,
                account_type=row.account_type,
                debit_total=row.debit_total + line.debit_amount,
                credit_total=row.credit_total + line.credit_amount,
            )
        rows = sorted(totals.values(), key=lambda row: row.account_code)
        debit_total = sum(row.debit_total for row in rows)
        credit_total = sum(row.credit_total for row in rows)
        return TrialBalanceResponse(
            debit_total=debit_total,
            credit_total=credit_total,
            is_balanced=debit_total == credit_total,
            rows=rows,
        )

    def business_transaction_amounts(
        self,
        *,
        organization_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[int, int, int]:
        """Returns (income_total, expense_total, transaction_count) for BUSINESS activity."""
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.items))
            .where(Transaction.organization_id == organization_id)
        )
        stmt = stmt.where(Transaction.status != RecordStatus.REVERSED)
        stmt = stmt.where(Transaction.scope.in_((Scope.BUSINESS, Scope.MIXED)))
        if date_from is not None:
            stmt = stmt.where(Transaction.occurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.occurred_on <= date_to)
        transactions = self._session.scalars(stmt).all()

        income_total = 0
        expense_total = 0
        count = 0
        for transaction in transactions:
            amount = self.reported_business_amount(transaction)
            if amount <= 0:
                continue
            count += 1
            if transaction.transaction_type == TransactionType.INCOME:
                income_total += amount
            elif transaction.transaction_type == TransactionType.EXPENSE:
                expense_total += amount
        return income_total, expense_total, count

    def reported_business_amount(self, transaction: Transaction) -> int:
        if transaction.scope == Scope.BUSINESS:
            return transaction.amount
        items = list(transaction.items)
        if not items:
            items = list(
                self._session.scalars(
                    select(TransactionItem).where(TransactionItem.transaction_id == transaction.id)
                )
            )
        return sum(item.amount for item in items if item.scope == Scope.BUSINESS)

    def _business_item_totals(self, transaction_ids: set[int]) -> dict[int, int]:
        if not transaction_ids:
            return {}
        items = self._session.scalars(
            select(TransactionItem).where(TransactionItem.transaction_id.in_(transaction_ids))
        )
        totals: dict[int, int] = defaultdict(int)
        for item in items:
            if item.scope == Scope.BUSINESS:
                totals[item.transaction_id] += item.amount
        return dict(totals)

    def _adjust_line(
        self,
        *,
        line: JournalLine,
        transaction: Transaction | None,
        item: TransactionItem | None,
        business_only: bool,
        business_totals: dict[int, int],
    ) -> tuple[int, int] | None:
        if not business_only:
            return line.debit_amount, line.credit_amount
        if transaction is None:
            return line.debit_amount, line.credit_amount
        if transaction.scope == Scope.PERSONAL:
            return None
        if transaction.scope == Scope.BUSINESS:
            return line.debit_amount, line.credit_amount

        if item is not None:
            if item.scope != Scope.BUSINESS:
                return None
            return line.debit_amount, line.credit_amount

        business_total = business_totals.get(transaction.id, 0)
        if business_total <= 0 or transaction.amount <= 0:
            return None
        if line.debit_amount == transaction.amount:
            return business_total, 0
        if line.credit_amount == transaction.amount:
            return 0, business_total
        return None
