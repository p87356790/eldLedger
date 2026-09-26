from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, JournalEntry, JournalLine, Transaction, TransactionItem
from app.models.enums import NormalBalance, RecordStatus, Scope, TransactionType
from app.repositories.journal_repository import JournalRepository
from app.services.journal_balance import assert_journal_balanced, collect_line_amounts
from app.services.transaction_amounts import ItemAmountError, is_deduction_item, partition_items, validate_item_amounts


class AccountingError(ValueError):
    """Raised when a transaction cannot be converted into a balanced journal."""


class AccountingService:
    """Turns user-facing cashbook transactions into double-entry journals."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._journals = JournalRepository(session)

    def post_transaction(self, transaction: Transaction) -> JournalEntry:
        self._validate_transaction(transaction)
        self._session.add(transaction)
        self._session.flush()

        if transaction.id is not None and self._journals.active_for_transaction(transaction.id) is not None:
            raise AccountingError("이미 확정된 분개가 있습니다. 수정 시 역분개 후 재생성해야 합니다.")

        entry = self._build_journal(transaction)
        self._assert_balanced(entry)
        transaction.status = RecordStatus.CONFIRMED
        self._journals.add(entry)
        self._session.flush()
        return entry

    def correct_transaction(self, transaction: Transaction) -> JournalEntry:
        if transaction.status == RecordStatus.REVERSED:
            raise AccountingError("취소된 거래는 수정할 수 없습니다.")
        if transaction.id is not None:
            active = self._journals.active_for_transaction(transaction.id)
            if active is not None:
                self._reverse_entry(active)
                self._session.flush()
        return self.post_transaction(transaction)

    def cancel_transaction(self, transaction: Transaction) -> JournalEntry:
        if transaction.id is None:
            raise AccountingError("저장되지 않은 거래는 취소할 수 없습니다.")
        active = self._journals.active_for_transaction(transaction.id)
        if active is None:
            raise AccountingError("확정된 분개가 없어 취소할 수 없습니다.")
        reversal = self._reverse_entry(active)
        transaction.status = RecordStatus.REVERSED
        self._session.flush()
        return reversal

    def _reverse_entry(self, original: JournalEntry) -> JournalEntry:
        if original.status != RecordStatus.CONFIRMED:
            raise AccountingError("확정된 분개만 역분개할 수 있습니다.")
        if original.id is None:
            self._session.flush()
        if original.id is None:
            raise AccountingError("분개 ID를 생성할 수 없습니다.")

        reversal_lines = [
            JournalLine(
                account_id=line.account_id,
                debit_amount=line.credit_amount,
                credit_amount=line.debit_amount,
                memo=line.memo,
                line_no=index,
                transaction_item_id=line.transaction_item_id,
            )
            for index, line in enumerate(_ordered_lines(original.lines), start=1)
        ]
        reversal = JournalEntry(
            organization_id=original.organization_id,
            transaction_id=original.transaction_id,
            occurred_on=original.occurred_on,
            description=_reversal_description(original.description),
            status=RecordStatus.CONFIRMED,
            reverses_entry_id=original.id,
            lines=reversal_lines,
        )
        self._assert_balanced(reversal)
        original.status = RecordStatus.REVERSED
        self._journals.add(reversal)
        return reversal

    def post_capital_adjustment(
        self,
        *,
        organization_id: int,
        wallet: Account,
        amount_delta: int,
        occurred_on: date,
        description: str,
    ) -> JournalEntry:
        if amount_delta == 0:
            raise AccountingError("바꿀 금액이 없어요.")
        if not wallet.is_postable:
            raise AccountingError("이 계좌에는 잔액을 넣을 수 없어요.")
        equity = self._account_by_code(organization_id, "3100")
        abs_amount = abs(amount_delta)
        increase = amount_delta > 0
        if wallet.normal_balance == NormalBalance.DEBIT:
            wallet_debit, wallet_credit = (abs_amount, 0) if increase else (0, abs_amount)
            equity_debit, equity_credit = (0, abs_amount) if increase else (abs_amount, 0)
        else:
            wallet_debit, wallet_credit = (0, abs_amount) if increase else (abs_amount, 0)
            equity_debit, equity_credit = (abs_amount, 0) if increase else (0, abs_amount)

        entry = JournalEntry(
            organization_id=organization_id,
            transaction_id=None,
            occurred_on=occurred_on,
            description=description,
            status=RecordStatus.CONFIRMED,
            lines=[
                JournalLine(
                    account_id=wallet.id,
                    debit_amount=wallet_debit,
                    credit_amount=wallet_credit,
                    memo=description,
                    line_no=1,
                ),
                JournalLine(
                    account_id=equity.id,
                    debit_amount=equity_debit,
                    credit_amount=equity_credit,
                    memo=description,
                    line_no=2,
                ),
            ],
        )
        self._assert_balanced(entry)
        self._journals.add(entry)
        self._session.flush()
        return entry

    def _account_by_code(self, organization_id: int, code: str) -> Account:
        account = self._session.scalar(
            select(Account).where(Account.organization_id == organization_id, Account.code == code)
        )
        if account is None:
            raise AccountingError("자본 계정을 찾을 수 없습니다.")
        return account

    def _build_journal(self, transaction: Transaction) -> JournalEntry:
        if transaction.transaction_type == TransactionType.TRANSFER:
            lines = self._transfer_lines(transaction)
        elif transaction.transaction_type == TransactionType.INCOME:
            lines = self._income_lines(transaction)
        elif transaction.transaction_type == TransactionType.EXPENSE:
            lines = self._expense_lines(transaction)
        else:
            raise AccountingError("지원하지 않는 거래 유형입니다.")

        entry = JournalEntry(
            organization_id=transaction.organization_id,
            transaction_id=transaction.id,
            occurred_on=transaction.occurred_on,
            description=_journal_description(transaction),
            status=RecordStatus.CONFIRMED,
            lines=lines,
        )
        self._assert_balanced(entry)
        return entry

    def _expense_lines(self, transaction: Transaction) -> list[JournalLine]:
        items = self._required_items(transaction)
        lines: list[JournalLine] = []
        line_no = 1
        for item in items:
            account = self._item_posting_account(item, expected_type=TransactionType.EXPENSE)
            lines.append(
                JournalLine(
                    account_id=account.id,
                    debit_amount=item.amount,
                    credit_amount=0,
                    memo=item.memo or transaction.memo,
                    line_no=line_no,
                    transaction_item_id=item.id,
                )
            )
            line_no += 1
        payment = self._require_postable_account(transaction.payment_account_id, "결제수단")
        lines.append(
            JournalLine(
                account_id=payment.id,
                debit_amount=0,
                credit_amount=transaction.amount,
                memo=transaction.memo,
                line_no=line_no,
            )
        )
        return lines

    def _income_lines(self, transaction: Transaction) -> list[JournalLine]:
        items = self._required_items(transaction)
        standard_items, deduction_items = partition_items(items)
        payment = self._require_postable_account(transaction.payment_account_id, "입금계좌")
        lines: list[JournalLine] = [
            JournalLine(
                account_id=payment.id,
                debit_amount=transaction.amount,
                credit_amount=0,
                memo=transaction.memo,
                line_no=1,
            )
        ]
        line_no = 2
        for item in deduction_items:
            account = self._item_posting_account(item, expected_type=TransactionType.EXPENSE)
            lines.append(
                JournalLine(
                    account_id=account.id,
                    debit_amount=item.amount,
                    credit_amount=0,
                    memo=item.memo or transaction.memo,
                    line_no=line_no,
                    transaction_item_id=item.id,
                )
            )
            line_no += 1
        for item in standard_items:
            account = self._item_posting_account(item, expected_type=TransactionType.INCOME)
            lines.append(
                JournalLine(
                    account_id=account.id,
                    debit_amount=0,
                    credit_amount=item.amount,
                    memo=item.memo or transaction.memo,
                    line_no=line_no,
                    transaction_item_id=item.id,
                )
            )
            line_no += 1
        return lines

    def _transfer_lines(self, transaction: Transaction) -> list[JournalLine]:
        if transaction.transfer_account_id is None:
            raise AccountingError("이체는 상대 계정이 필요합니다.")
        if transaction.transfer_account_id == transaction.payment_account_id:
            raise AccountingError("이체의 출금 계정과 입금 계정이 같을 수 없습니다.")
        source = self._require_postable_account(transaction.payment_account_id, "출금 계정")
        destination = self._require_postable_account(transaction.transfer_account_id, "입금 계정")
        return [
            JournalLine(
                account_id=destination.id,
                debit_amount=transaction.amount,
                credit_amount=0,
                memo=transaction.memo,
                line_no=1,
            ),
            JournalLine(
                account_id=source.id,
                debit_amount=0,
                credit_amount=transaction.amount,
                memo=transaction.memo,
                line_no=2,
            ),
        ]

    def _required_items(self, transaction: Transaction) -> list[TransactionItem]:
        items = _ordered_items(transaction.items)
        if not items:
            raise AccountingError("수입/지출 거래는 분류 항목이 필요합니다.")
        try:
            validate_item_amounts(
                transaction_type=transaction.transaction_type,
                amount=transaction.amount,
                items=items,
            )
        except ItemAmountError as exc:
            raise AccountingError(str(exc)) from exc
        if transaction.scope == Scope.MIXED and any(item.scope == Scope.MIXED for item in items):
            raise AccountingError("혼합 거래의 각 항목은 개인 또는 사업으로 지정해야 합니다.")
        return items

    def _item_posting_account(
        self,
        item: TransactionItem,
        *,
        expected_type: TransactionType | None = None,
    ) -> Account:
        account: Account | None = item.account
        if account is None and item.account_id is not None:
            account = self._session.get(Account, item.account_id)
        category: Category | None = item.category
        if category is None and item.category_id is not None:
            category = self._session.get(Category, item.category_id)
            if category is None:
                raise AccountingError("분류를 찾을 수 없습니다.")
        if expected_type is not None and category is not None and category.transaction_type != expected_type:
            if expected_type == TransactionType.INCOME:
                raise AccountingError("수입 분류를 골라 주세요.")
            if is_deduction_item(item):
                raise AccountingError("공제 분류는 지출 항목에서 골라 주세요.")
            raise AccountingError("지출 분류를 골라 주세요.")
        if account is None and category is not None:
            account = category.account
            if account is None:
                account = self._session.get(Account, category.account_id)
        if account is None:
            raise AccountingError("거래 항목에 분류 또는 계정과목이 필요합니다.")
        return self._ensure_postable(account, "분류 계정")

    def _require_postable_account(self, account_id: int, label: str) -> Account:
        account = self._session.get(Account, account_id)
        if account is None:
            raise AccountingError(f"{label} 계정을 찾을 수 없습니다.")
        return self._ensure_postable(account, label)

    def _ensure_postable(self, account: Account, label: str) -> Account:
        if not account.is_postable:
            raise AccountingError(f"{label} '{account.name}'은(는) 분개에 사용할 수 없는 상위 계정입니다.")
        if not account.is_active:
            raise AccountingError(f"{label} '{account.name}'은(는) 사용 중지된 계정입니다.")
        return account

    def _validate_transaction(self, transaction: Transaction) -> None:
        if transaction.amount <= 0:
            raise AccountingError("거래 금액은 0보다 큰 정수여야 합니다.")
        if transaction.status == RecordStatus.REVERSED:
            raise AccountingError("취소된 거래는 다시 분개할 수 없습니다.")
        if transaction.scope == Scope.MIXED and not transaction.items:
            raise AccountingError("혼합 거래는 개인/사업 항목 분할이 필요합니다.")
        if transaction.items:
            try:
                validate_item_amounts(
                    transaction_type=transaction.transaction_type,
                    amount=transaction.amount,
                    items=transaction.items,
                )
            except ItemAmountError as exc:
                raise AccountingError(str(exc)) from exc
        if transaction.transaction_type == TransactionType.TRANSFER and transaction.transfer_account_id is None:
            raise AccountingError("이체는 상대 계정이 필요합니다.")

    def _assert_balanced(self, entry: JournalEntry) -> None:
        assert_journal_balanced(collect_line_amounts(entry.lines))


def _ordered_items(items: Sequence[TransactionItem]) -> list[TransactionItem]:
    return sorted(items, key=lambda item: (item.line_no, item.id or 0))


def _ordered_lines(lines: Sequence[JournalLine]) -> list[JournalLine]:
    return sorted(lines, key=lambda line: (line.line_no, line.id or 0))


def _journal_description(transaction: Transaction) -> str:
    labels = {
        TransactionType.INCOME: "수입",
        TransactionType.EXPENSE: "지출",
        TransactionType.TRANSFER: "이체",
    }
    label = labels[transaction.transaction_type]
    if transaction.memo:
        return f"{label}: {transaction.memo}"
    return label


def _reversal_description(original_description: str | None) -> str:
    if original_description:
        return f"역분개: {original_description}"
    return "역분개"
