# Ambiguous Product Journey

- **Starting state:** RFQ requested for "ambiguous switch"
- **Request/Event:** POST `/catalog/match`
- **Expected response:** `AMBIGUOUS` with candidates, `selected_product_id` = null
- **State mutation allowed:** None (read-only)
- **State mutation forbidden:** Database writes, stock reservation
- **Expected error code:** N/A (200 OK with AMBIGUOUS status)
- **Idempotency behavior:** Deterministic read, safely repeatable
