"""Render an explicitly demo/non-tax invoice from its frozen DB snapshot."""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _line(pdf: canvas.Canvas, y: float, label: str, value: str) -> float:
    pdf.drawString(42, y, f"{label}: {value}"[:105])
    return y - 17


def render_invoice_pdf(snapshot: dict) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, invariant=1, pageCompression=1)
    pdf.setTitle(f"StockAware demo invoice {snapshot['invoice_number']}")
    width, height = A4
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(42, height - 48, "STOCKAWARE DEMO INVOICE")
    pdf.setFont("Helvetica", 9)
    y = height - 75
    y = _line(pdf, y, "Invoice", snapshot["invoice_number"])
    y = _line(pdf, y, "Issued UTC", snapshot["issued_at"])
    y = _line(pdf, y, "Seller", snapshot["seller"]["legal_name"])
    y = _line(pdf, y, "Seller address", snapshot["seller"]["billing_address"])
    y = _line(pdf, y, "Buyer", snapshot["buyer"]["legal_name"])
    y = _line(pdf, y, "Buyer address", snapshot["buyer"]["billing_address"])
    y = _line(pdf, y, "Payment reference", snapshot["provider_payment_id"])
    y -= 10
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(42, y, "Item")
    pdf.drawRightString(width - 170, y, "Qty")
    pdf.drawRightString(width - 105, y, "Taxable")
    pdf.drawRightString(width - 42, y, "Tax")
    y -= 18
    pdf.setFont("Helvetica", 9)
    for item in snapshot["items"]:
        if y < 90:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = height - 50
        pdf.drawString(42, y, f"{item['sku']} {item['name']}"[:53])
        pdf.drawRightString(width - 170, y, item["quantity"])
        pdf.drawRightString(width - 105, y, str(item["taxable_paise"]))
        pdf.drawRightString(width - 42, y, str(item["tax_paise"]))
        y -= 16
    y -= 12
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(42, y, "TOTAL")
    pdf.drawRightString(width - 42, y, f"INR {snapshot['total_paise']} paise")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42, 42, "DEMO ONLY - not a legally validated GST tax invoice")
    pdf.save()
    return output.getvalue()
