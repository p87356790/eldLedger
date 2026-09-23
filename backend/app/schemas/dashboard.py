from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.models.enums import Scope, TransactionType


class DashboardScopeFilter(str, Enum):
    ALL = "ALL"
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"


class DashboardPeriodSummary(BaseModel):
    start_date: date
    end_date: date
    total_income: int
    total_expense: int
    net_change: int
    business_income: int
    business_expense: int
    business_profit: int


class DashboardDailyAggregate(BaseModel):
    date: date
    total_income: int
    total_expense: int
    transaction_count: int


class DashboardTransactionRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_on: date
    amount: int
    signed_amount: int
    transaction_type: TransactionType
    scope: Scope
    category_name: str | None
    payment_method: str
    merchant: str | None
    memo: str | None
    has_attachment: bool


class DashboardCategoryTotal(BaseModel):
    category_id: int | None
    name: str
    transaction_type: TransactionType
    current_amount: int
    previous_amount: int
    sort_order: int


class DashboardSummaryResponse(BaseModel):
    summary: DashboardPeriodSummary
    daily: list[DashboardDailyAggregate]
    transactions: list[DashboardTransactionRow]
    previous_start_date: date
    previous_end_date: date
    category_totals: list[DashboardCategoryTotal]
