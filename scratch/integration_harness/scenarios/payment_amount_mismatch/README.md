# Payment Amount Mismatch Journey

- **Starting state:** Payment intent created for 10030 paise.
- **Request/Event:** POST `/payments/webhook` with amount = 9000 paise.
- **Expected response:** 200 OK (to acknowledge Razorpay), but payment quarantined
- **State mutation allowed:** Logging/quarantining the event
- **State mutation forbidden:** Marking the payment as PAID or updating outbox
- **Expected error code:** N/A (Razorpay must see 200 to not retry)
- **Idempotency behavior:** Safe to replay webhook, remains quarantined
