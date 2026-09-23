"""이체: 은행→은행, 은행→카드대금이 양쪽 잔액·내역에 반영되는지."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Organization


def _seed(db_session: Session) -> Organization:
    organization = seed_standard_data(db_session)
    db_session.flush()
    return organization


def _wallet_by_name(client: TestClient, organization_id: int, name: str) -> dict:
    rows = client.get(f"/api/v1/accounts?organization_id={organization_id}").json()
    matched = next((row for row in rows if row["name"] == name), None)
    assert matched is not None, f"지갑 없음: {name}"
    return matched


def _post_transfer(
    client: TestClient,
    *,
    organization_id: int,
    amount: int,
    from_id: int,
    to_id: int,
    memo: str,
) -> dict:
    response = client.post(
        "/api/transactions",
        json={
            "organization_id": organization_id,
            "occurred_on": "2026-09-14",
            "transaction_type": "TRANSFER",
            "scope": "PERSONAL",
            "amount": amount,
            "memo": memo,
            "payment_account_id": from_id,
            "transfer_account_id": to_id,
            "items": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_bank_to_bank_transfer_updates_both_balances_and_history(
    client: TestClient, db_session: Session
) -> None:
    organization = _seed(db_session)

    bank1 = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization.id,
            "name": "은행1",
            "instrument_kind": "BANK",
            "opening_balance": 1_000_000,
            "opening_on": "2026-09-01",
        },
    ).json()
    bank2 = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization.id,
            "name": "은행2",
            "instrument_kind": "BANK",
            "opening_balance": 100_000,
            "opening_on": "2026-09-01",
        },
    ).json()

    _post_transfer(
        client,
        organization_id=organization.id,
        amount=250_000,
        from_id=bank1["id"],
        to_id=bank2["id"],
        memo="은행1→은행2",
    )

    bank1_after = _wallet_by_name(client, organization.id, "은행1")
    bank2_after = _wallet_by_name(client, organization.id, "은행2")
    assert bank1_after["current_balance"] == 750_000
    assert bank2_after["current_balance"] == 350_000

    out_dash = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={bank1['id']}"
    ).json()
    assert out_dash["summary"]["total_expense"] == 250_000
    out_row = next(row for row in out_dash["transactions"] if row["transaction_type"] == "TRANSFER")
    assert out_row["signed_amount"] == -250_000
    assert "은행1" in out_row["payment_method"] and "은행2" in out_row["payment_method"]

    in_dash = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={bank2['id']}"
    ).json()
    assert in_dash["summary"]["total_income"] == 250_000
    in_row = next(row for row in in_dash["transactions"] if row["transaction_type"] == "TRANSFER")
    assert in_row["signed_amount"] == 250_000


def test_bank_to_card_payment_reduces_bank_and_card_balance(
    client: TestClient, db_session: Session
) -> None:
    organization = _seed(db_session)

    bank = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization.id,
            "name": "결제은행",
            "instrument_kind": "BANK",
            "opening_balance": 500_000,
            "opening_on": "2026-09-01",
        },
    ).json()
    card = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization.id,
            "name": "테스트카드",
            "instrument_kind": "CREDIT_CARD",
            "opening_balance": 200_000,
            "opening_on": "2026-09-01",
            "card_payment_day": 14,
            "settlement_account_id": bank["id"],
        },
    ).json()
    assert card["current_balance"] == 200_000

    _post_transfer(
        client,
        organization_id=organization.id,
        amount=80_000,
        from_id=bank["id"],
        to_id=card["id"],
        memo="카드대금",
    )

    bank_after = _wallet_by_name(client, organization.id, "결제은행")
    card_after = _wallet_by_name(client, organization.id, "테스트카드")
    assert bank_after["current_balance"] == 420_000
    assert card_after["current_balance"] == 120_000

    bank_dash = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={bank['id']}"
    ).json()
    assert bank_dash["summary"]["total_expense"] == 80_000
    bank_row = next(row for row in bank_dash["transactions"] if row["transaction_type"] == "TRANSFER")
    assert bank_row["signed_amount"] == -80_000

    card_dash = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={card['id']}"
    ).json()
    assert card_dash["summary"]["total_income"] == 80_000
    card_row = next(row for row in card_dash["transactions"] if row["transaction_type"] == "TRANSFER")
    assert card_row["signed_amount"] == 80_000
