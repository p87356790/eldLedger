from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import STANDARD_ACCOUNTS, seed_standard_data
from app.models import Account, Category, Organization, Setting
from app.models.enums import AccountType, NormalBalance


def test_seed_creates_chart_of_accounts_tree(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()

    accounts = list(db_session.scalars(select(Account).where(Account.organization_id == organization.id)))
    by_code = {account.code: account for account in accounts}

    assert organization.name == "내 장부"
    assert len(by_code) == len(STANDARD_ACCOUNTS)

    assert by_code["1000"].name == "자산"
    assert by_code["1000"].account_type == AccountType.ASSET
    assert by_code["1000"].is_postable is False
    assert by_code["1000"].parent_id is None

    assert by_code["1100"].name == "현금"
    assert by_code["1100"].parent_id == by_code["1000"].id
    assert by_code["1100"].is_postable is True
    assert by_code["1100"].is_payment_method is True
    assert by_code["1100"].normal_balance == NormalBalance.DEBIT

    assert by_code["2100"].name == "카드미지급금"
    assert by_code["2100"].parent_id == by_code["2000"].id
    assert by_code["2100"].account_type == AccountType.LIABILITY
    assert by_code["2100"].normal_balance == NormalBalance.CREDIT

    assert by_code["3100"].name == "개인자본"
    assert by_code["4100"].name == "사업매출"
    assert by_code["5100"].name == "사무용품비"
    assert by_code["5700"].name == "개인사용"


def test_seed_is_idempotent(db_session: Session) -> None:
    seed_standard_data(db_session)
    db_session.flush()
    seed_standard_data(db_session)
    db_session.flush()

    assert db_session.scalar(select(Organization).where(Organization.name == "내 장부")) is not None
    account_count = len(list(db_session.scalars(select(Account))))
    assert account_count == len(STANDARD_ACCOUNTS)


def test_seed_creates_user_facing_categories(db_session: Session) -> None:
    organization = seed_standard_data(db_session)
    db_session.flush()
    categories = {
        category.name: category
        for category in db_session.scalars(
            select(Category).where(Category.organization_id == organization.id)
        )
    }
    supplies = db_session.scalar(select(Account).where(Account.code == "5100"))
    assert supplies is not None
    assert "사무용품" in categories
    assert categories["사무용품"].account_id == supplies.id

    currency = db_session.scalar(
        select(Setting).where(Setting.organization_id == organization.id, Setting.key == "currency")
    )
    assert currency is not None
    assert currency.value == "KRW"
