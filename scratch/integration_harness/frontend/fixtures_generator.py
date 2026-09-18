import json
import os
from frontend.validator import validate_frontend_fixture

def _write_fixture(name: str, data: dict):
    validate_frontend_fixture(data)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, f"{name}.json")
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def generate_frontend_fixtures():
    # Catalog
    _write_fixture("catalog_matched", {
        "status": "MATCHED",
        "requested_text": "LED-9W",
        "selected_product_id": "dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7",
        "selected_sku": "LED-9W",
        "candidates": [{"id": "dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7", "sku": "LED-9W"}],
        "reason": "Exact match"
    })
    
    _write_fixture("catalog_ambiguous", {
        "status": "AMBIGUOUS",
        "requested_text": "WIRE",
        "selected_product_id": None,
        "selected_sku": None,
        "candidates": [
            {"id": "uuid-1", "sku": "WIRE-1MM"},
            {"id": "uuid-2", "sku": "WIRE-2MM"}
        ],
        "reason": "Multiple candidates found"
    })
    
    # Inventory
    _write_fixture("inventory_available", {
        "status": "AVAILABLE",
        "product_id": "dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7",
        "requested_qty": "10.000",
        "stock_unit": "piece",
        "available_qty": "50.000",
        "checked_at": "2026-09-18T10:00:00Z",
        "substitutes": []
    })

    _write_fixture("inventory_out_of_stock", {
        "status": "OUT_OF_STOCK",
        "product_id": "dcdb744a-0dc6-5e5a-b179-928ae8c6d9e7",
        "requested_qty": "10.000",
        "stock_unit": "piece",
        "available_qty": "0.000",
        "checked_at": "2026-09-18T10:00:00Z",
        "substitutes": []
    })

    # Quote
    _write_fixture("quote_generated", {
        "business_id": "ff720599-56e8-53f4-9279-27ae059da37f",
        "run_id": "RFQ-1042",
        "quote_id": "6b530cb4-3510-4b83-9152-d7182b9164d5",
        "quote_version": 1,
        "status": "GENERATED",
        "currency": "INR",
        "subtotal_paise": 24000,
        "tax_paise": 4320,
        "total_paise": 28320,
        "expires_at": "2026-09-19T10:00:00Z",
        "approval_required": False,
        "approval_satisfied": False,
        "approval_reasons": [],
        "lines": [{
            "sku": "LED-9W",
            "quantity": "2.000",
            "unit": "piece",
            "unit_price_paise": 12000,
            "discount_bps": 0,
            "discount_paise": 0,
            "taxable_paise": 24000,
            "gst_rate_bps": 1800,
            "tax_paise": 4320,
            "line_total_paise": 28320
        }]
    })
    
    # Payment & Invoice
    _write_fixture("payment_pending", {
        "payment_id": "pay_123",
        "quote_id": "6b530cb4-3510-4b83-9152-d7182b9164d5",
        "quote_version": 1,
        "status": "PENDING",
        "amount_paise": 28320,
        "currency": "INR",
        "provider_link_id": "plink_abc123",
        "payment_url": "https://rzp.io/i/fakelink",
        "expires_at": "2026-09-19T10:00:00Z"
    })

    _write_fixture("invoice_generated", {
        "invoice_id": "inv_123",
        "invoice_number": "INV-2026-000001",
        "payment_id": "pay_123",
        "quote_id": "6b530cb4-3510-4b83-9152-d7182b9164d5",
        "status": "GENERATED",
        "currency": "INR",
        "total_paise": 28320,
        "download_url": "https://stockaware.local/invoices/inv_123/artifact"
    })
    
    # Error
    _write_fixture("canonical_error", {
        "error": {
            "code": "QUOTE_VERSION_MISMATCH",
            "message": "The quote version is no longer current.",
            "details": {"run_id": "RFQ-1042", "current_quote_id": "6b530cb4-3510-4b83-9152-d7182b9164d5"},
            "request_id": "req_7a1"
        }
    })

if __name__ == "__main__":
    generate_frontend_fixtures()
