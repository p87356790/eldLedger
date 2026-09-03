from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import STANDARD_ACCOUNTS, seed_standard_data
from app.models import Account, Category, Organization, Setting, Tag
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
    food_acct = db_session.scalar(select(Account).where(Account.code == "5400"))
    assert food_acct is not None
    assert "식비" in categories
    assert "주식" in categories
    assert "매출" in categories
    assert categories["식비"].account_id == food_acct.id
    assert categories["매출"].default_scope.value == "BUSINESS"
    assert categories["식비"].default_scope.value == "PERSONAL"
    assert categories["주식"].parent_id == categories["식비"].id
    assert categories["식비"].parent_id is None

    currency = db_session.scalar(
        select(Setting).where(Setting.organization_id == organization.id, Setting.key == "currency")
    )
    assert currency is not None
    assert currency.value == "KRW"

    tags = {
        tag.name
        for tag in db_session.scalars(select(Tag).where(Tag.organization_id == organization.id))
    }
    assert {"출장", "사무실", "거래처"}.issubset(tags)


def test_clone_template_into_two_organizations_is_independent(db_session: Session) -> None:
    from app.services.chart_template_service import ChartTemplateService, template_account_count, template_category_count

    first = ChartTemplateService(db_session).create_ledger("장부 A")
    second = ChartTemplateService(db_session).create_ledger("장부 B")
    db_session.flush()

    first_accounts = {
        account.code: account
        for account in db_session.scalars(select(Account).where(Account.organization_id == first.organization.id))
    }
    second_accounts = {
        account.code: account
        for account in db_session.scalars(select(Account).where(Account.organization_id == second.organization.id))
    }
    first_categories = list(
        db_session.scalars(select(Category).where(Category.organization_id == first.organization.id))
    )
    second_categories = list(
        db_session.scalars(select(Category).where(Category.organization_id == second.organization.id))
    )

    assert first.accounts_added == template_account_count()
    assert first.categories_added == template_category_count()
    assert second.accounts_added == template_account_count()
    assert {account.id for account in first_accounts.values()}.isdisjoint({account.id for account in second_accounts.values()})
    assert first_accounts["5400"].name == second_accounts["5400"].name == "식비"
    assert first_accounts["5400"].id != second_accounts["5400"].id
    assert len(first_categories) == len(second_categories) == template_category_count()
    food_a = next(category for category in first_categories if category.name == "식비")
    food_b = next(category for category in second_categories if category.name == "식비")
    assert food_a.account_id == first_accounts["5400"].id
    assert food_b.account_id == second_accounts["5400"].id
    assert food_a.id != food_b.id


def test_provision_user_ledger_is_idempotent(db_session: Session) -> None:
    from app.models import User
    from app.models.enums import UserRole
    from app.security.passwords import hash_password
    from app.services.chart_template_service import ChartTemplateService, template_account_count, template_category_count

    organization = seed_standard_data(db_session)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        username="keeper",
        email="keeper@example.com",
        hashed_password=hash_password("user-pass-1"),
        display_name="기록원",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    result = ChartTemplateService(db_session).provision_user_ledger(user)
    db_session.flush()
    wallet_count = len(
        list(
            db_session.scalars(
                select(Account).where(
                    Account.organization_id == organization.id,
                    Account.owner_user_id == user.id,
                    Account.instrument_kind.is_not(None),
                )
            )
        )
    )
    assert result.accounts_added == wallet_count
    assert wallet_count > 0
    assert result.categories_added == template_category_count()
    again = ChartTemplateService(db_session).provision_user_ledger(user)
    db_session.flush()
    assert again.accounts_added == 0
    assert again.categories_added == 0
    assert len(list(db_session.scalars(select(Account).where(Account.organization_id == organization.id)))) >= template_account_count()
    assert len(list(db_session.scalars(select(Category).where(Category.owner_user_id == user.id)))) == template_category_count()


