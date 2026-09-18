# WhatsApp Commerce Codebase Audit

Audit date: 2026-09-18. Scope was source, migrations, fixtures and tests only. No database was queried and no secrets were read. Labels: **Confirmed** is source/test evidence; **Missing** is absent from the inspected implementation; **Unknown** requires a live, authorized environment check.

## 1. Executive Summary

**Confirmed:** This is a FastAPI/PostgreSQL/SQLAlchemy backend with a React/Next # WhatsApp Commerce Codebase Audit

Audit date: 2026-09-18. Scope was source, migrations, fixtures and tests only. No database was queried and no secrets were read. Labels: **Confirmed** is source/test evidence; **Missing** is absent from the inspected implementation; **Unknown** requires a live, authorized environment check.

## 1. Executive Summary

**Confirmed:** This is a FastAPI/PostgreSQL/SQLAlchemy backend with a React/Next client, LangGraph/LangChain/OpenAI conversational components, Meta Cloud API transport, and a separate, substantially more complete commercial quote/payment/invoice domain. The inbound WhatsApp path currently drives an older RFQ `Run` workflow that uses hard-coded `mock_desks` for matching/stock/pricing; it does **not** call the real catalog, inventory, pricing, payment, or invoice services.

The most important conclusion is that Number B cannot safely be assigned a different customer-commerce experience today: receiving-number credentials exist, but no receiving-number-to-business/experience mapping exists and the actor router is based on the sender's WA ID. The reliable payment stack is reusable, but it is not connected to the WhatsApp RFQ stack.

## 2. Repository / Stack Overview

Backend: Python, FastAPI, SQLAlchemy/PostgreSQL, Alembic, Pydantic, httpx. AI: LangGraph, LangChain OpenAI (`gpt-4o-mini` in the Manager) and OpenAI Whisper/TTS. Frontend: `client/` Next/React; operational bot test apps: `bot-biz/`, `bot-test/`. Infrastructure: Docker Compose and Terraform for ECS/RDS/ALB/ECR/logs/secrets. Evidence: `server/pyproject.toml`, `compose.yaml`, `infra/terraform/*.tf`, `server/app/main.py:1-35`, `server/app/modules/runs/manager_graph.py:15-57`.

## 3. Current Git State

At audit start: branch `main`; HEAD `748e812e17d48f9ff1ebb1e75b9db09664c82234`; `git status --short` emitted no entries. This audit adds this documentation file only.

## 4. Existing WhatsApp Architecture

Meta verification is `GET /webhook/whatsapp`; it accepts either configured verify token. `POST /webhook/whatsapp` parses JSON and calls `handle_webhook_payload` without an inbound Meta signature verification step. `WhatsAppMessage` persists inbound/outbound raw-normalized payloads and de-duplicates only inbound provider message IDs. Evidence: `server/app/modules/whatsapp/router.py:12-30`, `server/app/core/config.py:31-80`, `server/app/modules/whatsapp/models.py:11-30`, `server/app/modules/whatsapp/service.py:109-153`.

## 5. `whatsapp_test` Investigation

**Confirmed:** `whatsapp_test` is an environment configuration slot, not a module, route, tenant, database record, or workflow. It consists of `whatsapp_test_phone_number_id`, access token and verify token, then becomes one entry in `whatsapp_number_credentials`. Both slots use the same `/webhook/whatsapp` route. Evidence: `server/app/core/config.py:31-36,63-80`; repository search found no model/table/route named `whatsapp_test`.

**Unknown:** Which real number it represents, its Meta WABA association, and whether it is presently configured; those values were deliberately not read.

## 6. Two-Number Routing Analysis

**Partial transport support:** inbound normalization captures `metadata.phone_number_id`; mark-read, download/upload and send select credentials by that ID and replies use the inbound ID. Evidence: `server/app/modules/whatsapp/service.py:109-128,203-218,252-289`; `server/app/modules/whatsapp/client.py:65-118`.

**P0 blocker:** there is no configuration/model resolving `phone_number_id -> business_id -> interface/agent`, nor WABA ID routing. `route_message` receives a sender `wa_id` and classifies ADMIN/VENDOR/BUYER; it never receives the receiving number. Thus Number B currently reaches the same admin/vendor/buyer branching as Number A. Exact extension point: after inbound idempotency and before `route_message` in `handle_webhook_payload` (`service.py:220-249`), introduce a DB-backed receiving-number binding and dispatch to a commerce orchestrator only for `experience=customer_commerce`.

## 7. Rehbar Tenant/Data Mapping

**Confirmed:** “Rehbar” is present as owner-demo seed material (`OWNER_NAME = "Rehbar Khan"`) and as an integration-harness simulator/fixtures; it is not a tenant type or WhatsApp binding in application models. Businesses, users and buyers are tenant-scoped (`Business`, `User.business_id`, `Buyer.business_id`). Evidence: `server/app/seed.py:314-426`, `server/app/modules/identity/models.py:16-70`, `server/app/modules/identity/owner_models.py:12-45`, `scratch/integration_harness/simulators/rehbar.py`.

**Unknown live map:** business UUID, catalog/product/inventory/customer/order/payment counts, and phone linkage cannot be established from source without a safe authorized DB query. Do not hardcode the UUID. Required architecture: a `whatsapp_number_bindings` record keyed by provider/phone_number_id with `business_id`, `experience`, enabled state, and optional WABA ID; bind the development Number B to the Rehbar business through data/config, not code.

## 8. Incoming Message Call Chain

`Meta POST -> whatsapp.router.receive_webhook -> request.json -> whatsapp.service.handle_webhook_payload -> _extract_inbound_messages -> _log_message/unique provider_message_id -> commit -> mark_read_with_typing -> optional audio download/transcribe -> route_message -> process_admin_message | process_vendor_message | process_buyer_message -> commit`.

Inputs/outputs/persistence: metadata provides `phone_number_id`; sender maps only to `wa_id`/profile name; `WhatsAppMessage` stores normalized payload; audio transcript is only an in-memory mutation and is not re-persisted. Duplicate inbound message IDs return early. Exceptions from Meta/AI are mostly swallowed only within audio/agent helpers; the top-level webhook has no explicit error/retry envelope. Evidence: `server/app/modules/whatsapp/router.py:20-29`, `service.py:35-153,184-250`, `audio.py:13-94`.

Status/delivery webhook handling is **Missing**: `_extract_inbound_messages` ignores Meta `statuses`, and no outbound Meta message ID is persisted (outbound ID is random local `out-UUID`).

