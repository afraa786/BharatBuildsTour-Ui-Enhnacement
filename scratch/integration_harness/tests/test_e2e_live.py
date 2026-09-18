"""Strict live HTTP gate plus raw-body webhook rejection coverage."""

from pathlib import Path

import pytest
from app.main import app
from client.config import config
from fastapi.testclient import TestClient
from run_journey import JourneyStatus, run_http


@pytest.mark.skipif(
    not config.http_acceptance_enabled,
    reason="set STOCKAWARE_HTTP_ACCEPTANCE=1 and explicit local HTTP credentials",
)
def test_live_e2e_happy_path():
    assert run_http() == JourneyStatus.PASS


def test_webhook_raw_body_security():
    raw_body = (
        Path(__file__).parents[1] / "fixtures" / "webhooks" / "escaped_unicode.raw.json"
    ).read_bytes()
    with TestClient(app) as client:
        response = client.post(
            "/payments/webhook",
            headers={
                "X-Razorpay-Signature": "dummy_sig",
                "Content-Type": "application/json",
            },
            content=raw_body,
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"
