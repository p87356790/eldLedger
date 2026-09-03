from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.init_db import seed_standard_data
from app.models import Account, Category, JournalEntry, Organization, Tag
from app.models.enums import Scope, TransactionType
from app.services.csv_import_service import import_fingerprint, parse_krw
from app.services.journal_balance import assert_journal_balanced, collect_line_amounts


def _seed(db_session: Session) -> tuple[Organization, dict[str, Account], dict[str, Category]]:
    organization = seed_standard_data(db_session)
    db_session.flush()
    accounts = {account.code: account for account in db_session.scalars(select(Account))}
    categories = {category.name: category for category in db_session.scalars(select(Category))}
    return organization, accounts, categories


def test_parse_krw_strips_currency_and_commas() -> None:
    assert parse_krw("₩12,000원") == 12_000
    assert parse_krw("(3,500)") == -3_500
    assert parse_krw("-1,000.99") == -1_000
    assert parse_krw("") == 0


def test_fingerprint_is_stable_for_same_merchant() -> None:
    first = import_fingerprint(date(2026, 9, 1), 12_000, "  쿠팡  ")
    second = import_fingerprint(date(2026, 9, 1), 12_000, "쿠팡")
    assert first == second
    assert first != import_fingerprint(date(2026, 9, 2), 12_000, "쿠팡")


def test_preview_cp949_and_duplicate_and_auto_rule(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    tag = db_session.scalar(select(Tag).where(Tag.name == "온라인"))
    assert tag is not None
    created_rule = client.post(
        "/api/v1/import/rules",
        json={
            "name": "쿠팡 사무",
            "merchant_keyword": "쿠팡",
            "payment_account_id": accounts["2100"].id,
            "category_id": categories["사무용품"].id,
            "scope": Scope.BUSINESS.value,
            "tag_ids": [tag.id],
            "sort_order": 1,
        },
    )
    assert created_rule.status_code == 201, created_rule.text

    csv_text = "이용일자,이용금액,가맹점명\n2026-09-01,\"12,000원\",쿠팡\n2026-09-01,12000,쿠팡\n"
    payload = csv_text.encode("cp949")
    preview = client.post(
        "/api/v1/import/preview",
        data={"account_id": str(accounts["2100"].id), "organization_id": str(organization.id)},
        files={"file": ("card.csv", payload, "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["encoding"] in {"cp949", "euc-kr"}
    assert body["total_rows"] == 2
    assert body["duplicate_count"] == 1
    assert body["rows"][0]["suggested"] is True
    assert body["rows"][0]["category_id"] == categories["사무용품"].id
    assert body["rows"][0]["scope"] == "BUSINESS"
    assert body["rows"][1]["duplicate"] is True
    assert body["rows"][1]["skip"] is True


def test_commit_creates_balanced_journal_and_skips_duplicate(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    existing = client.post(
        "/api/transactions",
        json={
            "organization_id": organization.id,
            "occurred_on": "2026-09-01",
            "transaction_type": TransactionType.EXPENSE.value,
            "scope": Scope.BUSINESS.value,
            "amount": 12_000,
            "memo": "쿠팡",
            "payment_account_id": accounts["2100"].id,
            "items": [
                {"category_id": categories["사무용품"].id, "amount": 12_000, "scope": "BUSINESS", "line_no": 1}
            ],
        },
    )
    assert existing.status_code == 201, existing.text

    csv_text = "이용일자,이용금액,가맹점명\n2026-09-01,12000,쿠팡\n2026-09-02,5000,스타벅스\n"
    preview = client.post(
        "/api/v1/import/preview",
        data={"account_id": str(accounts["2100"].id), "organization_id": str(organization.id)},
        files={"file": ("card.csv", csv_text.encode("utf-8"), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert rows[0]["duplicate"] is True

    commit = client.post(
        "/api/v1/import/commit",
        json={
            "organization_id": organization.id,
            "payment_account_id": accounts["2100"].id,
            "rows": [
                {
                    "occurred_on": "2026-09-01",
                    "amount": 12_000,
                    "merchant": "쿠팡",
                    "transaction_type": "EXPENSE",
                    "scope": "BUSINESS",
                    "category_id": categories["사무용품"].id,
                    "tag_ids": [],
                    "skip": True,
                },
                {
                    "occurred_on": "2026-09-02",
                    "amount": 5_000,
                    "merchant": "스타벅스",
                    "transaction_type": "EXPENSE",
                    "scope": "PERSONAL",
                    "category_id": categories["식비"].id,
                    "tag_ids": [],
                    "skip": False,
                },
            ],
        },
    )
    assert commit.status_code == 200, commit.text
    result = commit.json()
    assert result["created"] == 1
    assert result["skipped"] == 1
    assert result["failed"] == []

    db_session.expire_all()
    entry = db_session.scalars(
        select(JournalEntry).options(selectinload(JournalEntry.lines)).order_by(JournalEntry.id.desc())
    ).first()
    assert entry is not None
    assert_journal_balanced(collect_line_amounts(list(entry.lines)))


def test_rule_crud(client: TestClient, db_session: Session) -> None:
    _organization, accounts, categories = _seed(db_session)
    created = client.post(
        "/api/v1/import/rules",
        json={
            "name": "쿠팡",
            "merchant_keyword": "쿠팡",
            "category_id": categories["사무용품"].id,
            "scope": "BUSINESS",
            "tag_ids": [],
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]
    listed = client.get("/api/v1/import/rules")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    patched = client.patch(
        f"/api/v1/import/rules/{rule_id}",
        json={"is_active": False, "payment_account_id": accounts["2100"].id},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    deleted = client.delete(f"/api/v1/import/rules/{rule_id}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/import/rules").json() == []
