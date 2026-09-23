from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.init_db import seed_standard_data
from app.models import Account, Category, JournalEntry, Organization, Tag
from app.models.enums import Scope, TransactionType
from app.services.csv_import_service import import_fingerprint, match_wallet, parse_csv_table, parse_date, parse_krw
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


def test_parse_date_keeps_year_month_day_and_drops_time() -> None:
    assert parse_date("2026.04.30 10:14") == date(2026, 4, 30)
    assert parse_date("2026-04-28 18:44") == date(2026, 4, 28)
    assert parse_date("2026.4.23") == date(2026, 4, 23)


def test_parse_csv_table_prefers_tabs_when_amounts_have_commas() -> None:
    tsv = (
        "언제인가요?\t사용처\t어떻게 냈나요?\t얼마인가요?\t어디에 사용했나요?\t메모\n"
        "2026.04.30 10:14\t한국전력공사\t신한카드\t29,100\t주거/공과금\t\n"
        "2026.04.28 18:44\t지에스(GS)25 봉산문화점\t현금\t4,800\t용돈/유흥비\t담배\n"
    )
    delimiter, headers, records = parse_csv_table(tsv)
    assert delimiter == "\t"
    assert "메모" in headers
    assert records[0]["얼마인가요?"] == "29,100"
    assert records[0]["메모"] == ""
    assert records[1]["메모"] == "담배"
    assert records[1]["어떻게 냈나요?"] == "현금"


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
            "category_id": categories["관리비"].id,
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
    assert body["rows"][0]["category_id"] == categories["관리비"].id
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
                {"category_id": categories["관리비"].id, "amount": 12_000, "scope": "BUSINESS", "line_no": 1}
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
                    "category_id": categories["관리비"].id,
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

    listed = client.get(f"/api/transactions?organization_id={organization.id}")
    assert listed.status_code == 200
    imported = next(item for item in listed.json()["items"] if item["amount"] == 5_000)
    assert imported["merchant"] == "스타벅스"
    assert imported["memo"] is None


