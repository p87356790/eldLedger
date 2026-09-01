from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Account, Category, JournalEntry, JournalLine, Transaction, TransactionItem
from app.models.enums import RecordStatus, Scope, TransactionType
from app.services.accounting_service import AccountingError, AccountingService


def _account(session: Session, code: str) -> Account:
    account = session.scalar(select(Account).where(Account.code == code))
    assert account is not None
    return account


def _category(session: Session, name: str) -> Category:
    category = session.scalar(select(Category).where(Category.name == name))
    assert category is not None
    return category


def _debit_credit_totals(entry: JournalEntry) -> tuple[int, int]:
    debit_total = sum(line.debit_amount for line in entry.lines)
    credit_total = sum(line.credit_amount for line in entry.lines)
    return debit_total, credit_total


def _line_for_account(entry: JournalEntry, account_id: int) -> JournalLine:
    matched = [line for line in entry.lines if line.account_id == account_id]
    assert len(matched) == 1
    return matched[0]


def test_card_expense_50000_creates_balanced_journal(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    payable = _account(db_session, "2100")
    supplies = _account(db_session, "5100")
    office = _category(db_session, "사무용품")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.BUSINESS,
        amount=50_000,
        memo="프린터 용지",
        payment_account_id=payable.id,
        items=[
            TransactionItem(
                category_id=office.id,
                amount=50_000,
                scope=Scope.BUSINESS,
                line_no=1,
            )
        ],
    )

    entry = AccountingService(db_session).post_transaction(transaction)
    debit_total, credit_total = _debit_credit_totals(entry)

    assert transaction.status == RecordStatus.CONFIRMED
    assert entry.transaction_id == transaction.id
    assert debit_total == credit_total == 50_000
    assert _line_for_account(entry, supplies.id).debit_amount == 50_000
    assert _line_for_account(entry, supplies.id).credit_amount == 0
    assert _line_for_account(entry, payable.id).debit_amount == 0
    assert _line_for_account(entry, payable.id).credit_amount == 50_000


def test_mixed_mart_payment_100000_debits_and_credits_match(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    payable = _account(db_session, "2100")
    supplies = _account(db_session, "5100")
    personal_use = _account(db_session, "5700")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.MIXED,
        amount=100_000,
        memo="마트 혼합 결제",
        payment_account_id=payable.id,
        items=[
            TransactionItem(
                account_id=supplies.id,
                amount=30_000,
                scope=Scope.BUSINESS,
                memo="사업용품",
                line_no=1,
            ),
            TransactionItem(
                account_id=personal_use.id,
                amount=70_000,
                scope=Scope.PERSONAL,
                memo="개인생활용품",
                line_no=2,
            ),
        ],
    )

    entry = AccountingService(db_session).post_transaction(transaction)
    debit_total, credit_total = _debit_credit_totals(entry)

    assert debit_total == credit_total == 100_000
    assert _line_for_account(entry, supplies.id).debit_amount == 30_000
    assert _line_for_account(entry, personal_use.id).debit_amount == 70_000
    assert _line_for_account(entry, payable.id).credit_amount == 100_000
    assert sum(item.amount for item in transaction.items) == transaction.amount


def test_income_posts_bank_debit_and_revenue_credit(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    bank = _account(db_session, "1200")
    sales = _account(db_session, "4100")
    sales_category = _category(db_session, "사업매출")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.INCOME,
        scope=Scope.BUSINESS,
        amount=1_000_000,
        payment_account_id=bank.id,
        items=[
            TransactionItem(
                category_id=sales_category.id,
                amount=1_000_000,
                scope=Scope.BUSINESS,
                line_no=1,
            )
        ],
    )

    entry = AccountingService(db_session).post_transaction(transaction)
    debit_total, credit_total = _debit_credit_totals(entry)
    assert debit_total == credit_total == 1_000_000
    assert _line_for_account(entry, bank.id).debit_amount == 1_000_000
    assert _line_for_account(entry, sales.id).credit_amount == 1_000_000


def test_transfer_moves_between_asset_accounts(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    source = _account(db_session, "1200")
    destination = _account(db_session, "1100")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.TRANSFER,
        scope=Scope.PERSONAL,
        amount=500_000,
        payment_account_id=source.id,
        transfer_account_id=destination.id,
    )

    entry = AccountingService(db_session).post_transaction(transaction)
    debit_total, credit_total = _debit_credit_totals(entry)
    assert debit_total == credit_total == 500_000
    assert _line_for_account(entry, destination.id).debit_amount == 500_000
    assert _line_for_account(entry, source.id).credit_amount == 500_000


def test_correct_confirmed_transaction_reverses_then_reposts(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    payable = _account(db_session, "2100")
    supplies = _account(db_session, "5100")
    office = _category(db_session, "사무용품")
    service = AccountingService(db_session)

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.BUSINESS,
        amount=50_000,
        payment_account_id=payable.id,
        items=[
            TransactionItem(category_id=office.id, amount=50_000, scope=Scope.BUSINESS, line_no=1)
        ],
    )
    original = service.post_transaction(transaction)
    original_id = original.id

    transaction.amount = 55_000
    transaction.items[0].amount = 55_000
    replacement = service.correct_transaction(transaction)

    db_session.refresh(original)
    entries = list(
        db_session.scalars(select(JournalEntry).where(JournalEntry.transaction_id == transaction.id))
    )
    reversal = next(entry for entry in entries if entry.reverses_entry_id == original_id)

    assert original.status == RecordStatus.REVERSED
    assert reversal.status == RecordStatus.CONFIRMED
    assert _line_for_account(reversal, supplies.id).credit_amount == 50_000
    assert _line_for_account(reversal, payable.id).debit_amount == 50_000
    assert _debit_credit_totals(reversal) == (50_000, 50_000)
    assert _debit_credit_totals(replacement) == (55_000, 55_000)
    assert _line_for_account(replacement, supplies.id).debit_amount == 55_000
    assert transaction.status == RecordStatus.CONFIRMED
    assert replacement.id != original_id


def test_repost_without_reversal_is_rejected(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    payable = _account(db_session, "2100")
    office = _category(db_session, "사무용품")
    service = AccountingService(db_session)

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.BUSINESS,
        amount=50_000,
        payment_account_id=payable.id,
        items=[
            TransactionItem(category_id=office.id, amount=50_000, scope=Scope.BUSINESS, line_no=1)
        ],
    )
    service.post_transaction(transaction)
    with pytest.raises(AccountingError, match="이미 확정된 분개"):
        service.post_transaction(transaction)


def test_mixed_item_total_mismatch_is_rejected(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    payable = _account(db_session, "2100")
    supplies = _account(db_session, "5100")
    personal_use = _account(db_session, "5700")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.MIXED,
        amount=100_000,
        payment_account_id=payable.id,
        items=[
            TransactionItem(account_id=supplies.id, amount=30_000, scope=Scope.BUSINESS, line_no=1),
            TransactionItem(account_id=personal_use.id, amount=60_000, scope=Scope.PERSONAL, line_no=2),
        ],
    )
    with pytest.raises(AccountingError, match="항목 금액 합계"):
        AccountingService(db_session).post_transaction(transaction)
