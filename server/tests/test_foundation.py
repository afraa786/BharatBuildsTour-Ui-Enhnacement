from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db.session import database_url
from app.main import app


def test_live_health() -> None:
    with TestClient(app) as client:
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
