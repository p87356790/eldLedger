from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Account, JournalEntry, JournalLine, Transaction, TransactionItem
from app.models.enums import RecordStatus, Scope, TransactionType
from app.services.journal_balance import UnbalancedJournalError


def _account(session: Session, code: str) -> Account:
    account = session.scalar(select(Account).where(Account.code == code))
    assert account is not None
    return account


def test_transaction_and_journal_are_separate_tables() -> None:
    assert Transaction.__tablename__ == "transactions"
    assert JournalEntry.__tablename__ == "journal_entries"
    assert Transaction.__table__ is not JournalEntry.__table__


def test_office_supply_example_persists_balanced_journal(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()

    payable = _account(db_session, "2100")
    housing = _account(db_session, "5800")
    category = next(c for c in organization.categories if c.name == "관리비")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.BUSINESS,
        amount=50_000,
        memo="관리비 결제",
        status=RecordStatus.CONFIRMED,
        payment_account_id=payable.id,
        items=[
            TransactionItem(
                category_id=category.id,
                account_id=housing.id,
                amount=50_000,
                scope=Scope.BUSINESS,
                line_no=1,
            )
        ],
    )
    entry = JournalEntry(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        description="국민카드로 관리비 50,000원",
        status=RecordStatus.CONFIRMED,
        transaction=transaction,
        lines=[
            JournalLine(account_id=housing.id, debit_amount=50_000, credit_amount=0, line_no=1),
            JournalLine(account_id=payable.id, debit_amount=0, credit_amount=50_000, line_no=2),
        ],
    )
    db_session.add(transaction)
    db_session.add(entry)
    db_session.flush()

    assert entry.id is not None
    assert transaction.id is not None
    assert entry.transaction_id == transaction.id
    assert sum(line.debit_amount for line in entry.lines) == sum(line.credit_amount for line in entry.lines)


def test_unbalanced_journal_cannot_be_flushed(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    supplies = _account(db_session, "5100")
    payable = _account(db_session, "2100")

    entry = JournalEntry(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        lines=[
            JournalLine(account_id=supplies.id, debit_amount=50_000, credit_amount=0, line_no=1),
            JournalLine(account_id=payable.id, debit_amount=0, credit_amount=40_000, line_no=2),
        ],
    )
    db_session.add(entry)
    with pytest.raises(UnbalancedJournalError):
        db_session.flush()


def test_mixed_transaction_items_and_matching_journal(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    payable = _account(db_session, "2100")
    supplies = _account(db_session, "5100")
    personal = _account(db_session, "5700")

    transaction = Transaction(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction_type=TransactionType.EXPENSE,
        scope=Scope.MIXED,
        amount=100_000,
        payment_account_id=payable.id,
        items=[
            TransactionItem(account_id=supplies.id, amount=30_000, scope=Scope.BUSINESS, line_no=1),
            TransactionItem(account_id=personal.id, amount=70_000, scope=Scope.PERSONAL, line_no=2),
        ],
    )
    entry = JournalEntry(
        organization_id=organization.id,
        occurred_on=date(2026, 9, 1),
        transaction=transaction,
        lines=[
            JournalLine(account_id=supplies.id, debit_amount=30_000, credit_amount=0, line_no=1),
            JournalLine(account_id=personal.id, debit_amount=70_000, credit_amount=0, line_no=2),
            JournalLine(account_id=payable.id, debit_amount=0, credit_amount=100_000, line_no=3),
        ],
    )
    db_session.add_all([transaction, entry])
    db_session.flush()
    assert sum(item.amount for item in transaction.items) == transaction.amount
    assert sum(line.debit_amount for line in entry.lines) == 100_000
    assert sum(line.credit_amount for line in entry.lines) == 100_000
