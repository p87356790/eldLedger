import os
import tempfile
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-minimum!!")
os.environ.setdefault("DATA_DIR", str(Path(tempfile.gettempdir()) / "eldledger-test-data"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, get_db
from app.db.init_db import seed_standard_data
from app.main import app
from app.models import Base, User
from app.models.enums import UserRole
from app.security.deps import get_current_user
from app.security.passwords import hash_password


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


def create_test_admin(session: Session) -> User:
    organization = seed_standard_data(session)
    session.flush()
    existing = session.scalar(select(User).where(User.username == "admin"))
    if existing is not None:
        return existing
    user = User(
        organization_id=organization.id,
        username="admin",
        email="admin@eldledger.local",
        hashed_password=hash_password("test-pass-1"),
        display_name="관리자",
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    admin = create_test_admin(db_session)
    db_session.commit()
    db_session.refresh(admin)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_user() -> User:
        loaded = db_session.get(User, admin.id)
        assert loaded is not None
        return loaded

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
