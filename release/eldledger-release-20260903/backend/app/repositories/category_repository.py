from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Account, Category, TransactionItem
from app.models.enums import AccountType, TransactionType


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, category_id: int) -> Category | None:
        return self._session.scalar(
            select(Category).options(selectinload(Category.account)).where(Category.id == category_id)
        )

    def list_categories(
        self,
        organization_id: int,
        *,
        owner_user_id: int | None = None,
        transaction_type: TransactionType | None = None,
        include_hidden: bool = False,
    ) -> list[Category]:
        stmt = (
            select(Category)
            .options(selectinload(Category.account))
            .where(Category.organization_id == organization_id)
            .order_by(Category.sort_order, Category.name)
        )
        if owner_user_id is not None:
            stmt = stmt.where(Category.owner_user_id == owner_user_id)
        if transaction_type is not None:
            stmt = stmt.where(Category.transaction_type == transaction_type)
        if not include_hidden:
            stmt = stmt.where(Category.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def get_by_name(
        self,
        organization_id: int,
        name: str,
        *,
        owner_user_id: int | None = None,
    ) -> Category | None:
        stmt = select(Category).where(Category.organization_id == organization_id, Category.name == name)
        if owner_user_id is not None:
            stmt = stmt.where(Category.owner_user_id == owner_user_id)
        else:
            stmt = stmt.where(Category.owner_user_id.is_(None))
        return self._session.scalar(stmt)

    def next_sort_order(
        self,
        organization_id: int,
        parent_id: int | None,
        *,
        owner_user_id: int | None = None,
    ) -> int:
        stmt = select(func.max(Category.sort_order)).where(Category.organization_id == organization_id)
        if owner_user_id is not None:
            stmt = stmt.where(Category.owner_user_id == owner_user_id)
        if parent_id is None:
            stmt = stmt.where(Category.parent_id.is_(None))
        else:
            stmt = stmt.where(Category.parent_id == parent_id)
        current = self._session.scalar(stmt)
        return int(current or 0) + 10

    def list_children(self, parent_id: int, *, include_hidden: bool = True) -> list[Category]:
        stmt = select(Category).where(Category.parent_id == parent_id).order_by(Category.sort_order, Category.name)
        if not include_hidden:
            stmt = stmt.where(Category.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def has_children(self, category_id: int) -> bool:
        return (
            self._session.scalar(select(Category.id).where(Category.parent_id == category_id).limit(1)) is not None
        )

    def used_in_transactions(self, category_id: int) -> bool:
        return (
            self._session.scalar(select(TransactionItem.id).where(TransactionItem.category_id == category_id).limit(1))
            is not None
        )

    def list_chart_accounts(self, organization_id: int, transaction_type: TransactionType) -> list[Account]:
        account_type = AccountType.REVENUE if transaction_type == TransactionType.INCOME else AccountType.EXPENSE
        return list(
            self._session.scalars(
                select(Account)
                .where(
                    Account.organization_id == organization_id,
                    Account.account_type == account_type,
                    Account.is_postable.is_(True),
                    Account.is_active.is_(True),
                )
                .order_by(Account.sort_order, Account.code)
            ).all()
        )
