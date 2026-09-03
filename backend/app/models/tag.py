from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IntPKMixin, TimestampMixin


class Tag(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("organization_id", "owner_user_id", "name"),)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="tags")
    owner: Mapped["User | None"] = relationship("User", foreign_keys=[owner_user_id])
    transaction_tags: Mapped[list["TransactionTag"]] = relationship(
        "TransactionTag",
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class TransactionTag(Base):
    __tablename__ = "transaction_tags"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="transaction_tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="transaction_tags")
