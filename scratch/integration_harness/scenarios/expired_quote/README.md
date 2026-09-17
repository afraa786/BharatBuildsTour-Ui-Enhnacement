# Expired Quote Journey

- **Starting state:** Quote status = EXPIRED (or `expires_at` is in the past)
- **Request/Event:** POST `/payments/create-link`
- **Expected response:** `QUOTE_EXPIRED` rejection
- **State mutation allowed:** None
- **State mutation forbidden:** Creating payment link
- **Expected error code:** 409 Conflict (`QUOTE_EXPIRED`)
- **Idempotency behavior:** Same error on repeated requests
