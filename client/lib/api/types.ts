/**
 * Backend response types for the StockAware FastAPI service.
 *
 * Field names match the backend exactly (snake_case). The backend is the source
 * of truth for money, tax, discounts, stock availability, quote state, and
 * approval decisions; these types only describe what the API already decided.
 *
 * The running service exposes two surfaces:
 *
 * 1. Browser-callable, no credentials (local/demo workflow store):
 *      GET  /health/live, /health/ready
 *      GET  /demo/products, /demo/runs, /demo/runs/{id}, /demo/runs/{id}/timeline
 *      POST /demo/webhook/whatsapp, /demo/runs/{id}/accept
 *      POST /demo/payments/create-link, /demo/payments/{id}/confirm
 *      POST /demo/invoice/generate, /demo/admin/command
 *
 * 2. Commercial endpoints which require the `X-Internal-Service-Token` header
 *    (server-to-server only). They are typed here so the mock layer can mirror
 *    the frozen contract, NOT so the browser can call them: the token is a
 *    backend secret and must never reach `NEXT_PUBLIC_*` or the browser.
 *      GET  /products, POST /catalog/match, POST /inventory/check
 *      POST /pricing/quote, POST /payments/create-link, GET /payments/{id}
 *      POST /invoice/generate, GET /invoices/{id}
 */

/** Money is always an integer count of paise (minor units). */
export type Paise = number

/** ISO-8601 UTC timestamp string as serialized by FastAPI. */
export type IsoTimestamp = string

// ---------------------------------------------------------------------------
// Error envelope
// ---------------------------------------------------------------------------

/**
 * Fareed error envelope: `{ "error": { "code", "message", "request_id", "details" } }`.
 *
 * Note: the current backend returns `request_id` (and an optional `details`
 * object) rather than the `run_id` shown in the earlier build-plan sketch, and
 * Rehbar-owned routes still return FastAPI's `{ "detail": ... }` shape.
 */
