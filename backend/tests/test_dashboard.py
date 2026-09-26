from calendar import monthrange
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.db.init_db import seed_standard_data
from app.main import app
from app.models import Organization, User
from app.models.enums import UserRole
from app.security.deps import get_current_user
from app.security.passwords import hash_password
from app.services.chart_template_service import ChartTemplateService


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


def _post_tx(
    client: TestClient,
    *,
    organization_id: int,
    occurred_on: str,
    transaction_type: str,
    scope: str,
    amount: int,
    payment_account_id: int,
    category_id: int | None = None,
    items: list[dict] | None = None,
    transfer_account_id: int | None = None,
    memo: str | None = None,
) -> dict:
    payload: dict = {
        "organization_id": organization_id,
        "occurred_on": occurred_on,
        "transaction_type": transaction_type,
        "scope": scope,
        "amount": amount,
        "memo": memo,
        "payment_account_id": payment_account_id,
        "transfer_account_id": transfer_account_id,
        "items": items
        if items is not None
        else (
            []
            if transaction_type == "TRANSFER"
            else [
                {
                    "category_id": category_id,
                    "amount": amount,
                    "scope": scope,
                    "line_no": 1,
                }
            ]
        ),
    }
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_dashboard_defaults_to_current_month(client: TestClient, db_session: Session) -> None:
    _seed(db_session)
    today = date.today()
    last_day = monthrange(today.year, today.month)[1]
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert summary["start_date"] == date(today.year, today.month, 1).isoformat()
    assert summary["end_date"] == date(today.year, today.month, last_day).isoformat()
    assert summary["total_income"] == 0
    assert summary["total_expense"] == 0
    assert summary["net_change"] == 0
    assert summary["business_profit"] == 0


def test_dashboard_rejects_inverted_range(client: TestClient, db_session: Session) -> None:
    _seed(db_session)
    response = client.get("/api/v1/dashboard/summary?start_date=2026-09-30&end_date=2026-09-01")
    assert response.status_code == 400


def test_dashboard_summarizes_scope_and_excludes_transfers(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    cash = wallets["CASH"]
    bank = wallets["BANK"]

    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-02",
        transaction_type="INCOME",
        scope="PERSONAL",
        amount=50_000,
        payment_account_id=bank["id"],
        category_id=categories["기타수익"]["id"],
        memo="개인 입금",
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-03",
        transaction_type="INCOME",
        scope="BUSINESS",
        amount=200_000,
        payment_account_id=bank["id"],
        category_id=categories["매출"]["id"],
        memo="세금계산서",
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-04",
        transaction_type="EXPENSE",
        scope="MIXED",
        amount=100_000,
        payment_account_id=cash["id"],
        items=[
            {
                "category_id": categories["관리비"]["id"],
                "amount": 40_000,
                "scope": "BUSINESS",
                "line_no": 1,
            },
            {
                "category_id": categories["식비"]["id"],
                "amount": 60_000,
                "scope": "PERSONAL",
                "line_no": 2,
            },
        ],
        memo="혼합 결제",
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-05",
        transaction_type="TRANSFER",
        scope="PERSONAL",
        amount=30_000,
        payment_account_id=bank["id"],
        transfer_account_id=cash["id"],
        memo="이체",
    )

    all_rows = client.get(
        "/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30"
    )
    assert all_rows.status_code == 200, all_rows.text
    body = all_rows.json()
    assert body["summary"]["total_income"] == 250_000
    assert body["summary"]["total_expense"] == 100_000
    assert body["summary"]["net_change"] == 150_000
    assert body["summary"]["business_income"] == 200_000
    assert body["summary"]["business_expense"] == 40_000
    assert body["summary"]["business_profit"] == 160_000
    assert len(body["transactions"]) == 4
    assert any(row["transaction_type"] == "TRANSFER" for row in body["transactions"])
    daily_by_date = {row["date"]: row for row in body["daily"]}
    assert daily_by_date["2026-09-04"]["total_expense"] == 100_000
    assert daily_by_date["2026-09-04"]["transaction_count"] == 1
    assert daily_by_date["2026-09-05"]["total_income"] == 0
    assert daily_by_date["2026-09-05"]["total_expense"] == 0
    assert daily_by_date["2026-09-05"]["transaction_count"] == 1

    personal = client.get(
        "/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&scope=PERSONAL"
    ).json()
    assert personal["summary"]["total_income"] == 50_000
    assert personal["summary"]["total_expense"] == 60_000
    assert personal["summary"]["net_change"] == -10_000
    assert personal["summary"]["business_profit"] == 160_000
    assert {row["transaction_type"] for row in personal["transactions"]} == {"INCOME", "EXPENSE", "TRANSFER"}

    business = client.get(
        "/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&scope=BUSINESS"
    ).json()
    assert business["summary"]["total_income"] == 200_000
    assert business["summary"]["total_expense"] == 40_000
    assert business["summary"]["net_change"] == 160_000
    assert business["summary"]["business_profit"] == 160_000
    assert all(row["transaction_type"] != "TRANSFER" for row in business["transactions"])


