from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.init_db import seed_standard_data
from app.models import Account, Category, Organization
from app.models.enums import Scope, TransactionItemKind, TransactionType


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
            "merchant": "오피스디포",
            "memo": "프린터 용지",
            "payment_account_id": accounts["2100"].id,
            "items": [
                {
                    "category_id": categories["관리비"].id,
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
    body = fetched.json()
    assert body["memo"] == "프린터 용지"
    assert body["merchant"] == "오피스디포"


def test_create_without_merchant_returns_null(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    response = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": TransactionType.EXPENSE.value,
            "scope": Scope.PERSONAL.value,
            "amount": 3_000,
            "payment_account_id": accounts["1100"].id,
            "items": [
                {
                    "category_id": categories["식비"].id,
                    "amount": 3_000,
                    "scope": Scope.PERSONAL.value,
                    "line_no": 1,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["merchant"] is None
    assert response.json()["memo"] is None


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
                {"category_id": categories["관리비"].id, "amount": 50_000, "scope": "BUSINESS", "line_no": 1}
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
                {"category_id": categories["관리비"].id, "amount": 55_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount"] == 55_000

    trial = client.get(f"/api/reports/trial-balance?organization_id={organization.id}").json()
    assert trial["is_balanced"] is True
    housing = next(row for row in trial["rows"] if row["account_code"] == "5800")
    assert housing["debit_total"] == 55_000


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
                {"category_id": categories["관리비"].id, "amount": 50_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    ).json()
    cancelled = client.delete(f"/api/transactions/{created['id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "REVERSED"
    listed = client.get(f"/api/transactions?organization_id={organization.id}").json()
    assert listed["total"] == 0


def test_attachment_is_stored_by_transaction_month(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    created = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-03",
            "transaction_type": "EXPENSE",
            "scope": "BUSINESS",
            "amount": 12_000,
            "payment_account_id": accounts["2100"].id,
            "items": [
                {"category_id": categories["관리비"].id, "amount": 12_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    ).json()

    attached = client.post(
        f"/api/transactions/{created['id']}/attachments",
        files={"file": ("receipt.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")},
    )
    assert attached.status_code == 201, attached.text
    stored_path = attached.json()["stored_path"]
    assert stored_path.startswith("uploads/2026-09/")
    assert stored_path.endswith(".jpg")
    saved = Path(settings.data_dir) / stored_path
    assert saved.is_file()
    assert saved.read_bytes() == b"\xff\xd8\xff\xd9"

    attachment_id = attached.json()["id"]
    viewed = client.get(f"/api/transactions/{created['id']}/attachments/{attachment_id}")
    assert viewed.status_code == 200, viewed.text
    assert viewed.content == b"\xff\xd8\xff\xd9"
    assert viewed.headers["content-type"].startswith("image/jpeg")
    assert "inline" in viewed.headers["content-disposition"]

    missing = client.get(f"/api/transactions/{created['id']}/attachments/999999")
    assert missing.status_code == 404
    mismatched = client.get(f"/api/transactions/999999/attachments/{attachment_id}")
    assert mismatched.status_code == 404


def test_duplicate_check_finds_same_expense_and_transfer(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    expense_payload = {
        "organization_id": organization.id,
        "occurred_on": "2026-09-16",
        "transaction_type": "EXPENSE",
        "scope": "PERSONAL",
        "amount": 4_500,
        "merchant": "스타벅스",
        "payment_account_id": accounts["1100"].id,
        "items": [{"category_id": categories["관리비"].id, "amount": 4_500, "scope": "PERSONAL", "line_no": 1}],
    }
    created = client.post("/api/transactions", json=expense_payload)
    assert created.status_code == 201, created.text

    same = client.post(
        "/api/transactions/duplicate-check",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-16",
            "transaction_type": "EXPENSE",
            "amount": 4_500,
            "merchant": "스타벅스",
            "payment_account_id": accounts["1100"].id,
            "items": [{"category_id": categories["관리비"].id, "amount": 4_500, "scope": "PERSONAL", "line_no": 1}],
        },
    )
    assert same.status_code == 200, same.text
    assert [row["id"] for row in same.json()["matches"]] == [created.json()["id"]]

    different_merchant = client.post(
        "/api/transactions/duplicate-check",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-16",
            "transaction_type": "EXPENSE",
            "amount": 4_500,
            "merchant": "이마트",
            "payment_account_id": accounts["1100"].id,
            "items": [{"category_id": categories["관리비"].id, "amount": 4_500, "scope": "PERSONAL", "line_no": 1}],
        },
    )
    assert different_merchant.json()["matches"] == []

    self_excluded = client.post(
        "/api/transactions/duplicate-check",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-16",
            "transaction_type": "EXPENSE",
            "amount": 4_500,
            "merchant": "스타벅스",
            "payment_account_id": accounts["1100"].id,
            "items": [{"category_id": categories["관리비"].id, "amount": 4_500, "scope": "PERSONAL", "line_no": 1}],
            "exclude_id": created.json()["id"],
        },
    )
    assert self_excluded.json()["matches"] == []

    transfer_payload = {
        "organization_id": organization.id,
        "occurred_on": "2026-09-16",
        "transaction_type": "TRANSFER",
        "scope": "PERSONAL",
        "amount": 100_000,
        "payment_account_id": accounts["1100"].id,
        "transfer_account_id": accounts["1200"].id,
        "items": [],
    }
    transferred = client.post("/api/transactions", json=transfer_payload)
    assert transferred.status_code == 201, transferred.text

    transfer_dup = client.post(
        "/api/transactions/duplicate-check",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-16",
            "transaction_type": "TRANSFER",
            "amount": 100_000,
            "payment_account_id": accounts["1100"].id,
            "transfer_account_id": accounts["1200"].id,
            "items": [],
        },
    )
    assert transfer_dup.status_code == 200, transfer_dup.text
    assert [row["id"] for row in transfer_dup.json()["matches"]] == [transferred.json()["id"]]

    other_destination = client.post(
        "/api/transactions/duplicate-check",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-16",
            "transaction_type": "TRANSFER",
            "amount": 100_000,
            "payment_account_id": accounts["1100"].id,
            "transfer_account_id": accounts["2100"].id,
            "items": [],
        },
    )
    assert other_destination.json()["matches"] == []


def test_income_with_deductions_is_one_transaction(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    response = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-25",
            "transaction_type": TransactionType.INCOME.value,
            "scope": Scope.PERSONAL.value,
            "amount": 4_200_000,
            "merchant": "근무처",
            "memo": "9월 급여",
            "payment_account_id": accounts["1200"].id,
            "items": [
                {
                    "category_id": categories["급여"].id,
                    "amount": 5_000_000,
                    "scope": Scope.PERSONAL.value,
                    "line_no": 1,
                    "line_kind": TransactionItemKind.STANDARD.value,
                },
                {
                    "category_id": categories["세금"].id,
                    "amount": 800_000,
                    "scope": Scope.PERSONAL.value,
                    "line_no": 2,
                    "line_kind": TransactionItemKind.DEDUCTION.value,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["amount"] == 4_200_000
    assert created["transaction_type"] == "INCOME"
    assert {item["line_kind"] for item in created["items"]} == {"STANDARD", "DEDUCTION"}

    listed = client.get(f"/api/transactions?organization_id={organization.id}")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == created["id"]
    assert payload["items"][0]["amount"] == 4_200_000

    trial = client.get(f"/api/reports/trial-balance?organization_id={organization.id}").json()
    assert trial["is_balanced"] is True
    bank = next(row for row in trial["rows"] if row["account_code"] == "1200")
    salary = next(row for row in trial["rows"] if row["account_code"] == "4300")
    tax = next(row for row in trial["rows"] if row["account_code"] == "6300")
    assert bank["debit_total"] - bank["credit_total"] == 4_200_000
    assert salary["credit_total"] - salary["debit_total"] == 5_000_000
    assert tax["debit_total"] - tax["credit_total"] == 800_000


def test_itemized_expense_stores_line_memos(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    response = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-20",
            "transaction_type": TransactionType.EXPENSE.value,
            "scope": Scope.PERSONAL.value,
            "amount": 5_000,
            "merchant": "이마트",
            "payment_account_id": accounts["1100"].id,
            "items": [
                {
                    "category_id": categories["식비"].id,
                    "amount": 3_000,
                    "scope": Scope.PERSONAL.value,
                    "memo": "우유",
                    "line_no": 1,
                },
                {
                    "category_id": categories["식비"].id,
                    "amount": 2_000,
                    "scope": Scope.PERSONAL.value,
                    "memo": "라면",
                    "line_no": 2,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["amount"] == 5_000
    assert [item["memo"] for item in created["items"]] == ["우유", "라면"]

    trial = client.get(f"/api/reports/trial-balance?organization_id={organization.id}").json()
    assert trial["is_balanced"] is True
    cash = next(row for row in trial["rows"] if row["account_code"] == "1100")
    food = next(row for row in trial["rows"] if row["account_code"] == "5400")
    assert cash["credit_total"] - cash["debit_total"] == 5_000
    assert food["debit_total"] - food["credit_total"] == 5_000


def test_income_deduction_line_memos_are_stored(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    response = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-25",
            "transaction_type": TransactionType.INCOME.value,
            "scope": Scope.PERSONAL.value,
            "amount": 4_200_000,
            "merchant": "근무처",
            "payment_account_id": accounts["1200"].id,
            "items": [
                {
                    "category_id": categories["급여"].id,
                    "amount": 5_000_000,
                    "scope": Scope.PERSONAL.value,
                    "memo": "기본급",
                    "line_no": 1,
                    "line_kind": TransactionItemKind.STANDARD.value,
                },
                {
                    "category_id": categories["세금"].id,
                    "amount": 800_000,
                    "scope": Scope.PERSONAL.value,
                    "memo": "국민연금",
                    "line_no": 2,
                    "line_kind": TransactionItemKind.DEDUCTION.value,
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    memos = {item["line_kind"]: item["memo"] for item in created["items"]}
    assert memos["STANDARD"] == "기본급"
    assert memos["DEDUCTION"] == "국민연금"