def test_provision_user_ledger_restores_missing_standard_category(db_session: Session) -> None:
    from app.models import User
    from app.models.enums import UserRole
    from app.security.passwords import hash_password
    from app.services.chart_template_service import ChartTemplateService, template_category_count

    organization = seed_standard_data(db_session)
    db_session.flush()
    snack = db_session.scalar(select(Category).where(Category.organization_id == organization.id, Category.name == "주식"))
    assert snack is not None
    db_session.delete(snack)
    db_session.flush()
    assert db_session.scalar(select(Category).where(Category.organization_id == organization.id, Category.name == "주식")) is None

    user = User(
        organization_id=organization.id,
        username="keeper",
        email="keeper@example.com",
        hashed_password=hash_password("user-pass-1"),
        display_name="기록원",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    restored = ChartTemplateService(db_session).provision_user_ledger(user)
    db_session.flush()
    snack = db_session.scalar(
        select(Category).where(
            Category.organization_id == organization.id,
            Category.owner_user_id == user.id,
            Category.name == "주식",
        )
    )
    assert restored.categories_added == template_category_count()
    assert snack is not None
    assert snack.parent_id is not None
    food = db_session.scalar(
        select(Category).where(
            Category.organization_id == organization.id,
            Category.owner_user_id == user.id,
            Category.name == "식비",
        )
    )
    assert food is not None
    assert snack.parent_id == food.id
    assert snack.account_id == db_session.scalar(
        select(Account.id).where(Account.organization_id == organization.id, Account.code == "5400")
    )


def test_second_user_gets_separate_wallets_and_categories(db_session: Session) -> None:
    from app.models import User
    from app.models.enums import UserRole
    from app.security.passwords import hash_password
    from app.services.chart_template_service import ChartTemplateService, template_category_count

    organization = seed_standard_data(db_session)
    db_session.flush()
    first = User(
        organization_id=organization.id,
        username="first",
        email="first@example.com",
        hashed_password=hash_password("user-pass-1"),
        display_name="첫째",
        role=UserRole.ADMIN,
        is_active=True,
    )
    second = User(
        organization_id=organization.id,
        username="second",
        email="second@example.com",
        hashed_password=hash_password("user-pass-1"),
        display_name="둘째",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add_all([first, second])
    db_session.flush()
    ChartTemplateService(db_session).provision_user_ledger(first)
    ChartTemplateService(db_session).provision_user_ledger(second)
    db_session.flush()

    first_cats = {
        category.name: category.id
        for category in db_session.scalars(select(Category).where(Category.owner_user_id == first.id))
    }
    second_cats = {
        category.name: category.id
        for category in db_session.scalars(select(Category).where(Category.owner_user_id == second.id))
    }
    first_wallets = {
        account.id
        for account in db_session.scalars(
            select(Account).where(Account.owner_user_id == first.id, Account.instrument_kind.is_not(None))
        )
    }
    second_wallets = {
        account.id
        for account in db_session.scalars(
            select(Account).where(Account.owner_user_id == second.id, Account.instrument_kind.is_not(None))
        )
    }
    assert "식비" in first_cats and "식비" in second_cats
    assert first_cats["식비"] != second_cats["식비"]
    assert len(first_cats) == len(second_cats) == template_category_count()
    assert first_wallets and second_wallets
    assert first_wallets.isdisjoint(second_wallets)


def test_reset_all_data_restores_first_run(db_session: Session) -> None:
    from app.db.reset import reset_all_data
    from app.models import User
    from app.models.enums import UserRole
    from app.security.passwords import hash_password

    organization = seed_standard_data(db_session)
    db_session.flush()
    db_session.add(
        User(
            organization_id=organization.id,
            username="admin",
            email="admin@eldledger.local",
            hashed_password=hash_password("secret-pass-1"),
            display_name="관리자",
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    db_session.flush()
    assert db_session.scalar(select(User)) is not None

    reset_all_data(db_session)
    db_session.flush()
    assert db_session.scalar(select(User)) is None
    assert len(list(db_session.scalars(select(Account)))) == len(STANDARD_ACCOUNTS)
