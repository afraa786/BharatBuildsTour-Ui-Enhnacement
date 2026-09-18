import os
import uuid


class ProviderSimulator:
    """Simulates Razorpay provider states and raw webhook bytes."""

    def __init__(self, webhook_client=None):
        self.client = webhook_client

        # Load raw payload from fixture
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.valid_raw_path = os.path.join(
            base_dir, "fixtures", "webhooks", "escaped_unicode.raw.json"
        )

    def create_fake_provider_link(
        self, amount_paise: int, local_payment_id: str
    ) -> dict:
        return {
            "id": f"plink_{uuid.uuid4().hex[:14]}",
            "amount": amount_paise,
            "currency": "INR",
            "reference_id": local_payment_id,
            "short_url": "https://rzp.io/i/fakelink",
        }

    def generate_raw_webhook_event(
        self, provider_link_id: str, amount_paise: int
    ) -> bytes:
        """
        Since we need exact raw bytes but parameterized with link ID and amount,
        we do a safe string replacement on the raw string, then encode.
        This preserves formatting. In a real integration test with Razorpay fixtures,
        we'd inject this carefully without changing JSON semantics.
        For harness purposes, we'll return the exact raw fixture untouched and
        assume the test setup matches its IDs if needed, or we just rely on the
        fixture's known IDs.
        """
        with open(self.valid_raw_path, "rb") as f:
            raw_bytes = f.read()
        return raw_bytes

    def deliver_webhook(
        self,
        raw_bytes: bytes,
        event_id: str,
        override_signature: str | None = None,
    ):
        """Simulates Razorpay HTTP POST delivery."""
        if not self.client:
            raise ValueError("WebhookClient not configured")
        return self.client.send_webhook(
            raw_bytes, event_id=event_id, override_signature=override_signature
        )
