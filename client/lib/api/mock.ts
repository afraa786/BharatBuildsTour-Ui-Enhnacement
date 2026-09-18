/**
 * Contract-shaped mock fallback.
 *
 * Scope: these fixtures exist ONLY for capabilities the running backend does not
 * expose to the browser yet. They must never override a real backend response.
 * Concretely, on the current build the backend has no *list* endpoint for
 * payments, invoices, or quotes, so those three collections (and single invoice
 * reads) fall back to the fixtures below.
 *
 * Everything else is served by real endpoints: `/health/*`, `/demo/products`,
 * `/demo/runs`, `/demo/runs/{id}`, `/demo/runs/{id}/timeline`,
 * `/demo/payments/{id}`, `/demo/invoice/generate`.
 *
 * Deliberately absent: any authoritative arithmetic. The money values below are
 * fixed, hand-checked demo constants shaped like the frozen commercial contract
 * (`subtotal + tax = total`, paise integers). This file can be deleted once the
 * corresponding backend endpoints exist; nothing else imports it directly.
 */

import type {
  CommercialInvoice,
  CommercialPayment,
  CommercialQuote,
  DemoEvent,
  DemoProduct,
  DemoRun,
} from './types'

const BUSINESS_ID = '0f1e2d3c-4b5a-4678-9abc-def012345678'
const BUYER_ID = '1a2b3c4d-5e6f-4718-8a9b-0c1d2e3f4a5b'
const P_MCB = '11111111-1111-4111-8111-111111111111'
const P_WIRE = '22222222-2222-4222-8222-222222222222'
const P_LED9 = '33333333-3333-4333-8333-333333333333'
const P_LED12 = '44444444-4444-4444-8444-444444444444'
const Q_ONE = '55555555-5555-4555-8555-555555555555'
const Q_TWO = '66666666-6666-4666-8666-666666666666'
const PAY_ONE = '77777777-7777-4777-8777-777777777777'
const PAY_TWO = '88888888-8888-4888-8888-888888888888'
const INV_ONE = '99999999-9999-4999-8999-999999999999'
const INV_TWO = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

const MOCK_RUN_ONE = 'RUN-1A2B3C4D'
const MOCK_RUN_TWO = 'RUN-5E6F7A8B'

const GST_18_BPS = 1800

/** Mirrors the four seeded products served by `GET /demo/products`. */
export const MOCK_PRODUCTS: DemoProduct[] = [
  {
    sku: 'MCB-32A-SP',
    name: '32A SP MCB C Curve',
    unit: 'each',
    price_paise: 26000,
    stock: 38,
    threshold: 12,
  },
  {
    sku: 'WIRE-1.5SQ-RED',
    name: '1.5 sq mm FR Copper Wire Red',
    unit: 'metre',
    price_paise: 2050,
    stock: 450,
    threshold: 180,
  },
  {
    sku: 'LED-9W',
    name: '9W LED Bulb Cool Day Light',
    unit: 'each',
    price_paise: 7500,
    stock: 20,
    threshold: 30,
  },
  {
    sku: 'LED-12W',
    name: '12W LED Bulb Cool Day Light',
    unit: 'each',
    price_paise: 9300,
    stock: 80,
    threshold: 30,
  },
]

