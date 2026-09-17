# Approval Required Journey

- **Starting state:** Quote generated with discount > max_discount_bps. Status = DRAFT.
- **Request/Event:** POST `/payments/create-link`
- **Expected response:** `APPROVAL_REQUIRED` rejection
- **State mutation allowed:** None
- **State mutation forbidden:** Creating a payment link, transitioning quote status
- **Expected error code:** 409 Conflict (`APPROVAL_REQUIRED`)
- **Idempotency behavior:** Same error on repeated requests
