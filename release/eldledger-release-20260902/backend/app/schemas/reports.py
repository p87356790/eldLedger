from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import AccountType, NormalBalance, Scope, TransactionType
from app.schemas.accounting import ORMModel


class ReportQuery(BaseModel):
    organization_id: int
    date_from: date | None = None
    date_to: date | None = None
    business_only: bool = False
    account_id: int | None = None


class TransactionLedgerRow(BaseModel):
    occurred_on: date
    account_code: str
    account_name: str
    description: str | None
    debit_amount: int
    credit_amount: int
    journal_entry_id: int
    transaction_id: int | None


class JournalBookLine(BaseModel):
    account_code: str
    account_name: str
    debit_amount: int
    credit_amount: int
    memo: str | None = None


class JournalBookEntry(BaseModel):
    journal_entry_id: int
    occurred_on: date
    description: str | None
    transaction_id: int | None
    debit_total: int
    credit_total: int
    lines: list[JournalBookLine]


class AccountLedgerLine(BaseModel):
    occurred_on: date
    description: str | None
    debit_amount: int
    credit_amount: int
    balance: int
    journal_entry_id: int


class AccountLedger(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    normal_balance: NormalBalance
    debit_total: int
    credit_total: int
    closing_balance: int
    lines: list[AccountLedgerLine]


class TrialBalanceRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    debit_total: int
    credit_total: int


class TrialBalanceResponse(BaseModel):
    debit_total: int
    credit_total: int
    is_balanced: bool
    rows: list[TrialBalanceRow]


class BusinessReportSummary(BaseModel):
    date_from: date | None
    date_to: date | None
    scope: Scope = Scope.BUSINESS
    transaction_count: int
    income_total: int = Field(description="사업 수입 합계 (원)")
    expense_total: int = Field(description="사업 지출 합계 (원)")
    net_income: int = Field(description="사업 손익 (원)")
    trial_balance_debit_total: int
    trial_balance_credit_total: int
    is_balanced: bool


class BusinessTransactionRow(ORMModel):
    id: int
    occurred_on: date
    transaction_type: TransactionType
    scope: Scope
    amount: int
    memo: str | None
    payment_account_id: int
