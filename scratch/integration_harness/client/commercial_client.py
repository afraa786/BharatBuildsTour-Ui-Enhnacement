from typing import Any

from .config import config
from .http_client import BaseHttpClient


class CommercialClient(BaseHttpClient):
    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "X-Internal-Service-Token": config.internal_service_token,
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def debug_request(self, method: str, path: str, headers: dict, payload: Any = None):
        safe_headers = headers.copy()
        if "X-Internal-Service-Token" in safe_headers:
            safe_headers["X-Internal-Service-Token"] = "[REDACTED]"
        return safe_headers, payload

    def openapi(self):
        return self._handle_response(self._client.get("/openapi.json"))

    def get_products(self):
        headers = self._headers()
        self.debug_request("GET", "/products", headers)
        return self._handle_response(self._client.get("/products", headers=headers))

    def catalog_match(
        self,
        business_id: str,
        run_id: str,
        requested_text: str,
        requested_unit: str,
    ):
        payload = {
            "business_id": business_id,
            "run_id": run_id,
            "requested_text": requested_text,
            "requested_unit": requested_unit,
        }
        headers = self._headers()
        self.debug_request("POST", "/catalog/match", headers, payload)
        res = self._client.post("/catalog/match", headers=headers, json=payload)
        return self._handle_response(res)

    def inventory_check(
        self,
        business_id: str,
        run_id: str,
        product_id: str,
        requested_qty: str,
        requested_unit: str,
    ):
        payload = {
            "business_id": business_id,
            "run_id": run_id,
            "product_id": product_id,
            "requested_qty": requested_qty,
            "requested_unit": requested_unit,
        }
        headers = self._headers()
        self.debug_request("POST", "/inventory/check", headers, payload)
        res = self._client.post("/inventory/check", headers=headers, json=payload)
        return self._handle_response(res)

    def pricing_quote(
        self,
        business_id: str,
        run_id: str,
        buyer_id: str,
        idempotency_key: str,
        lines: list[dict],
    ):
        payload = {
            "business_id": business_id,
            "run_id": run_id,
            "buyer_id": buyer_id,
            "lines": lines,
        }
        headers = self._headers(idempotency_key=idempotency_key)
        self.debug_request("POST", "/pricing/quote", headers, payload)
        res = self._client.post("/pricing/quote", headers=headers, json=payload)
        return self._handle_response(res)

    def apply_approval(self, *args, **kwargs):
        raise NotImplementedError("DEFERRED_REHBAR_TRANSPORT")

    def apply_acceptance(self, *args, **kwargs):
        raise NotImplementedError("DEFERRED_REHBAR_TRANSPORT")

    def create_payment_link(
        self,
        business_id: str,
        run_id: str,
        quote_id: str,
        quote_version: int,
        idempotency_key: str,
        amount_paise: int | None = None,
    ):
        payload = {
            "business_id": business_id,
            "run_id": run_id,
            "quote_id": quote_id,
            "quote_version": quote_version,
        }
        if amount_paise is not None:
            payload["amount_paise"] = amount_paise

        headers = self._headers(idempotency_key=idempotency_key)
        self.debug_request("POST", "/payments/create-link", headers, payload)
        res = self._client.post("/payments/create-link", headers=headers, json=payload)
        return self._handle_response(res)

    def get_payment(self, payment_id: str):
        headers = self._headers()
        self.debug_request("GET", f"/payments/{payment_id}", headers)
        res = self._client.get(f"/payments/{payment_id}", headers=headers)
        return self._handle_response(res)

    def generate_invoice(
        self,
        business_id: str,
        run_id: str,
        quote_id: str,
        quote_version: int,
        payment_id: str,
        idempotency_key: str,
    ):
        payload = {
            "business_id": business_id,
            "run_id": run_id,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "payment_id": payment_id,
        }
        headers = self._headers(idempotency_key=idempotency_key)
        self.debug_request("POST", "/invoice/generate", headers, payload)
        res = self._client.post("/invoice/generate", headers=headers, json=payload)
        return self._handle_response(res)

    def get_invoice(self, invoice_id: str):
        headers = self._headers()
        self.debug_request("GET", f"/invoices/{invoice_id}", headers)
        res = self._client.get(f"/invoices/{invoice_id}", headers=headers)
        return self._handle_response(res)

    def get_invoice_artifact(self, invoice_id: str):
        headers = self._headers()
        self.debug_request("GET", f"/invoices/{invoice_id}/artifact", headers)
        response = self._client.get(f"/invoices/{invoice_id}/artifact", headers=headers)
        if response.status_code >= 400:
            self._handle_response(response)
        return response