## 9. Outgoing Message Call Chain

`Run/agent returns OutboundMessage -> handle_webhook_payload builds kwargs -> optional TTS/upload -> client.send_message -> Graph API /{phone_number_id}/messages -> local outbound log -> commit`. Send failures are only logged; they are neither retried nor persisted as failed delivery. Evidence: `server/app/modules/whatsapp/service.py:252-307`, `client.py:14-118`, `audio.py:47-94`.

## 10. Media / STT / TTS Capability Matrix

| Type | Status | Evidence / limitation |
|---|---|---|
| Text | SUPPORTED | extraction and send: `service.py:35-39`, `client.py:30-31` |
| Image/video/document inbound | PARTIAL | metadata/caption extracted, no image/video/document understanding/download except audio: `service.py:65-74,205-218` |
| Image/video/document outbound | SUPPORTED transport | IDs/links/captions supported, no product-media model: `client.py:32-49` |
| Audio/voice | PARTIAL | Meta download -> Whisper -> text; failures fall back; no duration/size validation: `audio.py:13-80` |
| TTS response | PARTIAL | keyword/request mode triggers OpenAI `tts-1`, uploads MP3; not commerce policy: `service.py:270-287`, `audio.py:82-94` |
| Location/contacts | PARTIAL | extraction and transport only: `service.py:90-105`, `client.py:50-61` |
| Interactive buttons/list replies | PARTIAL | replies parsed; generic outbound interactive payload supported, no commerce builder: `service.py:40-64`, `client.py:60-61` |
| Product/catalog/reactions/reply context | NOT IMPLEMENTED | no parser/sender/model evidence |
| Stickers | PARTIAL | inbound acknowledgement; client schema declares sticker but payload builder cannot produce it without id/link branch support evidence |

## 11. Existing Agent Architecture

**Confirmed:** deterministic intent routing precedes persona use. Buyer side chat uses a LangGraph history/reply graph; RFQ actions use deterministic `mock_desks`. Owner Manager uses LangGraph ReAct, `ChatOpenAI(gpt-4o-mini)`, history and six read-only tools. There are no confirmed finance/CRM/catalog/inventory/social-media agents—only named “desks” and mock implementations. Evidence: `server/app/modules/runs/service.py:120-345`, `sales_desk_graph.py:1-38`, `manager_graph.py:1-57`, `manager_tools.py:1-176`, `mock_desks.py`.

Clean extension: a new customer commerce graph/service selected by the receiving-number binding, with only scoped deterministic tools. Do not extend `mock_desks`.

## 12. Customer Identity & CRM

`Buyer` supports business-scoped display name, WhatsApp E.164, legal/billing fields, type/source/last_contacted. The WhatsApp pipeline does not look up or create Buyer records; runs store only `buyer_wa_id`, and lookup is globally by that WA ID. First/returning messages therefore do not resolve CRM identity; changed names and duplicates are unmanaged. Evidence: `identity/models.py:45-70`, `runs/models.py:18-52`, `runs/repository.py:16-37`.

## 13. Conversation Memory / State

**Partial:** last eight text-bearing `WhatsAppMessage` rows are loaded by `(wa_id, phone_number_id)` for chat personas. An open RFQ Run stores raw text, line items, quote snapshot and status. It cannot persist product cards shown, variant/colour/size, cart, address, comparison candidates, or active order. Run lookup lacks phone/business scope and has no locking/version predicate on update, creating cross-number and concurrent-turn risk. Evidence: `conversation_graph.py:23-68`, `runs/models.py:18-52`, `runs/repository.py:31-37`.

## 14. Catalog Architecture

Real catalog consists of tenant-scoped `Product`, `Category`, aliases and substitutes. Product supports SKU/name, units/pack size, costs/base price, GST, active/category—not descriptions, sale prices, arbitrary attributes/variants, colour/size, images or videos. Evidence: `catalog/models.py:20-90`; `identity/owner_models.py:29-45`.

## 15. Product Search Architecture

**Partial:** list by business and exact normalized SKU/name/alias match only. No fuzzy/full-text/vector/semantic search, category/price/stock filters or recommendation engine. “black shirt 1500” and fashion variants cannot be answered truthfully by this schema/query layer. Evidence: `catalog/repository.py:12-72`, `catalog/service.py:16-100`.

## 16. Inventory Architecture

Inventory is tenant/product on-hand quantity with version and immutable-key stock movements; read checks classify availability and substitutes. Payment link creation rechecks stock but does not reserve it. The signed payment webhook rechecks stock and sets `reconciliation_hold` if unavailable; it does not decrement inventory. Therefore two buyers can pay for the last unit. Evidence: `inventory/models.py:18-74`, `inventory/service.py:17-89`, `payments/service.py:51-66,396-420`.

## 17. Cart / Draft Order Architecture

**Missing:** no Cart, CartItem, draft order, address, fulfilment or Order model exists. Quote lineage/versioning is a B2B quote abstraction and cannot safely act as a customer cart without a designed bridge. Evidence: model inventory under `server/app/modules`; quote/payment FKs in `pricing/models.py`, `payments/models.py`.

## 18. Order State Machine

The only WhatsApp state machine is RFQ `Run`: RECEIVED -> NORMALIZING -> stock/price -> quote -> accepted -> mock payment pending -> payment confirmed -> invoice -> order confirmed. Its live WhatsApp path creates a mock payment link and has no integration that advances it from the real payment webhook. Evidence: `runs/state_machine.py:4-53`, `runs/service.py:270-343`.

## 19. Payment / Razorpay Architecture

**Confirmed reusable backend:** `payments.create_link` validates accepted/current quote, business scope, amount, stock, idempotency and provider response; Razorpay endpoint HMAC-verifies raw body, validates account/link/payment/currency/amount/captured status, deduplicates event IDs, stores events and sets PAID/reconciliation hold. Evidence: `payments/service.py:69-265,277-420`; `payments/routes.py:16-40`; tests `test_phase4_postgres.py`, `test_phase5_concurrency.py`, `test_phase6_concurrency.py`.

Buyer claim is not authoritative: it merely logs a claim and replies that provider verification is pending. Evidence: `runs/service.py:315-334`. However WhatsApp currently sends a `pay.stockaware.test` mock URL, not the real payment URL: `runs/service.py:174-178,270-288`.

## 20. Invoice Architecture

