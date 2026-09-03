from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class PaymentInstrumentKind(str, Enum):
    """User-facing wallet type. Maps onto a chart-of-accounts parent code."""

    CASH = "CASH"
    BANK = "BANK"
    CREDIT_CARD = "CREDIT_CARD"
    LOAN = "LOAN"
    OTHER_ASSET = "OTHER_ASSET"


class NormalBalance(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Scope(str, Enum):
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"
    MIXED = "MIXED"


class CategoryDefaultScope(str, Enum):
    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"
    COMMON = "COMMON"


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


class RecordStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    REVERSED = "REVERSED"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class CsvAmountMode(str, Enum):
    SIGNED = "SIGNED"
    UNSIGNED_EXPENSE = "UNSIGNED_EXPENSE"
    SPLIT = "SPLIT"


NORMAL_BALANCE_BY_TYPE: dict[AccountType, NormalBalance] = {
    AccountType.ASSET: NormalBalance.DEBIT,
    AccountType.EXPENSE: NormalBalance.DEBIT,
    AccountType.LIABILITY: NormalBalance.CREDIT,
    AccountType.EQUITY: NormalBalance.CREDIT,
    AccountType.REVENUE: NormalBalance.CREDIT,
}


class IntPKMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