/** Mirrors the shape of `GET /demo/runs` (statuses use the demo vocabulary). */
export const MOCK_RUNS: DemoRun[] = [
  {
    id: MOCK_RUN_ONE,
    buyer_name: 'Sharma Electricals',
    buyer_phone: '919876543210',
    status: 'QUOTED',
    lines: [
      {
        requested_name: '32A SP MCB C Curve',
        quantity: 10,
        unit: 'each',
        match_status: 'MATCHED',
        sku: 'MCB-32A-SP',
        product_name: '32A SP MCB C Curve',
        available_quantity: 10,
        stock_status: 'AVAILABLE',
        unit_price_paise: 26000,
        line_total_paise: 260000,
      },
      {
        requested_name: '12W LED Bulb Cool Day Light',
        quantity: 40,
        unit: 'each',
        match_status: 'MATCHED',
        sku: 'LED-12W',
        product_name: '12W LED Bulb Cool Day Light',
        available_quantity: 40,
        stock_status: 'AVAILABLE',
        unit_price_paise: 9300,
        line_total_paise: 372000,
      },
    ],
    quote: {
      id: 'QT-MOCK01',
      version: 1,
      status: 'SENT',
      total_paise: 632000,
      currency: 'INR',
      expires_at: '2026-09-20T09:48:11+00:00',
    },
  },
  {
    id: MOCK_RUN_TWO,
    buyer_name: 'Kumar & Sons',
    buyer_phone: '919812345678',
    status: 'INVOICED',
    lines: [
      {
        requested_name: '9W LED Bulb Cool Day Light',
        quantity: 40,
        unit: 'each',
        match_status: 'MATCHED',
        sku: 'LED-9W',
        product_name: '9W LED Bulb Cool Day Light',
        available_quantity: 20,
        stock_status: 'INSUFFICIENT',
        unit_price_paise: 7500,
        line_total_paise: 300000,
      },
      {
        requested_name: '1.5 sq mm FR Copper Wire Red',
        quantity: 100,
        unit: 'metre',
        match_status: 'MATCHED',
        sku: 'WIRE-1.5SQ-RED',
        product_name: '1.5 sq mm FR Copper Wire Red',
        available_quantity: 100,
        stock_status: 'AVAILABLE',
        unit_price_paise: 2050,
        line_total_paise: 205000,
      },
    ],
    quote: {
      id: 'QT-MOCK02',
      version: 1,
      status: 'ACCEPTED',
      total_paise: 505000,
      currency: 'INR',
      expires_at: '2026-09-19T11:20:00+00:00',
    },
  },
]

/** Mirrors the shape of `GET /demo/runs/{id}/timeline`. */
export const MOCK_EVENTS: Record<string, DemoEvent[]> = {
  [MOCK_RUN_ONE]: [
    {
      id: 'EVT-MOCK0001',
      type: 'RFQ_RECEIVED',
      message: 'RFQ received from Sharma Electricals.',
      occurred_at: '2026-09-17T14:04:02+00:00',
    },
    {
      id: 'EVT-MOCK0002',
      type: 'ITEM_MATCHED',
      message: '2 of 2 requested items matched the catalogue.',
      occurred_at: '2026-09-17T14:04:03+00:00',
    },
    {
      id: 'EVT-MOCK0003',
      type: 'STOCK_CHECKED',
      message: 'Stock check completed; all lines available.',
      occurred_at: '2026-09-17T14:04:04+00:00',
    },
    {
      id: 'EVT-MOCK0004',
      type: 'QUOTE_READY',
      message: 'Quote prepared and waiting for buyer acceptance.',
      occurred_at: '2026-09-17T14:04:06+00:00',
    },
  ],
  [MOCK_RUN_TWO]: [
    {
      id: 'EVT-MOCK0005',
      type: 'RFQ_RECEIVED',
      message: 'RFQ received from Kumar & Sons.',
      occurred_at: '2026-09-16T13:22:15+00:00',
    },
    {
      id: 'EVT-MOCK0006',
      type: 'STOCK_SHORTAGE',
      message: '9W LED stock is insufficient; buyer informed.',
      occurred_at: '2026-09-16T13:22:18+00:00',
    },
    {
      id: 'EVT-MOCK0007',
      type: 'PAYMENT_CONFIRMED',
      message: 'Payment confirmed by the provider webhook.',
      occurred_at: '2026-09-16T15:02:44+00:00',
    },
    {
      id: 'EVT-MOCK0008',
      type: 'INVOICE_GENERATED',
      message: 'Invoice SA/2026/0001 generated.',
      occurred_at: '2026-09-16T15:02:45+00:00',
    },
  ],
}
/** Commercial-contract quote rows. No browser-callable quote list exists yet. */
export const MOCK_QUOTES: CommercialQuote[] = [
  {
    business_id: BUSINESS_ID,
    run_id: MOCK_RUN_ONE,
    quote_id: Q_ONE,
    quote_version: 1,
    status: 'GENERATED',
    currency: 'INR',
    subtotal_paise: 632000,
    tax_paise: 113760,
    total_paise: 745760,
    expires_at: '2026-09-20T09:48:11+00:00',
    approval_required: false,
    approval_satisfied: true,
    approval_reasons: [],
    lines: [
      {
        product_id: P_MCB,
        sku: 'MCB-32A-SP',
        name: '32A SP MCB C Curve',
        quantity: '10.000',
        unit: 'each',
        unit_price_paise: 26000,
        discount_bps: 0,
        discount_paise: 0,
        taxable_paise: 260000,
        gst_rate_bps: GST_18_BPS,
        tax_paise: 46800,
        line_total_paise: 306800,
      },
      {
        product_id: P_LED12,
        sku: 'LED-12W',
        name: '12W LED Bulb Cool Day Light',
        quantity: '40.000',
        unit: 'each',
        unit_price_paise: 9300,
        discount_bps: 0,
        discount_paise: 0,
        taxable_paise: 372000,
        gst_rate_bps: GST_18_BPS,
        tax_paise: 66960,
        line_total_paise: 438960,
      },
    ],
  },
]

