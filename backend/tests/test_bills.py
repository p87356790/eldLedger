import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.init_db import seed_standard_data
from app.models import Organization
from app.models.journal import JournalEntry, JournalLine
from app.services.bill_service import add_months


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


def _bill_payload(organization_id: int, category_id: int, **overrides: object) -> dict:
    payload: dict = {
        "organization_id": organization_id,
        "title": "관리비",
        "amount": 185_000,
        "category_id": category_id,
        "scope": "PERSONAL",
        "billed_on": "2026-10-01",
        "pay_on": "2026-10-20",
        "memo": "10월",
        "repeats_monthly": False,
    }
    payload.update(overrides)
    return payload


def test_add_months_clamps_to_month_end() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 1, 20), 1) == date(2026, 2, 20)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)


def test_open_bill_stays_off_the_ledger_until_paid(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    created = client.post(
        "/api/v1/bills",
        json=_bill_payload(organization.id, categories["관리비"]["id"], payment_account_id=wallets["BANK"]["id"]),
    )
    assert created.status_code == 201, created.text
    bill = created.json()
    assert bill["status"] == "OPEN"
    assert bill["transaction_id"] is None

    before = client.get(f"/api/transactions?organization_id={organization.id}")
    assert before.json()["total"] == 0

    paid = client.post(
        f"/api/v1/bills/{bill['id']}/pay",
        json={"occurred_on": "2026-10-20", "payment_account_id": wallets["CASH"]["id"]},
    )
    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body["status"] == "PAID"
    assert body["paid_on"] == "2026-10-20"
    assert body["payment_account_id"] == wallets["CASH"]["id"]

    listed = client.get(f"/api/transactions?organization_id={organization.id}").json()
    assert listed["total"] == 1
    transaction = listed["items"][0]
    assert transaction["id"] == body["transaction_id"]
    assert transaction["transaction_type"] == "EXPENSE"
    assert transaction["amount"] == 185_000
    assert transaction["merchant"] == "관리비"
    assert transaction["memo"] == "10월"
    assert transaction["occurred_on"] == "2026-10-20"
    assert transaction["status"] == "CONFIRMED"
    assert transaction["payment_account_id"] == wallets["CASH"]["id"]
    assert transaction["items"][0]["category_id"] == categories["관리비"]["id"]

    totals = db_session.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit_amount), 0),
            func.coalesce(func.sum(JournalLine.credit_amount), 0),
        )
        .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
        .where(JournalEntry.transaction_id == transaction["id"])
    ).one()
    assert totals[0] == totals[1]
    assert totals[0] == 185_000

    again = client.post(
        f"/api/v1/bills/{bill['id']}/pay",
        json={"occurred_on": "2026-10-21", "payment_account_id": wallets["CASH"]["id"]},
    )
    assert again.status_code == 400


