from calendar import monthrange
from collections import defaultdict
from datetime import date
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.models import Category, Transaction, TransactionItem
from app.models.enums import Scope, TransactionType
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.dashboard import (
    DashboardCategoryTotal,
    DashboardDailyAggregate,
    DashboardPeriodSummary,
    DashboardScopeFilter,
    DashboardSummaryResponse,
    DashboardTransactionRow,
)
from app.services.account_service import AccountService


class DashboardService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = TransactionRepository(session)
        self._accounts = AccountService(session)

    def summary(
        self,
        *,
        organization_id: int,
        owner_user_id: int,
        start_date: date | None,
        end_date: date | None,
        account_id: int | None,
        scope: DashboardScopeFilter,
    ) -> DashboardSummaryResponse:
        resolved_start, resolved_end = resolve_dashboard_range(start_date, end_date)
        if resolved_start > resolved_end:
            raise ValueError("시작일이 종료일보다 늦을 수 없어요.")
        if account_id is not None:
            self._accounts.get_wallet(account_id, owner_user_id=owner_user_id)

        previous_start, previous_end = previous_month_bounds(resolved_start)
        query_start = min(resolved_start, previous_start)
        query_end = max(resolved_end, previous_end)
        rows = self._repo.list_for_dashboard(
            organization_id=organization_id,
            created_by_user_id=owner_user_id,
            date_from=query_start,
            date_to=query_end,
            account_id=account_id,
        )
        current_rows = [row for row in rows if resolved_start <= row.occurred_on <= resolved_end]
        previous_rows = [row for row in rows if previous_start <= row.occurred_on <= previous_end]
        matching = [row for row in current_rows if _matches_scope(row, scope)]

        total_income = 0
        total_expense = 0
        business_income = 0
        business_expense = 0
        daily_map: dict[date, list[int]] = defaultdict(lambda: [0, 0, 0])

        for transaction in matching:
            income, expense = _income_expense_amounts(transaction, scope, account_id)
            total_income += income
            total_expense += expense
            bucket = daily_map[transaction.occurred_on]
            bucket[0] += income
            bucket[1] += expense
            bucket[2] += 1

        for transaction in current_rows:
            business_amount = _business_amount(transaction)
            if business_amount <= 0:
                continue
            if transaction.transaction_type == TransactionType.INCOME:
                business_income += business_amount
            elif transaction.transaction_type == TransactionType.EXPENSE:
                business_expense += business_amount

        daily = [
            DashboardDailyAggregate(
                date=day,
                total_income=values[0],
                total_expense=values[1],
                transaction_count=values[2],
            )
            for day, values in sorted(daily_map.items())
        ]
        return DashboardSummaryResponse(
            summary=DashboardPeriodSummary(
                start_date=resolved_start,
                end_date=resolved_end,
                total_income=total_income,
                total_expense=total_expense,
                net_change=total_income - total_expense,
                business_income=business_income,
                business_expense=business_expense,
                business_profit=business_income - business_expense,
            ),
            daily=daily,
            transactions=[_to_row(transaction, account_id, scope) for transaction in matching],
            previous_start_date=previous_start,
            previous_end_date=previous_end,
            category_totals=_category_totals(matching, previous_rows, scope),
        )


def resolve_dashboard_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    today = date.today()
    if start_date is None and end_date is None:
        last_day = monthrange(today.year, today.month)[1]
        return date(today.year, today.month, 1), date(today.year, today.month, last_day)
    if start_date is None:
        assert end_date is not None
        return date(end_date.year, end_date.month, 1), end_date
    if end_date is None:
        last_day = monthrange(start_date.year, start_date.month)[1]
        return start_date, date(start_date.year, start_date.month, last_day)
    return start_date, end_date


def previous_month_bounds(start_date: date) -> tuple[date, date]:
    if start_date.month == 1:
        year = start_date.year - 1
        month = 12
    else:
        year = start_date.year
        month = start_date.month - 1
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


class _CategoryBucket(NamedTuple):
    category_id: int | None
    name: str
    transaction_type: TransactionType
    sort_order: int


def _category_totals(
    current_rows: list[Transaction],
    previous_rows: list[Transaction],
    scope: DashboardScopeFilter,
) -> list[DashboardCategoryTotal]:
    current_amounts: dict[_CategoryBucket, int] = defaultdict(int)
    previous_amounts: dict[_CategoryBucket, int] = defaultdict(int)
    for transaction in current_rows:
        for bucket, amount in _category_amounts(transaction, scope):
            current_amounts[bucket] += amount
    for transaction in previous_rows:
        if not _matches_scope(transaction, scope):
            continue
        for bucket, amount in _category_amounts(transaction, scope):
            previous_amounts[bucket] += amount
    keys = set(current_amounts) | set(previous_amounts)
    rows = [
        DashboardCategoryTotal(
            category_id=bucket.category_id,
            name=bucket.name,
            transaction_type=bucket.transaction_type,
            current_amount=current_amounts.get(bucket, 0),
            previous_amount=previous_amounts.get(bucket, 0),
            sort_order=bucket.sort_order,
        )
        for bucket in keys
        if current_amounts.get(bucket, 0) > 0 or previous_amounts.get(bucket, 0) > 0
    ]
    rows.sort(key=lambda item: (-item.current_amount, -item.previous_amount, item.sort_order, item.name))
    return rows


