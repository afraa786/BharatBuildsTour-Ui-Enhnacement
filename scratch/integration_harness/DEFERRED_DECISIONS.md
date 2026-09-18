# Deferred Decisions Log

The following architectural and business decisions are intentionally DEFERRED and should not block the core Phase 2-6 backend implementation.

## 1. GST Legal Classification
- **Decision:** Whether to split IGST vs CGST/SGST based on state boundaries.
- **Affected Phase:** Phase 3 Pricing, Phase 5 Invoices.
- **Status:** Currently treating GST as a single flat bps rate per item.

## 2. Rehbar Transport Layer
- **Decision:** The exact mechanism (polling vs webhook vs websockets) for Rehbar to notify StockAware of Quote Acceptance/Approval.
- **Affected Phase:** Phase 3 Quotes.
- **Status:** We only accept an evidence payload synchronously via API for now.

## 3. Stock Deduction Trigger
- **Decision:** Whether stock is decremented immediately upon Quote Acceptance, Payment Link generation, or Webhook PAID.
- **Affected Phase:** Phase 4/6.
- **Status:** Currently deferred. We recheck stock adequacy at Payment generation.

## 4. Payment Outbox Delivery
- **Decision:** How the Payment Outbox messages actually reach the Invoice generator.
- **Affected Phase:** Phase 4/5 boundary.
- **Status:** Outbox is written to PostgreSQL. Worker implementation is deferred.
