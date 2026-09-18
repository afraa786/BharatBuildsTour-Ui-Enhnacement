import json
from typing import Any


class StockAwareClientError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
        request_id: str | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.request_id = request_id
        # Safe repr avoiding secrets
        super().__init__(f"[{status_code}] {code}: {message}")

    def __repr__(self):
        return f"StockAwareClientError(status={self.status_code}, code='{self.code}')"


class BaseHttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = None

    def set_client(self, client):
        self._client = client

    @staticmethod
    def _handle_response(response) -> Any:
        if response.status_code >= 400:
            try:
                data = response.json()
                err = data.get("error", {})
                raise StockAwareClientError(
                    status_code=response.status_code,
                    code=err.get("code", "UNKNOWN_ERROR"),
                    message=err.get("message", response.text),
                    details=err.get("details", {}),
                    request_id=err.get("request_id"),
                )
            except (json.JSONDecodeError, ValueError):
                raise StockAwareClientError(
                    status_code=response.status_code,
                    code="UNPARSABLE_ERROR",
                    message=response.text,
                )
        return response.json()
