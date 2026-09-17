# Duplicate Webhook Journey

- **Starting state:** Webhook previously received, payment is PAID.
- **Request/Event:** POST `/payments/webhook` with identical payload (Razorpay at-least-once delivery).
- **Expected response:** 200 OK with `{"duplicate": true}`
- **State mutation allowed:** None (already paid)
- **State mutation forbidden:** Creating duplicate outbox events, duplicate state updates
- **Expected error code:** N/A
- **Idempotency behavior:** Catches `UniqueViolation` on event insert, checks payload hash, returns idempotent success.
