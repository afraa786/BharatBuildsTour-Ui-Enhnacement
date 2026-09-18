"""ASGI target that injects a fake Razorpay provider without changing production."""

from datetime import datetime
from threading import Lock

from app.api.commercial import CommercialError
from app.main import app
from app.modules.payments import service as payment_service
from app.modules.payments.provider import ProviderLink


class RecoveringFakeProvider:
    """Creates once, loses the first response, then recovers by reference lookup."""

    def __init__(self) -> None:
        self._links: dict[str, ProviderLink] = {}
        self._lock = Lock()

    def create_link(
        self, *, reference_id: str, amount_paise: int, expire_by: datetime
    ) -> ProviderLink:
        del expire_by
        with self._lock:
            if reference_id in self._links:
                raise AssertionError("Production attempted a duplicate provider create")
            link = ProviderLink(
                link_id=f"plink_{reference_id.replace('-', '')[:18]}",
                short_url="https://rzp.io/i/http-acceptance",
                reference_id=reference_id,
                amount_paise=amount_paise,
                currency="INR",
                status="created",
            )
            self._links[reference_id] = link
        raise CommercialError(
            503,
            "PROVIDER_OUTCOME_UNKNOWN",
            "Synthetic provider created the link but its response was lost.",
        )

    def find_link(self, *, reference_id: str) -> ProviderLink | None:
        with self._lock:
            return self._links.get(reference_id)


fake_provider = RecoveringFakeProvider()
payment_service.RazorpayProvider = lambda: fake_provider

__all__ = ["app"]