**Confirmed reusable backend:** invoice generation is payment/quote-bound, idempotent, locks/replays generated artifacts and renders/stores PDF. **Partial WhatsApp:** document transport can send a link/media ID, but no code connects generated invoice artifacts to an outbound WhatsApp document. Evidence: `invoices/service.py`, `invoices/models.py`, `invoices/storage.py`, `whatsapp/client.py:41-49`, tests `test_invoice_service.py`, `test_phase6_invoice_replay.py`.

## 21. Shipping / Tracking Architecture

**Missing:** no shipment, tracking, courier, delivery address, COD or fulfilment provider model/service found. `expected_delivery_date` on RFQ Run is not shipment tracking. Evidence: `runs/models.py:35-45` and repository-wide search.

## 22. Existing Agent Tool Inventory

| Tool | File | Schema/side effects | Commerce reuse |
|---|---|---|---|
| `get_run_status`, `why_run_blocked` | `runs/manager_tools.py:25-72` | `run_id`; read-only, unscoped by tenant/customer | No—also IDOR risk |
| `get_inventory`, `get_low_stock_items` | `runs/manager_tools.py:75-105` | none; reads `mock_desks`, not DB | No |
| `get_pending_payments`, `get_open_quotes_today` | `runs/manager_tools.py:108-145` | none; reads global Runs | No |

No customer-facing catalog/inventory/cart/payment/order/invoice/tracking tool exists. Real REST/service equivalents: catalog list/match, inventory check, pricing quotes, payment create/get/webhook and invoice creation; each must be wrapped with resolved-business and current-customer authorization.

## 23. Tenant Isolation Analysis

Real commercial services generally require a `business_id` and repositories predicate on it. Composite foreign keys reinforce product/inventory/payment quote ownership. Evidence: `catalog/models.py:20-49`, `inventory/models.py:18-43`, `payments/service.py:69-75,326-329`.

**P0 gaps in WhatsApp/Runs:** no business resolution; `Run` creation omits business; `get_open_run_for_buyer`, `get_run_by_run_id`, `list_runs`, Manager tools and unauthenticated run endpoints are global. A sender may be classified as admin merely by membership in global config, independent of receiving number. Evidence: `runs/repository.py:16-49`, `whatsapp/service.py:220-249`, `runs/router.py:43-92`.

## 24. Security Findings

| Severity | Confirmed finding |
|---|---|
| P0 | WhatsApp POST has no Meta signature/authentication validation (`whatsapp/router.py:20-29`). |
| P0 | No number->tenant/experience binding; Runs and agent reads are globally addressable (`runs/repository.py:31-49`, `manager_tools.py`). |
| P0 | WhatsApp checkout is mock and disconnected from authoritative payment/inventory services (`runs/service.py:270-288`). |
| P0 | Stock is not reserved/decremented transactionally on paid fulfilment; paid shortage is only held (`payments/service.py:409-416`). |
| P1 | Outbound send failures log response body, potentially PII/provider content; no retry/outbox (`whatsapp/client.py:106-117`). |
| P1 | LLM history contains raw message payload text; no prompt-injection/tool authorization boundary for customer commerce exists. |
| P2 | Inbound media lacks explicit size/content validation and non-audio media is not safely processed. |
| P2 | No delivery/status persistence, response idempotency key or retry worker. |

## 25. Idempotency Analysis

Inbound WhatsApp duplicate message IDs are protected by a unique DB constraint, committed before processing. This avoids a normal duplicate webhook response, but rollback inside `_log_message` can roll back the session and sequential side effects lack an outbox. Payment and invoice operations have strong idempotency keys/event uniqueness. Quote/RFQ updates, outgoing sends, cart/order (absent), CRM creation (absent), and Meta status processing have no solution. Evidence: `whatsapp/models.py:13-19`, `whatsapp/service.py:131-153`; `payments/service.py:89-265,330-339`; `invoices/service.py`.

## 26. Failure Scenario Matrix

| Scenario | Status | Reason |
|---|---|---|
| Same WhatsApp message / Meta retry | PARTIAL | duplicate inbound ID suppressed; no authenticated Meta request/outbox |
| AI timeout | PARTIAL | persona fallback exists; run mutations may already be committed |
| STT failure | SAFE | falls back to acknowledgement/text (`audio.py`) |
| Out of stock at checkout | PARTIAL | checked before link and held after paid; no reservation |
| Payment succeeds/callback fails | PARTIAL | signed webhook retry/idempotency good; no fulfilment consumer shown |
| Razorpay webhook twice | SAFE | event ID+digest handled |
| Paid after stock unavailable | PARTIAL | PAID plus reconciliation hold, not automatic remedy |
| Invoice artifact fails | PARTIAL | retry-safe pending artifact; no async retry shown |
| WhatsApp send fails | UNSAFE | logged only; no retry/state |
| DB failure midway | PARTIAL | commercial transactions robust; WhatsApp processing spans commits/network |
| Other customer order request | UNSAFE | no customer order API; RFQ lookup/tools globally scoped |
| Malformed media | PARTIAL | API failures handled; validation missing |
| Resume days later | PARTIAL | persistent message/RFQ state, no commerce checkout expiration/resume model |

## 27. Existing Tests

WhatsApp: `server/tests/test_whatsapp_multimodal.py` checks extraction/payloads; `test_demo_workflow.py` covers a demo webhook duplicate. Audio: `test_audio.py`. Payments: `test_razorpay_service.py`, `test_razorpay_router.py`, Phase 4/5/6 PostgreSQL/concurrency/recovery tests. Invoice: `test_invoice_service.py`, `test_phase6_invoice_replay.py`. Catalog/inventory/security: Phase 1–3 tests and integration harness fixtures. Evidence: `server/tests/` inventory.

No test proves Meta signature validation, Number A/B routing isolation, resolved-business customer identity, real catalog media presentation, cart/variant checkout, customer-only order access, stock reservation/decrement, WhatsApp payment-link handoff, invoice send, shipment tracking, or outbound retry. No test suite was run because the requested audit must not change production state and PostgreSQL-backed tests may require mutable fixtures.

## 28. Database Relationship Map

```mermaid
erDiagram
  BUSINESS ||--o{ USER : owns
  BUSINESS ||--o{ BUYER : owns
  BUSINESS ||--o{ CATEGORY : owns
  BUSINESS ||--o{ PRODUCT : owns
  CATEGORY ||--o{ PRODUCT : groups
  PRODUCT ||--|| INVENTORY : has
  PRODUCT ||--o{ STOCK_MOVEMENT : records
  BUSINESS ||--o{ QUOTE : owns
  BUYER ||--o{ QUOTE : quoted_to
  QUOTE ||--o{ PAYMENT : funds
  PAYMENT ||--o{ PAYMENT_EVENT : receives
  PAYMENT ||--o| INVOICE : invoices
  RUN ||--o{ RUN_EVENT : timeline
  RUN ||--o{ APPROVAL : approvals
  WHATSAPP_MESSAGE : "independent log; wa_id/phone_number_id only"
```

