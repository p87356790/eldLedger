from datetime import date

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import BillStatus, IntPKMixin, Scope, TimestampMixin


class Bill(IntPKMixin, TimestampMixin, Base):
    """A bill received before the money actually leaves. Paying it posts a cashbook expense."""

    __tablename__ = "bills"
    __table_args__ = (CheckConstraint("amount > 0", name="bill_amount_positive"),)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    scope: Mapped[Scope] = mapped_column(
        Enum(Scope, native_enum=False, length=32),
        nullable=False,
    )
    billed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pay_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    repeats_monthly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[BillStatus] = mapped_column(
        Enum(BillStatus, native_enum=False, length=32),
        default=BillStatus.OPEN,
        nullable=False,
        index=True,
    )
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="bills")
    created_by: Mapped["User | None"] = relationship("User")
    category: Mapped["Category"] = relationship("Category")
    payment_account: Mapped["Account | None"] = relationship("Account")
    transaction: Mapped["Transaction | None"] = relationship("Transaction")
