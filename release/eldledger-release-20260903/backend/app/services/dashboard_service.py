from calendar import monthrange
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.models import Transaction
from app.models.enums import Scope, TransactionType
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.dashboard import (
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

        rows = self._repo.list_for_dashboard(
            organization_id=organization_id,
            created_by_user_id=owner_user_id,
            date_from=resolved_start,
            date_to=resolved_end,
            account_id=account_id,
        )
        matching = [row for row in rows if _matches_scope(row, scope)]

        total_income = 0
        total_expense = 0
        business_income = 0
        business_expense = 0
        daily_map: dict[date, list[int]] = defaultdict(lambda: [0, 0, 0])

        for transaction in matching:
            income, expense = _income_expense_amounts(transaction, scope)
            total_income += income
            total_expense += expense
            bucket = daily_map[transaction.occurred_on]
            bucket[0] += income
            bucket[1] += expense
            bucket[2] += 1

        for transaction in rows:
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
            transactions=[_to_row(transaction) for transaction in matching],
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


def _income_expense_amounts(transaction: Transaction, scope: DashboardScopeFilter) -> tuple[int, int]:
    if transaction.transaction_type == TransactionType.TRANSFER:
        return 0, 0
    amount = _amount_for_scope(transaction, scope)
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


def _to_row(transaction: Transaction) -> DashboardTransactionRow:
    category_names = [
        item.category.name
        for item in transaction.items
        if item.category is not None and item.category.name
    ]
    payment = transaction.payment_account.name if transaction.payment_account is not None else ""
    if transaction.transaction_type == TransactionType.TRANSFER and transaction.transfer_account is not None:
        payment = f"{payment} → {transaction.transfer_account.name}"
    return DashboardTransactionRow(
        id=transaction.id,
        occurred_on=transaction.occurred_on,
        amount=int(transaction.amount),
        transaction_type=transaction.transaction_type,
        scope=transaction.scope,
        category_name=" · ".join(category_names) if category_names else None,
        payment_method=payment,
        memo=transaction.memo,
        has_attachment=len(transaction.attachments) > 0,
    )
