from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.whatsapp import bindings_cli


def test_unconfigured_slot_exits_without_database_access(monkeypatch) -> None:
    monkeypatch.setattr(
        bindings_cli,
        "get_settings",
        lambda: SimpleNamespace(whatsapp_test_phone_number_id=""),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "bindings_cli",
            "--credential-slot",
            "test",
            "--business-id",
            str(uuid4()),
            "--experience",
            "customer_commerce",
        ],
    )
    with pytest.raises(SystemExit, match="not configured"):
        bindings_cli.main()


def test_existing_binding_requires_explicit_replace(monkeypatch) -> None:
    business_id = uuid4()
    existing = SimpleNamespace(
        business_id=uuid4(), experience="owner_manager", waba_id=None, enabled=True
    )

    class FakeDb:
        def get(self, *_args):
            return object()

        def scalar(self, _statement):
            return existing

    @contextmanager
    def fake_session():
        yield FakeDb()

    monkeypatch.setattr(bindings_cli, "transaction_session", fake_session)
    monkeypatch.setattr(
        bindings_cli,
        "get_settings",
        lambda: SimpleNamespace(whatsapp_test_phone_number_id="configured-test-id"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "bindings_cli",
            "--credential-slot",
            "test",
            "--business-id",
            str(business_id),
            "--experience",
            "customer_commerce",
        ],
    )
    with pytest.raises(SystemExit, match="replace-existing"):
        bindings_cli.main()
    assert existing.experience == "owner_manager"
