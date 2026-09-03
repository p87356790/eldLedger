"""Clone the built-in chart/category template into a user's ledger (organization)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init_db import (
    STANDARD_ACCOUNTS,
    STANDARD_CATEGORIES,
    _account_by_code,
    seed_accounts,
    seed_categories,
    seed_missing_standard_accounts,
    seed_settings,
    seed_tags,
    seed_wallet_metadata,
)
from app.models import Account, Category, Organization, User
from app.services.accounting_service import AccountingError


@dataclass(frozen=True)
class ChartCloneResult:
    organization: Organization
    accounts_added: int
    categories_added: int


class ChartTemplateService:
    """Copies STANDARD_ACCOUNTS / STANDARD_CATEGORIES into an organization.

    Accounts and categories are scoped to Organization (the user's ledger), not User.
    Invited users share the actor's ledger, so a second clone is a no-op except for
    missing template rows. A brand-new organization always gets a full independent copy.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def provision_user_ledger(self, user: User) -> ChartCloneResult:
        organization = self._session.get(Organization, user.organization_id)
        if organization is None:
            raise AccountingError("장부를 찾을 수 없어요.")
        return self.clone_into(organization)

    def create_ledger(self, name: str) -> ChartCloneResult:
        organization = Organization(name=name.strip(), is_active=True)
        self._session.add(organization)
        self._session.flush()
        return self.clone_into(organization)

    def clone_into(self, organization: Organization) -> ChartCloneResult:
        accounts_before = self._account_count(organization.id)
        categories_before = self._category_count(organization.id)
        seed_accounts(self._session, organization)
        seed_missing_standard_accounts(self._session, organization)
        seed_wallet_metadata(self._session, organization)
        seed_categories(self._session, organization)
        self._insert_missing_categories(organization)
        seed_tags(self._session, organization)
        seed_settings(self._session, organization)
        self._session.flush()
        return ChartCloneResult(
            organization=organization,
            accounts_added=self._account_count(organization.id) - accounts_before,
            categories_added=self._category_count(organization.id) - categories_before,
        )

    def _insert_missing_categories(self, organization: Organization) -> None:
        existing = {
            category.name: category
            for category in self._session.scalars(
                select(Category).where(Category.organization_id == organization.id)
            )
        }
        for seed in STANDARD_CATEGORIES:
            if seed.name in existing:
                continue
            account = _account_by_code(self._session, organization.id, seed.account_code)
            parent_id = existing[seed.parent_name].id if seed.parent_name is not None and seed.parent_name in existing else None
            category = Category(
                organization_id=organization.id,
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

    def _account_count(self, organization_id: int) -> int:
        return len(
            list(
                self._session.scalars(select(Account.id).where(Account.organization_id == organization_id))
            )
        )

    def _category_count(self, organization_id: int) -> int:
        return len(
            list(
                self._session.scalars(select(Category.id).where(Category.organization_id == organization_id))
            )
        )


def template_account_count() -> int:
    return len(STANDARD_ACCOUNTS)


def template_category_count() -> int:
    return len(STANDARD_CATEGORIES)
