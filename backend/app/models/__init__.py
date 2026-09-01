"""ORM models. Importing this package registers every table with Base.metadata."""

from app.models.account import Account
from app.models.attachment import Attachment
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.category import Category
from app.models.enums import (
    AccountType,
    NormalBalance,
    RecordStatus,
    Scope,
    TransactionType,
    UserRole,
)
from app.models.journal import JournalEntry, JournalLine
from app.models.organization import Organization
from app.models.setting import Setting
from app.models.tag import Tag, TransactionTag
from app.models.transaction import Transaction, TransactionItem
from app.models.user import User

__all__ = [
    "Account",
    "AccountType",
    "Attachment",
    "AuditLog",
    "Base",
    "Category",
    "JournalEntry",
    "JournalLine",
    "NormalBalance",
    "Organization",
    "RecordStatus",
    "Scope",
    "Setting",
    "Tag",
    "Transaction",
    "TransactionItem",
    "TransactionTag",
    "TransactionType",
    "User",
    "UserRole",
]
