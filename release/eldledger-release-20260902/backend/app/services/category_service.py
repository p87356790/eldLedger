from sqlalchemy.orm import Session

from app.models import Account, Category, Organization
from app.models.enums import AccountType, TransactionType
from app.repositories.category_repository import CategoryRepository
from app.schemas.categories import (
    CategoryCreate,
    CategoryRead,
    CategoryReorderItem,
    CategoryUpdate,
    ChartAccountOption,
)
from app.services.accounting_service import AccountingError


class CategoryService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = CategoryRepository(session)

    def list_categories(
        self,
        organization_id: int,
        *,
        transaction_type: TransactionType | None = None,
        include_hidden: bool = False,
    ) -> list[CategoryRead]:
        self._require_organization(organization_id)
        return [
            self._to_read(category)
            for category in self._repo.list_categories(
                organization_id,
                transaction_type=transaction_type,
                include_hidden=include_hidden,
            )
        ]

    def list_chart_options(self, organization_id: int, transaction_type: TransactionType) -> list[ChartAccountOption]:
        self._require_organization(organization_id)
        if transaction_type not in {TransactionType.INCOME, TransactionType.EXPENSE}:
            raise AccountingError("분류는 수입 또는 지출만 지정할 수 있습니다.")
        return [ChartAccountOption.model_validate(account) for account in self._repo.list_chart_accounts(organization_id, transaction_type)]

    def get_category(self, category_id: int) -> CategoryRead:
        return self._to_read(self._require_category(category_id))

    def create_category(self, payload: CategoryCreate) -> CategoryRead:
        self._require_organization(payload.organization_id)
        self._assert_unique_name(payload.organization_id, payload.name)
        account = self._require_chart_account(payload.organization_id, payload.account_id, payload.transaction_type)
        parent = self._require_parent(payload.organization_id, payload.parent_id, payload.transaction_type)
        sort_order = payload.sort_order or self._repo.next_sort_order(payload.organization_id, payload.parent_id)
        category = Category(
            organization_id=payload.organization_id,
            parent_id=parent.id if parent is not None else None,
            account_id=account.id,
            name=payload.name,
            transaction_type=payload.transaction_type,
            default_scope=payload.default_scope,
            icon=payload.icon,
            is_system=False,
            is_active=True,
            sort_order=sort_order,
        )
        self._session.add(category)
        self._session.flush()
        loaded = self._repo.get(category.id)
        if loaded is None:
            raise AccountingError("분류를 저장하지 못했습니다.")
        return self._to_read(loaded)

    def update_category(self, category_id: int, payload: CategoryUpdate) -> CategoryRead:
        category = self._require_category(category_id)
        if payload.name is not None and payload.name != category.name:
            self._assert_unique_name(category.organization_id, payload.name, exclude_id=category.id)
            category.name = payload.name
        if payload.account_id is not None:
            account = self._require_chart_account(category.organization_id, payload.account_id, category.transaction_type)
            category.account_id = account.id
        if payload.default_scope is not None:
            category.default_scope = payload.default_scope
        fields = payload.model_fields_set
        if "icon" in fields:
            category.icon = payload.icon or None
        if payload.sort_order is not None:
            category.sort_order = payload.sort_order
        if payload.clear_parent or ("parent_id" in fields and payload.parent_id is None):
            category.parent_id = None
        elif payload.parent_id is not None:
            parent = self._require_parent(
                category.organization_id,
                payload.parent_id,
                category.transaction_type,
                moving_id=category.id,
            )
            if parent is not None and parent.id == category.id:
                raise AccountingError("분류를 자기 아래에 둘 수 없습니다.")
            category.parent_id = parent.id if parent is not None else None
        if payload.is_active is not None:
            self._set_active(category, payload.is_active)
        self._session.flush()
        loaded = self._repo.get(category.id)
        if loaded is None:
            raise LookupError("분류를 찾을 수 없습니다.")
        return self._to_read(loaded)

    def deactivate_category(self, category_id: int) -> CategoryRead:
        return self.update_category(category_id, CategoryUpdate(is_active=False))

    def delete_category(self, category_id: int) -> None:
        category = self._require_category(category_id)
        if category.is_system:
            raise AccountingError("기본 분류는 삭제할 수 없어요. 숨기기를 사용해 주세요.")
        if self._repo.has_children(category.id):
            raise AccountingError("하위 분류가 있으면 삭제할 수 없어요.")
        if self._repo.used_in_transactions(category.id):
            raise AccountingError("이미 거래에 쓰인 분류는 삭제할 수 없어요. 숨기기를 사용해 주세요.")
        self._session.delete(category)
        self._session.flush()

    def reorder(self, organization_id: int, items: list[CategoryReorderItem]) -> list[CategoryRead]:
        self._require_organization(organization_id)
        by_id = {category.id: category for category in self._repo.list_categories(organization_id, include_hidden=True)}
        for item in items:
            category = by_id.get(item.id)
            if category is None:
                raise LookupError("분류를 찾을 수 없습니다.")
            parent = self._require_parent(
                organization_id,
                item.parent_id,
                category.transaction_type,
                moving_id=category.id,
            )
            category.parent_id = parent.id if parent is not None else None
            category.sort_order = item.sort_order
        self._session.flush()
        return self.list_categories(organization_id, include_hidden=True)

    def _set_active(self, category: Category, is_active: bool) -> None:
        if not is_active:
            for child in self._repo.list_children(category.id, include_hidden=False):
                child.is_active = False
        elif category.parent_id is not None:
            parent = self._require_category(category.parent_id)
            if not parent.is_active:
                raise AccountingError("상위 분류를 먼저 다시 보여 주세요.")
        category.is_active = is_active

    def _require_parent(
        self,
        organization_id: int,
        parent_id: int | None,
        transaction_type: TransactionType,
        *,
        moving_id: int | None = None,
    ) -> Category | None:
        if parent_id is None:
            return None
        parent = self._require_category(parent_id)
        if parent.organization_id != organization_id:
            raise LookupError("분류를 찾을 수 없습니다.")
        if parent.transaction_type != transaction_type:
            raise AccountingError("상위 분류는 같은 수입/지출 유형이어야 해요.")
        if parent.parent_id is not None:
            raise AccountingError("분류는 대분류-소분류 두 단계까지만 만들 수 있어요.")
        if moving_id is not None and self._repo.has_children(moving_id):
            raise AccountingError("하위 분류가 있는 항목은 다른 분류 아래로 옮길 수 없어요.")
        return parent

    def _require_chart_account(
        self,
        organization_id: int,
        account_id: int,
        transaction_type: TransactionType,
    ) -> Account:
        account = self._session.get(Account, account_id)
        if account is None or account.organization_id != organization_id:
            raise LookupError("연결할 항목을 찾을 수 없습니다.")
        expected = AccountType.REVENUE if transaction_type == TransactionType.INCOME else AccountType.EXPENSE
        if account.account_type != expected or not account.is_postable:
            raise AccountingError("수입은 수익 항목, 지출은 비용 항목에만 연결할 수 있어요.")
        return account

    def _assert_unique_name(self, organization_id: int, name: str, *, exclude_id: int | None = None) -> None:
        existing = self._repo.get_by_name(organization_id, name)
        if existing is not None and existing.id != exclude_id:
            raise AccountingError("같은 이름의 분류가 이미 있어요.")

    def _require_category(self, category_id: int) -> Category:
        category = self._repo.get(category_id)
        if category is None:
            raise LookupError("분류를 찾을 수 없습니다.")
        return category

    def _require_organization(self, organization_id: int) -> None:
        organization = self._session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("조직을 찾을 수 없습니다.")

    def _to_read(self, category: Category) -> CategoryRead:
        return CategoryRead.model_validate(category)