Absent: WhatsApp configuration/binding, conversation entity, product variant/media, cart, order/order item, shipping/fulfilment/tracking. Real commercial Quote is not linked to the legacy WhatsApp Run by FK.

## 29. Reusable Components

Reuse Meta message normalization/sending/audio transport; `WhatsAppMessage` basic history/idempotency; tenant-scoped Product/Inventory and substitutions; deterministic pricing/quote services; Razorpay link/webhook/reconciliation; invoice generation/artifact storage; commercial idempotency constructs. Reuse only after tenant binding and customer authorization are introduced.

## 30. Missing Components

Receiving-number binding/router; Meta signed POST verification and status handler; CRM resolution/upsert; product attributes/variants/media/search; commerce conversation state/cart; customer order/address/fulfilment; atomic reservation/paid allocation and outbox consumers; commerce tools; WhatsApp product card/media response layer; delivery retries/observability; shipping/COD.

## 31. Proposed WhatsApp Commerce Architecture

`Meta webhook -> signature verify + normalize -> immutable inbound event -> phone_number_binding resolves business+experience -> customer resolver (business, wa_id) -> CommerceConversation -> CommerceOrchestrator -> scoped deterministic services -> transactional outbox -> WhatsApp sender/status reconciler`.

Number A binds to `owner_manager`; Number B binds to `customer_commerce`; both retain common transport only. The LLM may interpret Hinglish and choose tools, but tool input is server-bound to the resolved business/customer and tool output is the only source of product/price/stock/order/payment facts.

## 32. Proposed Commerce Tool Surface

| Tool capability | Disposition |
|---|---|
| exact product/list and inventory check | Wrap existing, then extend search/filter schema |
| quote/pricing | Wrap/extend existing pricing service |
| customer get/upsert | Extend Buyer/CRM service |
| cart, variants, address, order | New required |
| payment link/status | Wrap existing payment service; never accept chat claim |
| invoice | Wrap existing invoice service; add sender adapter |
| product media and shipment | New required |

## 33. Proposed Conversation State Model

DB: `CommerceConversation` (business/customer/phone binding, optimistic version, current intent, referenced product/variant IDs, active cart/order) and Cart/Order facts. Conversation metadata may retain last shown product-card IDs, comparison candidates and pending question. Product/price/stock are always dynamically re-read. Payment/invoice states stay in their authoritative tables. Suggested transitions: discovery -> exploration -> selection -> variant/quantity -> cart -> address -> payment pending -> verified/held -> confirmed -> fulfilment/post-purchase. Ensure every mutation has idempotency key and version/row lock.

## 34. File-by-File Implementation Plan

Modify `whatsapp/router.py` (raw-body Meta auth), `whatsapp/service.py` (binding dispatch/outbox), `whatsapp/models.py` (events/statuses or dedicated tables), `runs/*` only to isolate legacy owner flow; add `modules/commerce/{models,service,router,tools,orchestrator}.py`, `modules/whatsapp/bindings.py`, and media/search modules. Wrap—not duplicate—`catalog`, `inventory`, `pricing`, `payments`, `invoices`. Add a worker/outbox dispatcher and migration(s). Do not retrofit generic commerce into `mock_desks`.

## 35. Migration Requirements

Required before a purchasable MVP: phone bindings, customer uniqueness/index by `(business_id, whatsapp_e164)`, commerce conversation/version, product variants/attributes/media, cart/cart items, address/order/order items, stock reservations/allocation/outbox, and shipment fields only if a provider is selected. Data migration/configuration should create the Number-B-to-Rehbar binding; it must not embed Rehbar UUID in source.

## 36. Required Tests

Meta valid/invalid signature and replay; Number A/B isolation; tenant escape/IDOR; first/returning customer resolution; Hinglish discovery mapped to real catalog; product fact/media correctness; variants/quantity bounds; cart/order concurrency; stock reservation and paid shortage reconciliation; real Razorpay link and signed duplicate webhook; chat claim cannot mark paid; invoice artifact/send replay; outbound failure/retry/status; malformed media/STT fallback; conversation resume/race; authorization of customer order lookup.

## 37. Risks / Blockers

P0 blockers are exactly the four P0 findings in section 24. Live Rehbar mapping and actual WhatsApp/Meta configuration remain Unknown until an authorized read-only environment inspection.

## 38. Recommended Implementation Sequence

1. **Routing isolation/security:** bindings, Meta signature/auth, statuses, tests; rollback by disabling Number-B binding.
2. **Read-only commerce discovery:** customer resolution plus scoped real catalog/inventory tools and product/media schema; no checkout mutations.
3. **State/cart/order foundation:** variants, durable state/cart/address, locking/idempotency and tests.
4. **Checkout/payment bridge:** turn accepted cart/order into existing quote/payment link; authoritative webhook-to-order allocation, reservations and reconciliation.
5. **Invoice/confirmation/reliable send:** outbox, document sending/status and retry.
6. **Fulfilment/tracking/COD:** only after provider/domain choice.
7. **Sales intelligence/hardening:** search/recommendations/upsell, observability and adversarial tests.

## Direct Answers

1. Today `whatsapp_test` is merely a credential slot; messages use the common webhook, sender-based actor router and legacy RFQ flow.
2. `route_message` plus `handle_webhook_payload` decide: `whatsapp/service.py:220-249`.
3. No; transport credentials differ but experiences are not routed by receiving number.
4. Bind Number B to a DB/config `business_id` record with `experience=customer_commerce`.
5. Not through the current agent; real catalog API exists but current WhatsApp uses mocks.
6. Transport can send images/media; real product media data is absent.
7. Partially: Whisper is implemented with graceful fallback, not reliability guarantees.
8. Partial message-history persistence exists; durable commerce state does not.
9. No usable cart/draft order exists.
10. No; no reservation/decrement allocation prevents oversell.
11. Yes, real Razorpay link creation exists, but current WhatsApp sends a mock link.
12. Raw-body signed Razorpay webhook validates account/link/payment/amount/currency/status and stores event.
13. Payment becomes PAID with `reconciliation_hold`; no allocation/refund flow exists.
14. PDF invoice generation exists; WhatsApp delivery linkage does not.
15. No real shipment/tracking implementation exists.
16. Scoped wrappers around catalog, inventory, pricing, payments and invoices.
17. Minimum MVP: P0 fixes, binding/customer resolver, read-only catalog tools, cart/order/reservation, payment bridge and outbox.
18. The four confirmed P0 blockers.
19. Section 36 is the required production-safety suite.
20. Implement receiving-number tenant/experience routing plus authenticated idempotent webhook processing first.
client, LangGraph/LangChain/OpenAI conversational components, Meta Cloud API transport, and a separate, substantially more complete commercial quote/payment/invoice domain. The inbound WhatsApp path currently drives an older RFQ `Run` workflow that uses hard-coded `mock_desks` for matching/stock/pricing; it does **not** call the real catalog, inventory, pricing, payment, or invoice services.

