from datetime import datetime
from hashlib import sha256
from html import escape
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class InvoiceDraft(BaseModel):
    invoice_number: str
    run_id: str
    buyer_name: str
    total_paise: int = Field(gt=0)
    currency: str = "INR"
    issued_at: datetime
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    payment_reference: str


class InvoiceArtifact(BaseModel):
    artifact_key: str
    artifact_sha256: str


def next_invoice_number(now: datetime, sequence_value: int) -> str:
    if sequence_value <= 0:
        raise ValueError("invoice sequence must be positive")
    return f"INV-{now.year}-{sequence_value:06d}"


def _rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def _render_invoice_html(draft: InvoiceDraft) -> str:
    rows = []
    for index, item in enumerate(draft.line_items, start=1):
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(str(item.get('name', 'Item')))}</td>"
            f"<td>{escape(str(item.get('quantity', '')))}</td>"
            f"<td>{escape(str(item.get('unit', '')))}</td>"
            f"<td>{_rupees(int(item.get('unit_price_paise', 0)))}</td>"
            f"<td>{_rupees(int(item.get('tax_paise', 0)))}</td>"
            f"<td>{_rupees(int(item.get('line_total_paise', 0)))}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Invoice {escape(draft.invoice_number)}</title>
  <style>
    body {{ font-family: Inter, Arial, sans-serif; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    .total {{ font-size: 20px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>Tax Invoice</h1>
  <p><strong>Invoice:</strong> {escape(draft.invoice_number)}</p>
  <p><strong>Run:</strong> {escape(draft.run_id)}</p>
  <p><strong>Buyer:</strong> {escape(draft.buyer_name)}</p>
  <p><strong>Issued:</strong> {escape(draft.issued_at.isoformat())}</p>
  <p><strong>Payment Ref:</strong> {escape(draft.payment_reference)}</p>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Item</th><th>Qty</th><th>Unit</th>
        <th>Unit Price</th><th>Tax</th><th>Total</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p class="total">Grand Total: {_rupees(draft.total_paise)}</p>
</body>
</html>
"""


def generate_invoice_artifact(draft: InvoiceDraft, artifact_root: Path) -> InvoiceArtifact:
    html = _render_invoice_html(draft)
    artifact_key = f"invoices/{draft.run_id}/{draft.invoice_number}.html"
    path = artifact_root / artifact_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return InvoiceArtifact(
        artifact_key=artifact_key,
        artifact_sha256=sha256(html.encode("utf-8")).hexdigest(),
    )


def _pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_invoice_pdf(draft: InvoiceDraft) -> bytes:
    lines = [
        "Tax Invoice",
        f"Invoice: {draft.invoice_number}",
        f"Run: {draft.run_id}",
        f"Buyer: {draft.buyer_name}",
        f"Issued: {draft.issued_at.isoformat()}",
        f"Payment Ref: {draft.payment_reference}",
        "",
    ]
    for index, item in enumerate(draft.line_items, start=1):
        lines.append(
            f"{index}. {item.get('name', 'Item')} | Qty {item.get('quantity', '')} "
            f"{item.get('unit', '')} | Total {_rupees(int(item.get('line_total_paise', 0)))}"
        )
    lines.append("")
    lines.append(f"Grand Total: {_rupees(draft.total_paise)}")

    content_lines = ["BT", "/F1 12 Tf", "50 780 Td", "16 TL"]
    for line in lines:
        content_lines.append(f"({_pdf_text(line)}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def generate_invoice_pdf_artifact(draft: InvoiceDraft, artifact_root: Path) -> InvoiceArtifact:
    pdf = _render_invoice_pdf(draft)
    artifact_key = f"invoices/{draft.run_id}/{draft.invoice_number}.pdf"
    path = artifact_root / artifact_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf)
    return InvoiceArtifact(
        artifact_key=artifact_key,
        artifact_sha256=sha256(pdf).hexdigest(),
    )
