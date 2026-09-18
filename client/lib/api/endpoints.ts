/**
 * Typed API functions for the StockAware backend.
 *
 * Every call is a direct browser request to `NEXT_PUBLIC_API_BASE_URL`. There is
 * no Next.js proxy route and no `app/api` handler.
 *
 * Which surface each function uses:
 *
 *   Health            -> real `/health/live`, `/health/ready`
 *   Inventory/catalog -> real `GET /demo/products` (browser-safe workflow store)
 *   Runs + timeline   -> real `GET /demo/runs*`, plus Rehbar's `GET /runs*`
 *   Payments/invoices -> real `/demo/payments*`, `POST /demo/invoice/generate`
 *   Commercial endpoints (`/products`, `/catalog/match`, `/inventory/check`,
 *   `/pricing/quote`, `/payments/*`, `/invoice*`) require the header
 *   `X-Internal-Service-Token`. They are server-to-server only: the token is a
 *   backend secret, so these wrappers exist for completeness and are NOT called
 *   by the UI. Calling them from the browser returns 503 today.
 *
 * Mock fallback: reads fall back to `lib/api/mock.ts` only when
 * `NEXT_PUBLIC_USE_MOCKS=true` AND the real call fails because the endpoint does
 * not exist, is unreachable, or rejects the browser as unauthenticated. A real
 * response, including an empty list, always wins.
 */

import { ApiError, apiFetchBlob, apiGet, apiPost } from './client'
import { USE_MOCKS } from '@/lib/config'
import * as mock from './mock'
import type {
  ApiResult,
  ApprovalActionRequest,
  CatalogMatchRequest,
  CatalogMatchResponse,
  CommercialInvoice,
  CommercialPayment,
  CommercialProduct,
  CommercialQuote,
  AdminCommandRequest,
  DemoEvent,
  DemoInvoice,
  DemoPayment,
  DemoProduct,
  DemoRun,
  DemoRunLine,
  ProductRecord,
  HealthLive,
  HealthReady,
  InventoryCheckRequest,
  InventoryCheckResponse,
  InvoiceGenerateRequest,
  OutboundMessageOut,
  PaymentLinkRequest,
  QuoteRequest,
  RunOut,
  TimelineEventOut,
  WhatsAppIntakeRequest,
  WhatsAppIntakeResponse,
} from './types'

export { ApiError }
export type { ApiResult, DataSource } from './types'

/** A failed call may be replaced by contract-shaped mock data. */
function canFallBack(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false
  return error.isMissingEndpoint || error.isUnavailable || error.isAuthFailure
}

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

function toDemoRun(run: RunOut): DemoRun {
  const snapshot = record(run.quote_snapshot)
  const rawLines = Array.isArray(snapshot?.lines) ? snapshot.lines : run.line_items
  const lines = rawLines.flatMap((value): DemoRunLine[] => {
    const line = record(value)
    if (!line) return []
    const matchStatus = stringValue(line.match_status)
    const stockStatus = stringValue(line.stock_status)
    return [{
      requested_name: stringValue(line.requested_name) ?? stringValue(line.name) ?? 'Item',
      quantity: numberValue(line.quantity) ?? 0,
      unit: line.unit === 'metre' ? 'metre' : 'each',
      match_status: matchStatus === 'NOT_FOUND' || matchStatus === 'AMBIGUOUS' ? matchStatus : 'MATCHED',
      sku: stringValue(line.sku) ?? undefined,
      product_name: stringValue(line.product_name) ?? stringValue(line.name) ?? undefined,
      available_quantity: numberValue(line.available_quantity) ?? undefined,
      stock_status: stockStatus === 'INSUFFICIENT' ? 'INSUFFICIENT' : stockStatus ? 'AVAILABLE' : undefined,
      unit_price_paise: numberValue(line.unit_price_paise) ?? undefined,
      line_total_paise: numberValue(line.line_total_paise) ?? undefined,
    } as DemoRunLine]
  })
  return {
    id: run.run_id,
    buyer_name: run.buyer_name ?? 'Unknown buyer',
    buyer_phone: run.buyer_wa_id,
    status: run.status,
    lines,
    quote: {
      id: run.quote_id ?? stringValue(snapshot?.quote_id) ?? run.run_id,
      version: run.version,
      status: stringValue(snapshot?.status) ?? run.status,
      total_paise: numberValue(snapshot?.total_paise),
      currency: stringValue(snapshot?.currency) ?? 'INR',
      expires_at: stringValue(snapshot?.expires_at),
    },
  }
}

