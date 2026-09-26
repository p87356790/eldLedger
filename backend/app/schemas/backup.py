from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CategoryDefaultScope, PaymentInstrumentKind, Scope, TransactionItemKind, TransactionType

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
    line_kind: TransactionItemKind = TransactionItemKind.STANDARD


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
    merchant: str | None = Field(default=None, max_length=255)
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


CONFIG_FORMAT = "eldledger-config"
CONFIG_VERSION = 1


class ConfigBundle(BaseModel):
    format: str = CONFIG_FORMAT
    version: int = CONFIG_VERSION
    exported_at: datetime
    wallets: list[LedgerWallet] = Field(default_factory=list)
    categories: list[LedgerCategory] = Field(default_factory=list)


class ConfigImportResult(BaseModel):
    wallets_deleted: int
    wallets_created: int
    categories_deleted: int
    categories_created: int


class BackupFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BackupScheduleUpdate(BaseModel):
    enabled: bool = False
    frequency: BackupFrequency = BackupFrequency.DAILY
    weekday: int = Field(default=0, ge=0, le=6)
    monthday: int = Field(default=1, ge=1, le=31)
    hour: int = Field(default=3, ge=0, le=23)


class BackupScheduleState(BackupScheduleUpdate):
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_filename: str | None = None
    last_error: str | None = None


class BackupScheduleRead(BackupScheduleState):
    retention_days: int
    next_run_at: datetime | None = None


class ServerBackupFile(BaseModel):
    filename: str
    created_at: datetime
    size_bytes: int
    kind: str

    @field_validator("kind")
    @classmethod
    def kind_must_be_known(cls, value: str) -> str:
        if value not in {"zip", "directory"}:
            raise ValueError("kind must be zip or directory")
        return value


class ServerBackupRunResult(BaseModel):
    filename: str
    size_bytes: int
    purged_count: int


class ServerBackupDeleteRequest(BaseModel):
    filenames: list[str] = Field(..., min_length=1, max_length=200)


class ServerBackupDeleteResult(BaseModel):
    deleted: list[str]