def test_dashboard_filters_by_owned_account(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    cash = wallets["CASH"]
    bank = wallets["BANK"]
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-10",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=12_000,
        payment_account_id=cash["id"],
        category_id=categories["식비"]["id"],
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-11",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=33_000,
        payment_account_id=bank["id"],
        category_id=categories["식비"]["id"],
    )
    filtered = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={cash['id']}"
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["summary"]["total_expense"] == 12_000
    assert len(body["transactions"]) == 1
    assert body["transactions"][0]["payment_method"] == cash["name"]
    assert body["transactions"][0]["category_name"] == "식비"
    assert body["transactions"][0]["has_attachment"] is False

    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-12",
        transaction_type="TRANSFER",
        scope="PERSONAL",
        amount=20_000,
        payment_account_id=bank["id"],
        transfer_account_id=cash["id"],
        memo="은행에서 현금",
    )
    incoming = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={cash['id']}"
    )
    assert incoming.status_code == 200, incoming.text
    cash_body = incoming.json()
    assert cash_body["summary"]["total_income"] == 20_000
    assert cash_body["summary"]["total_expense"] == 12_000
    cash_daily = {row["date"]: row for row in cash_body["daily"]}
    assert cash_daily["2026-09-12"]["total_income"] == 20_000
    assert cash_daily["2026-09-12"]["transaction_count"] == 1
    transfer_row = next(row for row in cash_body["transactions"] if row["transaction_type"] == "TRANSFER")
    assert transfer_row["signed_amount"] == 20_000
    assert "→" in transfer_row["payment_method"]

    outgoing = client.get(
        f"/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id={bank['id']}"
    ).json()
    assert outgoing["summary"]["total_income"] == 0
    assert outgoing["summary"]["total_expense"] == 53_000
    bank_transfer = next(row for row in outgoing["transactions"] if row["transaction_type"] == "TRANSFER")
    assert bank_transfer["signed_amount"] == -20_000

    missing = client.get(
        "/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30&account_id=999999"
    )
    assert missing.status_code == 404


