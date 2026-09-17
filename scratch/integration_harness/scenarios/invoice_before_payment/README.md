# Invoice Before Payment Journey

- **Starting state:** Payment intent is CREATED (or PENDING), not PAID.
- **Request/Event:** POST `/invoice/generate`
- **Expected response:** `PAYMENT_NOT_PAID` rejection
- **State mutation allowed:** None
- **State mutation forbidden:** Allocating invoice number, creating invoice row
- **Expected error code:** 409 Conflict (`PAYMENT_NOT_PAID`)
- **Idempotency behavior:** Same error on repeated requests
