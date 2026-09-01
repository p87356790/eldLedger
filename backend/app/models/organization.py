from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IntPKMixin, TimestampMixin


class Organization(IntPKMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="organization")
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="organization")
    tags: Mapped[list["Tag"]] = relationship("Tag", back_populates="organization")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="organization")
    journal_entries: Mapped[list["JournalEntry"]] = relationship("JournalEntry", back_populates="organization")
    settings: Mapped[list["Setting"]] = relationship("Setting", back_populates="organization")
