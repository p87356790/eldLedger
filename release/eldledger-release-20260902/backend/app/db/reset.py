"""Wipe ledger data and restore first-run seed. Schema (Alembic) is kept."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from sqlalchemy import text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.init_db import seed_standard_data
from app.models import Account, Category, Organization
from app.models.base import Base

CONFIRM_PHRASE = "초기화"
PROTECTED_TABLES = frozenset({"alembic_version"})


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


def reset_all_data(session: Session) -> Organization:
    """Delete every application row, reset SQLite ids, re-seed the chart, keep backups."""
    session.execute(update(Category).values(parent_id=None))
    session.execute(update(Account).values(parent_id=None))
    session.flush()
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in PROTECTED_TABLES:
            continue
        session.execute(table.delete())
    if session.get_bind().dialect.name == "sqlite":
        try:
            session.execute(text("DELETE FROM sqlite_sequence"))
        except OperationalError:
            pass
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
