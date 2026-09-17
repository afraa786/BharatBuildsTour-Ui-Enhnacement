# StockAware Integration Simulator and API Fixture Suite

> [!WARNING]
> **THIS DIRECTORY IS NOT PRODUCTION IMPLEMENTATION.**
> This is an integration simulator and contract fixture suite. It does not connect to the database or modify the production Phase 1 schema.

## Purpose
This harness models the complete expected commercial journey for StockAware (Phases 2-6) derived explicitly from `docs/contracts.md`. It provides deterministic golden vectors and API fixtures for use by all integrating parties (Fareed, Rehbar, Yunus, QA, and Codex) so they can develop independently against stable examples before full E2E connectivity is established.

## Directory Layout
- `fixtures/`: Deterministic JSON representations of all entities and API payloads (Catalog, Inventory, Pricing vectors, Quotes, Rehbar evidence, Payments, Razorpay Webhooks, Invoices).
- `scenarios/`: Step-by-step sequential workflows representing both the Happy Path and various Failure Journeys.
- `payment_state_machine.md`: Documentation on payment transitions.
- `validator.py`: Script to ensure all fixtures maintain referential integrity.
- `tests/`: Offline pytest suite covering logic invariants (e.g. margin/discount calculations, HMAC verification).

## How to use the Fixtures

### Fareed Backend
- Use the request/response payloads in `fixtures/` as exact structural expectations for API routes.
- Use `fixtures/pricing/golden_vectors.json` as unit test inputs for the pricing calculator (ensure `ROUND_HALF_UP` is used).
- Use `fixtures/webhooks/*.raw.json` to unit test webhook HMAC verification (these must be read as raw bytes).

### Rehbar Orchestration
- Use `fixtures/rehbar_evidence.json` to see exactly what Fareed requires for quote approval and acceptance.
- Use the `run_id` mapping to understand how state flows back.
- Review `scenarios/` to understand exactly how Fareed handles edge cases (e.g. duplicate requests, stale versions).

### Yunus Frontend
- Use the mock JSON responses in `scenarios/happy_path/` and `fixtures/` to build UI states without needing a running Fareed backend.
- Understand the error shapes returned when quotes expire or require approval.

### QA
- Use `scenarios/happy_path/` as the blueprint for the primary E2E automation script.
- Execute `pytest tests/` to verify local fixture rules.
- Review the `scenarios/*` failure directories for negative test cases.

## How to Run Validation and Tests
The harness contains its own isolated test suite. Do not run this using the production `pytest` command.

1. **Tests:**
   ```bash
   cd scratch/integration_harness
   pytest tests/
   ```

2. **Validator:**
   ```bash
   cd scratch/integration_harness
   python validator.py
   ```

## Authoritative vs Illustrative
- **Authoritative**: `docs/contracts.md` remains the sole source of truth. The schemas, error shapes, pricing math, and state machines here exactly mirror it.
- **Illustrative**: The precise values of UUIDs, product names, prices, and timestamp strings.

## Deferred Contract Items
The following items are deferred in `contracts.md` and are modeled as `"DEFERRED"` or intentionally mocked here. Do NOT rely on these as final production behaviors:
- Rehbar approval/acceptance transport (HTTP push vs. queue vs. inline).
- PaymentOutbox delivery mechanism.
- Exact numeric live pricing thresholds for products.
- Exact low-stock thresholds.
- CGST/SGST vs IGST specific classification logic.
- Multi-Razorpay-account routing setup.
- Database trigger mechanisms for stock deduction.
