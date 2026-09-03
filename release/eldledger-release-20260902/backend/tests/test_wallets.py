from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Account, JournalEntry, Organization
from app.models.enums import RecordStatus
from app.schemas.wallets import WalletAccountCreate, WalletBalanceAdjust
from app.services.account_service import AccountService
from app.services.journal_balance import assert_journal_balanced, collect_line_amounts


def _seed(db_session: Session) -> Organization:
    organization = seed_standard_data(db_session)
    db_session.flush()
    return organization


def test_opening_balance_posts_balanced_equity_journal(db_session: Session) -> None:
    organization = _seed(db_session)
    service = AccountService(db_session)
    wallet = service.create_wallet(
        WalletAccountCreate(
            organization_id=organization.id,
            name="국민은행",
            instrument_kind="BANK",
            opening_balance=1_000_000,
            opening_on=date(2026, 9, 1),
            institution="국민은행",
        )
    )
    assert wallet.current_balance == 1_000_000
    assert wallet.chart_code.startswith("12")

    entry = db_session.scalar(select(JournalEntry).where(JournalEntry.transaction_id.is_(None)))
    assert entry is not None
    assert entry.status == RecordStatus.CONFIRMED
    assert_journal_balanced(collect_line_amounts(entry.lines))
    equity = db_session.scalar(select(Account).where(Account.code == "3100"))
    assert equity is not None
    credits = {line.account_id: line.credit_amount for line in entry.lines}
    debits = {line.account_id: line.debit_amount for line in entry.lines}
    assert debits.get(wallet.id, 0) == 1_000_000
    assert credits.get(equity.id, 0) == 1_000_000


def test_credit_card_opening_credits_liability(db_session: Session) -> None:
    organization = _seed(db_session)
    service = AccountService(db_session)
    bank = next(item for item in service.list_wallets(organization.id) if item.instrument_kind.value == "BANK")
    card = service.create_wallet(
        WalletAccountCreate(
            organization_id=organization.id,
            name="국민카드",
            instrument_kind="CREDIT_CARD",
            opening_balance=200_000,
            opening_on=date(2026, 9, 1),
            institution="국민카드",
            card_payment_day=14,
            settlement_account_id=bank.id,
        )
    )
    assert card.current_balance == 200_000
    entry = db_session.scalars(select(JournalEntry).order_by(JournalEntry.id.desc())).first()
    assert entry is not None
    assert_journal_balanced(collect_line_amounts(entry.lines))


def test_adjust_balance_posts_difference_journal(db_session: Session) -> None:
    organization = _seed(db_session)
    service = AccountService(db_session)
    cash = next(item for item in service.list_wallets(organization.id) if item.instrument_kind.value == "CASH")
    updated = service.adjust_balance(
        cash.id,
        WalletBalanceAdjust(actual_balance=50_000, occurred_on=date(2026, 9, 1), memo="지갑 세기"),
    )
    assert updated.current_balance == 50_000
    entry = db_session.scalars(select(JournalEntry).order_by(JournalEntry.id.desc())).first()
    assert entry is not None
    assert_journal_balanced(collect_line_amounts(list(entry.lines)))


def test_deactivate_hides_wallet(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    listed = client.get(f"/api/v1/accounts?organization_id={organization.id}")
    assert listed.status_code == 200
    cash = next(item for item in listed.json() if item["instrument_kind"] == "CASH")
    hidden = client.post(f"/api/v1/accounts/{cash['id']}/deactivate")
    assert hidden.status_code == 200
    assert hidden.json()["is_active"] is False
    visible = client.get(f"/api/v1/accounts?organization_id={organization.id}")
    assert all(item["id"] != cash["id"] for item in visible.json())
    including = client.get(f"/api/v1/accounts?organization_id={organization.id}&include_hidden=true")
    assert any(item["id"] == cash["id"] for item in including.json())


def test_create_wallet_api(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    response = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization.id,
            "name": "카카오뱅크",
            "instrument_kind": "BANK",
            "opening_balance": 300_000,
            "opening_on": "2026-09-01",
            "institution": "카카오뱅크",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "카카오뱅크"
    assert body["current_balance"] == 300_000
    assert body["currency"] == "KRW"
