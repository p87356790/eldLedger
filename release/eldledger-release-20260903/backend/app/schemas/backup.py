from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import CategoryDefaultScope, PaymentInstrumentKind, Scope, TransactionType

LEDGER_FORMAT = "eldledger-ledger"
LEDGER_VERSION = 1


class LedgerWallet(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    instrument_kind: PaymentInstrumentKind
    currency: str = "KRW"
    opening_balance: int = 0
    institution: str | None = None
    card_payment_day: int | None = None
    settlement_account_id: int | None = None
    sort_order: int = 0
    is_active: bool = True


class LedgerCategory(BaseModel):
    id: int
    parent_id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    transaction_type: TransactionType
    default_scope: CategoryDefaultScope = CategoryDefaultScope.COMMON
    icon: str | None = None
    chart_code: str = Field(..., min_length=1, max_length=32)
    sort_order: int = 0
    is_active: bool = True


class LedgerTag(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=50)


class LedgerRule(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    merchant_keyword: str = Field(..., min_length=1, max_length=100)
    payment_account_id: int | None = None
    category_id: int
    scope: Scope
    tag_ids: list[int] = Field(default_factory=list)
    sort_order: int = 0
    is_active: bool = True


class LedgerItem(BaseModel):
    category_id: int | None = None
    amount: int = Field(..., gt=0)
    scope: Scope
    memo: str | None = None
    line_no: int = 0


class LedgerAttachment(BaseModel):
    original_filename: str
    content_type: str
    file_size: int
    path: str


class LedgerTransaction(BaseModel):
    id: int
    occurred_on: date
    transaction_type: TransactionType
    scope: Scope
    amount: int = Field(..., gt=0)
    memo: str | None = None
    payment_account_id: int
    transfer_account_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)
    items: list[LedgerItem] = Field(default_factory=list)
    attachments: list[LedgerAttachment] = Field(default_factory=list)


class LedgerBundle(BaseModel):
    format: str = LEDGER_FORMAT
    version: int = LEDGER_VERSION
    exported_at: datetime
    organization_name: str | None = None
    wallets: list[LedgerWallet] = Field(default_factory=list)
    categories: list[LedgerCategory] = Field(default_factory=list)
    tags: list[LedgerTag] = Field(default_factory=list)
    rules: list[LedgerRule] = Field(default_factory=list)
    transactions: list[LedgerTransaction] = Field(default_factory=list)


class LedgerImportResult(BaseModel):
    wallets_created: int
    wallets_matched: int
    categories_created: int
    categories_matched: int
    tags_created: int
    rules_created: int
    transactions_created: int
    attachments_created: int
    replaced_transactions: int
