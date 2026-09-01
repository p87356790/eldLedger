from dataclasses import dataclass

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Account, Category, Organization, Setting
from app.models.enums import AccountType, NORMAL_BALANCE_BY_TYPE, TransactionType

DEFAULT_ORGANIZATION_NAME = "내 장부"


@dataclass(frozen=True)
class AccountSeed:
    code: str
    name: str
    account_type: AccountType
    parent_code: str | None
    is_postable: bool
    is_payment_method: bool = False
    sort_order: int = 0


@dataclass(frozen=True)
class CategorySeed:
    name: str
    account_code: str
    transaction_type: TransactionType
    sort_order: int = 0


# Section 13 chart of accounts (tree). 5700 개인사용 is included so MIXED
# splits in section 11 can post the personal portion to a formal account.
STANDARD_ACCOUNTS: tuple[AccountSeed, ...] = (
    AccountSeed("1000", "자산", AccountType.ASSET, None, False, sort_order=1000),
    AccountSeed("1100", "현금", AccountType.ASSET, "1000", True, True, 1100),
    AccountSeed("1200", "보통예금", AccountType.ASSET, "1000", True, True, 1200),
    AccountSeed("1300", "신용카드", AccountType.ASSET, "1000", True, True, 1300),
    AccountSeed("1400", "미수금", AccountType.ASSET, "1000", True, False, 1400),
    AccountSeed("1500", "비품", AccountType.ASSET, "1000", True, False, 1500),
    AccountSeed("2000", "부채", AccountType.LIABILITY, None, False, sort_order=2000),
    AccountSeed("2100", "카드미지급금", AccountType.LIABILITY, "2000", True, True, 2100),
    AccountSeed("2200", "미지급금", AccountType.LIABILITY, "2000", True, False, 2200),
    AccountSeed("2300", "대출금", AccountType.LIABILITY, "2000", True, False, 2300),
    AccountSeed("3000", "자본", AccountType.EQUITY, None, False, sort_order=3000),
    AccountSeed("3100", "개인자본", AccountType.EQUITY, "3000", True, False, 3100),
    AccountSeed("4000", "수익", AccountType.REVENUE, None, False, sort_order=4000),
    AccountSeed("4100", "사업매출", AccountType.REVENUE, "4000", True, False, 4100),
    AccountSeed("4200", "기타수익", AccountType.REVENUE, "4000", True, False, 4200),
    AccountSeed("5000", "비용", AccountType.EXPENSE, None, False, sort_order=5000),
    AccountSeed("5100", "사무용품비", AccountType.EXPENSE, "5000", True, False, 5100),
    AccountSeed("5200", "통신비", AccountType.EXPENSE, "5000", True, False, 5200),
    AccountSeed("5300", "교통비", AccountType.EXPENSE, "5000", True, False, 5300),
    AccountSeed("5400", "식비", AccountType.EXPENSE, "5000", True, False, 5400),
    AccountSeed("5500", "접대비", AccountType.EXPENSE, "5000", True, False, 5500),
    AccountSeed("5600", "차량유지비", AccountType.EXPENSE, "5000", True, False, 5600),
    AccountSeed("5700", "개인사용", AccountType.EXPENSE, "5000", True, False, 5700),
)

STANDARD_CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed("사업매출", "4100", TransactionType.INCOME, 10),
    CategorySeed("기타수익", "4200", TransactionType.INCOME, 20),
    CategorySeed("사무용품", "5100", TransactionType.EXPENSE, 30),
    CategorySeed("통신", "5200", TransactionType.EXPENSE, 40),
    CategorySeed("교통", "5300", TransactionType.EXPENSE, 50),
    CategorySeed("식비", "5400", TransactionType.EXPENSE, 60),
    CategorySeed("접대", "5500", TransactionType.EXPENSE, 70),
    CategorySeed("차량유지", "5600", TransactionType.EXPENSE, 80),
    CategorySeed("개인사용", "5700", TransactionType.EXPENSE, 90),
)


def _get_or_create_organization(session: Session) -> Organization:
    organization = session.scalar(
        select(Organization).where(Organization.name == DEFAULT_ORGANIZATION_NAME)
    )
    if organization is None:
        organization = Organization(name=DEFAULT_ORGANIZATION_NAME, is_active=True)
        session.add(organization)
        session.flush()
    return organization


def _account_by_code(session: Session, organization_id: int, code: str) -> Account:
    account = session.scalar(
        select(Account).where(
            Account.organization_id == organization_id,
            Account.code == code,
        )
    )
    if account is None:
        raise RuntimeError(f"표준 계정과목을 찾을 수 없습니다: {code}")
    return account


def seed_accounts(session: Session, organization: Organization) -> None:
    existing = session.scalar(
        select(Account.id).where(Account.organization_id == organization.id).limit(1)
    )
    if existing is not None:
        return

    created: dict[str, Account] = {}
    for seed in STANDARD_ACCOUNTS:
        parent_id = created[seed.parent_code].id if seed.parent_code is not None else None
        account = Account(
            organization_id=organization.id,
            parent_id=parent_id,
            code=seed.code,
            name=seed.name,
            account_type=seed.account_type,
            normal_balance=NORMAL_BALANCE_BY_TYPE[seed.account_type],
            is_postable=seed.is_postable,
            is_payment_method=seed.is_payment_method,
            is_system=True,
            is_active=True,
            sort_order=seed.sort_order,
        )
        session.add(account)
        session.flush()
        created[seed.code] = account


def seed_categories(session: Session, organization: Organization) -> None:
    existing = session.scalar(
        select(Category.id).where(Category.organization_id == organization.id).limit(1)
    )
    if existing is not None:
        return

    for seed in STANDARD_CATEGORIES:
        account = _account_by_code(session, organization.id, seed.account_code)
        session.add(
            Category(
                organization_id=organization.id,
                account_id=account.id,
                name=seed.name,
                transaction_type=seed.transaction_type,
                is_active=True,
                sort_order=seed.sort_order,
            )
        )


def seed_settings(session: Session, organization: Organization) -> None:
    existing = session.scalar(
        select(Setting.id).where(
            Setting.organization_id == organization.id,
            Setting.key == "currency",
        )
    )
    if existing is not None:
        return
    session.add(Setting(organization_id=organization.id, key="currency", value="KRW"))


def seed_standard_data(session: Session) -> Organization:
    organization = _get_or_create_organization(session)
    seed_accounts(session, organization)
    seed_categories(session, organization)
    seed_settings(session, organization)
    return organization


def init_db() -> None:
    """Insert reference data. Table schema is owned by Alembic migrations."""
    inspector = inspect(engine)
    if "organizations" not in inspector.get_table_names():
        return
    with SessionLocal() as session:
        seed_standard_data(session)
        session.commit()


if __name__ == "__main__":
    init_db()
