# StockAware Integration Guide

## For Fareed Backend
Run the full acceptance suite locally using:
`python scratch/integration_harness/release_smoke.py`

## For Rehbar
The exact stable IDs and expected handoffs are governed by `simulators/rehbar.py`.
Production Rehbar transport is currently DEFERRED. Use the adapter `NOT_IMPLEMENTED_TRANSPORT`.

## For Yunus
Sanitized fixtures suitable for frontend development are located in `scratch/integration_harness/frontend/`. They have been validated for leakage.

## For QA
Run offline and HTTP journeys via:
`python scratch/integration_harness/run_journey.py --offline --http`

HTTP acceptance is opt-in and strict. It requires
`STOCKAWARE_HTTP_ACCEPTANCE=1`, an explicit base URL, synthetic internal and
webhook test secrets, the demo business/buyer IDs, and a disposable PostgreSQL
database. Missing configuration is reported as `SKIP / CONFIG_NOT_AVAILABLE`;
401, 403, 404, 422, 500, and 503 responses are never accepted as a successful
happy-path result.

For the full downstream test journey, launch
`http_acceptance_server:app` from this directory on the Python path. That
harness-owned ASGI target uses a fake provider which creates one link, loses
the first response, and supports recovery by the stable reference. Set
`STOCKAWARE_TEST_FIXTURE_INJECTION=1` to use the established PostgreSQL helper
for approval and acceptance. The runner labels this
`TEST_FIXTURE_STATE_INJECTION`; it never represents real Rehbar transport.

## Security
The `X-Internal-Service-Token` and `webhook_secret` are strictly for backend service-to-service and provider-to-backend communication. They must NEVER reach the frontend.

## Deferred
- Real buyer auth
- Exact production Rehbar transport
- Production outbox transport
- Live Razorpay
- GST legal requirements
- Stock deduction trigger
- Production artifact hosting
