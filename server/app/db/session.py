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


def get_db() -> Generator[Session, None, None]:
    """Plain request-scoped session. Callers commit explicitly.

    Handlers that need several commits within one request (e.g. the
    WhatsApp webhook: dedup-log commit, business-logic commit, outbound-log
    commit) require this -- a `Session.begin()`-style auto-commit-on-success
    wrapper cannot support more than one commit per request.
    """
    with get_sessionmaker()() as session:
        yield session


@contextmanager
def transaction_session() -> Iterator[Session]:
    """Commit on success, roll back on failure, and always close the session.

    For single-shot scripts (e.g. seeding) that only need one commit.
    FastAPI request handlers should use `get_db` instead.
    """
    with get_sessionmaker().begin() as session:
        yield session
