import pytest

from app.core.config import get_settings
from app.modules.runs.manager_graph import manager_chat


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_manager_chat_falls_back_without_db_or_key() -> None:
    reply = manager_chat(db=None, admin_wa_id="admin", message="hi", fallback="fallback text")
    assert reply == "fallback text"


def test_manager_chat_history_uses_fallback_when_no_openai_key() -> None:
    reply = manager_chat(db=None, admin_wa_id="admin", message="hi again", fallback="fallback text")
    assert reply == "fallback text"
