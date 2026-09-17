from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def database_url(settings: Settings) -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(get_settings()), pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def transaction_session() -> Iterator[Session]:
    """Commit on success, roll back on failure, and always close the session."""
    with get_sessionmaker().begin() as session:
        yield session


def get_db() -> Generator[Session, None, None]:
    with transaction_session() as session:
        yield session
