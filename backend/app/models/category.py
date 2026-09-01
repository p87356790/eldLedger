from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IntPKMixin, TimestampMixin, TransactionType


class Category(IntPKMixin, TimestampMixin, Base):
    """User-facing 분류. Maps to a postable income/expense account for auto-journal."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False, length=32),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="categories")
    account: Mapped["Account"] = relationship("Account", back_populates="categories")
    items: Mapped[list["TransactionItem"]] = relationship("TransactionItem", back_populates="category")
