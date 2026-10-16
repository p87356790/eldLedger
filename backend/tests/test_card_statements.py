from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.init_db import seed_standard_data
from app.models import Organization
from app.models.journal import JournalEntry, JournalLine


def _seed(db_session: Session) -> Organization:
    organization = seed_standard_data(db_session)
    db_session.flush()
    return organization


def _wallets(client: TestClient, organization_id: int) -> dict[str, dict]:
    rows = client.get(f"/api/v1/accounts?organization_id={organization_id}").json()
    return {row["instrument_kind"]: row for row in rows}


def _categories(client: TestClient, organization_id: int) -> dict[str, dict]:
    rows = client.get(f"/api/v1/categories?organization_id={organization_id}").json()
    return {row["name"]: row for row in rows}


def _card(client: TestClient, organization_id: int, bank_id: int) -> dict:
    created = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization_id,
            "name": "신한카드",
            "instrument_kind": "CREDIT_CARD",
            "opening_balance": 0,
            "card_payment_day": 15,
            "settlement_account_id": bank_id,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _expense(
    client: TestClient,
    *,
    organization_id: int,
    card_id: int,
    category_id: int,
    occurred_on: str,
    amount: int,
    transaction_type: str = "EXPENSE",
) -> dict:
    created = client.post(
        "/api/transactions",
        json={
            "organization_id": organization_id,
            "occurred_on": occurred_on,
            "transaction_type": transaction_type,
            "scope": "PERSONAL",
            "amount": amount,
            "merchant": "마트",
            "payment_account_id": card_id,
            "items": [
                {
                    "category_id": category_id,
                    "amount": amount,
                    "scope": "PERSONAL",
                    "line_no": 1,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_closed_month_becomes_next_month_statement(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    card = _card(client, organization.id, wallets["BANK"]["id"])
    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["식비"]["id"],
        occurred_on="2026-09-10",
        amount=30_000,
    )
    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["기타수익"]["id"],
        occurred_on="2026-09-12",
        amount=5_000,
        transaction_type="INCOME",
    )
    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["식비"]["id"],
        occurred_on="2026-10-05",
        amount=10_000,
    )

    listed = client.get(f"/api/v1/card-statements?organization_id={organization.id}")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    statement = rows[0]
    assert statement["title"] == "9월 신한카드 정산"
    assert statement["period_start"] == "2026-09-01"
    assert statement["period_end"] == "2026-09-30"
    assert statement["pay_on"] == "2026-10-15"
    assert statement["amount"] == 25_000
    assert statement["book_amount"] == 25_000
    assert statement["status"] == "OPEN"
    assert statement["bank_account_id"] == wallets["BANK"]["id"]
    assert [line["signed_amount"] for line in statement["lines"]] == [30_000, -5_000]
    assert "식비" in statement["lines"][0]["label"]

    before = client.get(
        "/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30"
    ).json()["summary"]
    assert before["total_expense"] == 30_000
    assert before["total_income"] == 5_000


def test_pay_settles_the_card_without_a_new_expense(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    card = _card(client, organization.id, wallets["BANK"]["id"])
    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["식비"]["id"],
        occurred_on="2026-09-10",
        amount=30_000,
    )
    statement = client.get(f"/api/v1/card-statements?organization_id={organization.id}").json()[0]
    paid = client.post(
        f"/api/v1/card-statements/{statement['id']}/pay",
        json={"occurred_on": "2026-10-15"},
    )
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body["status"] == "PAID"
    assert body["paid_on"] == "2026-10-15"
    assert body["transaction_id"] is not None

    again = client.post(
        f"/api/v1/card-statements/{statement['id']}/pay",
        json={"occurred_on": "2026-10-16"},
    )
    assert again.status_code == 400

    october = client.get(
        "/api/v1/dashboard/summary?start_date=2026-10-01&end_date=2026-10-31"
    ).json()["summary"]
    assert october["total_expense"] == 0

    listed = client.get(f"/api/transactions?organization_id={organization.id}").json()
    transfer = next(row for row in listed["items"] if row["id"] == body["transaction_id"])
    assert transfer["transaction_type"] == "TRANSFER"
    assert transfer["amount"] == 30_000
    assert transfer["payment_account_id"] == wallets["BANK"]["id"]
    assert transfer["transfer_account_id"] == card["id"]

    totals = db_session.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit_amount), 0),
            func.coalesce(func.sum(JournalLine.credit_amount), 0),
        )
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(JournalEntry.transaction_id == transfer["id"])
    ).one()
    assert totals[0] == totals[1]
    assert totals[0] == 30_000


def test_locked_amount_stays_when_usage_changes(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    card = _card(client, organization.id, wallets["BANK"]["id"])
    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["식비"]["id"],
        occurred_on="2026-08-02",
        amount=20_000,
    )
    statement = client.get(f"/api/v1/card-statements?organization_id={organization.id}").json()[0]
    updated = client.patch(f"/api/v1/card-statements/{statement['id']}", json={"amount": 22_000})
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount"] == 22_000
    assert updated.json()["amount_locked"] is True

    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["식비"]["id"],
        occurred_on="2026-08-20",
        amount=1_000,
    )
    again = client.get(f"/api/v1/card-statements?organization_id={organization.id}").json()
    august = next(row for row in again if row["period_start"] == "2026-08-01")
    assert august["amount"] == 22_000
    assert august["book_amount"] == 21_000


def test_card_statement_backup_roundtrip(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    card = _card(client, organization.id, wallets["BANK"]["id"])
    _expense(
        client,
        organization_id=organization.id,
        card_id=card["id"],
        category_id=categories["식비"]["id"],
        occurred_on="2026-09-10",
        amount=30_000,
    )
    statement = client.get(f"/api/v1/card-statements?organization_id={organization.id}").json()[0]
    paid = client.post(
        f"/api/v1/card-statements/{statement['id']}/pay",
        json={"occurred_on": "2026-10-15"},
    )
    assert paid.status_code == 200, paid.text

    exported = client.get("/api/v1/backup/export")
    assert exported.status_code == 200, exported.text
    restored = client.post(
        "/api/v1/backup/import?replace=true",
        files={"file": ("backup.zip", exported.content, "application/zip")},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["card_statements_created"] == 1
    rows = client.get(f"/api/v1/card-statements?organization_id={organization.id}").json()
    assert len(rows) == 1
    assert rows[0]["status"] == "PAID"
    assert rows[0]["amount"] == 30_000
    assert rows[0]["transaction_id"] is not None


def test_unlinking_a_receipt_keeps_the_file(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    created = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-03",
            "transaction_type": "EXPENSE",
            "scope": "PERSONAL",
            "amount": 12_000,
            "payment_account_id": wallets["CASH"]["id"],
            "items": [
                {
                    "category_id": categories["식비"]["id"],
                    "amount": 12_000,
                    "scope": "PERSONAL",
                    "line_no": 1,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]
    attached = client.post(
        f"/api/transactions/{transaction_id}/attachments",
        files={"file": ("receipt.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")},
    )
    assert attached.status_code == 201, attached.text
    stored = Path(settings.data_dir) / attached.json()["stored_path"]
    assert stored.is_file()

    removed = client.delete(f"/api/transactions/{transaction_id}/attachments/{attached.json()['id']}")
    assert removed.status_code == 204, removed.text
    assert stored.is_file()
    assert stored.read_bytes() == b"\xff\xd8\xff\xd9"
    gone = client.get(f"/api/transactions/{transaction_id}/attachments/{attached.json()['id']}")
    assert gone.status_code == 404
    reloaded = client.get(f"/api/transactions/{transaction_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["attachments"] == []
