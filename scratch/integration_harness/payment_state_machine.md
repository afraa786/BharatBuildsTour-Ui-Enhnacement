# StockAware Payment State Machine

The payment state machine represents the intent to pay for an ACCEPTED quote version.

## Allowed Transitions

- `CREATED` → `PENDING`: Triggered when the Razorpay payment link is successfully created.
- `CREATED` → `FAILED`: Triggered if the Razorpay link creation API call fails. (Terminal for this intent).

- `PENDING` → `PAID`: Triggered by a verified Razorpay `payment_link.paid` webhook for the full exact amount.
- `PENDING` → `EXPIRED`: Triggered when the payment link reaches its expiry time without payment.
- `PENDING` → `CANCELLED`: Triggered if the payment link is explicitly cancelled by a business operator.

### Exceptional Late Payment
- `EXPIRED` or `CANCELLED` → `PAID` (with `reconciliation_hold = true`): Triggered if a buyer manages to pay after the link was considered expired or cancelled. This blocks automatic invoice issuance until a business owner resolves it.

## Forbidden Transitions

- `PAID` → `FAILED`: A paid payment cannot regress to failed in this MVP.
- `PAID` → `EXPIRED`: Once paid, it does not expire.
- `PAID` → `CANCELLED`: Once paid, it cannot be cancelled (refunds are out of scope for MVP).
- `CREATED` / `PENDING` → `PAID`: Using any mechanism other than a verified Razorpay webhook (e.g., browser redirect, buyer WhatsApp message) is strictly forbidden.
- `PENDING` → `PAID`: If the webhook event is `payment.authorized` only (must be fully captured/paid).
- `PENDING` → `PAID`: If the webhook amount is a partial payment.