The most important conclusion is that Number B cannot safely be assigned a different customer-commerce experience today: receiving-number credentials exist, but no receiving-number-to-business/experience mapping exists and the actor router is based on the sender's WA ID. The reliable payment stack is reusable, but it is not connected to the WhatsApp RFQ stack.

## 2. Repository / Stack Overview

Backend: Python, FastAPI, SQLAlchemy/PostgreSQL, Alembic, Pydantic, httpx. AI: LangGraph, LangChain OpenAI (`gpt-4o-mini` in the Manager) and OpenAI Whisper/TTS. Frontend: `client/` Next/React; operational bot test apps: `bot-biz/`, `bot-test/`. Infrastructure: Docker Compose and Terraform for ECS/RDS/ALB/ECR/logs/secrets. Evidence: `server/pyproject.toml`, `compose.yaml`, `infra/terraform/*.tf`, `server/app/main.py:1-35`, `server/app/modules/runs/manager_graph.py:15-57`.

## 3. Current Git State

At audit start: branch `main`; HEAD `748e812e17d48f9ff1ebb1e75b9db09664c82234`; `git status --short` emitted no entries. This audit adds this documentation file only.

## 4. Existing WhatsApp Architecture

Meta verification is `GET /webhook/whatsapp`; it accepts either configured verify token. `POST /webhook/whatsapp` parses JSON and calls `handle_webhook_payload` without an inbound Meta signature verification step. `WhatsAppMessage` persists inbound/outbound raw-normalized payloads and de-duplicates only inbound provider message IDs. Evidence: `server/app/modules/whatsapp/router.py:12-30`, `server/app/core/config.py:31-80`, `server/app/modules/whatsapp/models.py:11-30`, `server/app/modules/whatsapp/service.py:109-153`.

## 5. `whatsapp_test` Investigation

**Confirmed:** `whatsapp_test` is an environment configuration slot, not a module, route, tenant, database record, or workflow. It consists of `whatsapp_test_phone_number_id`, access token and verify token, then becomes one entry in `whatsapp_number_credentials`. Both slots use the same `/webhook/whatsapp` route. Evidence: `server/app/core/config.py:31-36,63-80`; repository search found no model/table/route named `whatsapp_test`.

**Unknown:** Which real number it represents, its Meta WABA association, and whether it is presently configured; those values were deliberately not read.

## 6. Two-Number Routing Analysis

**Partial transport support:** inbound normalization captures `metadata.phone_number_id`; mark-read, download/upload and send select credentials by that ID and replies use the inbound ID. Evidence: `server/app/modules/whatsapp/service.py:109-128,203-218,252-289`; `server/app/modules/whatsapp/client.py:65-118`.

**P0 blocker:** there is no configuration/model resolving `phone_number_id -> business_id -> interface/agent`, nor WABA ID routing. `route_message` receives a sender `wa_id` and classifies ADMIN/VENDOR/BUYER; it never receives the receiving number. Thus Number B currently reaches the same admin/vendor/buyer branching as Number A. Exact extension point: after inbound idempotency and before `route_message` in `handle_webhook_payload` (`service.py:220-249`), introduce a DB-backed receiving-number binding and dispatch to a commerce orchestrator only for `experience=customer_commerce`.

## 7. Rehbar Tenant/Data Mapping

**Confirmed:** “Rehbar” is present as owner-demo seed material (`OWNER_NAME = "Rehbar Khan"`) and as an integration-harness simulator/fixtures; it is not a tenant type or WhatsApp binding in application models. Businesses, users and buyers are tenant-scoped (`Business`, `User.business_id`, `Buyer.business_id`). Evidence: `server/app/seed.py:314-426`, `server/app/modules/identity/models.py:16-70`, `server/app/modules/identity/owner_models.py:12-45`, `scratch/integration_harness/simulators/rehbar.py`.

**Unknown live map:** business UUID, catalog/product/inventory/customer/order/payment counts, and phone linkage cannot be established from source without a safe authorized DB query. Do not hardcode the UUID. Required architecture: a `whatsapp_number_bindings` record keyed by provider/phone_number_id with `business_id`, `experience`, enabled state, and optional WABA ID; bind the development Number B to the Rehbar business through data/config, not code.

## 8. Incoming Message Call Chain

`Meta POST -> whatsapp.router.receive_webhook -> request.json -> whatsapp.service.handle_webhook_payload -> _extract_inbound_messages -> _log_message/unique provider_message_id -> commit -> mark_read_with_typing -> optional audio download/transcribe -> route_message -> process_admin_message | process_vendor_message | process_buyer_message -> commit`.

Inputs/outputs/persistence: metadata provides `phone_number_id`; sender maps only to `wa_id`/profile name; `WhatsAppMessage` stores normalized payload; audio transcript is only an in-memory mutation and is not re-persisted. Duplicate inbound message IDs return early. Exceptions from Meta/AI are mostly swallowed only within audio/agent helpers; the top-level webhook has no explicit error/retry envelope. Evidence: `server/app/modules/whatsapp/router.py:20-29`, `service.py:35-153,184-250`, `audio.py:13-94`.

Status/delivery webhook handling is **Missing**: `_extract_inbound_messages` ignores Meta `statuses`, and no outbound Meta message ID is persisted (outbound ID is random local `out-UUID`).

## 9. Outgoing Message Call Chain

`Run/agent returns OutboundMessage -> handle_webhook_payload builds kwargs -> optional TTS/upload -> client.send_message -> Graph API /{phone_number_id}/messages -> local outbound log -> commit`. Send failures are only logged; they are neither retried nor persisted as failed delivery. Evidence: `server/app/modules/whatsapp/service.py:252-307`, `client.py:14-118`, `audio.py:47-94`.

