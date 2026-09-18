# Manager updates, alerts, and reminders

These are customer-safe and owner-facing copy templates. Replace `{{placeholders}}`
from saved records; do not disclose cost price, margin, approval reasoning, or other
customer data in buyer messages.

## Daily owner update

```text
Good morning, {{owner_name}} — {{business_name}} update for {{date}}.

• {{approval_count}} quote(s) need approval: {{approval_refs}}
• {{expiry_count}} quote(s) expire today: {{expiry_refs}}
• {{payment_pending_count}} payment(s) pending: {{payment_refs}}
• {{low_stock_count}} low-stock item(s): {{low_stock_refs}}
• Vendor updates: {{vendor_update_summary}}
• Today’s follow-ups: {{follow_up_summary}}

Reply “show {{reference}}” for details or “approve {{quote_id}}” only after reviewing the quote version.
```

If every count is zero: `All clear for {{date}} — no approvals, expiring quotes, or payment follow-ups need attention.`

## Important admin alerts

| Event | Owner alert |
| --- | --- |
| Quote needs approval | `Approval needed: {{quote_id}} v{{version}} for {{buyer_name}}, total {{total}}. Reason: {{reason_summary}}. Expires {{expiry_at}}.` |
| Quote expires today | `Quote {{quote_id}} for {{buyer_name}} expires today at {{expiry_at}}. {{next_action}}` |
| Low stock | `Low stock: {{sku}} — {{available_quantity}} {{unit}} available (threshold {{reorder_threshold}}). {{open_rfq_count}} active RFQ(s) may be affected.` |
| Payment pending | `Payment pending: {{payment_id}} for {{buyer_name}}, {{amount}}, linked to {{quote_id}}. Link expires {{link_expiry}}.` |
| Payment failure | `Payment failed: {{payment_id}} for {{buyer_name}}. No payment has been confirmed. Offer a fresh link only after buyer confirmation.` |
| Payment confirmed | `Payment confirmed: {{payment_id}} for {{buyer_name}}, {{amount}}. Generate or send invoice {{invoice_reference}}.` |
| Vendor price revision | `Vendor update: {{vendor_name}} revised prices for {{affected_products}}, effective {{effective_date}}. Review open quotes before sending.` |
| Vendor shortage | `Vendor shortage: {{vendor_name}} reports {{affected_products}} delayed until {{expected_date}}. Check impacted RFQs and alternatives.` |
| Callback/meeting | `Reminder: {{subject}} with {{contact_name}} at {{time}}. Context: {{context}}.` |

## Buyer reminder templates

```text
Quote follow-up
Hi {{buyer_name}}, sharing a quick reminder that quote {{quote_id}} for {{summary}} is valid until {{expiry_at}}. Reply here if you’d like any changes.

Payment follow-up
Hi {{buyer_name}}, payment for quote {{quote_id}} ({{amount}}) is still pending. You can use the secure link: {{payment_url}}. It expires {{link_expiry}}. Please let us know if you need a new link.

Payment retry
Hi {{buyer_name}}, the payment for quote {{quote_id}} was not completed. If you still want to proceed, reply “send link” and we’ll issue a fresh secure payment link.
```

Do not send a payment reminder after `PAID`, `CANCELLED`, or an expired/invalid link. Rate-limit automated buyer follow-ups and allow an owner to pause them.

## Vendor escalation

```text
{{vendor_name}} update requires review: {{event_summary}}. Affected SKUs: {{affected_skus}}. Impacted customer commitments: {{impact_summary}}. Recommended next step: {{recommended_action}}.
```

## Suggested event payload

The Manager can render the templates from this timeline-compatible shape:

```json
{
  "event_id": "EVT-001",
  "event_type": "LOW_STOCK",
  "occurred_at": "2026-09-18T10:00:00Z",
  "run_id": "RFQ-DEMO-002",
  "entity_type": "product",
  "entity_id": "MCB32",
  "severity": "HIGH",
  "audience": "OWNER",
  "data": {"available_quantity": 8, "unit": "each", "reorder_threshold": 10}
}
```

For canonical demo values, use `fixtures/canonical-demo-data.json`. The payload
above represents `SCN-LOW-STOCK-RFQ`; `run_id` carries the canonical RFQ reference
because the canonical fixture does not define a separate run ID. This is an
example shape only, not a live alert engine.
