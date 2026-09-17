# Invoice PDF Retry Journey

- **Starting state:** Invoice exists in `PENDING_ARTIFACT` status (PDF generation crashed previously).
- **Request/Event:** POST `/invoice/generate` (retry attempt)
- **Expected response:** Re-generates PDF, updates state to `GENERATED`
- **State mutation allowed:** Writing artifact metadata to DB, state to `GENERATED`
- **State mutation forbidden:** Allocating a NEW invoice number or creating a duplicate invoice row
- **Expected error code:** N/A (Success)
- **Idempotency behavior:** Must re-use the exact same `invoice_id` and `invoice_number`
