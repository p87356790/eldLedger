"""Wipe ledger data and restore first-run seed. Schema (Alembic) is kept."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db.init_db import STANDARD_ACCOUNTS, seed_standard_data
from app.models import (
    Account,
    AutoCategoryRule,
    Category,
    Organization,
    Tag,
    Transaction,
    User,
)
from app.models.base import Base
from app.models.journal import JournalEntry, JournalLine
from app.services.chart_template_service import ChartTemplateService

CONFIRM_PHRASE = "초기화"
PROTECTED_TABLES = frozenset({"alembic_version"})
STANDARD_WALLET_CODES = frozenset(seed.code for seed in STANDARD_ACCOUNTS if seed.instrument_kind is not None)


def _empty_directory(path: Path) -> None:
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            shutil.rmtree(child)


def clear_generated_files() -> None:
    data_root = Path(settings.data_dir)
    _empty_directory(data_root / "uploads")
    _empty_directory(data_root / "reports")


def reset_user_ledger(session: Session, user: User) -> int:
    """Wipe one user's cashbook and restore that user's standard wallets/categories.

    Login accounts and other users' ledgers are left alone.
    """
    transactions = list(
        session.scalars(
            select(Transaction)
            .options(
                selectinload(Transaction.attachments),
                selectinload(Transaction.journal_entries),
            )
            .where(Transaction.created_by_user_id == user.id)
        )
    )
    tx_count = len(transactions)
    data_root = Path(settings.data_dir)
    for transaction in transactions:
        for attachment in transaction.attachments:
            stored = data_root / attachment.stored_path
            if stored.is_file():
                stored.unlink(missing_ok=True)

    entry_ids = [entry.id for transaction in transactions for entry in transaction.journal_entries]
    wallets = list(
        session.scalars(
            select(Account).where(
                Account.organization_id == user.organization_id,
                Account.owner_user_id == user.id,
                Account.instrument_kind.is_not(None),
            )
        )
    )
    wallet_ids = [wallet.id for wallet in wallets]
    if wallet_ids:
        opening_ids = list(
            session.scalars(
                select(JournalEntry.id)
                .join(JournalLine)
                .where(JournalEntry.transaction_id.is_(None))
                .where(JournalLine.account_id.in_(wallet_ids))
            ).unique()
        )
        entry_ids.extend(opening_ids)
    entry_ids = list(dict.fromkeys(entry_ids))
    if entry_ids:
        session.execute(update(JournalEntry).where(JournalEntry.id.in_(entry_ids)).values(reverses_entry_id=None))
        session.execute(
            update(JournalLine).where(JournalLine.journal_entry_id.in_(entry_ids)).values(transaction_item_id=None)
        )
        session.flush()
        session.execute(delete(JournalLine).where(JournalLine.journal_entry_id.in_(entry_ids)))
        session.flush()
        session.execute(delete(JournalEntry).where(JournalEntry.id.in_(entry_ids)))
        session.flush()

    for transaction in transactions:
        session.delete(transaction)
    session.flush()

    rules = list(
        session.scalars(
            select(AutoCategoryRule).where(
                AutoCategoryRule.organization_id == user.organization_id,
                AutoCategoryRule.owner_user_id == user.id,
            )
        )
    )
    for rule in rules:
        session.delete(rule)
    session.flush()

    categories = list(
        session.scalars(
            select(Category).where(
                Category.organization_id == user.organization_id,
                Category.owner_user_id == user.id,
            )
        )
    )
    for category in categories:
        category.parent_id = None
    session.flush()
    for category in categories:
        session.delete(category)
    session.flush()

    tags = list(
        session.scalars(
            select(Tag).where(
                Tag.organization_id == user.organization_id,
                Tag.owner_user_id == user.id,
            )
        )
    )
    for tag in tags:
        session.delete(tag)
    session.flush()

    for wallet in wallets:
        wallet.settlement_account_id = None
        wallet.opening_balance = 0
        wallet.is_active = True
    session.flush()
    for wallet in wallets:
        if wallet.code in STANDARD_WALLET_CODES:
            continue
        session.delete(wallet)
    session.flush()

    ChartTemplateService(session).provision_user_ledger(user)
    session.flush()
    return tx_count


def reset_all_data(session: Session) -> Organization:
    """Delete every application row, reset SQLite ids, re-seed the chart, keep backups."""
    session.execute(update(Category).values(parent_id=None))
    session.execute(update(Account).values(parent_id=None, settlement_account_id=None))
    session.flush()
    bind = session.get_bind()
    if bind.dialect.name == "sqlite":
        session.execute(text("PRAGMA foreign_keys=OFF"))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in PROTECTED_TABLES:
            continue
        session.execute(table.delete())
    if session.get_bind().dialect.name == "sqlite":
        try:
            session.execute(text("DELETE FROM sqlite_sequence"))
        except OperationalError:
            pass
        session.execute(text("PRAGMA foreign_keys=ON"))
    session.flush()
    session.expunge_all()
    clear_generated_files()
    return seed_standard_data(session)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="eldLedger 장부 데이터를 모두 지우고 처음 설치 상태로 돌립니다.")
    parser.add_argument("--yes", action="store_true", help="확인 없이 바로 초기화합니다.")
    args = parser.parse_args(argv)
    if not args.yes:
        print('장부의 모든 기록·사용자·첨부파일을 지웁니다. 계속하려면 --yes 를 붙여 주세요.')
        return 1

    from app.database import SessionLocal

    with SessionLocal() as session:
        reset_all_data(session)
        session.commit()
    print("초기화했어요. 앱에서 관리자 계정을 다시 만들어 주세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
