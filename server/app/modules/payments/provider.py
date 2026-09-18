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

    def find_link(self, *, reference_id: str) -> ProviderLink | None: ...


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

    def find_link(self, *, reference_id: str) -> ProviderLink | None:
        """Fetch by Razorpay's documented unique Payment Link reference_id."""
        settings = get_settings()
        key_id = settings.razorpay_key_id
        key_secret = settings.razorpay_key_secret.get_secret_value()
        if not key_id or not key_secret:
            raise CommercialError(
                503, "PAYMENT_PROVIDER_UNCONFIGURED", "Payment provider is unavailable."
            )
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    "https://api.razorpay.com/v1/payment_links/",
                    auth=(key_id, key_secret),
                    params={"reference_id": reference_id},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CommercialError(
                503, "PROVIDER_OUTCOME_UNKNOWN", "Payment link lookup is uncertain."
            ) from exc
        if not isinstance(payload, dict):
            raise CommercialError(
                503, "PROVIDER_OUTCOME_UNKNOWN", "Payment link lookup is uncertain."
            )
        # Razorpay documents a direct object for reference filtering; collection
        # responses from the listing API are accepted only when unambiguous.
        if "id" in payload:
            candidates = [payload]
        elif isinstance(payload.get("payment_links"), list):
            candidates = payload["payment_links"]
        elif payload.get("count") == 0 and payload.get("items") == []:
            candidates = []
        else:
            raise CommercialError(
                503, "PROVIDER_OUTCOME_UNKNOWN", "Payment link lookup is uncertain."
            )
        if not candidates:
            return None
        if len(candidates) != 1 or not isinstance(candidates[0], dict):
            raise CommercialError(
                503, "PROVIDER_OUTCOME_UNKNOWN", "Payment link lookup is ambiguous."
            )
        item = candidates[0]
        try:
            return ProviderLink(
                link_id=item["id"],
                short_url=item["short_url"],
                reference_id=item["reference_id"],
                amount_paise=item["amount"],
                currency=item["currency"],
                status=item["status"],
            )
        except (KeyError, TypeError) as exc:
            raise CommercialError(
                503, "PROVIDER_OUTCOME_UNKNOWN", "Payment link lookup is incomplete."
            ) from exc
