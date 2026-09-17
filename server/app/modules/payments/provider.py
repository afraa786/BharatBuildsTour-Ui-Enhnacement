"""Razorpay Standard Payment Link adapter. Never log credentials or raw responses."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

from app.api.commercial import CommercialError
from app.core.config import get_settings


@dataclass(frozen=True)
class ProviderLink:
    link_id: str
    short_url: str
    reference_id: str
    amount_paise: int
    currency: str
    status: str


class PaymentLinkProvider(Protocol):
    def create_link(
        self, *, reference_id: str, amount_paise: int, expire_by: datetime
    ) -> ProviderLink: ...


class RazorpayProvider:
    def create_link(
        self, *, reference_id: str, amount_paise: int, expire_by: datetime
    ) -> ProviderLink:
        settings = get_settings()
        key_id = settings.razorpay_key_id
        key_secret = settings.razorpay_key_secret.get_secret_value()
        if not key_id or not key_secret:
            raise CommercialError(
                503, "PAYMENT_PROVIDER_UNCONFIGURED", "Payment provider is unavailable."
            )
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    "https://api.razorpay.com/v1/payment_links",
                    auth=(key_id, key_secret),
                    json={
                        "amount": amount_paise,
                        "currency": "INR",
                        "accept_partial": False,
                        "reference_id": reference_id,
                        "expire_by": int(expire_by.timestamp()),
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # HTTP failures may be ambiguous: never create a second link blindly.
            raise CommercialError(
                503,
                "PROVIDER_OUTCOME_UNKNOWN",
                "Payment link outcome requires provider-reference reconciliation.",
            ) from exc
        try:
            return ProviderLink(
                link_id=payload["id"],
                short_url=payload["short_url"],
                reference_id=payload["reference_id"],
                amount_paise=payload["amount"],
                currency=payload["currency"],
                status=payload["status"],
            )
        except (KeyError, TypeError) as exc:
            raise CommercialError(
                503,
                "PROVIDER_OUTCOME_UNKNOWN",
                "Payment link response requires provider-reference reconciliation.",
            ) from exc
