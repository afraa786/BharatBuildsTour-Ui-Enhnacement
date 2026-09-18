from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db.session import (
    CONNECT_ARGS,
    NAT_IDLE_TIMEOUT_SECONDS,
    POOL_RECYCLE_SECONDS,
    database_url,
    get_engine,
)
from app.main import create_app


def test_live_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_url_encodes_special_characters() -> None:
    settings = Settings(
        _env_file=None,
        postgres_user="stockaware",
        postgres_password=SecretStr("a@b:c/d"),
        postgres_db="stockaware",
        jwt_secret=SecretStr("test-only-jwt-secret"),
    )
    url = database_url(settings)
    assert url.password == settings.postgres_password.get_secret_value()
    assert "a%40b%3Ac%2Fd" in url.render_as_string(hide_password=False)


def test_pool_recycles_before_the_nat_idle_timeout() -> None:
    """A dropped idle socket must never be handed out to a request.

    The database sits behind a NAT gateway that silently drops idle TCP flows.
    Such a socket does not fail `pool_pre_ping`'s probe either -- it black-holes
    it -- so the first request after an idle period hung until the OS TCP timeout
    and the browser rendered a request-timeout error. Recycling first keeps every
    handed-out connection fresh.
    """
    pool = get_engine().pool
    assert pool._pre_ping is True  # type: ignore[attr-defined]
    assert pool._recycle == POOL_RECYCLE_SECONDS  # type: ignore[attr-defined]
    assert POOL_RECYCLE_SECONDS < NAT_IDLE_TIMEOUT_SECONDS


def test_connection_fails_fast_instead_of_hanging() -> None:
    """Keepalives and a connect timeout bound how long a dead socket can stall."""
    assert CONNECT_ARGS["keepalives"] == 1
    assert CONNECT_ARGS["keepalives_idle"] <= 30
    assert CONNECT_ARGS["keepalives_count"] >= 1
    connect_timeout = CONNECT_ARGS["connect_timeout"]
    assert isinstance(connect_timeout, int) and connect_timeout <= 5


def test_unhandled_errors_stay_readable_in_the_browser() -> None:
    """A 500 must carry CORS headers, or the UI shows "Failed to fetch" instead.

    Starlette builds an unhandled-error response outside the CORS middleware, so
    without this the browser blocks it and the real failure is invisible.
    """
    failing_app: FastAPI = create_app()

    @failing_app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(failing_app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "RuntimeError" not in response.text
