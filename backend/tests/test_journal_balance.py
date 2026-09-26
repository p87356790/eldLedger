from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.accounting import JournalEntryCreate, JournalLineCreate, TransactionCreate, TransactionItemCreate
from app.services.journal_balance import InvalidJournalLineError, UnbalancedJournalError, assert_journal_balanced
from app.models.enums import Scope, TransactionItemKind, TransactionType


def test_balanced_expense_journal() -> None:
    assert_journal_balanced([(50_000, 0), (0, 50_000)])


def test_mixed_split_journal_is_balanced() -> None:
    assert_journal_balanced([(30_000, 0), (70_000, 0), (0, 100_000)])


def test_unbalanced_journal_is_rejected() -> None:
    with pytest.raises(UnbalancedJournalError) as exc_info:
        assert_journal_balanced([(50_000, 0), (0, 40_000)])
    assert exc_info.value.debit_total == 50_000
    assert exc_info.value.credit_total == 40_000


def test_empty_journal_is_rejected() -> None:
    with pytest.raises(UnbalancedJournalError):
        assert_journal_balanced([])


def test_line_must_be_debit_xor_credit() -> None:
    with pytest.raises(InvalidJournalLineError):
        assert_journal_balanced([(50_000, 50_000)])
    with pytest.raises(InvalidJournalLineError):
        assert_journal_balanced([(0, 0), (0, 0)])


def test_negative_amount_is_rejected() -> None:
    with pytest.raises(InvalidJournalLineError):
        assert_journal_balanced([(-1, 0), (0, 1)])


def test_journal_entry_schema_enforces_balance() -> None:
    with pytest.raises(ValidationError):
        JournalEntryCreate(
            organization_id=1,
            occurred_on=date(2026, 9, 1),
            lines=[
                JournalLineCreate(account_id=1, debit_amount=50_000, line_no=1),
                JournalLineCreate(account_id=2, credit_amount=40_000, line_no=2),
            ],
        )


def test_transaction_schema_requires_item_total_to_match() -> None:
    with pytest.raises(ValidationError):
        TransactionCreate(
            organization_id=1,
            occurred_on=date(2026, 9, 1),
            transaction_type=TransactionType.EXPENSE,
            scope=Scope.MIXED,
            amount=100_000,
            payment_account_id=1,
            items=[
                TransactionItemCreate(amount=30_000, scope=Scope.BUSINESS, line_no=1),
                TransactionItemCreate(amount=60_000, scope=Scope.PERSONAL, line_no=2),
            ],
        )


def test_income_with_deductions_schema_accepts_gross_minus_net() -> None:
    payload = TransactionCreate(
        organization_id=1,
        occurred_on=date(2026, 9, 25),
        transaction_type=TransactionType.INCOME,
        scope=Scope.PERSONAL,
        amount=4_200_000,
        payment_account_id=1,
        items=[
            TransactionItemCreate(
                amount=5_000_000,
                scope=Scope.PERSONAL,
                line_no=1,
                line_kind=TransactionItemKind.STANDARD,
            ),
            TransactionItemCreate(
                amount=800_000,
                scope=Scope.PERSONAL,
                line_no=2,
                line_kind=TransactionItemKind.DEDUCTION,
            ),
        ],
    )
    assert payload.amount == 4_200_000


def test_income_with_deductions_schema_rejects_unbalanced_net() -> None:
    with pytest.raises(ValidationError):
        TransactionCreate(
            organization_id=1,
            occurred_on=date(2026, 9, 25),
            transaction_type=TransactionType.INCOME,
            scope=Scope.PERSONAL,
            amount=4_200_000,
            payment_account_id=1,
            items=[
                TransactionItemCreate(amount=5_000_000, scope=Scope.PERSONAL, line_no=1),
                TransactionItemCreate(
                    amount=900_000,
                    scope=Scope.PERSONAL,
                    line_no=2,
                    line_kind=TransactionItemKind.DEDUCTION,
                ),
            ],
        )
