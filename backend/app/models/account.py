from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AccountType, IntPKMixin, NormalBalance, TimestampMixin


class Account(IntPKMixin, TimestampMixin, Base):
    """Formal chart-of-accounts node. Headers are not postable."""

    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    normal_balance: Mapped[NormalBalance] = mapped_column(
        Enum(NormalBalance, native_enum=False, length=16),
        nullable=False,
    )
    is_postable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_payment_method: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="accounts")
    parent: Mapped["Account | None"] = relationship(
        "Account",
        remote_side="Account.id",
        foreign_keys=[parent_id],
        back_populates="children",
    )
    children: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="parent",
        foreign_keys=[parent_id],
    )
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="account")
    journal_lines: Mapped[list["JournalLine"]] = relationship("JournalLine", back_populates="account")