def test_monthly_bill_spawns_the_next_open_bill(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    created = client.post(
        "/api/v1/bills",
        json=_bill_payload(
            organization.id,
            categories["관리비"]["id"],
            billed_on="2026-01-31",
            pay_on="2026-01-20",
            repeats_monthly=True,
        ),
    )
    assert created.status_code == 201, created.text
    paid = client.post(
        f"/api/v1/bills/{created.json()['id']}/pay",
        json={"occurred_on": "2026-01-20", "payment_account_id": wallets["BANK"]["id"]},
    )
    assert paid.status_code == 200, paid.text

    rows = client.get(f"/api/v1/bills?organization_id={organization.id}").json()
    assert len(rows) == 2
    nxt = next(row for row in rows if row["status"] == "OPEN")
    assert nxt["title"] == "관리비"
    assert nxt["amount"] == 185_000
    assert nxt["billed_on"] == "2026-02-28"
    assert nxt["pay_on"] == "2026-02-20"
    assert nxt["repeats_monthly"] is True
    assert nxt["payment_account_id"] == wallets["BANK"]["id"]


def test_open_bill_can_be_edited_and_deleted(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    categories = _categories(client, organization.id)
    created = client.post("/api/v1/bills", json=_bill_payload(organization.id, categories["관리비"]["id"]))
    assert created.status_code == 201, created.text
    bill_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/bills/{bill_id}",
        json={
            "title": "전기요금",
            "amount": 42_000,
            "category_id": categories["관리비"]["id"],
            "scope": "PERSONAL",
            "billed_on": "2026-10-05",
            "pay_on": None,
            "memo": None,
            "payment_account_id": None,
            "repeats_monthly": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "전기요금"
    assert updated.json()["amount"] == 42_000

    removed = client.delete(f"/api/v1/bills/{bill_id}")
    assert removed.status_code == 204
    listed = client.get(f"/api/v1/bills?organization_id={organization.id}")
    assert listed.json() == []


def test_paid_bill_cannot_be_deleted(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    created = client.post("/api/v1/bills", json=_bill_payload(organization.id, categories["관리비"]["id"]))
    bill_id = created.json()["id"]
    client.post(
        f"/api/v1/bills/{bill_id}/pay",
        json={"occurred_on": "2026-10-20", "payment_account_id": wallets["CASH"]["id"]},
    )
    removed = client.delete(f"/api/v1/bills/{bill_id}")
    assert removed.status_code == 400


def test_mixed_scope_is_rejected(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    categories = _categories(client, organization.id)
    response = client.post(
        "/api/v1/bills",
        json=_bill_payload(organization.id, categories["관리비"]["id"], scope="MIXED"),
    )
    assert response.status_code == 422


def test_bill_backup_roundtrip(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    created = client.post(
        "/api/v1/bills",
        json=_bill_payload(organization.id, categories["관리비"]["id"], payment_account_id=wallets["BANK"]["id"]),
    )
    assert created.status_code == 201, created.text
    paid = client.post(
        f"/api/v1/bills/{created.json()['id']}/pay",
        json={"occurred_on": "2026-10-20", "payment_account_id": wallets["BANK"]["id"]},
    )
    assert paid.status_code == 200, paid.text

    exported = client.get("/api/v1/backup/export")
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(BytesIO(exported.content)) as archive:
        bundle = archive.read("ledger.json")
    assert "관리비".encode() in bundle

    restored = client.post(
        "/api/v1/backup/import?replace=true",
        files={"file": ("backup.zip", exported.content, "application/zip")},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["bills_created"] == 1
    assert restored.json()["transactions_created"] == 1

    rows = client.get(f"/api/v1/bills?organization_id={organization.id}").json()
    assert len(rows) == 1
    assert rows[0]["status"] == "PAID"
    assert rows[0]["transaction_id"] is not None
    listed = client.get(f"/api/transactions?organization_id={organization.id}").json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == rows[0]["transaction_id"]


def test_bill_invoice_is_kept_and_copied_onto_the_expense(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    created = client.post(
        "/api/v1/bills",
        json=_bill_payload(organization.id, categories["관리비"]["id"], payment_account_id=wallets["BANK"]["id"]),
    )
    assert created.status_code == 201, created.text
    bill_id = created.json()["id"]

    attached = client.post(
        f"/api/v1/bills/{bill_id}/attachments",
        files={"file": ("관리비청구서.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")},
    )
    assert attached.status_code == 201, attached.text
    attachment = attached.json()
    stored = Path(settings.data_dir) / attachment["stored_path"]
    assert stored.is_file()
    assert attachment["bill_id"] == bill_id
    assert attachment["transaction_id"] is None

    viewed = client.get(f"/api/v1/bills/{bill_id}/attachments/{attachment['id']}")
    assert viewed.status_code == 200, viewed.text
    assert viewed.content == b"\xff\xd8\xff\xd9"

    paid = client.post(
        f"/api/v1/bills/{bill_id}/pay",
        json={"occurred_on": "2026-10-20", "payment_account_id": wallets["BANK"]["id"]},
    )
    assert paid.status_code == 200, paid.text
    expense_id = paid.json()["transaction_id"]
    expense = client.get(f"/api/transactions/{expense_id}").json()
    assert len(expense["attachments"]) == 1
    assert expense["attachments"][0]["stored_path"] == attachment["stored_path"]
    assert Path(settings.data_dir).joinpath(attachment["stored_path"]).read_bytes() == b"\xff\xd8\xff\xd9"

    exported = client.get("/api/v1/backup/export")
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(BytesIO(exported.content)) as archive:
        names = archive.namelist()
    assert any(name.startswith("bill-attachments/") for name in names)

    restored = client.post(
        "/api/v1/backup/import?replace=true",
        files={"file": ("backup.zip", exported.content, "application/zip")},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["bills_created"] == 1
    assert restored.json()["attachments_created"] >= 2
    rows = client.get(f"/api/v1/bills?organization_id={organization.id}").json()
    assert len(rows) == 1
    assert len(rows[0]["attachments"]) == 1
    restored_file = client.get(f"/api/v1/bills/{rows[0]['id']}/attachments/{rows[0]['attachments'][0]['id']}")
    assert restored_file.status_code == 200
    assert restored_file.content == b"\xff\xd8\xff\xd9"


def test_unlinking_a_bill_invoice_keeps_the_file(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    categories = _categories(client, organization.id)
    created = client.post("/api/v1/bills", json=_bill_payload(organization.id, categories["관리비"]["id"]))
    assert created.status_code == 201, created.text
    bill_id = created.json()["id"]
    attached = client.post(
        f"/api/v1/bills/{bill_id}/attachments",
        files={"file": ("invoice.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert attached.status_code == 201, attached.text
    stored = Path(settings.data_dir) / attached.json()["stored_path"]
    removed = client.delete(f"/api/v1/bills/{bill_id}/attachments/{attached.json()['id']}")
    assert removed.status_code == 204, removed.text
    assert stored.is_file()
    assert stored.read_bytes() == b"%PDF-1.4"
    missing = client.get(f"/api/v1/bills/{bill_id}/attachments/{attached.json()['id']}")
    assert missing.status_code == 404