def test_dashboard_rolls_up_parent_categories_with_previous_month(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    cash = wallets["CASH"]

    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-08-20",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=80_000,
        payment_account_id=cash["id"],
        category_id=categories["공과금"]["id"],
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-08-21",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=20_000,
        payment_account_id=cash["id"],
        category_id=categories["식비"]["id"],
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-04",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=100_000,
        payment_account_id=cash["id"],
        category_id=categories["공과금"]["id"],
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-05",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=45_000,
        payment_account_id=cash["id"],
        category_id=categories["간식"]["id"],
    )
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-06",
        transaction_type="INCOME",
        scope="PERSONAL",
        amount=50_000,
        payment_account_id=cash["id"],
        category_id=categories["급여"]["id"],
    )

    body = client.get("/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30").json()
    assert body["previous_start_date"] == "2026-08-01"
    assert body["previous_end_date"] == "2026-08-31"
    expenses = {row["name"]: row for row in body["category_totals"] if row["transaction_type"] == "EXPENSE"}
    incomes = {row["name"]: row for row in body["category_totals"] if row["transaction_type"] == "INCOME"}
    assert "공과금" not in expenses
    assert "간식" not in expenses
    assert expenses["주거"]["current_amount"] == 100_000
    assert expenses["주거"]["previous_amount"] == 80_000
    assert expenses["식비"]["current_amount"] == 45_000
    assert expenses["식비"]["previous_amount"] == 20_000
    assert incomes["급여"]["current_amount"] == 50_000
    assert incomes["급여"]["previous_amount"] == 0
    assert body["summary"]["total_expense"] == 145_000
    assert body["summary"]["total_income"] == 50_000


def test_dashboard_hides_other_users_transactions(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-12",
        transaction_type="EXPENSE",
        scope="PERSONAL",
        amount=9_000,
        payment_account_id=wallets["CASH"]["id"],
        category_id=categories["식비"]["id"],
    )
    second = User(
        organization_id=organization.id,
        username="other",
        email="other@eldledger.local",
        hashed_password=hash_password("test-pass-1"),
        display_name="다른사람",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(second)
    db_session.flush()
    ChartTemplateService(db_session).provision_user_ledger(second)
    db_session.flush()

    def override_second() -> User:
        loaded = db_session.get(User, second.id)
        assert loaded is not None
        return loaded

    app.dependency_overrides[get_current_user] = override_second
    try:
        response = client.get("/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30")
        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["total_expense"] == 0
        assert body["transactions"] == []
    finally:
        admin = db_session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None

        def override_admin() -> User:
            loaded = db_session.get(User, admin.id)
            assert loaded is not None
            return loaded

        app.dependency_overrides[get_current_user] = override_admin


def test_dashboard_income_with_deductions_uses_gross_and_withholding(client: TestClient, db_session: Session) -> None:
    organization = _seed(db_session)
    wallets = _wallets(client, organization.id)
    categories = _categories(client, organization.id)
    bank = wallets["BANK"]

    created = _post_tx(
        client,
        organization_id=organization.id,
        occurred_on="2026-09-25",
        transaction_type="INCOME",
        scope="PERSONAL",
        amount=4_200_000,
        payment_account_id=bank["id"],
        items=[
            {
                "category_id": categories["급여"]["id"],
                "amount": 5_000_000,
                "scope": "PERSONAL",
                "line_no": 1,
                "line_kind": "STANDARD",
            },
            {
                "category_id": categories["세금"]["id"],
                "amount": 800_000,
                "scope": "PERSONAL",
                "line_no": 2,
                "line_kind": "DEDUCTION",
            },
        ],
        memo="9월 급여",
    )
    assert created["amount"] == 4_200_000

    body = client.get("/api/v1/dashboard/summary?start_date=2026-09-01&end_date=2026-09-30").json()
    assert body["summary"]["total_income"] == 5_000_000
    assert body["summary"]["total_expense"] == 800_000
    assert body["summary"]["net_change"] == 4_200_000
    assert len(body["transactions"]) == 1
    row = body["transactions"][0]
    assert row["amount"] == 4_200_000
    assert row["signed_amount"] == 4_200_000
    assert row["gross_amount"] == 5_000_000
    assert row["deduction_amount"] == 800_000
    tax_total = next(item for item in body["category_totals"] if item["name"] == "세금/이자")
    salary_total = next(item for item in body["category_totals"] if item["name"] == "급여")
    assert tax_total["transaction_type"] == "EXPENSE"
    assert tax_total["current_amount"] == 800_000
    assert salary_total["transaction_type"] == "INCOME"
    assert salary_total["current_amount"] == 5_000_000
