from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Account, Category, Organization
from app.models.enums import Scope, TransactionType


def _seed(db_session: Session) -> tuple[Organization, dict[str, Account], dict[str, Category]]:
    organization = seed_standard_data(db_session)
    db_session.flush()
    accounts = {account.code: account for account in db_session.scalars(select(Account))}
    categories = {category.name: category for category in db_session.scalars(select(Category))}
    return organization, accounts, categories


def test_create_and_list_expense_transaction(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    response = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": TransactionType.EXPENSE.value,
            "scope": Scope.BUSINESS.value,
            "amount": 50_000,
            "memo": "프린터 용지",
            "payment_account_id": accounts["2100"].id,
            "items": [
                {
                    "category_id": categories["사무용품"].id,
                    "amount": 50_000,
                    "scope": Scope.BUSINESS.value,
                    "line_no": 1,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["amount"] == 50_000
    assert created["status"] == "CONFIRMED"

    listed = client.get(f"/api/transactions?organization_id={organization.id}&transaction_type=EXPENSE")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == created["id"]

    fetched = client.get(f"/api/transactions/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["memo"] == "프린터 용지"


def test_update_transaction_reverses_and_reposts(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    created = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": "EXPENSE",
            "scope": "BUSINESS",
            "amount": 50_000,
            "payment_account_id": accounts["2100"].id,
            "items": [
                {"category_id": categories["사무용품"].id, "amount": 50_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    ).json()

    updated = client.put(
        f"/api/transactions/{created['id']}",
        json={
            "occurred_on": "2026-09-01",
            "transaction_type": "EXPENSE",
            "scope": "BUSINESS",
            "amount": 55_000,
            "payment_account_id": accounts["2100"].id,
            "items": [
                {"category_id": categories["사무용품"].id, "amount": 55_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount"] == 55_000

    trial = client.get(f"/api/reports/trial-balance?organization_id={organization.id}").json()
    assert trial["is_balanced"] is True
    supplies = next(row for row in trial["rows"] if row["account_code"] == "5100")
    assert supplies["debit_total"] == 55_000


def test_delete_cancels_transaction(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    created = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": "EXPENSE",
            "scope": "BUSINESS",
            "amount": 50_000,
            "payment_account_id": accounts["2100"].id,
            "items": [
                {"category_id": categories["사무용품"].id, "amount": 50_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    ).json()
    cancelled = client.delete(f"/api/transactions/{created['id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "REVERSED"
    listed = client.get(f"/api/transactions?organization_id={organization.id}").json()
    assert listed["total"] == 0
