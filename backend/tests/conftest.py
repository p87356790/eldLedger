import os
import tempfile
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATA_DIR", str(Path(tempfile.gettempdir()) / "eldledger-test-data"))

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            connection.commit()
            Base.metadata.drop_all(bind=connection)
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.commit()
