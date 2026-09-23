from __future__ import annotations

import asyncio
import logging

from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import SessionLocal
from app.services.server_backup_service import ServerBackupService

logger = logging.getLogger(__name__)


def run_backup_tick() -> None:
    session = SessionLocal()
    try:
        ServerBackupService(session).run_if_due()
        session.commit()
    except OperationalError:
        session.rollback()
        logger.debug("자동 백업을 건너뜁니다. 데이터베이스가 아직 준비되지 않았어요.")
    except Exception:
        session.rollback()
        logger.exception("자동 백업 실행에 실패했어요.")
    finally:
        session.close()


async def backup_scheduler_loop(stop: asyncio.Event) -> None:
    interval = max(30, settings.backup_scheduler_interval_seconds)
    while not stop.is_set():
        try:
            await asyncio.to_thread(run_backup_tick)
        except Exception:
            logger.exception("자동 백업 확인에 실패했어요.")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue
