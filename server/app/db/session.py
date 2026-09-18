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


# The production database sits behind an AWS NAT gateway, which silently drops
# idle TCP flows after ~350s without sending a reset. A black-holed socket like
# that does not even fail `pool_pre_ping`'s `SELECT 1` -- the probe blocks on the
# dead socket until the OS TCP timeout, so the first request after a quiet period
# hangs for ~40s and the browser gives up. Recycling connections before the NAT
# idle timeout keeps every handed-out socket fresh, and keepalives plus a connect
# timeout make any remaining dead socket fail fast instead of hanging.
NAT_IDLE_TIMEOUT_SECONDS = 350
POOL_RECYCLE_SECONDS = 280

# libpq parameters so a dead or black-holed socket fails fast (seconds) instead
# of blocking until the OS-level TCP timeout, which the browser never waits for.
CONNECT_ARGS: dict[str, object] = {
    "connect_timeout": 5,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        database_url(get_settings()),
        pool_pre_ping=True,
        pool_recycle=POOL_RECYCLE_SECONDS,
        pool_timeout=10,
        connect_args=dict(CONNECT_ARGS),
    )


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