function toDemoEvent(event: TimelineEventOut): DemoEvent {
  return {
    id: `${event.run_id}-${event.time}-${event.event}`,
    type: event.event,
    message: event.event,
    occurred_at: event.time,
  }
}

/** Read `path` from the backend, falling back to `fallback` while mocks are on. */
async function readWithFallback<T>(
  path: string,
  fallback: () => T,
): Promise<ApiResult<T>> {
  try {
    return { data: await apiGet<T>(path), source: 'backend' }
  } catch (error) {
    if (USE_MOCKS && canFallBack(error)) {
      const missing = error instanceof ApiError && error.isMissingEndpoint ? path : undefined
      return { data: fallback(), source: 'mock', missingEndpoint: missing }
    }
    throw error
  }
}

// ---------------------------------------------------------------------------
// Health (always real - these endpoints exist on every build)
// ---------------------------------------------------------------------------

export function getHealthLive(): Promise<HealthLive> {
  return apiGet<HealthLive>('/health/live')
}

export function getHealthReady(): Promise<HealthReady> {
  return apiGet<HealthReady>('/health/ready')
}

// ---------------------------------------------------------------------------
// Demo workflow store (browser-callable): catalogue, runs, timeline
// ---------------------------------------------------------------------------

/**
 * `GET /demo/products` - the browser-safe catalogue the UI should render.
 *
 * The commercial `GET /products` endpoint returns a richer record but requires
 * the internal service token, so it cannot be used from the browser.
 */
export function listProducts(): Promise<ApiResult<ProductRecord[]>> {
  return readWithFallback<ProductRecord[]>('/products', () => mock.mockProducts())
}

/** Single product by SKU, resolved from the same browser-safe catalogue list. */
export async function getProduct(sku: string): Promise<ApiResult<ProductRecord | null>> {
  const result = await listProducts()
  const found = result.data.find((product) => product.sku === sku) ?? null
  return { ...result, data: found }
}

/** `GET /demo/runs` - RFQ runs from the demo workflow store. */
export function listRuns(): Promise<ApiResult<DemoRun[]>> {
  return apiGet<RunOut[]>('/runs')
    .then((runs) => ({ data: runs.map(toDemoRun), source: 'backend' as const }))
    .catch((error: unknown) => {
      if (USE_MOCKS && canFallBack(error)) {
        return { data: mock.mockRuns(), source: 'mock' as const, missingEndpoint: error instanceof ApiError && error.isMissingEndpoint ? '/runs' : undefined }
      }
      throw error
    })
}

/** `GET /demo/runs/{id}` */
export async function getRun(runId: string): Promise<ApiResult<DemoRun | null>> {
  try {
    const run = await apiGet<RunOut>(`/runs/${encodeURIComponent(runId)}`)
    return { data: toDemoRun(run), source: 'backend' }
  } catch (error) {
    if (USE_MOCKS && canFallBack(error)) {
      return { data: mock.mockRun(runId), source: 'mock', missingEndpoint: error instanceof ApiError && error.isMissingEndpoint ? `/runs/${encodeURIComponent(runId)}` : undefined }
    }
    throw error
  }
}

