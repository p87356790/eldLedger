from datetime import date

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    AccountType,
    CategoryDefaultScope,
    NormalBalance,
    RecordStatus,
    Scope,
    TransactionType,
    UserRole,
)
from app.services.journal_balance import assert_journal_balanced


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrganizationRead(ORMModel):
    id: int
    name: str
    is_active: bool


class UserCreate(BaseModel):
    organization_id: int
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.USER


class UserRead(ORMModel):
    id: int
    organization_id: int
    email: str
    display_name: str
    role: UserRole
    is_active: bool


class AccountCreate(BaseModel):
    organization_id: int
    parent_id: int | None = None
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=100)
    account_type: AccountType
    normal_balance: NormalBalance
    is_postable: bool = True
    is_payment_method: bool = False
    sort_order: int = 0


class AccountRead(ORMModel):
    id: int
    organization_id: int
    parent_id: int | None
    code: str
    name: str
    account_type: AccountType
    normal_balance: NormalBalance
    is_postable: bool
    is_payment_method: bool
    is_system: bool
    is_active: bool
    sort_order: int
    instrument_kind: str | None = None
    currency: str = "KRW"
    opening_balance: int = 0
    institution: str | None = None
    card_payment_day: int | None = None
    settlement_account_id: int | None = None


class CategoryCreate(BaseModel):
    organization_id: int
    parent_id: int | None = None
    account_id: int
    name: str = Field(..., min_length=1, max_length=100)
    transaction_type: TransactionType
    default_scope: CategoryDefaultScope = CategoryDefaultScope.COMMON
    icon: str | None = None
    sort_order: int = 0


class CategoryRead(ORMModel):
    id: int
    organization_id: int
    parent_id: int | None = None
    account_id: int
    name: str
    transaction_type: TransactionType
    default_scope: CategoryDefaultScope = CategoryDefaultScope.COMMON
    icon: str | None = None
    is_system: bool = False
    is_active: bool
    sort_order: int
    chart_code: str | None = None
    chart_name: str | None = None


class TagCreate(BaseModel):
    organization_id: int
    name: str = Field(..., min_length=1, max_length=50)


class TagRead(ORMModel):
    id: int
    organization_id: int
    name: str


class TransactionItemCreate(BaseModel):
    category_id: int | None = None
    account_id: int | None = None
    amount: int = Field(..., gt=0)
    scope: Scope
    memo: str | None = Field(default=None, max_length=255)
    line_no: int = 0


class TransactionItemRead(ORMModel):
    id: int
    transaction_id: int
    category_id: int | None
    account_id: int | None
    amount: int
    scope: Scope
    memo: str | None
    line_no: int


class TransactionCreate(BaseModel):
    organization_id: int
    occurred_on: date
    transaction_type: TransactionType
    scope: Scope
    amount: int = Field(..., gt=0)
    merchant: str | None = Field(default=None, max_length=255)
    memo: str | None = None
    payment_account_id: int
    transfer_account_id: int | None = None
    items: list[TransactionItemCreate] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_splits_and_transfer(self) -> Self:
        if self.items:
            item_total = sum(item.amount for item in self.items)
            if item_total != self.amount:
                raise ValueError("항목 금액 합계가 거래 금액과 일치해야 합니다.")
        if self.scope == Scope.MIXED:
            if not self.items:
                raise ValueError("혼합 거래는 개인/사업 항목 분할이 필요합니다.")
            if any(item.scope == Scope.MIXED for item in self.items):
                raise ValueError("혼합 거래의 각 항목은 개인 또는 사업으로 지정해야 합니다.")
        if self.transaction_type == TransactionType.TRANSFER and self.transfer_account_id is None:
            raise ValueError("이체는 상대 계정이 필요합니다.")
        return self


