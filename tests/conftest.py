import os

# Point to the test database before any app imports
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5435/eve_healthcare_test",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.api.deps import get_db
from app.core.security import hash_password, create_access_token
import app.main

# All models must be imported so Base.metadata knows about them
import app.models  # noqa: F401

engine = create_engine(os.environ["DATABASE_URL"])
TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Create all tables once per test session
Base.metadata.create_all(bind=engine)


def _truncate_all(db):
    """TRUNCATE all tables between tests for clean isolation."""
    table_names = ", ".join(Base.metadata.tables.keys())
    db.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    db.commit()


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate all tables before each test."""
    db = TestSession()
    _truncate_all(db)
    db.close()
    yield


@pytest.fixture()
def db():
    """Provide a test database session."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """FastAPI test client with overridden DB dependency."""
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.main.app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app.main.app) as c:
        yield c
    app.main.app.dependency_overrides.clear()


# --- Helper fixtures ---


@pytest.fixture()
def admin_user(db):
    from app.models.user import User
    user = User(
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        full_name="Test Admin",
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def regular_user(db):
    from app.models.user import User
    user = User(
        email="user@test.com",
        password_hash=hash_password("user123"),
        full_name="Test User",
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_token(admin_user):
    return create_access_token(admin_user.id)


@pytest.fixture()
def user_token(regular_user):
    return create_access_token(regular_user.id)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
