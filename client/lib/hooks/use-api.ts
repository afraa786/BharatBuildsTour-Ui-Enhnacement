'use client'

/**
 * Minimal data-fetching helpers for the control room.
 *
 * These wrap the typed functions in `lib/api/endpoints.ts` and expose the four
 * UI states every connected screen needs: loading, ready, empty, error. They do
 * not cache or retry automatically; `reload()` is explicit so the operator stays
 * in control of what the screen is showing.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '@/lib/api/client'
import type { ApiResult, DataSource } from '@/lib/api/types'

export type ResourceStatus = 'loading' | 'ready' | 'empty' | 'error'

export interface ResourceState<T> {
  status: ResourceStatus
  data: T | null
  /** `backend` or `mock`, so the UI can label fixture data honestly. */
  source: DataSource | null
  /** Set when the screen is showing a fixture because the endpoint is missing. */
  missingEndpoint: string | null
  error: ApiError | null
  reload: () => void
}

/** Normalize any thrown value into the typed ApiError surface. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  return new ApiError({
    kind: 'network',
    status: null,
    code: 'UNEXPECTED',
    message: error instanceof Error ? error.message : 'An unexpected error occurred.',
  })
}

/**
 * Run `load` once on mount (and again after `reload()`), tracking its state.
 *
 * `load` and `isEmpty` are read through refs so an inline arrow function does
 * not restart the request on every render.
 */
export function useApiResource<T>(
  load: () => Promise<ApiResult<T>>,
  isEmpty: (data: T) => boolean = () => false,
): ResourceState<T> {
  const loadRef = useRef(load)
  const isEmptyRef = useRef(isEmpty)
  const [state, setState] = useState<Omit<ResourceState<T>, 'reload'>>({
    status: 'loading',
    data: null,
    source: null,
    missingEndpoint: null,
    error: null,
  })
  const [nonce, setNonce] = useState(0)

  // Keep the latest callbacks without restarting the effect. Declared before the
  // loader effect so the ref holds the current function on first run.
  useEffect(() => {
    loadRef.current = load
  }, [load])
  useEffect(() => {
    isEmptyRef.current = isEmpty
  }, [isEmpty])

  useEffect(() => {
    let active = true
    setState({ status: 'loading', data: null, source: null, missingEndpoint: null, error: null })

    loadRef
      .current()
      .then((result) => {
        if (!active) return
        setState({
          status: isEmptyRef.current(result.data) ? 'empty' : 'ready',
          data: result.data,
          source: result.source,
          missingEndpoint: result.missingEndpoint ?? null,
          error: null,
        })
      })
      .catch((error: unknown) => {
        if (!active) return
        setState({
          status: 'error',
          data: null,
          source: null,
          missingEndpoint: null,
          error: toApiError(error),
        })
      })

    return () => {
      active = false
    }
  }, [nonce])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return { ...state, reload }
}

export interface ActionState {
  pending: boolean
  error: ApiError | null
  reset: () => void
}

/**
 * Track a mutation (approve, reject, create link, generate invoice).
 *
 * Returns `null` instead of throwing so click handlers can branch on the result;
 * the failure is exposed through `error` for inline messaging.
 */
export function useApiAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
): ActionState & { run: (...args: TArgs) => Promise<TResult | null> } {
  const actionRef = useRef(action)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    actionRef.current = action
  }, [action])

  const run = useCallback(async (...args: TArgs): Promise<TResult | null> => {
    setPending(true)
    setError(null)
    try {
      return await actionRef.current(...args)
    } catch (caught) {
      setError(toApiError(caught))
      return null
    } finally {
      setPending(false)
    }
  }, [])

  const reset = useCallback(() => setError(null), [])

  return { pending, error, reset, run }
}