## 10. Media / STT / TTS Capability Matrix

| Type | Status | Evidence / limitation |
|---|---|---|
| Text | SUPPORTED | extraction and send: `service.py:35-39`, `client.py:30-31` |
| Image/video/document inbound | PARTIAL | metadata/caption extracted, no image/video/document understanding/download except audio: `service.py:65-74,205-218` |
| Image/video/document outbound | SUPPORTED transport | IDs/links/captions supported, no product-media model: `client.py:32-49` |
| Audio/voice | PARTIAL | Meta download -> Whisper -> text; failures fall back; no duration/size validation: `audio.py:13-80` |
| TTS response | PARTIAL | keyword/request mode triggers OpenAI `tts-1`, uploads MP3; not commerce policy: `service.py:270-287`, `audio.py:82-94` |
| Location/contacts | PARTIAL | extraction and transport only: `service.py:90-105`, `client.py:50-61` |
| Interactive buttons/list replies | PARTIAL | replies parsed; generic outbound interactive payload supported, no commerce builder: `service.py:40-64`, `client.py:60-61` |
| Product/catalog/reactions/reply context | NOT IMPLEMENTED | no parser/sender/model evidence |
| Stickers | PARTIAL | inbound acknowledgement; client schema declares sticker but payload builder cannot produce it without id/link branch support evidence |

## 11. Existing Agent Architecture

**Confirmed:** deterministic intent routing precedes persona use. Buyer side chat uses a LangGraph history/reply graph; RFQ actions use deterministic `mock_desks`. Owner Manager uses LangGraph ReAct, `ChatOpenAI(gpt-4o-mini)`, history and six read-only tools. There are no confirmed finance/CRM/catalog/inventory/social-media agents—only named “desks” and mock implementations. Evidence: `server/app/modules/runs/service.py:120-345`, `sales_desk_graph.py:1-38`, `manager_graph.py:1-57`, `manager_tools.py:1-176`, `mock_desks.py`.

Clean extension: a new customer commerce graph/service selected by the receiving-number binding, with only scoped deterministic tools. Do not extend `mock_desks`.

## 12. Customer Identity & CRM

`Buyer` supports business-scoped display name, WhatsApp E.164, legal/billing fields, type/source/last_contacted. The WhatsApp pipeline does not look up or create Buyer records; runs store only `buyer_wa_id`, and lookup is globally by that WA ID. First/returning messages therefore do not resolve CRM identity; changed names and duplicates are unmanaged. Evidence: `identity/models.py:45-70`, `runs/models.py:18-52`, `runs/repository.py:16-37`.

## 13. Conversation Memory / State

**Partial:** last eight text-bearing `WhatsAppMessage` rows are loaded by `(wa_id, phone_number_id)` for chat personas. An open RFQ Run stores raw text, line items, quote snapshot and status. It cannot persist product cards shown, variant/colour/size, cart, address, comparison candidates, or active order. Run lookup lacks phone/business scope and has no locking/version predicate on update, creating cross-number and concurrent-turn risk. Evidence: `conversation_graph.py:23-68`, `runs/models.py:18-52`, `runs/repository.py:31-37`.

## 14. Catalog Architecture

Real catalog consists of tenant-scoped `Product`, `Category`, aliases and substitutes. Product supports SKU/name, units/pack size, costs/base price, GST, active/category—not descriptions, sale prices, arbitrary attributes/variants, colour/size, images or videos. Evidence: `catalog/models.py:20-90`; `identity/owner_models.py:29-45`.

## 15. Product Search Architecture

**Partial:** list by business and exact normalized SKU/name/alias match only. No fuzzy/full-text/vector/semantic search, category/price/stock filters or recommendation engine. “black shirt 1500” and fashion variants cannot be answered truthfully by this schema/query layer. Evidence: `catalog/repository.py:12-72`, `catalog/service.py:16-100`.

## 16. Inventory Architecture

Inventory is tenant/product on-hand quantity with version and immutable-key stock movements; read checks classify availability and substitutes. Payment link creation rechecks stock but does not reserve it. The signed payment webhook rechecks stock and sets `reconciliation_hold` if unavailable; it does not decrement inventory. Therefore two buyers can pay for the last unit. Evidence: `inventory/models.py:18-74`, `inventory/service.py:17-89`, `payments/service.py:51-66,396-420`.

## 17. Cart / Draft Order Architecture

**Missing:** no Cart, CartItem, draft order, address, fulfilment or Order model exists. Quote lineage/versioning is a B2B quote abstraction and cannot safely act as a customer cart without a designed bridge. Evidence: model inventory under `server/app/modules`; quote/payment FKs in `pricing/models.py`, `payments/models.py`.

## 18. Order State Machine

The only WhatsApp state machine is RFQ `Run`: RECEIVED -> NORMALIZING -> stock/price -> quote -> accepted -> mock payment pending -> payment confirmed -> invoice -> order confirmed. Its live WhatsApp path creates a mock payment link and has no integration that advances it from the real payment webhook. Evidence: `runs/state_machine.py:4-53`, `runs/service.py:270-343`.

## 19. Payment / Razorpay Architecture

**Confirmed reusable backend:** `payments.create_link` validates accepted/current quote, business scope, amount, stock, idempotency and provider response; Razorpay endpoint HMAC-verifies raw body, validates account/link/payment/currency/amount/captured status, deduplicates event IDs, stores events and sets PAID/reconciliation hold. Evidence: `payments/service.py:69-265,277-420`; `payments/routes.py:16-40`; tests `test_phase4_postgres.py`, `test_phase5_concurrency.py`, `test_phase6_concurrency.py`.

Buyer claim is not authoritative: it merely logs a claim and replies that provider verification is pending. Evidence: `runs/service.py:315-334`. However WhatsApp currently sends a `pay.stockaware.test` mock URL, not the real payment URL: `runs/service.py:174-178,270-288`.

## 20. Invoice Architecture

**Confirmed reusable backend:** invoice generation is payment/quote-bound, idempotent, locks/replays generated artifacts and renders/stores PDF. **Partial WhatsApp:** document transport can send a link/media ID, but no code connects generated invoice artifacts to an outbound WhatsApp document. Evidence: `invoices/service.py`, `invoices/models.py`, `invoices/storage.py`, `whatsapp/client.py:41-49`, tests `test_invoice_service.py`, `test_phase6_invoice_replay.py`.

## 21. Shipping / Tracking Architecture

