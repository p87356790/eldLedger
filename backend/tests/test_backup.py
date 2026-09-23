import zipfile
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.init_db import seed_standard_data
from app.models import Organization


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


def _post_tx(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_export_and_import_restores_ledger(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    cash = wallets["CASH"]
    bank = wallets["BANK"]

    extra = client.post(
        "/api/v1/accounts",
        json={
            "organization_id": organization.id,
            "name": "카카오뱅크",
            "instrument_kind": "BANK",
            "currency": "KRW",
            "opening_balance": 250_000,
            "opening_on": "2026-01-01",
            "institution": "카카오뱅크",
        },
    )
    assert extra.status_code == 201, extra.text
    extra_bank = extra.json()

    created_category = client.post(
        "/api/v1/categories",
        json={
            "organization_id": organization.id,
            "name": "구독료",
            "transaction_type": "EXPENSE",
            "default_scope": "PERSONAL",
            "account_id": categories["통신"]["account_id"],
            "icon": "phone",
        },
    )
    assert created_category.status_code == 201, created_category.text
    subscription = created_category.json()

    _post_tx(
        client,
        {
            "organization_id": organization.id,
            "occurred_on": "2026-09-02",
            "transaction_type": "INCOME",
            "scope": "BUSINESS",
            "amount": 200_000,
            "memo": "용역비",
            "payment_account_id": extra_bank["id"],
            "items": [
                {
                    "category_id": categories["매출"]["id"],
                    "amount": 200_000,
                    "scope": "BUSINESS",
                    "line_no": 1,
                }
            ],
        },
    )
    expense = _post_tx(
        client,
        {
            "organization_id": organization.id,
            "occurred_on": "2026-09-03",
            "transaction_type": "EXPENSE",
            "scope": "MIXED",
            "amount": 80_000,
            "memo": "회식+개인",
            "payment_account_id": cash["id"],
            "items": [
                {
                    "category_id": categories["경조사"]["id"],
                    "amount": 50_000,
                    "scope": "BUSINESS",
                    "line_no": 1,
                },
                {
                    "category_id": subscription["id"],
                    "amount": 30_000,
                    "scope": "PERSONAL",
                    "line_no": 2,
                },
            ],
        },
    )
    attach = client.post(
        f"/api/transactions/{expense['id']}/attachments",
        files={"file": ("receipt.jpg", b"\xff\xd8\xff\xd9", "image/jpeg")},
    )
    assert attach.status_code == 201, attach.text
    _post_tx(
        client,
        {
            "organization_id": organization.id,
            "occurred_on": "2026-09-04",
            "transaction_type": "TRANSFER",
            "scope": "PERSONAL",
            "amount": 20_000,
            "memo": "현금 인출",
            "payment_account_id": bank["id"],
            "transfer_account_id": cash["id"],
            "items": [],
        },
    )

    exported = client.get("/api/v1/backup/export")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/zip")
    backup = exported.content
    with zipfile.ZipFile(BytesIO(backup)) as archive:
        receipt_names = [
            name for name in archive.namelist() if name.startswith("attachments/") and not name.endswith("/")
        ]
        assert len(receipt_names) == 1
        assert receipt_names[0].startswith("attachments/2026-09/")
        assert receipt_names[0].endswith(".jpg")

    conflict = client.post("/api/v1/backup/import", files={"file": ("backup.zip", backup, "application/zip")})
    assert conflict.status_code == 409

    restored = client.post(
        "/api/v1/backup/import?replace=true",
        files={"file": ("backup.zip", backup, "application/zip")},
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["transactions_created"] == 3
    assert body["attachments_created"] == 1
    assert body["replaced_transactions"] == 3
    assert body["wallets_matched"] >= 1
    assert body["categories_matched"] >= 1

    listed = client.get(f"/api/transactions?organization_id={organization.id}&limit=50").json()
    assert listed["total"] == 3
    memos = {item["memo"] for item in listed["items"]}
    assert memos == {"용역비", "회식+개인", "현금 인출"}
    mixed = next(item for item in listed["items"] if item["memo"] == "회식+개인")
    assert mixed["amount"] == 80_000
    assert mixed["scope"] == "MIXED"
    assert len(mixed["attachments"]) == 1

    wallet_names = {row["name"] for row in client.get(f"/api/v1/accounts?organization_id={organization.id}").json()}
    assert "카카오뱅크" in wallet_names
    category_names = {row["name"] for row in client.get(f"/api/v1/categories?organization_id={organization.id}").json()}
    assert "구독료" in category_names

    trial = client.get(f"/api/reports/trial-balance?organization_id={organization.id}").json()
    assert trial["is_balanced"] is True


def test_config_import_succeeds_when_auto_rules_exist(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)

    exported = client.get("/api/v1/backup/config/export")
    assert exported.status_code == 200, exported.text

    created_rule = client.post(
        "/api/v1/import/rules",
        json={
            "name": "스타벅스",
            "merchant_keyword": "스타벅스",
            "payment_account_id": wallets["CASH"]["id"],
            "category_id": categories["식비"]["id"],
            "scope": "PERSONAL",
        },
    )
    assert created_rule.status_code == 201, created_rule.text

    import json

    restored = client.post(
        "/api/v1/backup/config/import",
        files={"file": ("config.json", json.dumps(exported.json()).encode(), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    after = _categories(client, organization.id)
    assert "식비" in after
    rules = client.get("/api/v1/import/rules").json()
    assert rules == []


def test_config_import_accepts_utf8_bom(client: TestClient, db_session: Session) -> None:
    _seed(db_session)
    exported = client.get("/api/v1/backup/config/export")
    assert exported.status_code == 200, exported.text
    import json

    body = b"\xef\xbb\xbf" + json.dumps(exported.json()).encode("utf-8")
    restored = client.post(
        "/api/v1/backup/config/import",
        files={"file": ("config.json", body, "application/json")},
    )
    assert restored.status_code == 200, restored.text


def test_import_rejects_unknown_file(client: TestClient, db_session: Session) -> None:
    _seed(db_session)
    response = client.post(
        "/api/v1/backup/import",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_config_export_and_import_replaces_wallets_and_categories(
    client: TestClient, db_session: Session,
) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    assert len(wallets) > 0
    assert len(categories) > 0

    exported = client.get("/api/v1/backup/config/export")
    assert exported.status_code == 200, exported.text
    config_json = exported.json()
    assert config_json["format"] == "eldledger-config"
    assert len(config_json["wallets"]) == len(wallets)
    assert len(config_json["categories"]) == len(categories)

    extra_cat = client.post(
        "/api/v1/categories",
        json={
            "organization_id": organization.id,
            "name": "임시분류",
            "transaction_type": "EXPENSE",
            "default_scope": "PERSONAL",
            "account_id": categories["통신"]["account_id"],
        },
    )
    assert extra_cat.status_code == 201, extra_cat.text
    assert len(_categories(client, organization.id)) == len(categories) + 1

    import json
    restored = client.post(
        "/api/v1/backup/config/import",
        files={"file": ("config.json", json.dumps(config_json).encode(), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["categories_deleted"] == len(categories) + 1
    assert body["categories_created"] >= len(categories)
    assert body["wallets_created"] >= len(wallets)

    after = _categories(client, organization.id)
    assert "임시분류" not in after
    assert "식비" in after


def test_config_import_blocked_when_transactions_exist(
    client: TestClient, db_session: Session,
) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)

    _post_tx(
        client,
        {
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": "EXPENSE",
            "scope": "PERSONAL",
            "amount": 10_000,
            "payment_account_id": wallets["CASH"]["id"],
            "items": [
                {"category_id": categories["식비"]["id"], "amount": 10_000, "scope": "PERSONAL", "line_no": 1}
            ],
        },
    )

    exported = client.get("/api/v1/backup/config/export")
    assert exported.status_code == 200

    import json
    result = client.post(
        "/api/v1/backup/config/import",
        files={"file": ("config.json", json.dumps(exported.json()).encode(), "application/json")},
    )
    assert result.status_code == 400
    assert "거래가" in result.json()["detail"]
