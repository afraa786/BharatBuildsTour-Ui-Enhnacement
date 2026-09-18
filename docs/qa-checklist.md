# Quote-to-cash QA checklist

Use `fixtures/canonical-demo-data.json` as the Amir scenario source and record the
run ID, observed result, tester, and timestamp in the release checklist. The
older `fixtures/workflow-cases.json` cases remain compatibility examples; their
SKU/ID differences are documented in `docs/amir-data-reconciliation.md`.

| ID | Scenario | Expected outcome |
| --- | --- | --- |
| QA-01 | Valid RFQ (`SCN-NORMAL-RFQ-MCB16`) | Aliases resolve, stock is available, quote is sent, acceptance leads to one payment link, verified payment leads to one invoice. |
| QA-02 | Unknown SKU (`SCN-UNKNOWN-SKU`) | Return `NOT_FOUND`; ask a clarification question; never invent an SKU or price. |
| QA-03 | Ambiguous request/unit | Return `AMBIGUOUS` or clarification; do not quote a product where poles, pack, or unit are unclear. |
| QA-04 | Low stock (`SCN-LOW-STOCK-RFQ`) | Show available quantity, low-stock alert, and approved substitute; no silent substitution. |
| QA-05 | Unsafe price (`SCN-UNSAFE-PRICING`) | Quote requires approval with explicit reason codes; it cannot be paid before valid approval for the same version. |
| QA-06 | Duplicate WhatsApp intake (`SCN-DUPLICATE-RFQ`) | Same source message ID yields one run and an auditable duplicate/no-op result. |
| QA-07 | Duplicate approval | Replaying an approval does not alter quote version or create a second side effect. |
| QA-08 | Stale approval | Approval for an old quote version is rejected after a revision. |
| QA-09 | Quote expiry | Expired quote cannot create a payment link. |
| QA-10 | Payment pending | Pending payment sends an owner alert and a buyer reminder only while the link is valid. |
| QA-11 | Payment failed (`SCN-PAYMENT-FAILED`) | Status stays non-paid; no invoice is generated; fresh-link workflow requires buyer confirmation. |
| QA-12 | Invalid webhook | Bad Razorpay signature is rejected and does not advance payment state. |
| QA-13 | Amount/currency mismatch | Verified webhook with mismatched commercial data is quarantined/rejected; no invoice. |
| QA-14 | Duplicate webhook | Same provider event ID is idempotent; one paid state and one invoice trigger only. |
| QA-15 | Invoice before payment | Invoice generation rejects payment statuses other than verified paid. |
| QA-16 | Invoice idempotency | A repeated generation request returns the original invoice number/artifact. |
| QA-17 | Low-stock alert | Alert includes SKU, available amount, threshold, and affected active RFQs without exposing cost/margin. |
| QA-18 | Vendor price revision (`SCN-VENDOR-PRICE-REVISION`) | Owner sees effective date and affected products; open quotes are flagged for review. |

## Release gates

- [ ] No buyer-facing copy exposes cost, margin floor, approval reason internals, or another buyer’s data.
- [ ] Every payment and invoice mutation has a recorded idempotency key/event ID.
- [ ] All timestamps render in the business timezone while stored in UTC.
- [ ] Every outcome adds an auditable run/timeline event.
- [ ] QA-01 through QA-16 pass before a payment-enabled demo.