/**
 * Commercial-contract payment rows. The backend exposes
 * `POST /demo/payments/create-link` and `GET /demo/payments/{id}` but no list
 * endpoint, so the payments *list* falls back to this fixture.
 */
export const MOCK_PAYMENTS: CommercialPayment[] = [
  {
    business_id: BUSINESS_ID,
    run_id: MOCK_RUN_ONE,
    payment_id: PAY_ONE,
    quote_id: Q_ONE,
    quote_version: 1,
    status: 'PENDING',
    amount_paise: 745760,
    currency: 'INR',
    provider_link_id: 'plink_mock_0001',
    payment_url: 'https://pay.stockaware.demo/link/plink_mock_0001',
    link_expires_at: '2026-09-20T09:48:11+00:00',
    reconciliation_hold: false,
  },
  {
    business_id: BUSINESS_ID,
    run_id: MOCK_RUN_TWO,
    payment_id: PAY_TWO,
    quote_id: Q_TWO,
    quote_version: 1,
    status: 'PAID',
    amount_paise: 595900,
    currency: 'INR',
    provider_link_id: 'plink_mock_0002',
    payment_url: null,
    link_expires_at: '2026-09-19T11:20:00+00:00',
    reconciliation_hold: false,
  },
]

/**
 * Commercial-contract invoice rows. There is no browser-callable invoice list
 * and `GET /invoices/{id}` is internal-token gated, so invoice reads fall back
 * to this fixture until those endpoints accept a browser session.
 */
export const MOCK_INVOICES: CommercialInvoice[] = [
  {
    business_id: BUSINESS_ID,
    run_id: MOCK_RUN_TWO,
    invoice_id: INV_ONE,
    invoice_number: 'SA/2026/0001',
    quote_id: Q_TWO,
    quote_version: 1,
    payment_id: PAY_TWO,
    status: 'GENERATED',
    currency: 'INR',
    total_paise: 595900,
    issued_at: '2026-09-16T15:02:45+00:00',
    artifact_sha256: null,
    download_url: null,
  },
  {
    business_id: BUSINESS_ID,
    run_id: MOCK_RUN_ONE,
    invoice_id: INV_TWO,
    invoice_number: 'SA/2026/0002',
    quote_id: Q_ONE,
    quote_version: 1,
    payment_id: PAY_ONE,
    status: 'PENDING_ARTIFACT',
    currency: 'INR',
    total_paise: 745760,
    issued_at: '2026-09-17T16:00:00+00:00',
    artifact_sha256: null,
    download_url: null,
  },
]

function clone<T>(value: T): T {
  return structuredClone(value)
}

export function mockProducts(): DemoProduct[] {
  return clone(MOCK_PRODUCTS)
}

export function mockRuns(): DemoRun[] {
  return clone(MOCK_RUNS)
}

export function mockRun(runId: string): DemoRun | null {
  const found = MOCK_RUNS.find((run) => run.id === runId)
  return found ? clone(found) : null
}

export function mockEvents(runId: string): DemoEvent[] {
  return clone(MOCK_EVENTS[runId] ?? [])
}

export function mockQuotes(): CommercialQuote[] {
  return clone(MOCK_QUOTES)
}

export function mockPayments(): CommercialPayment[] {
  return clone(MOCK_PAYMENTS)
}

export function mockInvoices(): CommercialInvoice[] {
  return clone(MOCK_INVOICES)
}

export function mockInvoice(invoiceId: string): CommercialInvoice | null {
  const found = MOCK_INVOICES.find((invoice) => invoice.invoice_id === invoiceId)
  return found ? clone(found) : null
}