**Missing:** no shipment, tracking, courier, delivery address, COD or fulfilment provider model/service found. `expected_delivery_date` on RFQ Run is not shipment tracking. Evidence: `runs/models.py:35-45` and repository-wide search.

## 22. Existing Agent Tool Inventory

| Tool | File | Schema/side effects | Commerce reuse |
|---|---|---|---|
| `get_run_status`, `why_run_blocked` | `runs/manager_tools.py:25-72` | `run_id`; read-only, unscoped by tenant/customer | No—also IDOR risk |
| `get_inventory`, `get_low_stock_items` | `runs/manager_tools.py:75-105` | none; reads `mock_desks`, not DB | No |
| `get_pending_payments`, `get_open_quotes_today` | `runs/manager_tools.py:108-145` | none; reads global Runs | No |

No customer-facing catalog/inventory/cart/payment/order/invoice/tracking tool exists. Real REST/service equivalents: catalog list/match, inventory check, pricing quotes, payment create/get/webhook and invoice creation; each must be wrapped with resolved-business and current-customer authorization.

## 23. Tenant Isolation Analysis

Real commercial services generally require a `business_id` and repositories predicate on it. Composite foreign keys reinforce product/inventory/payment quote ownership. Evidence: `catalog/models.py:20-49`, `inventory/models.py:18-43`, `payments/service.py:69-75,326-329`.

**P0 gaps in WhatsApp/Runs:** no business resolution; `Run` creation omits business; `get_open_run_for_buyer`, `get_run_by_run_id`, `list_runs`, Manager tools and unauthenticated run endpoints are global. A sender may be classified as admin merely by membership in global config, independent of receiving number. Evidence: `runs/repository.py:16-49`, `whatsapp/service.py:220-249`, `runs/router.py:43-92`.

## 24. Security Findings

| Severity | Confirmed finding |
|---|---|
| P0 | WhatsApp POST has no Meta signature/authentication validation (`whatsapp/router.py:20-29`). |
| P0 | No number->tenant/experience binding; Runs and agent reads are globally addressable (`runs/repository.py:31-49`, `manager_tools.py`). |
| P0 | WhatsApp checkout is mock and disconnected from authoritative payment/inventory services (`runs/service.py:270-288`). |
| P0 | Stock is not reserved/decremented transactionally on paid fulfilment; paid shortage is only held (`payments/service.py:409-416`). |
| P1 | Outbound send failures log response body, potentially PII/provider content; no retry/outbox (`whatsapp/client.py:106-117`). |
| P1 | LLM history contains raw message payload text; no prompt-injection/tool authorization boundary for customer commerce exists. |
| P2 | Inbound media lacks explicit size/content validation and non-audio media is not safely processed. |
| P2 | No delivery/status persistence, response idempotency key or retry worker. |

## 25. Idempotency Analysis

Inbound WhatsApp duplicate message IDs are protected by a unique DB constraint, committed before processing. This avoids a normal duplicate webhook response, but rollback inside `_log_message` can roll back the session and sequential side effects lack an outbox. Payment and invoice operations have strong idempotency keys/event uniqueness. Quote/RFQ updates, outgoing sends, cart/order (absent), CRM creation (absent), and Meta status processing have no solution. Evidence: `whatsapp/models.py:13-19`, `whatsapp/service.py:131-153`; `payments/service.py:89-265,330-339`; `invoices/service.py`.

## 26. Failure Scenario Matrix

| Scenario | Status | Reason |
|---|---|---|
| Same WhatsApp message / Meta retry | PARTIAL | duplicate inbound ID suppressed; no authenticated Meta request/outbox |
| AI timeout | PARTIAL | persona fallback exists; run mutations may already be committed |
| STT failure | SAFE | falls back to acknowledgement/text (`audio.py`) |
| Out of stock at checkout | PARTIAL | checked before link and held after paid; no reservation |
| Payment succeeds/callback fails | PARTIAL | signed webhook retry/idempotency good; no fulfilment consumer shown |
| Razorpay webhook twice | SAFE | event ID+digest handled |
| Paid after stock unavailable | PARTIAL | PAID plus reconciliation hold, not automatic remedy |
| Invoice artifact fails | PARTIAL | retry-safe pending artifact; no async retry shown |
| WhatsApp send fails | UNSAFE | logged only; no retry/state |
| DB failure midway | PARTIAL | commercial transactions robust; WhatsApp processing spans commits/network |
| Other customer order request | UNSAFE | no customer order API; RFQ lookup/tools globally scoped |
| Malformed media | PARTIAL | API failures handled; validation missing |
| Resume days later | PARTIAL | persistent message/RFQ state, no commerce checkout expiration/resume model |

## 27. Existing Tests

WhatsApp: `server/tests/test_whatsapp_multimodal.py` checks extraction/payloads; `test_demo_workflow.py` covers a demo webhook duplicate. Audio: `test_audio.py`. Payments: `test_razorpay_service.py`, `test_razorpay_router.py`, Phase 4/5/6 PostgreSQL/concurrency/recovery tests. Invoice: `test_invoice_service.py`, `test_phase6_invoice_replay.py`. Catalog/inventory/security: Phase 1–3 tests and integration harness fixtures. Evidence: `server/tests/` inventory.

No test proves Meta signature validation, Number A/B routing isolation, resolved-business customer identity, real catalog media presentation, cart/variant checkout, customer-only order access, stock reservation/decrement, WhatsApp payment-link handoff, invoice send, shipment tracking, or outbound retry. No test suite was run because the requested audit must not change production state and PostgreSQL-backed tests may require mutable fixtures.

## 28. Database Relationship Map

```mermaid
erDiagram
  BUSINESS ||--o{ USER : owns
  BUSINESS ||--o{ BUYER : owns
  BUSINESS ||--o{ CATEGORY : owns
  BUSINESS ||--o{ PRODUCT : owns
  CATEGORY ||--o{ PRODUCT : groups
  PRODUCT ||--|| INVENTORY : has
  PRODUCT ||--o{ STOCK_MOVEMENT : records
  BUSINESS ||--o{ QUOTE : owns
  BUYER ||--o{ QUOTE : quoted_to
  QUOTE ||--o{ PAYMENT : funds
  PAYMENT ||--o{ PAYMENT_EVENT : receives
  PAYMENT ||--o| INVOICE : invoices
  RUN ||--o{ RUN_EVENT : timeline
  RUN ||--o{ APPROVAL : approvals
  WHATSAPP_MESSAGE : "independent log; wa_id/phone_number_id only"
```

