"""Offline simulator and strict real-HTTP commercial acceptance journey."""

import argparse
import json
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from client.commercial_client import CommercialClient
from client.config import config
from client.http_client import StockAwareClientError
from client.webhook_client import WebhookClient
from correlation import CorrelationTraceValidator
from drift_checker import DriftChecker
from simulators.buyer import BuyerSimulator
from simulators.outbox_consumer import OutboxConsumerSimulator
from simulators.provider import ProviderSimulator
from simulators.rehbar import RehbarSimulator

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "e2e" / "http_happy_path.json"


class JourneyStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP_CONFIG_NOT_AVAILABLE"
    DEFERRED = "DEFERRED_REHBAR_TRANSPORT"


def _expect(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _validate_request(
    checker: DriftChecker, openapi: dict, path: str, payload: dict
) -> None:
    errors = checker.validate_request(openapi, path, "post", payload)
    if errors:
        raise AssertionError("; ".join(errors))


def run_offline() -> bool:
    print("Running Offline Happy Path Journey...")
    validator = CorrelationTraceValidator()

    rehbar = RehbarSimulator()
    run_id = rehbar.start_rfq(config.default_business_id, config.default_buyer_id)
    product_id = "mock-product-id"
    quote_id = "mock-quote-id"
    payment_id = "mock-pay-id"
    invoice_id = "mock-invoice-id"
    quote_version = 1
    common = {
        "business_id": config.default_business_id,
        "run_id": run_id,
        "buyer_id": config.default_buyer_id,
        "product_id": product_id,
    }
    validator.record_step("rfq_started", common)
    validator.record_step("catalog_matched", common)
    validator.record_step("inventory_checked", {**common, "status": "AVAILABLE"})
    validator.record_step(
        "quote_generated",
        {
            **common,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "status": "GENERATED",
        },
    )

    buyer = BuyerSimulator(rehbar)
    buyer.review_quote({"status": "GENERATED"})
    buyer.accept_quote(run_id, quote_id, quote_version)
    validator.record_step(
        "payment_link_created",
        {
            **common,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "payment_id": payment_id,
        },
    )
    provider = ProviderSimulator()
    provider.generate_raw_webhook_event("mock-link", 28320)
    validator.record_step(
        "webhook_delivered",
        {
            **common,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "payment_id": payment_id,
        },
    )
    outbox = OutboxConsumerSimulator()
    outbox.consume("mock-event-id", {"payment_id": payment_id, "status": "PAID"})
    validator.record_step(
        "invoice_generated",
        {
            **common,
            "quote_id": quote_id,
            "quote_version": quote_version,
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "invoice_number": "INV-123",
            "download_url": f"/invoices/{invoice_id}/artifact",
        },
    )
    valid, message = validator.validate()
    print(f"{'PASS' if valid else 'FAIL'}: {message}")
    return valid


def run_http() -> JourneyStatus:
    missing = config.missing_http_configuration()
    if missing:
        print(f"HTTP SKIP / CONFIG_NOT_AVAILABLE: {', '.join(missing)}")
        return JourneyStatus.SKIP

    print(
        "Running strict HTTP commercial journey against the actual FastAPI application..."
    )
    fixture = json.loads(FIXTURE_PATH.read_text())
    business_id = UUID(config.default_business_id)
    buyer_id = UUID(config.default_buyer_id)
    run_id = f"RFQ-HTTP-{uuid4().hex}"

    if config.fixture_injection_enabled:
        from http_fixture import prepare_demo_state

        prepare_demo_state(business_id, buyer_id)

    import httpx

    trace = CorrelationTraceValidator()
    checker = DriftChecker()
    with httpx.Client(base_url=config.base_url, timeout=20.0) as http_client:
        commercial = CommercialClient(config.base_url)
        commercial.set_client(http_client)
        webhook = WebhookClient(config.base_url)
        webhook.set_client(http_client)

        try:
            openapi = commercial.openapi()
            products = commercial.get_products()
            if not products:
                raise AssertionError("Authenticated GET /products returned no products")
            product_listing = next(
                (
                    item
                    for item in products
                    if item["sku"] == fixture["product"]["selected_sku"]
                ),
                None,
            )
            if product_listing is None:
                raise AssertionError("Deterministic LED-9W product is absent")

            catalog_payload = {
                "business_id": str(business_id),
                "run_id": run_id,
                "requested_text": fixture["product"]["requested_text"],
                "requested_unit": fixture["product"]["requested_unit"],
            }
            _validate_request(checker, openapi, "/catalog/match", catalog_payload)
            matched = commercial.catalog_match(
                catalog_payload["business_id"],
                run_id,
                catalog_payload["requested_text"],
                catalog_payload["requested_unit"],
            )
            _expect(matched["status"], "MATCHED", "catalog status")
            _expect(
                matched["selected_sku"],
                fixture["product"]["selected_sku"],
                "catalog SKU",
            )
            product_id = matched.get("selected_product_id")
            if not product_id:
                raise AssertionError("MATCHED response did not select a product")
            _expect(
                product_id,
                product_listing["product_id"],
                "catalog/listing product correlation",
            )
            trace.record_step(
                "catalog_matched",
                {
                    "business_id": str(business_id),
                    "run_id": run_id,
                    "buyer_id": str(buyer_id),
                    "product_id": product_id,
                },
            )

            inventory_payload = {
                "business_id": str(business_id),
                "run_id": run_id,
                "product_id": product_id,
                "requested_qty": fixture["inventory"]["requested_qty"],
                "requested_unit": fixture["product"]["requested_unit"],
            }
            _validate_request(checker, openapi, "/inventory/check", inventory_payload)
            stock = commercial.inventory_check(
                str(business_id),
                run_id,
                product_id,
                inventory_payload["requested_qty"],
                inventory_payload["requested_unit"],
            )
            _expect(stock["product_id"], product_id, "inventory product")
            _expect(
                stock["requested_qty"],
                fixture["inventory"]["requested_qty"],
                "inventory quantity",
            )
            _expect(
                stock["status"],
                fixture["inventory"]["expected_status"],
                "inventory state",
            )
            _expect(
                stock["available_qty"],
                fixture["inventory"]["expected_available_qty"],
                "inventory available quantity",
            )
            trace.record_step(
                "inventory_checked",
                {
                    "business_id": str(business_id),
                    "run_id": run_id,
                    "buyer_id": str(buyer_id),
                    "product_id": product_id,
                },
            )

            quote_payload = {
                "business_id": str(business_id),
                "run_id": run_id,
                "buyer_id": str(buyer_id),
                "lines": [
                    {
                        "product_id": product_id,
                        "quantity": fixture["quote"]["quantity"],
                        "unit": fixture["quote"]["unit"],
                        "discount_bps": fixture["quote"]["discount_bps"],
                    }
                ],
            }
            _validate_request(checker, openapi, "/pricing/quote", quote_payload)
            quote = commercial.pricing_quote(
                str(business_id),
                run_id,
                str(buyer_id),
                f"http-quote-{run_id}",
                quote_payload["lines"],
            )
            for field, expected in {
                "business_id": str(business_id),
                "run_id": run_id,
                "quote_version": fixture["quote"]["expected_version"],
                "status": fixture["quote"]["expected_status"],
                "subtotal_paise": fixture["quote"]["expected_subtotal_paise"],
                "tax_paise": fixture["quote"]["expected_tax_paise"],
                "total_paise": fixture["quote"]["expected_total_paise"],
                "approval_required": fixture["quote"]["expected_approval_required"],
            }.items():
                _expect(quote[field], expected, f"quote {field}")
            quote_id = UUID(quote["quote_id"])
            quote_version = quote["quote_version"]
            trace.record_step(
                "quote_generated",
                {
                    "business_id": str(business_id),
                    "run_id": run_id,
                    "buyer_id": str(buyer_id),
                    "product_id": product_id,
                    "quote_id": str(quote_id),
                    "quote_version": quote_version,
                },
            )

            print("Rehbar approval transport: DEFERRED_REHBAR_TRANSPORT")
            print("Rehbar acceptance transport: DEFERRED_REHBAR_TRANSPORT")
            if not config.fixture_injection_enabled:
                return JourneyStatus.DEFERRED
            from http_fixture import (
                inject_rehbar_evidence,
                outbox_evidence,
                payment_evidence,
            )

            inject_rehbar_evidence(business_id, run_id, quote_id, quote_version)
            print("Approval/acceptance continuation: TEST_FIXTURE_STATE_INJECTION")

            payment_payload = {
                "business_id": str(business_id),
                "run_id": run_id,
                "quote_id": str(quote_id),
                "quote_version": quote_version,
                "amount_paise": quote["total_paise"],
            }
            _validate_request(
                checker, openapi, "/payments/create-link", payment_payload
            )
            payment_key = f"http-payment-{run_id}"
            try:
                commercial.create_payment_link(
                    str(business_id),
                    run_id,
                    str(quote_id),
                    quote_version,
                    payment_key,
                    quote["total_paise"],
                )
                raise AssertionError(
                    "Synthetic lost provider response unexpectedly succeeded"
                )
            except StockAwareClientError as error:
                _expect(error.status_code, 503, "uncertain provider HTTP status")
                _expect(
                    error.code, "PROVIDER_OUTCOME_UNKNOWN", "uncertain provider code"
                )

            recovered = commercial.create_payment_link(
                str(business_id),
                run_id,
                str(quote_id),
                quote_version,
                payment_key,
                quote["total_paise"],
            )
            _expect(recovered["quote_id"], str(quote_id), "payment quote")
            _expect(recovered["quote_version"], quote_version, "payment quote version")
            _expect(recovered["amount_paise"], quote["total_paise"], "payment amount")
            _expect(recovered["currency"], "INR", "payment currency")
            _expect(recovered["status"], "PENDING", "recovered payment state")
            payment_id = UUID(recovered["payment_id"])
            persisted = payment_evidence(business_id, payment_id)
            _expect(persisted["payment_id"], str(payment_id), "persisted payment")
            _expect(
                persisted["provider_reference_id"],
                str(payment_id),
                "stable provider reference",
            )
            _expect(
                persisted["provider_link_id"],
                recovered["provider_link_id"],
                "recovered provider link",
            )
            replay = commercial.create_payment_link(
                str(business_id),
                run_id,
                str(quote_id),
                quote_version,
                payment_key,
                quote["total_paise"],
            )
            _expect(replay, recovered, "payment idempotent replay")
            trace.record_step(
                "payment_link_created",
                {
                    "business_id": str(business_id),
                    "run_id": run_id,
                    "buyer_id": str(buyer_id),
                    "product_id": product_id,
                    "quote_id": str(quote_id),
                    "quote_version": quote_version,
                    "payment_id": str(payment_id),
                },
            )

            raw_webhook = json.dumps(
                {
                    "entity": "event",
                    "account_id": config.provider_account_id,
                    "event": "payment_link.paid",
                    "created_at": int(datetime.now(UTC).timestamp()),
                    "payload": {
                        "payment_link": {
                            "entity": {
                                "id": recovered["provider_link_id"],
                                "reference_id": persisted["provider_reference_id"],
                                "amount": recovered["amount_paise"],
                                "amount_paid": recovered["amount_paise"],
                                "currency": "INR",
                                "status": "paid",
                            }
                        },
                        "payment": {
                            "entity": {
                                "id": f"pay_{payment_id.hex[:18]}",
                                "amount": recovered["amount_paise"],
                                "currency": "INR",
                                "status": "captured",
                            }
                        },
                    },
                },
                separators=(",", ":"),
            ).encode()
            webhook_result = webhook.send_webhook(
                raw_webhook, event_id=f"evt_{payment_id.hex}"
            )
            _expect(webhook_result["status"], "PAID", "verified webhook state")
            paid = commercial.get_payment(str(payment_id))
            _expect(paid["status"], "PAID", "queried payment state")
            outbox = outbox_evidence(business_id, payment_id)
            _expect(outbox["events"], 1, "payment event count")
            _expect(outbox["verified_outbox"], 1, "verified outbox count")
            trace.record_step(
                "webhook_delivered",
                {
                    "business_id": str(business_id),
                    "run_id": run_id,
                    "buyer_id": str(buyer_id),
                    "product_id": product_id,
                    "quote_id": str(quote_id),
                    "quote_version": quote_version,
                    "payment_id": str(payment_id),
                },
            )

            invoice_payload = {
                "business_id": str(business_id),
                "run_id": run_id,
                "quote_id": str(quote_id),
                "quote_version": quote_version,
                "payment_id": str(payment_id),
            }
            _validate_request(checker, openapi, "/invoice/generate", invoice_payload)
            invoice = commercial.generate_invoice(
                str(business_id),
                run_id,
                str(quote_id),
                quote_version,
                str(payment_id),
                f"http-invoice-{run_id}",
            )
            _expect(invoice["status"], "GENERATED", "invoice state")
            _expect(invoice["payment_id"], str(payment_id), "invoice payment")
            _expect(invoice["quote_id"], str(quote_id), "invoice quote")
            if not invoice.get("invoice_number"):
                raise AssertionError("Invoice number is absent")
            invoice_id = invoice["invoice_id"]
            _expect(commercial.get_invoice(invoice_id), invoice, "invoice GET")
            artifact = commercial.get_invoice_artifact(invoice_id)
            _expect(artifact.status_code, 200, "artifact status")
            if not artifact.content.startswith(b"%PDF") or not artifact.content:
                raise AssertionError("Artifact is empty or not a PDF")
            if not artifact.headers.get("content-type", "").startswith(
                "application/pdf"
            ):
                raise AssertionError("Artifact content type is not application/pdf")
            disposition = artifact.headers.get("content-disposition", "")
            if "/" in disposition or "\\" in disposition:
                raise AssertionError("Artifact response leaks a filesystem path")
            trace.record_step(
                "invoice_generated",
                {
                    "business_id": str(business_id),
                    "run_id": run_id,
                    "buyer_id": str(buyer_id),
                    "product_id": product_id,
                    "quote_id": str(quote_id),
                    "quote_version": quote_version,
                    "payment_id": str(payment_id),
                    "invoice_id": invoice_id,
                    "invoice_number": invoice["invoice_number"],
                    "download_url": invoice["download_url"],
                },
            )
            valid, message = trace.validate()
            if not valid:
                raise AssertionError(message)
        except (
            AssertionError,
            StockAwareClientError,
            httpx.HTTPError,
            ValueError,
        ) as error:
            print(f"HTTP FAIL: {error}")
            return JourneyStatus.FAIL

    print("OUTBOX_CREATION = PASS")
    print("OUTBOX_DELIVERY_TO_REHBAR = DEFERRED")
    print("HTTP PASS: authenticated commercial chain and correlation verified")
    return JourneyStatus.PASS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()

    failed = args.offline and not run_offline()
    if args.http:
        failed = run_http() == JourneyStatus.FAIL or failed
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
