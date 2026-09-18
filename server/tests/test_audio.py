import pytest

from app.core.config import get_settings
from app.modules.whatsapp import audio


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_transcribe_returns_none_without_openai_key() -> None:
    assert audio.transcribe(b"fake-bytes", "audio/ogg") is None


def test_synthesize_returns_none_without_openai_key() -> None:
    assert audio.synthesize("hello") is None


def test_synthesize_returns_none_for_empty_text() -> None:
    assert audio.synthesize("") is None


def test_mime_to_extension_mapping() -> None:
    assert audio._mime_to_extension("audio/ogg; codecs=opus") == "ogg"
    assert audio._mime_to_extension("audio/mpeg") == "mp3"
    assert audio._mime_to_extension("audio/wav") == "wav"
    assert audio._mime_to_extension("audio/unknown") == "m4a"
