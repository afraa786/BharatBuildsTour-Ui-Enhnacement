# Stale Quote Version Journey

- **Starting state:** Quote v2 exists and is current.
- **Request/Event:** POST `/payments/create-link` requesting quote v1.
- **Expected response:** `QUOTE_VERSION_MISMATCH` rejection
- **State mutation allowed:** None
- **State mutation forbidden:** Creating payment link, marking v1 as paid
- **Expected error code:** 409 Conflict (`QUOTE_VERSION_MISMATCH`)
- **Idempotency behavior:** Same error on repeated requests