export interface BackendErrorEnvelope {
  error?: {
    code?: string
    message?: string
    request_id?: string
    details?: Record<string, unknown>
  }
  /** FastAPI HTTPException / default validation fallback shape. */
  detail?: unknown
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthLive {
  status: string
}

export interface HealthReady {
  status: string
  database: string
}

// ---------------------------------------------------------------------------
// /demo/* workflow store (browser-callable)
// ---------------------------------------------------------------------------

/** Unit values accepted by the demo RFQ intake contract. */
export type RfqUnit = 'each' | 'metre'

/** `GET /demo/products` — catalogue row without aliases. */
export interface DemoProduct {
  sku: string
  name: string
  unit: RfqUnit
  price_paise: Paise
  stock: number
  threshold: number
}

export interface ProductRecord {
  product_id?: string
  sku: string
  name: string
  sellable_unit?: string
  stock_unit?: string
  pack_size?: string
  indivisible?: boolean
  base_unit_price_paise?: Paise
  gst_rate_bps?: number
  active?: boolean
  unit?: RfqUnit
  price_paise?: Paise
  stock?: number
  threshold?: number
}

export type DemoMatchStatus = 'MATCHED' | 'NOT_FOUND' | 'AMBIGUOUS'
export type DemoStockStatus = 'AVAILABLE' | 'INSUFFICIENT'

/** A priced/checked RFQ line inside a demo run. */
export interface DemoRunLine {
  requested_name: string
  quantity: number
  unit: RfqUnit
  match_status: DemoMatchStatus
  sku?: string
  product_name?: string
  available_quantity?: number
  stock_status?: DemoStockStatus
  unit_price_paise?: Paise
  line_total_paise?: Paise
}

/** Saved quote snapshot attached to a demo run. */
export interface DemoQuote {
  id: string
  version: number
  status: string
  total_paise: Paise | null
  currency: string
  expires_at: IsoTimestamp | null
}

/**
 * `GET /demo/runs`, `GET /demo/runs/{id}`.
 * The single-run response omits `timeline`; use `GET /demo/runs/{id}/timeline`.
 */
export interface DemoRun {
  id: string
  buyer_name: string
  buyer_phone: string
  status: string
  lines: DemoRunLine[]
  quote: DemoQuote
}

/** `GET /demo/runs/{id}/timeline` */
export interface DemoEvent {
  id: string
  type: string
  message: string
  occurred_at: IsoTimestamp
}

/** `POST /demo/payments/create-link`, `GET /demo/payments/{id}` */
export interface DemoPayment {
  id: string
  run_id: string
  quote_id: string
  status: string
  amount_paise: Paise
  currency: string
  url: string
  /** The demo link flow is explicitly local and is not provider-verified. */
  demo_mode: boolean
  idempotent?: boolean
}

/** `POST /demo/invoice/generate` */
export interface DemoInvoice {
  id: string
  number: string
  payment_id: string
  quote_id: string
  total_paise: Paise
  currency: string
  artifact_url: string
  idempotent?: boolean
}

export interface DemoRfqLineIn {
  requested_name: string
  quantity: number
  unit: RfqUnit
}

/** `POST /demo/webhook/whatsapp` request body. */
export interface WhatsAppIntakeRequest {
  source_message_id: string
  buyer_name: string
  buyer_phone: string
  lines: DemoRfqLineIn[]
}

/** `POST /demo/webhook/whatsapp` response body. */
export interface WhatsAppIntakeResponse {
  duplicate: boolean
  run: DemoRun
  next_message?: string
}

/** `POST /demo/admin/command` response body. */
export interface DemoAdminCommandResult {
  result_type: 'LOW_STOCK' | 'VENDOR_UPDATE' | 'PAYMENTS' | 'HELP'
  message?: string
  items?: Array<Record<string, unknown>>
}

export interface AdminCommandRequest {
  actor: string
  text: string
}

// ---------------------------------------------------------------------------
// Rehbar run lifecycle (DB-backed, browser-callable, no credentials)
// ---------------------------------------------------------------------------

/** Run states from the backend state machine (`app/modules/runs/state_machine.py`). */
export type RunStatus =
  | 'RECEIVED'
  | 'NORMALIZING'
  | 'WAITING_FOR_CLARIFICATION'
  | 'CHECKING_STOCK'
  | 'CHECKING_PRICE'
  | 'APPROVAL_PENDING'
  | 'REJECTED'
  | 'EXPIRED'
  | 'QUOTE_CREATED'
  | 'QUOTE_SENT'
  | 'CHANGE_REQUESTED'
  | 'ACCEPTED'
  | 'PAYMENT_LINK_SENT'
  | 'PAYMENT_PENDING'
  | 'PAYMENT_FAILED'
  | 'PAYMENT_EXPIRED'
  | 'PAYMENT_CONFIRMED'
  | 'INVOICE_GENERATED'
  | 'ORDER_CONFIRMED'

/** `GET /runs`, `GET /runs/{run_id}` */
export interface RunOut {
  run_id: string
  status: string
  version: number
  source: string
  buyer_wa_id: string
  buyer_name: string | null
  line_items: unknown[]
  quote_snapshot: Record<string, unknown> | null
  quote_id: string | null
  payment_id: string | null
  invoice_id: string | null
  created_at: IsoTimestamp
  updated_at: IsoTimestamp
}

/** `GET /runs/{run_id}/timeline` (Rehbar audit event) */
export interface TimelineEventOut {
  time: IsoTimestamp
  role: string
  event: string
  run_id: string
  metadata: Record<string, unknown> | null
}

export type AgentCraftStatus = 'idle' | 'working' | 'waiting' | 'completed' | 'blocked' | 'failed'
export type AgentCraftEventType = 'task' | 'result' | 'status'

/** `GET /runs/{run_id}/agent-events` */
export interface AgentCraftEventOut {
  run_id: string
  from_agent: string
  to_agent: string
  type: AgentCraftEventType
  message: string
  status: AgentCraftStatus
  timestamp: IsoTimestamp
}

/** `POST /runs/{run_id}/approve` and `POST /runs/{run_id}/reject` body. */
export interface ApprovalActionRequest {
  actor: string
}

/** `POST /runs/{run_id}/approve|reject` response item (outbound WhatsApp message). */
export interface OutboundMessageOut {
  to: string
  text: string
  message_type: string
  media_id: string | null
  link: string | null
  caption: string | null
  filename: string | null
  latitude: number | null
  longitude: number | null
  name: string | null
  address: string | null
  contacts: Array<Record<string, unknown>>
  interactive: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Commercial contract (server-to-server only; the browser receives 503 today
// because `INTERNAL_SERVICE_TOKEN` / `INTERNAL_BUSINESS_ID` are not set)
// ---------------------------------------------------------------------------

/** `GET /products` (commercial, token-gated). */
export interface CommercialProduct {
  product_id: string
  sku: string
  name: string
  sellable_unit: string
  stock_unit: string
  pack_size: string
  indivisible: boolean
  base_unit_price_paise: Paise
  gst_rate_bps: number
  active: boolean
}

/** `POST /catalog/match` (commercial, token-gated). */
export interface CatalogMatchRequest {
  business_id: string
  run_id: string
  requested_text: string
  requested_unit: string
}

export interface CatalogCandidate {
  product_id: string
  sku: string
  name: string
  sellable_unit: string
  stock_unit: string
  pack_size: string
  match_type: 'sku' | 'name' | 'alias'
}

export interface CatalogMatchResponse {
  status: 'MATCHED' | 'AMBIGUOUS' | 'NOT_FOUND'
  requested_text: string
  selected_product_id: string | null
  selected_sku: string | null
  reason: string
  reason_code: string
  candidates: CatalogCandidate[]
}

/** `POST /inventory/check` (commercial, token-gated). */
export interface InventoryCheckRequest {
  business_id: string
  run_id: string
  product_id: string
  requested_qty: string
  requested_unit?: string
}

export interface SubstituteOut {
  product_id: string
  sku: string
  name: string
  rank: number
  reason: string | null
}

export interface InventoryCheckResponse {
  status: 'AVAILABLE' | 'LOW_STOCK' | 'INSUFFICIENT_STOCK' | 'OUT_OF_STOCK'
  product_id: string
  requested_qty: string
  stock_unit: string
  on_hand_qty: string
  available_qty: string
  checked_at: IsoTimestamp
  substitutes: SubstituteOut[]
}

/** `POST /pricing/quote` (commercial, token-gated). Requires Idempotency-Key. */
export interface QuoteLineRequest {
  product_id: string
  quantity: string
  unit: string
  discount_bps: number
}

export interface QuoteRequest {
  business_id: string
  run_id: string
  buyer_id: string
  lines: QuoteLineRequest[]
}

export interface CommercialQuoteLine {
  product_id: string
  sku: string
  name: string
  quantity: string
  unit: string
  unit_price_paise: Paise
  discount_bps: number
  discount_paise: Paise
  taxable_paise: Paise
  gst_rate_bps: number
  tax_paise: Paise
  line_total_paise: Paise
}

export interface CommercialQuote {
  business_id: string
  run_id: string
  quote_id: string
  quote_version: number
  status: 'DRAFT' | 'GENERATED' | 'ACCEPTED' | 'EXPIRED' | 'CANCELLED'
  currency: string
  subtotal_paise: Paise
  tax_paise: Paise
  total_paise: Paise
  expires_at: IsoTimestamp
  approval_required: boolean
  approval_satisfied: boolean
  approval_reasons: string[]
  lines: CommercialQuoteLine[]
}

/** `POST /payments/create-link` (commercial, token-gated). */
export interface PaymentLinkRequest {
  business_id: string
  run_id: string
  quote_id: string
  quote_version: number
  amount_paise?: number
}

export type CommercialPaymentStatus =
  | 'CREATED'
  | 'PENDING'
  | 'PAID'
  | 'FAILED'
  | 'EXPIRED'
  | 'CANCELLED'

/** `GET /payments/{id}` (commercial, token-gated). */
export interface CommercialPayment {
  business_id: string
  run_id: string
  payment_id: string
  quote_id: string
  quote_version: number
  status: CommercialPaymentStatus
  amount_paise: Paise
  currency: string
  provider_link_id: string | null
  payment_url: string | null
  link_expires_at: IsoTimestamp
  reconciliation_hold: boolean
}

/** `POST /invoice/generate` (commercial, token-gated). */
export interface InvoiceGenerateRequest {
  business_id: string
  run_id: string
  quote_id: string
  quote_version: number
  payment_id: string
}

/** `GET /invoices/{id}` (commercial, token-gated). */
export interface CommercialInvoice {
  business_id: string
  run_id: string
  invoice_id: string
  invoice_number: string
  quote_id: string
  quote_version: number
  payment_id: string
  status: 'PENDING_ARTIFACT' | 'GENERATED'
  currency: string
  total_paise: Paise
  issued_at: IsoTimestamp
  artifact_sha256: string | null
  download_url: string | null
}

/**
 * Where a returned payload came from. The UI surfaces this so demo/mock data is
 * never mistaken for a real backend record.
 */
export type DataSource = 'backend' | 'mock'

/** A payload plus its provenance. */
export interface ApiResult<T> {
  data: T
  source: DataSource
  /** Path of the endpoint that does not exist on the running backend, if any. */
  missingEndpoint?: string
}
