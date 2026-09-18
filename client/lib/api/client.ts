import { API_BASE_URL, API_TIMEOUT_MS } from '@/lib/config'

export type ApiErrorKind = 'http' | 'network' | 'timeout' | 'aborted'

/** Shape of the Fareed commercial error envelope: { "error": { ... } }. */
export interface BackendErrorEnvelope {
  error?: {
    code?: string
    message?: string
    request_id?: string
    details?: Record<string, unknown>
  }
  /** FastAPI HTTPException / validation fallback shape. */
  detail?: unknown
}

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  timeoutMs?: number
  /** Optional Idempotency-Key header for mutating commercial endpoints. */
  idempotencyKey?: string
  signal?: AbortSignal
  headers?: Record<string, string>
}

const DEFAULT_CODE_BY_STATUS: Record<number, string> = {
  400: 'BAD_REQUEST',
  401: 'UNAUTHORIZED',
  403: 'FORBIDDEN',
  404: 'NOT_FOUND',
  409: 'CONFLICT',
  422: 'VALIDATION_ERROR',
  500: 'INTERNAL_ERROR',
  503: 'SERVICE_UNAVAILABLE',
}

/** Typed error surfaced by every API call in this app. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null
  readonly code: string
  readonly requestId: string | null
  readonly details: Record<string, unknown> | null

  constructor(init: {
    kind: ApiErrorKind
    status: number | null
    code: string
    message: string
    requestId?: string | null
    details?: Record<string, unknown> | null
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.kind = init.kind
    this.status = init.status
    this.code = init.code
    this.requestId = init.requestId ?? null
    this.details = init.details ?? null
  }

  /** True when the endpoint does not exist on this backend build. */
  get isMissingEndpoint(): boolean {
    return this.status === 404
  }

  /** True when the network failed, the request timed out, or the API is not ready. */
  get isUnavailable(): boolean {
    return this.kind !== 'http' || this.status === null || this.status >= 500
  }

  /** True when the caller is not authorized for this endpoint. */
  get isAuthFailure(): boolean {
    return this.status === 401 || this.status === 403
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

function describeValidationDetail(detail: unknown[]): string | null {
  const messages = detail
    .map((item) => asString(asRecord(item)?.msg))
    .filter((message): message is string => message !== null)
  if (messages.length === 0) return null
  return Array.from(new Set(messages)).join(' ')
}

function describeErrorPayload(
  payload: unknown,
  status: number,
): {
  code: string
  message: string
  requestId: string | null
  details: Record<string, unknown> | null
} {
  const fallbackCode = DEFAULT_CODE_BY_STATUS[status] ?? `HTTP_${status}`
  const envelope = asRecord(payload) as BackendErrorEnvelope | null
  const error = asRecord(envelope?.error)

  if (error) {
    return {
      code: asString(error.code) ?? fallbackCode,
      message: asString(error.message) ?? 'The request failed.',
      requestId: asString(error.request_id),
      details: asRecord(error.details),
    }
  }

  const detail = envelope?.detail
  const plainDetail = asString(detail)
  if (plainDetail) {
    return { code: fallbackCode, message: plainDetail, requestId: null, details: null }
  }
  if (Array.isArray(detail)) {
    return {
      code: 'VALIDATION_ERROR',
      message: describeValidationDetail(detail) ?? 'The request failed validation.',
      requestId: null,
      details: null,
    }
  }
  return { code: fallbackCode, message: 'The request failed.', requestId: null, details: null }
}

/**
 * Direct browser request to the FastAPI service.
 *
 * Adds the configured base URL, JSON headers, a timeout/abort signal, and an
 * optional Idempotency-Key. All failures are normalized into {@link ApiError}.
 */
export async function apiFetch<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const timeoutMs = options.timeoutMs ?? API_TIMEOUT_MS
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`
  const controller = new AbortController()
  let timedOut = false

  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const externalSignal = options.signal
  const forwardAbort = () => controller.abort()
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort()
    else externalSignal.addEventListener('abort', forwardAbort)
  }

  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers }

  let body: string | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey
  }

  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    })

    if (!response.ok) {
      const raw = await response.text().catch(() => '')
      let payload: unknown = null
      if (raw) {
        try {
          payload = JSON.parse(raw)
        } catch {
          payload = { detail: raw }
        }
      }
      const described = describeErrorPayload(payload, response.status)
      throw new ApiError({
        kind: 'http',
        status: response.status,
        code: described.code,
        message: described.message,
        requestId: described.requestId,
        details: described.details,
      })
    }

    if (response.status === 204) return undefined as T

    const text = await response.text()
    return (text ? JSON.parse(text) : undefined) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (timedOut) {
      throw new ApiError({
        kind: 'timeout',
        status: null,
        code: 'TIMEOUT',
        message: `The request to ${path} timed out after ${timeoutMs}ms.`,
      })
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError({
        kind: 'aborted',
        status: null,
        code: 'ABORTED',
        message: `The request to ${path} was aborted.`,
      })
    }
    throw new ApiError({
      kind: 'network',
      status: null,
      code: 'NETWORK_ERROR',
      message: error instanceof Error ? error.message : `Could not reach ${API_BASE_URL}.`,
    })
  } finally {
    clearTimeout(timer)
    if (externalSignal) externalSignal.removeEventListener('abort', forwardAbort)
  }
}

export function apiGet<T>(path: string, options: Omit<ApiRequestOptions, 'method' | 'body'> = {}) {
  return apiFetch<T>(path, { ...options, method: 'GET' })
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  options: Omit<ApiRequestOptions, 'method' | 'body'> = {},
) {
  return apiFetch<T>(path, { ...options, method: 'POST', body })
}

export async function apiFetchBlob(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
  const timeoutMs = options.timeoutMs ?? API_TIMEOUT_MS
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers: { Accept: 'application/pdf, application/octet-stream', ...options.headers },
      signal: controller.signal,
    })
    if (!response.ok) {
      const raw = await response.text().catch(() => '')
      let payload: unknown = null
      if (raw) {
        try { payload = JSON.parse(raw) } catch { payload = { detail: raw } }
      }
      const described = describeErrorPayload(payload, response.status)
      throw new ApiError({
        kind: 'http',
        status: response.status,
        code: described.code,
        message: described.message,
        requestId: described.requestId,
        details: described.details,
      })
    }
    return await response.blob()
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (timedOut) throw new ApiError({ kind: 'timeout', status: null, code: 'TIMEOUT', message: `The request to ${path} timed out after ${timeoutMs}ms.` })
    if (error instanceof Error && error.name === 'AbortError') throw new ApiError({ kind: 'aborted', status: null, code: 'ABORTED', message: `The request to ${path} was aborted.` })
    throw new ApiError({ kind: 'network', status: null, code: 'NETWORK_ERROR', message: error instanceof Error ? error.message : `Could not reach ${API_BASE_URL}.` })
  } finally {
    clearTimeout(timer)
  }
}