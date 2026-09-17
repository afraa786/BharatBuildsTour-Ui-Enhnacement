# Insufficient Stock Journey

- **Starting state:** Product stock = 2. Buyer requests 5.
- **Request/Event:** POST `/inventory/check`
- **Expected response:** `INSUFFICIENT_STOCK` with ranked substitute suggestions
- **State mutation allowed:** None (read-only)
- **State mutation forbidden:** Stock deduction, creating a quote, reserving items
- **Expected error code:** N/A (200 OK with INSUFFICIENT_STOCK status)
- **Idempotency behavior:** Safely repeatable, read-only
