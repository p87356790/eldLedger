from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CsvAmountMode, Scope, TransactionType
from app.schemas.categories import TagRead


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ImportProfileRead(ORMModel):
    id: int
    organization_id: int
    name: str
    preset_key: str | None
    date_column: str
    merchant_column: str
    memo_column: str | None
    amount_column: str | None
    outflow_column: str | None
    inflow_column: str | None
    type_column: str | None
    amount_mode: CsvAmountMode
    is_preset: bool
    is_active: bool


class ImportPreviewRow(BaseModel):
    row_no: int
    occurred_on: date | None
    amount: int | None
    merchant: str
    memo: str | None
    transaction_type: TransactionType | None
    scope: Scope
    category_id: int | None
    category_name: str | None
    tag_ids: list[int] = Field(default_factory=list)
    suggested: bool = False
    duplicate: bool = False
    skip: bool = False
    fingerprint: str | None = None
    error: str | None = None


class ImportPreviewResponse(BaseModel):
    encoding: str
    delimiter: str
    headers: list[str]
    profile: ImportProfileRead
    rows: list[ImportPreviewRow]
    total_rows: int
    duplicate_count: int
    uncategorized_count: int
    error_count: int


class ImportCommitRow(BaseModel):
    occurred_on: date
    amount: int = Field(..., gt=0)
    merchant: str = Field(..., min_length=1, max_length=255)
    memo: str | None = None
    transaction_type: TransactionType
    scope: Scope
    category_id: int
    tag_ids: list[int] = Field(default_factory=list)
    skip: bool = False


class ImportCommitRequest(BaseModel):
    organization_id: int
    payment_account_id: int
    rows: list[ImportCommitRow] = Field(..., min_length=1)


class ImportCommitFailure(BaseModel):
    merchant: str
    error: str


class ImportCommitResponse(BaseModel):
    created: int
    skipped: int
    failed: list[ImportCommitFailure] = Field(default_factory=list)


class AutoCategoryRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    merchant_keyword: str = Field(..., min_length=1, max_length=100)
    payment_account_id: int | None = None
    category_id: int
    scope: Scope
    tag_ids: list[int] = Field(default_factory=list)
    sort_order: int = 0
    is_active: bool = True


class AutoCategoryRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    merchant_keyword: str | None = Field(default=None, min_length=1, max_length=100)
    payment_account_id: int | None = None
    clear_payment_account: bool = False
    category_id: int | None = None
    scope: Scope | None = None
    tag_ids: list[int] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class AutoCategoryRuleRead(ORMModel):
    id: int
    organization_id: int
    name: str
    merchant_keyword: str
    payment_account_id: int | None
    category_id: int
    category_name: str | None = None
    scope: Scope
    sort_order: int
    is_active: bool
    tags: list[TagRead] = Field(default_factory=list)