Absent: WhatsApp configuration/binding, conversation entity, product variant/media, cart, order/order item, shipping/fulfilment/tracking. Real commercial Quote is not linked to the legacy WhatsApp Run by FK.

## 29. Reusable Components

Reuse Meta message normalization/sending/audio transport; `WhatsAppMessage` basic history/idempotency; tenant-scoped Product/Inventory and substitutions; deterministic pricing/quote services; Razorpay link/webhook/reconciliation; invoice generation/artifact storage; commercial idempotency constructs. Reuse only after tenant binding and customer authorization are introduced.

## 30. Missing Components

Receiving-number binding/router; Meta signed POST verification and status handler; CRM resolution/upsert; product attributes/variants/media/search; commerce conversation state/cart; customer order/address/fulfilment; atomic reservation/paid allocation and outbox consumers; commerce tools; WhatsApp product card/media response layer; delivery retries/observability; shipping/COD.

## 31. Proposed WhatsApp Commerce Architecture

`Meta webhook -> signature verify + normalize -> immutable inbound event -> phone_number_binding resolves business+experience -> customer resolver (business, wa_id) -> CommerceConversation -> CommerceOrchestrator -> scoped deterministic services -> transactional outbox -> WhatsApp sender/status reconciler`.

Number A binds to `owner_manager`; Number B binds to `customer_commerce`; both retain common transport only. The LLM may interpret Hinglish and choose tools, but tool input is server-bound to the resolved business/customer and tool output is the only source of product/price/stock/order/payment facts.

## 32. Proposed Commerce Tool Surface

| Tool capability | Disposition |
|---|---|
| exact product/list and inventory check | Wrap existing, then extend search/filter schema |
| quote/pricing | Wrap/extend existing pricing service |
| customer get/upsert | Extend Buyer/CRM service |
| cart, variants, address, order | New required |
| payment link/status | Wrap existing payment service; never accept chat claim |
| invoice | Wrap existing invoice service; add sender adapter |
| product media and shipment | New required |

## 33. Proposed Conversation State Model

DB: `CommerceConversation` (business/customer/phone binding, optimistic version, current intent, referenced product/variant IDs, active cart/order) and Cart/Order facts. Conversation metadata may retain last shown product-card IDs, comparison candidates and pending question. Product/price/stock are always dynamically re-read. Payment/invoice states stay in their authoritative tables. Suggested transitions: discovery -> exploration -> selection -> variant/quantity -> cart -> address -> payment pending -> verified/held -> confirmed -> fulfilment/post-purchase. Ensure every mutation has idempotency key and version/row lock.

## 34. File-by-File Implementation Plan

Modify `whatsapp/router.py` (raw-body Meta auth), `whatsapp/service.py` (binding dispatch/outbox), `whatsapp/models.py` (events/statuses or dedicated tables), `runs/*` only to isolate legacy owner flow; add `modules/commerce/{models,service,router,tools,orchestrator}.py`, `modules/whatsapp/bindings.py`, and media/search modules. Wrap—not duplicate—`catalog`, `inventory`, `pricing`, `payments`, `invoices`. Add a worker/outbox dispatcher and migration(s). Do not retrofit generic commerce into `mock_desks`.

## 35. Migration Requirements

Required before a purchasable MVP: phone bindings, customer uniqueness/index by `(business_id, whatsapp_e164)`, commerce conversation/version, product variants/attributes/media, cart/cart items, address/order/order items, stock reservations/allocation/outbox, and shipment fields only if a provider is selected. Data migration/configuration should create the Number-B-to-Rehbar binding; it must not embed Rehbar UUID in source.

## 36. Required Tests

Meta valid/invalid signature and replay; Number A/B isolation; tenant escape/IDOR; first/returning customer resolution; Hinglish discovery mapped to real catalog; product fact/media correctness; variants/quantity bounds; cart/order concurrency; stock reservation and paid shortage reconciliation; real Razorpay link and signed duplicate webhook; chat claim cannot mark paid; invoice artifact/send replay; outbound failure/retry/status; malformed media/STT fallback; conversation resume/race; authorization of customer order lookup.

## 37. Risks / Blockers

P0 blockers are exactly the four P0 findings in section 24. Live Rehbar mapping and actual WhatsApp/Meta configuration remain Unknown until an authorized read-only environment inspection.

## 38. Recommended Implementation Sequence

1. **Routing isolation/security:** bindings, Meta signature/auth, statuses, tests; rollback by disabling Number-B binding.
2. **Read-only commerce discovery:** customer resolution plus scoped real catalog/inventory tools and product/media schema; no checkout mutations.
3. **State/cart/order foundation:** variants, durable state/cart/address, locking/idempotency and tests.
4. **Checkout/payment bridge:** turn accepted cart/order into existing quote/payment link; authoritative webhook-to-order allocation, reservations and reconciliation.
5. **Invoice/confirmation/reliable send:** outbox, document sending/status and retry.
6. **Fulfilment/tracking/COD:** only after provider/domain choice.
7. **Sales intelligence/hardening:** search/recommendations/upsell, observability and adversarial tests.

## Direct Answers

1. Today `whatsapp_test` is merely a credential slot; messages use the common webhook, sender-based actor router and legacy RFQ flow.
2. `route_message` plus `handle_webhook_payload` decide: `whatsapp/service.py:220-249`.
3. No; transport credentials differ but experiences are not routed by receiving number.
4. Bind Number B to a DB/config `business_id` record with `experience=customer_commerce`.
5. Not through the current agent; real catalog API exists but current WhatsApp uses mocks.
6. Transport can send images/media; real product media data is absent.
7. Partially: Whisper is implemented with graceful fallback, not reliability guarantees.
8. Partial message-history persistence exists; durable commerce state does not.
9. No usable cart/draft order exists.
10. No; no reservation/decrement allocation prevents oversell.
11. Yes, real Razorpay link creation exists, but current WhatsApp sends a mock link.
12. Raw-body signed Razorpay webhook validates account/link/payment/amount/currency/status and stores event.
13. Payment becomes PAID with `reconciliation_hold`; no allocation/refund flow exists.
14. PDF invoice generation exists; WhatsApp delivery linkage does not.
15. No real shipment/tracking implementation exists.
16. Scoped wrappers around catalog, inventory, pricing, payments and invoices.
17. Minimum MVP: P0 fixes, binding/customer resolver, read-only catalog tools, cart/order/reservation, payment bridge and outbox.
18. The four confirmed P0 blockers.
19. Section 36 is the required production-safety suite.
20. Implement receiving-number tenant/experience routing plus authenticated idempotent webhook processing first.