/** `GET /demo/runs/{id}/timeline` */
export function getRunTimeline(runId: string): Promise<ApiResult<DemoEvent[]>> {
  return apiGet<TimelineEventOut[]>(`/runs/${encodeURIComponent(runId)}/timeline`)
    .then((events) => ({ data: events.map(toDemoEvent), source: 'backend' as const }))
    .catch((error: unknown) => {
      if (USE_MOCKS && canFallBack(error)) {
        return { data: mock.mockEvents(runId), source: 'mock' as const, missingEndpoint: error instanceof ApiError && error.isMissingEndpoint ? `/runs/${encodeURIComponent(runId)}/timeline` : undefined }
      }
      throw error
    })
}

/** `GET /runs` - Rehbar's DB-backed run lifecycle (authoritative, may be empty). */
export function listLifecycleRuns(): Promise<RunOut[]> {
  return apiGet<RunOut[]>('/runs')
}

/** `GET /runs/{id}` */
export function getLifecycleRun(runId: string): Promise<RunOut> {
  return apiGet<RunOut>(`/runs/${encodeURIComponent(runId)}`)
}

/** `GET /runs/{id}/timeline` */
export function getLifecycleTimeline(runId: string): Promise<TimelineEventOut[]> {
  return apiGet<TimelineEventOut[]>(`/runs/${encodeURIComponent(runId)}/timeline`)
}

// ---------------------------------------------------------------------------
// Workflow actions. These mutate backend state, so they never fall back to mock
// data: a failed approval or payment-link request must surface as an error.
// ---------------------------------------------------------------------------

/** `POST /demo/webhook/whatsapp` - create a run from a buyer RFQ. */
export function createRunFromWhatsApp(
  payload: WhatsAppIntakeRequest,
): Promise<WhatsAppIntakeResponse> {
  return apiPost<WhatsAppIntakeResponse>('/demo/webhook/whatsapp', payload, {
    idempotencyKey: payload.source_message_id,
  })
}

/** `POST /demo/runs/{id}/accept` - buyer acceptance of the saved quote version. */
export function acceptQuote(runId: string): Promise<DemoRun> {
  return apiPost<DemoRun>(`/demo/runs/${encodeURIComponent(runId)}/accept`)
}

/** `POST /runs/{id}/approve` - owner approval captured by Rehbar. */
export function approveRun(runId: string, actor: string): Promise<OutboundMessageOut[]> {
  const body: ApprovalActionRequest = { actor }
  return apiPost<OutboundMessageOut[]>(`/runs/${encodeURIComponent(runId)}/approve`, body)
}

/** `POST /runs/{id}/reject` - owner rejection captured by Rehbar. */
export function rejectRun(runId: string, actor: string): Promise<OutboundMessageOut[]> {
  const body: ApprovalActionRequest = { actor }
  return apiPost<OutboundMessageOut[]>(`/runs/${encodeURIComponent(runId)}/reject`, body)
}

/** `POST /demo/payments/create-link` - demo payment link for an accepted quote. */
export function createDemoPaymentLink(runId: string): Promise<DemoPayment> {
  return apiPost<DemoPayment>(
    '/demo/payments/create-link',
    { run_id: runId },
    { idempotencyKey: `demo-payment-link-${runId}` },
  )
}

/** `GET /demo/payments/{id}` */
export function getDemoPayment(paymentId: string): Promise<DemoPayment> {
  return apiGet<DemoPayment>(`/demo/payments/${encodeURIComponent(paymentId)}`)
}

/**
 * `POST /demo/payments/{id}/confirm` - LOCAL DEMO ACTION ONLY.
 *
 * The backend marks its response `demo_mode: true`. Production payment state
 * comes from a verified Razorpay webhook, so the UI must never present this as
 * buyer-confirmed money.
 */
export function confirmDemoPayment(paymentId: string): Promise<DemoPayment> {
  return apiPost<DemoPayment>(`/demo/payments/${encodeURIComponent(paymentId)}/confirm`)
}

/** `POST /demo/invoice/generate` - issues one demo invoice per paid payment. */
export function generateDemoInvoice(paymentId: string): Promise<DemoInvoice> {
  return apiPost<DemoInvoice>(
    '/demo/invoice/generate',
    { payment_id: paymentId },
    { idempotencyKey: `demo-invoice-${paymentId}` },
  )
}

