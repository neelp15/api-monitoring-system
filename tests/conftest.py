
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.main import app as fastapi_app
from app.routers import incidents, monitors
import app.models  # Register all SQLAlchemy models


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    # Make the isolated session factory available to tests.
    fastapi_app.state.TestingSessionLocal = TestingSessionLocal

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[monitors.get_db] = override_get_db
    fastapi_app.dependency_overrides[incidents.get_db] = override_get_db

    try:
        with TestClient(fastapi_app) as test_client:
            yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()

        if hasattr(fastapi_app.state, "TestingSessionLocal"):
            del fastapi_app.state.TestingSessionLocal

        Base.metadata.drop_all(bind=engine)
        engine.dispose()
