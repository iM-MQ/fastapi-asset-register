"""Database connection: settings, engine, sessions and the base class for tables."""

from collections.abc import Iterator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Settings(BaseSettings):
    """Read from environment variables, or from a .env file in the lab folder."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str | None = None


settings = Settings()

# The engine manages a pool of connections. It does not connect until first used.
# pool_pre_ping checks each connection still works before handing it out, so a
# database restart does not break the next request
engine = create_engine(settings.database_url, pool_pre_ping=True)

# A factory for sessions. One session is one conversation with the database
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Every table class inherits from this."""


def get_session() -> Iterator[Session]:
    """Give each request its own session, and always close it afterwards."""
    with SessionLocal() as session:
        yield session