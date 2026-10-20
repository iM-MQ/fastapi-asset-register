"""Test set-up: point the API at a separate test database, and empty it before every test."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base, get_session, settings
from main import app

if not settings.test_database_url:
    raise RuntimeError("TEST_DATABASE_URL is not set, so the tests have no database to use")

test_engine = create_engine(settings.test_database_url)
TestSession = sessionmaker(bind=test_engine)
Base.metadata.create_all(test_engine)


def get_test_session():
    with TestSession() as session:
        yield session


# Every route that asks for get_session now gets a test database session instead
app.dependency_overrides[get_session] = get_test_session


@pytest.fixture(autouse=True)
def empty_table():
    """Start every test with no assets and IDs counting from 1."""
    with test_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE assets RESTART IDENTITY"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def database_rows():
    """Return a function that reads the assets table straight from PostgreSQL."""

    def fetch():
        with test_engine.connect() as connection:
            query = text("SELECT name, type, assigned_to FROM assets ORDER BY id")
            return [tuple(row) for row in connection.execute(query)]

    return fetch