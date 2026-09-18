from datetime import UTC, datetime

from app.modules.invoices.service import (
    InvoiceDraft,
    generate_invoice_artifact,
    generate_invoice_pdf_artifact,
    next_invoice_number,
)


def test_next_invoice_number_is_year_scoped_and_six_digit_sequence() -> None:
    assert next_invoice_number(datetime(2026, 9, 18, tzinfo=UTC), 1) == "INV-2026-000001"
    assert next_invoice_number(datetime(2027, 1, 1, tzinfo=UTC), 42) == "INV-2027-000042"


def test_generate_invoice_artifact_writes_auditable_html_with_checksum(tmp_path) -> None:
    draft = InvoiceDraft(
        invoice_number="INV-2026-000001",
        run_id="RFQ-1042",
        buyer_name="Sharma Electricals",
        total_paise=141600,
        currency="INR",
        issued_at=datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
        line_items=[
            {
                "name": "32A SP MCB C Curve",
                "quantity": 2,
                "unit": "each",
                "unit_price_paise": 60000,
                "tax_paise": 21600,
                "line_total_paise": 141600,
            }
        ],
        payment_reference="pay_test_123",
    )

    artifact = generate_invoice_artifact(draft, tmp_path)

    assert artifact.artifact_key == "invoices/RFQ-1042/INV-2026-000001.html"
    assert len(artifact.artifact_sha256) == 64
    invoice_file = tmp_path / artifact.artifact_key
    assert invoice_file.exists()
    content = invoice_file.read_text()
    assert "INV-2026-000001" in content


def test_generate_invoice_pdf_artifact_writes_pdf_with_checksum(tmp_path) -> None:
    draft = InvoiceDraft(
        invoice_number="INV-2026-000001",
        run_id="RFQ-1042",
        buyer_name="Acme Electricals",
        total_paise=14160,
        issued_at=datetime(2026, 9, 18, tzinfo=UTC),
        line_items=[
            {
                "name": "9W LED Bulb",
                "quantity": "1",
                "unit": "piece",
                "line_total_paise": 14160,
            }
        ],
        payment_reference="pay_test_123",
    )

    artifact = generate_invoice_pdf_artifact(draft, tmp_path)

    assert artifact.artifact_key == "invoices/RFQ-1042/INV-2026-000001.pdf"
    invoice_file = tmp_path / artifact.artifact_key
    content = invoice_file.read_bytes()
    assert content.startswith(b"%PDF-1.4")
    assert artifact.artifact_sha256
    assert b"Acme Electricals" in content
    assert b"9W LED Bulb" in content
    assert b"pay_test_123" in content
