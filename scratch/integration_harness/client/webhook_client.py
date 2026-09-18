import hashlib
import hmac

from .config import config
from .http_client import BaseHttpClient


class WebhookClient(BaseHttpClient):
    def sign_payload(self, raw_bytes: bytes) -> str:
        return hmac.new(
            config.webhook_secret.encode("utf-8"), raw_bytes, hashlib.sha256
        ).hexdigest()

    def send_webhook(
        self,
        raw_bytes: bytes,
        event_id: str,
        override_signature: str | None = None,
    ):
        signature = (
            override_signature
            if override_signature is not None
            else self.sign_payload(raw_bytes)
        )

        headers = {
            "X-Razorpay-Signature": signature,
            "x-razorpay-event-id": event_id,
            "Content-Type": "application/json",
        }

        # Raw bytes, no json= kwarg
        res = self._client.post("/payments/webhook", headers=headers, content=raw_bytes)
        return self._handle_response(res)
