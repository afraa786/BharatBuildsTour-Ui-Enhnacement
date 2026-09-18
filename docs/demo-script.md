# StockAware demo script

## Story

StockAware turns a WhatsApp RFQ into a safe, owner-controlled paid order. Use the
canonical scenarios in `fixtures/canonical-demo-data.json` and describe the
controls, not hidden AI reasoning. The older `fixtures/workflow-cases.json`
records are compatibility fixtures; see `docs/amir-data-reconciliation.md`.

1. **Buyer message** — Send: “Need 10 16 amp MCB. Please quote.” Explain that the `MCB16` alias converts informal buyer language into the catalog.
2. **Manager control room** — Open `RFQ-DEMO-001`. Show matched items, stock check, saved quote, and the audit timeline.
3. **Quote** — Present the buyer-friendly quote summary. The buyer sees the commercial quote, not inventory policy or margins.
4. **Acceptance and payment** — Mark the exact quote version accepted, then create one Razorpay link. Explain that buyer text alone never confirms payment.
5. **Verified payment and invoice** — Simulate the verified provider event. Show one invoice generated from the paid quote, then repeat the event to show no duplicate invoice.
6. **Owner intelligence** — Show the daily digest, the `SCN-LOW-STOCK-RFQ` alert for `MCB32`, and the `SCN-VENDOR-PRICE-REVISION` alert. Explain that the Manager surfaces action, not noise.
7. **Edge case** — Run `SCN-STOCK-SHORTAGE` or `SCN-UNSAFE-PRICING`. Show that the system asks for owner direction instead of silently making a risky sale.

## Sample admin commands

These are natural-language examples. Rehbar’s command parser should return the
actual action/result and preserve the actor and timestamp in the timeline.

```text
show RFQ-DEMO-001
show quote QT-DEMO-001
approve QT-DEMO-001 version 1
revise QT-DEMO-001: change the requested quantity
send payment link for QT-DEMO-004 version 1
show pending payments
show low stock
show vendor updates
send follow-up for RFQ-DEMO-002
```

## Sample WhatsApp conversation

```text
Buyer: Need 10 16 amp MCB. Please quote.
StockAware: Thanks — I’m checking availability and preparing your quote.
StockAware: Quote QT-DEMO-001 is ready for 10 × 16A MCB. Total: ₹{{total}}. Valid until {{expiry_at}}. Reply ACCEPT to proceed or tell me what to change.
Buyer: ACCEPT
StockAware: Thanks. Here is your secure payment link for ₹{{total}}: {{payment_url}}. Please complete it by {{link_expiry}}.
StockAware: Payment confirmed. Your invoice {{invoice_number}} is ready: {{invoice_url}}
```

For the low-stock alternative, say: `We can supply 20 today. We also have {{substitute_name}} available. Would you like a revised quote?` Never substitute or charge a buyer without confirmation.
