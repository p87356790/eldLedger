"""Clone the built-in chart/category template into a user's ledger."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import (
    STANDARD_ACCOUNTS,
    STANDARD_CATEGORIES,
    STANDARD_TAGS,
    _account_by_code,
    seed_accounts,
    seed_categories,
    seed_missing_standard_accounts,
    seed_settings,
    seed_tags,
    seed_wallet_metadata,
)
from app.models import Account, Category, Organization, Tag, User
from app.models.enums import NORMAL_BALANCE_BY_TYPE
from app.services.accounting_service import AccountingError
from app.services.account_service import KIND_PARENT_CODE


@dataclass(frozen=True)
class ChartCloneResult:
    organization: Organization
    accounts_added: int
    categories_added: int


class ChartTemplateService:
    """Copies STANDARD_ACCOUNTS into an organization (shared chart).

    User-facing wallets, categories, and tags are scoped to User via owner_user_id.
    The first member claims the seeded rows; later members get their own copies.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def provision_user_ledger(self, user: User) -> ChartCloneResult:
        organization = self._session.get(Organization, user.organization_id)
        if organization is None:
            raise AccountingError("장부를 찾을 수 없어요.")
        self.clone_into(organization)
        accounts_before = self._wallet_count(organization.id, user.id)
        categories_before = self._category_count(organization.id, user.id)
        self._claim_or_clone_wallets(user)
        self._claim_or_clone_categories(user)
        self._claim_or_clone_tags(user)
        self._session.flush()
        self._insert_missing_categories(user)
        self._session.flush()
        return ChartCloneResult(
            organization=organization,
            accounts_added=self._wallet_count(organization.id, user.id) - accounts_before,
            categories_added=self._category_count(organization.id, user.id) - categories_before,
        )

    def create_ledger(self, name: str) -> ChartCloneResult:
        organization = Organization(name=name.strip(), is_active=True)
        self._session.add(organization)
        self._session.flush()
        return self.clone_into(organization)

    def clone_into(self, organization: Organization) -> ChartCloneResult:
        accounts_before = self._account_count(organization.id)
        categories_before = self._category_count(organization.id, None)
        seed_accounts(self._session, organization)
        seed_missing_standard_accounts(self._session, organization)
        seed_wallet_metadata(self._session, organization)
        seed_categories(self._session, organization)
        seed_tags(self._session, organization)
        seed_settings(self._session, organization)
        self._session.flush()
        return ChartCloneResult(
            organization=organization,
            accounts_added=self._account_count(organization.id) - accounts_before,
            categories_added=self._category_count(organization.id, None) - categories_before,
        )

    def _claim_or_clone_wallets(self, user: User) -> None:
        owned = self._wallet_count(user.organization_id, user.id)
        if owned > 0:
            return
        unowned = list(
            self._session.scalars(
                select(Account).where(
                    Account.organization_id == user.organization_id,
                    Account.instrument_kind.is_not(None),
                    Account.owner_user_id.is_(None),
                )
            )
        )
        if unowned:
            for account in unowned:
                account.owner_user_id = user.id
            return
        used_codes = {
            code
            for code in self._session.scalars(
                select(Account.code).where(Account.organization_id == user.organization_id)
            )
        }
        for seed in STANDARD_ACCOUNTS:
            if seed.instrument_kind is None:
                continue
            parent = _account_by_code(self._session, user.organization_id, KIND_PARENT_CODE[seed.instrument_kind])
            code = self._next_code(parent.code, used_codes)
            used_codes.add(code)
            self._session.add(
                Account(
                    organization_id=user.organization_id,
                    owner_user_id=user.id,
                    parent_id=parent.id,
                    code=code,
                    name=seed.name,
                    account_type=seed.account_type,
                    normal_balance=NORMAL_BALANCE_BY_TYPE[seed.account_type],
                    is_postable=True,
                    is_payment_method=seed.is_payment_method,
                    is_system=False,
                    is_active=True,
                    sort_order=seed.sort_order,
                    instrument_kind=seed.instrument_kind,
                    currency="KRW",
                    opening_balance=0,
                )
            )

    def _claim_or_clone_categories(self, user: User) -> None:
        if self._category_count(user.organization_id, user.id) > 0:
            return
        unowned = list(
            self._session.scalars(
                select(Category).where(
                    Category.organization_id == user.organization_id,
                    Category.owner_user_id.is_(None),
                )
            )
        )
        if unowned:
            for category in unowned:
                category.owner_user_id = user.id
            return
        created: dict[str, Category] = {}
        for seed in STANDARD_CATEGORIES:
            account = _account_by_code(self._session, user.organization_id, seed.account_code)
            parent_id = created[seed.parent_name].id if seed.parent_name is not None else None
            category = Category(
                organization_id=user.organization_id,
                owner_user_id=user.id,
                parent_id=parent_id,
                account_id=account.id,
                name=seed.name,
                transaction_type=seed.transaction_type,
                default_scope=seed.default_scope,
                icon=seed.icon,
                is_system=True,
                is_active=True,
                sort_order=seed.sort_order,
            )
            self._session.add(category)
            self._session.flush()
            created[seed.name] = category

    def _claim_or_clone_tags(self, user: User) -> None:
        owned = list(
            self._session.scalars(
                select(Tag.id).where(
                    Tag.organization_id == user.organization_id,
                    Tag.owner_user_id == user.id,
                )
            )
        )
        if owned:
            return
        unowned = list(
            self._session.scalars(
                select(Tag).where(
                    Tag.organization_id == user.organization_id,
                    Tag.owner_user_id.is_(None),
                )
            )
        )
        if unowned:
            for tag in unowned:
                tag.owner_user_id = user.id
            return
        for seed in STANDARD_TAGS:
            self._session.add(
                Tag(organization_id=user.organization_id, owner_user_id=user.id, name=seed.name)
            )

    def _insert_missing_categories(self, user: User) -> None:
        existing = {
            category.name: category
            for category in self._session.scalars(
                select(Category).where(
                    Category.organization_id == user.organization_id,
                    Category.owner_user_id == user.id,
                )
            )
        }
        for seed in STANDARD_CATEGORIES:
            if seed.name in existing:
                continue
            account = _account_by_code(self._session, user.organization_id, seed.account_code)
            parent_id = existing[seed.parent_name].id if seed.parent_name is not None and seed.parent_name in existing else None
            category = Category(
                organization_id=user.organization_id,
                owner_user_id=user.id,
                parent_id=parent_id,
                account_id=account.id,
                name=seed.name,
                transaction_type=seed.transaction_type,
                default_scope=seed.default_scope,
                icon=seed.icon,
                is_system=True,
                is_active=True,
                sort_order=seed.sort_order,
            )
            self._session.add(category)
            self._session.flush()
            existing[seed.name] = category

    def _next_code(self, parent_code: str, used: set[str]) -> str:
        if parent_code.isdigit():
            base = int(parent_code)
            for offset in range(1, 1000):
                candidate = str(base + offset)
                if candidate not in used:
                    return candidate
        suffix = 1
        while True:
            candidate = f"{parent_code}-{suffix}"
            if candidate not in used:
                return candidate
            suffix += 1

    def _account_count(self, organization_id: int) -> int:
        return len(
            list(
                self._session.scalars(select(Account.id).where(Account.organization_id == organization_id))
            )
        )

    def _wallet_count(self, organization_id: int, owner_user_id: int) -> int:
        return len(
            list(
                self._session.scalars(
                    select(Account.id).where(
                        Account.organization_id == organization_id,
                        Account.owner_user_id == owner_user_id,
                        Account.instrument_kind.is_not(None),
                    )
                )
            )
        )

    def _category_count(self, organization_id: int, owner_user_id: int | None) -> int:
        stmt = select(Category.id).where(Category.organization_id == organization_id)
        if owner_user_id is None:
            stmt = stmt.where(Category.owner_user_id.is_(None))
        else:
            stmt = stmt.where(Category.owner_user_id == owner_user_id)
        return len(list(self._session.scalars(stmt)))


def template_account_count() -> int:
    return len(STANDARD_ACCOUNTS)


def template_category_count() -> int:
    return len(STANDARD_CATEGORIES)
