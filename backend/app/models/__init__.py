"""ORM models. Importing this package registers every table with Base.metadata."""

from app.models.account import Account
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.category import Category
from app.models.auto_category_rule import AutoCategoryRule, AutoCategoryRuleTag
from app.models.enums import (
    AccountType,
    CategoryDefaultScope,
    CsvAmountMode,
    NormalBalance,
    PaymentInstrumentKind,
    RecordStatus,
    Scope,
    TransactionType,
    TransactionItemKind,
    UserRole,
)
from app.models.import_profile import ImportProfile
from app.models.journal import JournalEntry, JournalLine
from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.setting import Setting
from app.models.tag import Tag, TransactionTag
from app.models.transaction import Transaction, TransactionItem
from app.models.user import User

__all__ = [
    "Account",
    "AccountType",
    "Attachment",
    "AuditLog",
    "AutoCategoryRule",
    "AutoCategoryRuleTag",
    "Base",
    "Category",
    "CategoryDefaultScope",
    "CsvAmountMode",
    "ImportProfile",
    "JournalEntry",
    "JournalLine",
    "NormalBalance",
    "Organization",
    "PaymentInstrumentKind",
    "RecordStatus",
    "RefreshToken",
    "Scope",
    "Setting",
    "Tag",
    "Transaction",
    "TransactionItem",
    "TransactionTag",
    "TransactionType",
    "TransactionItemKind",
    "User",
    "UserRole",
]
