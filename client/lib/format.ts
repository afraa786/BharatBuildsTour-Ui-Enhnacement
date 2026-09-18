/**
 * Display-only formatting helpers.
 *
 * The backend is the source of truth for money. These helpers only render values
 * the backend already computed (paise integers) and never calculate totals, tax,
 * discounts, or approval decisions.
 */

const INR = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const BUSINESS_TIME_ZONE = 'Asia/Kolkata'

/** Render integer paise as an Indian-format rupee string, e.g. 560000 -> "₹5,600". */
export function formatINR(paise: number | null | undefined): string {
  if (typeof paise !== 'number' || !Number.isFinite(paise)) return '—'
  return INR.format(paise / 100)
}

/** Human readable count, e.g. 1240000 -> "12.4L" is avoided; plain grouping is used. */
export function formatCount(value: number): string {
  return new Intl.NumberFormat('en-IN').format(value)
}

/** Render a backend ISO timestamp as a business-timezone clock time, e.g. "14:04:02". */
export function formatTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: BUSINESS_TIME_ZONE,
  }).format(date)
}

/** Render a backend ISO timestamp as a short business-timezone date, e.g. "Sep 17". */
export function formatShortDate(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: BUSINESS_TIME_ZONE,
  }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: BUSINESS_TIME_ZONE,
  }).format(date)
}

function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** Turn an UPPER_SNAKE status/enum value into a readable label. */
export function humanize(value: string | null | undefined): string {
  if (!value) return '—'
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ')
}