def _category_amounts(transaction: Transaction, scope: DashboardScopeFilter) -> list[tuple[_CategoryBucket, int]]:
    if transaction.transaction_type not in {TransactionType.INCOME, TransactionType.EXPENSE}:
        return []
    rows: list[tuple[_CategoryBucket, int]] = []
    for item in transaction.items:
        amount = _item_amount_for_scope(transaction, item, scope)
        if amount <= 0:
            continue
        rows.append((_category_bucket(item.category, transaction.transaction_type), amount))
    return rows


def _item_amount_for_scope(
    transaction: Transaction,
    item: TransactionItem,
    scope: DashboardScopeFilter,
) -> int:
    if scope == DashboardScopeFilter.ALL:
        return int(item.amount)
    target = Scope.PERSONAL if scope == DashboardScopeFilter.PERSONAL else Scope.BUSINESS
    if transaction.scope == target:
        return int(item.amount)
    if transaction.scope == Scope.MIXED and item.scope == target:
        return int(item.amount)
    return 0


def _category_bucket(category: Category | None, transaction_type: TransactionType) -> _CategoryBucket:
    root = _root_category(category)
    if root is None:
        return _CategoryBucket(None, "미분류", transaction_type, 10_000)
    return _CategoryBucket(root.id, root.name, transaction_type, root.sort_order)


def _root_category(category: Category | None) -> Category | None:
    if category is None:
        return None
    if category.parent is not None:
        return category.parent
    return category


def _matches_scope(transaction: Transaction, scope: DashboardScopeFilter) -> bool:
    if scope == DashboardScopeFilter.ALL:
        return True
    target = Scope.PERSONAL if scope == DashboardScopeFilter.PERSONAL else Scope.BUSINESS
    if transaction.scope == target:
        return True
    if transaction.scope == Scope.MIXED:
        return any(item.scope == target for item in transaction.items)
    return False


def _amount_for_scope(transaction: Transaction, scope: DashboardScopeFilter) -> int:
    if scope == DashboardScopeFilter.ALL:
        return int(transaction.amount)
    target = Scope.PERSONAL if scope == DashboardScopeFilter.PERSONAL else Scope.BUSINESS
    if transaction.scope == target:
        return int(transaction.amount)
    if transaction.scope == Scope.MIXED:
        return sum(int(item.amount) for item in transaction.items if item.scope == target)
    return 0


def _income_expense_amounts(
    transaction: Transaction,
    scope: DashboardScopeFilter,
    account_id: int | None = None,
) -> tuple[int, int]:
    amount = _amount_for_scope(transaction, scope)
    if transaction.transaction_type == TransactionType.TRANSFER:
        if account_id is None:
            return 0, 0
        if transaction.transfer_account_id == account_id:
            return amount, 0
        if transaction.payment_account_id == account_id:
            return 0, amount
        return 0, 0
    if transaction.transaction_type == TransactionType.INCOME:
        return amount, 0
    if transaction.transaction_type == TransactionType.EXPENSE:
        return 0, amount
    return 0, 0


def _business_amount(transaction: Transaction) -> int:
    if transaction.transaction_type == TransactionType.TRANSFER:
        return 0
    if transaction.scope == Scope.BUSINESS:
        return int(transaction.amount)
    if transaction.scope == Scope.MIXED:
        return sum(int(item.amount) for item in transaction.items if item.scope == Scope.BUSINESS)
    return 0


def _to_row(
    transaction: Transaction,
    account_id: int | None = None,
    scope: DashboardScopeFilter = DashboardScopeFilter.ALL,
) -> DashboardTransactionRow:
    category_names = [
        item.category.name
        for item in transaction.items
        if item.category is not None and item.category.name
    ]
    payment = transaction.payment_account.name if transaction.payment_account is not None else ""
    if transaction.transaction_type == TransactionType.TRANSFER and transaction.transfer_account is not None:
        payment = f"{payment} → {transaction.transfer_account.name}"
    income, expense = _income_expense_amounts(transaction, scope, account_id)
    signed_amount = income - expense
    return DashboardTransactionRow(
        id=transaction.id,
        occurred_on=transaction.occurred_on,
        amount=int(transaction.amount),
        signed_amount=signed_amount,
        transaction_type=transaction.transaction_type,
        scope=transaction.scope,
        category_name=" · ".join(category_names) if category_names else None,
        payment_method=payment,
        merchant=transaction.merchant,
        memo=transaction.memo,
        has_attachment=len(transaction.attachments) > 0,
    )