class TransactionUpdate(BaseModel):
    occurred_on: date
    transaction_type: TransactionType
    scope: Scope
    amount: int = Field(..., gt=0)
    merchant: str | None = Field(default=None, max_length=255)
    memo: str | None = None
    payment_account_id: int
    transfer_account_id: int | None = None
    items: list[TransactionItemCreate] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_splits_and_transfer(self) -> Self:
        if self.items:
            item_total = sum(item.amount for item in self.items)
            if item_total != self.amount:
                raise ValueError("항목 금액 합계가 거래 금액과 일치해야 합니다.")
        if self.scope == Scope.MIXED:
            if not self.items:
                raise ValueError("혼합 거래는 개인/사업 항목 분할이 필요합니다.")
            if any(item.scope == Scope.MIXED for item in self.items):
                raise ValueError("혼합 거래의 각 항목은 개인 또는 사업으로 지정해야 합니다.")
        if self.transaction_type == TransactionType.TRANSFER and self.transfer_account_id is None:
            raise ValueError("이체는 상대 계정이 필요합니다.")
        return self


class AttachmentCreate(BaseModel):
    transaction_id: int
    original_filename: str = Field(..., min_length=1, max_length=255)
    stored_path: str = Field(..., min_length=1, max_length=1024)
    content_type: str = Field(..., min_length=1, max_length=127)
    file_size: int = Field(..., ge=0)


class AttachmentRead(ORMModel):
    id: int
    transaction_id: int
    original_filename: str
    stored_path: str
    content_type: str
    file_size: int


class TransactionRead(ORMModel):
    id: int
    organization_id: int
    created_by_user_id: int | None
    occurred_on: date
    transaction_type: TransactionType
    scope: Scope
    amount: int
    merchant: str | None
    memo: str | None
    status: RecordStatus
    payment_account_id: int
    transfer_account_id: int | None
    items: list[TransactionItemRead] = Field(default_factory=list)
    attachments: list[AttachmentRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)


class TransactionListResponse(BaseModel):
    total: int
    items: list[TransactionRead]


class DuplicateCheckRequest(BaseModel):
    organization_id: int
    occurred_on: date
    transaction_type: TransactionType
    amount: int = Field(..., gt=0)
    merchant: str | None = Field(default=None, max_length=255)
    payment_account_id: int
    transfer_account_id: int | None = None
    items: list[TransactionItemCreate] = Field(default_factory=list)
    exclude_id: int | None = Field(default=None, ge=1)


class DuplicateCheckResponse(BaseModel):
    matches: list[TransactionRead] = Field(default_factory=list)


class JournalLineCreate(BaseModel):
    account_id: int
    debit_amount: int = Field(default=0, ge=0)
    credit_amount: int = Field(default=0, ge=0)
    memo: str | None = None
    line_no: int = 0
    transaction_item_id: int | None = None


class JournalLineRead(ORMModel):
    id: int
    journal_entry_id: int
    account_id: int
    debit_amount: int
    credit_amount: int
    memo: str | None
    line_no: int
    transaction_item_id: int | None


class JournalEntryCreate(BaseModel):
    organization_id: int
    transaction_id: int | None = None
    occurred_on: date
    description: str | None = None
    lines: list[JournalLineCreate] = Field(..., min_length=2)

    @model_validator(mode="after")
    def validate_double_entry(self) -> Self:
        assert_journal_balanced(
            [(line.debit_amount, line.credit_amount) for line in self.lines]
        )
        return self


class JournalEntryRead(ORMModel):
    id: int
    organization_id: int
    transaction_id: int | None
    occurred_on: date
    description: str | None
    status: RecordStatus
    reverses_entry_id: int | None
    lines: list[JournalLineRead] = Field(default_factory=list)


class AuditLogRead(ORMModel):
    id: int
    user_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    details: str | None


class SettingCreate(BaseModel):
    organization_id: int
    key: str = Field(..., min_length=1, max_length=100)
    value: str


class SettingRead(ORMModel):
    id: int
    organization_id: int
    key: str
    value: str