/** `POST /demo/admin/command` - owner command panel (low stock, vendor, payments). */
export function runAdminCommand(command: string): Promise<OutboundMessageOut[]> {
  const body: AdminCommandRequest = { actor: 'owner', text: command }
  return apiPost<OutboundMessageOut[]>('/admin/command', body)
}

// ---------------------------------------------------------------------------
// Collections the backend does not expose to the browser yet.
// Each attempts the real read first and only then serves a mock fixture.
// ---------------------------------------------------------------------------

/**
 * MISSING ENDPOINT: no payment list route exists. `/payments` is only
 * `POST /payments/create-link` (internal-token gated) and `GET /payments/{id}`.
 */
export function listPayments(): Promise<ApiResult<CommercialPayment[]>> {
  return readWithFallback<CommercialPayment[]>('/payments', mock.mockPayments)
}

/** MISSING ENDPOINT: no invoice list route exists. */
export function listInvoices(): Promise<ApiResult<CommercialInvoice[]>> {
  return readWithFallback<CommercialInvoice[]>('/invoices', mock.mockInvoices)
}

/** MISSING ENDPOINT: no quote list route exists. */
export function listQuotes(): Promise<ApiResult<CommercialQuote[]>> {
  return readWithFallback<CommercialQuote[]>('/quotes', mock.mockQuotes)
}

/**
 * `GET /invoices/{id}` is internal-token gated, so a browser read falls back to
 * the contract-shaped fixture.
 */
export function getInvoice(invoiceId: string): Promise<ApiResult<CommercialInvoice | null>> {
  return readWithFallback<CommercialInvoice | null>(
    `/invoices/${encodeURIComponent(invoiceId)}`,
    () => mock.mockInvoice(invoiceId),
  )
}

// ---------------------------------------------------------------------------
// Commercial contract wrappers (internal service token required).
//
// Server-to-server only: the token is a backend secret and must never reach the
// browser. These wrappers are exported so the API surface stays auditable and
// typed, and are deliberately NOT wired into any component.
// ---------------------------------------------------------------------------

/** `GET /products` (commercial) */
export function listCommercialProducts(): Promise<CommercialProduct[]> {
  return apiGet<CommercialProduct[]>('/products')
}

/** `POST /catalog/match` (commercial) */
export function matchCatalog(body: CatalogMatchRequest): Promise<CatalogMatchResponse> {
  return apiPost<CatalogMatchResponse>('/catalog/match', body)
}

/** `POST /inventory/check` (commercial) */
export function checkInventory(body: InventoryCheckRequest): Promise<InventoryCheckResponse> {
  return apiPost<InventoryCheckResponse>('/inventory/check', body)
}

/** `POST /pricing/quote` (commercial). Requires an Idempotency-Key header. */
export function createQuote(body: QuoteRequest, idempotencyKey: string): Promise<CommercialQuote> {
  return apiPost<CommercialQuote>('/pricing/quote', body, { idempotencyKey })
}

/** `POST /payments/create-link` (commercial). Requires an Idempotency-Key header. */
export function createPaymentLink(
  body: PaymentLinkRequest,
  idempotencyKey: string,
): Promise<CommercialPayment> {
  return apiPost<CommercialPayment>('/payments/create-link', body, { idempotencyKey })
}

/** `GET /payments/{id}` (commercial) */
export function getCommercialPayment(paymentId: string): Promise<CommercialPayment> {
  return apiGet<CommercialPayment>(`/payments/${encodeURIComponent(paymentId)}`)
}

/** `POST /invoice/generate` (commercial). Requires an Idempotency-Key header. */
export function generateInvoice(
  body: InvoiceGenerateRequest,
  idempotencyKey: string,
): Promise<CommercialInvoice> {
  return apiPost<CommercialInvoice>('/invoice/generate', body, { idempotencyKey })
}

export function getInvoiceArtifact(invoiceId: string): Promise<Blob> {
  return apiFetchBlob(`/invoices/${encodeURIComponent(invoiceId)}/artifact`)
}