def test_rule_crud(client: TestClient, db_session: Session) -> None:
    _organization, accounts, categories = _seed(db_session)
    created = client.post(
        "/api/v1/import/rules",
        json={
            "name": "쿠팡",
            "merchant_keyword": "쿠팡",
            "category_id": categories["관리비"].id,
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


def test_preview_cashbook_table_maps_wallet_category_and_date(client: TestClient, db_session: Session) -> None:
    organization, accounts, categories = _seed(db_session)
    for account in db_session.scalars(select(Account).where(Account.name == "카드미지급금")).all():
        account.name = "신한카드"
    db_session.flush()

    tsv = (
        "언제인가요?\t사용처\t어떻게 냈나요?\t얼마인가요?\t어디에 사용했나요?\t메모\n"
        "2026.04.30 10:14\t한국전력공사\t신한카드\t29,100\t주거/공과금\t\n"
        "2026.04.28 18:44\t지에스(GS)25 봉산문화점\t신한카드\t4,800\t용돈/유흥비\t담배\n"
    )
    preview = client.post(
        "/api/v1/import/preview",
        data={"account_id": str(accounts["1100"].id), "organization_id": str(organization.id)},
        files={"file": ("cashbook.csv", tsv.encode("utf-8"), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["profile"]["preset_key"] == "cashbook"
    rows = body["rows"]
    assert len(rows) == 2
    assert rows[0]["occurred_on"] == "2026-04-30"
    assert rows[0]["amount"] == 29_100
    assert rows[0]["merchant"] == "한국전력공사"
    assert rows[0]["transaction_type"] == TransactionType.EXPENSE.value
    assert rows[0]["category_name"] == "공과금"
    assert rows[0]["payment_account_name"] == "신한카드"
    assert rows[0]["error"] is None
    assert rows[1]["occurred_on"] == "2026-04-28"
    assert rows[1]["memo"] == "담배"
    assert rows[1]["category_name"] == "유흥비"

    commit = client.post(
        "/api/v1/import/commit",
        json={
            "organization_id": organization.id,
            "payment_account_id": accounts["1100"].id,
            "rows": [
                {
                    "occurred_on": rows[0]["occurred_on"],
                    "amount": rows[0]["amount"],
                    "merchant": rows[0]["merchant"],
                    "memo": rows[0]["memo"],
                    "transaction_type": rows[0]["transaction_type"],
                    "scope": rows[0]["scope"],
                    "category_id": rows[0]["category_id"],
                    "tag_ids": [],
                    "skip": False,
                    "payment_account_id": rows[0]["payment_account_id"],
                },
                {
                    "occurred_on": rows[1]["occurred_on"],
                    "amount": rows[1]["amount"],
                    "merchant": rows[1]["merchant"],
                    "memo": rows[1]["memo"],
                    "transaction_type": rows[1]["transaction_type"],
                    "scope": rows[1]["scope"],
                    "category_id": rows[1]["category_id"],
                    "tag_ids": [],
                    "skip": False,
                    "payment_account_id": rows[1]["payment_account_id"],
                },
            ],
        },
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["created"] == 2
    listed = client.get(f"/api/transactions?organization_id={organization.id}")
    imported = {item["merchant"]: item for item in listed.json()["items"]}
    assert imported["한국전력공사"]["amount"] == 29_100
    assert imported["한국전력공사"]["payment_account_id"] == rows[0]["payment_account_id"]
    assert imported["한국전력공사"]["occurred_on"] == "2026-04-30"
    assert imported["한국전력공사"]["memo"] is None
    assert imported["지에스(GS)25 봉산문화점"]["memo"] == "담배"


def test_preview_uses_row_wallets_without_fallback_account(client: TestClient, db_session: Session) -> None:
    organization, accounts, _categories = _seed(db_session)
    for account in db_session.scalars(select(Account).where(Account.name == "카드미지급금")).all():
        account.name = "신한 카드"
    db_session.flush()
    cash = accounts["1100"]
    card = next(account for account in db_session.scalars(select(Account).where(Account.name == "신한 카드")))
    assert match_wallet("신한카드", [cash, card]) is card

    tsv = (
        "언제인가요?\t사용처\t어떻게 냈나요?\t얼마인가요?\t어디에 사용했나요?\t메모\n"
        "2026.04.30 10:14\t한국전력공사\t신한카드\t29,100\t주거/공과금\t전기요금\n"
        "2026.04.28 18:44\t지에스(GS)25 봉산문화점\t현금\t4,800\t용돈/유흥비\t담배\n"
        "2026.04.27 19:33\t편의점\t없는카드\t4,500\t용돈/유흥비\t\n"
    )
    preview = client.post(
        "/api/v1/import/preview",
        data={"organization_id": str(organization.id)},
        files={"file": ("cashbook.csv", tsv.encode("utf-8"), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert rows[0]["payment_account_id"] == card.id
    assert rows[0]["memo"] == "전기요금"
    assert rows[1]["payment_account_id"] == cash.id
    assert rows[1]["memo"] == "담배"
    assert rows[2]["payment_account_id"] is None
    assert rows[2]["payment_account_name"] == "없는카드"

    commit = client.post(
        "/api/v1/import/commit",
        json={
            "organization_id": organization.id,
            "rows": [
                {
                    "occurred_on": rows[0]["occurred_on"],
                    "amount": rows[0]["amount"],
                    "merchant": rows[0]["merchant"],
                    "memo": rows[0]["memo"],
                    "transaction_type": rows[0]["transaction_type"],
                    "scope": rows[0]["scope"],
                    "category_id": rows[0]["category_id"],
                    "tag_ids": [],
                    "skip": False,
                    "payment_account_id": rows[0]["payment_account_id"],
                },
                {
                    "occurred_on": rows[1]["occurred_on"],
                    "amount": rows[1]["amount"],
                    "merchant": rows[1]["merchant"],
                    "memo": rows[1]["memo"],
                    "transaction_type": rows[1]["transaction_type"],
                    "scope": rows[1]["scope"],
                    "category_id": rows[1]["category_id"],
                    "tag_ids": [],
                    "skip": False,
                    "payment_account_id": rows[1]["payment_account_id"],
                },
            ],
        },
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["created"] == 2
    listed = {
        item["merchant"]: item
        for item in client.get(f"/api/transactions?organization_id={organization.id}").json()["items"]
    }
    assert listed["한국전력공사"]["memo"] == "전기요금"
    assert listed["한국전력공사"]["payment_account_id"] == card.id
    assert listed["지에스(GS)25 봉산문화점"]["memo"] == "담배"
    assert listed["지에스(GS)25 봉산문화점"]["payment_account_id"] == cash.id
