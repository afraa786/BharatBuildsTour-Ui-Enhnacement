/**
 * Frontend runtime configuration.
 *
 * Only NEXT_PUBLIC_* values are readable in the browser. Secrets (Razorpay keys,
 * internal service tokens, database credentials) must never be exposed here; the
 * commercial API endpoints are server-to-server and are called by the backend.
 */

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

/** Base URL for direct browser requests to the FastAPI service. */
export const API_BASE_URL: string = (
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/+$/, '')

export const BUSINESS_ID = process.env.NEXT_PUBLIC_BUSINESS_ID?.trim() || ''

/**
 * Contract-shaped mock fallback. Used only when a backend endpoint is missing or
 * unreachable; a real backend response (including an empty list) always wins.
 */
export const USE_MOCKS: boolean = process.env.NEXT_PUBLIC_USE_MOCKS === 'true'

/** Abort requests that hang so the UI can show an error state. */
export const API_TIMEOUT_MS = 12000
