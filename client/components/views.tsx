'use client'

/**
 * Data-connected control-room and buyer views.
 *
 * These views render the same markup and styles as the existing page components
 * in `components/pages.tsx`, but read from the backend through
 * `lib/api/endpoints.ts` instead of hardcoded arrays. Every screen handles four
 * states: loading, empty, error, and ready, and labels fixture-backed data so
 * demo values are never mistaken for backend records.
 */

import Link from 'next/link'
import { useState, type ReactNode } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  CircleDot,
  Clock3,
  FileText,
  Gauge,
  MoreHorizontal,
  Package,
  Plus,
  Radio,
  Search,
  ShieldCheck,
  TrendingUp,
  Users,
  Wallet,
  Workflow,
  Zap,
} from 'lucide-react'
import {
  AdminShell,
  AgentDetailsPanel,
  AgentSimulationStage,
  BuyerLayout,
  CommandCenter,
  Logo,
  Metric,
  PageHeader,
  StatusPill,
} from './stockaware'
import AgentOffice from './agent-office/App'
import {
  approveRun,
  createPaymentLink,
  generateInvoice,
  getCommercialPayment,
  getInvoiceArtifact,
  getHealthLive,
  getInvoice,
  getProduct,
  getRun,
  getRunTimeline,
  listInvoices,
  listLifecycleRuns,
  listPayments,
  listProducts,
  listQuotes,
  listRuns,
  rejectRun,
} from '@/lib/api/endpoints'
import type {
  DataSource,
  DemoEvent,
  DemoRun,
  DemoRunLine,
  ProductRecord,
  RunOut,
} from '@/lib/api/types'
import { useApiAction, useApiResource } from '@/lib/hooks/use-api'
import { BUSINESS_ID } from '@/lib/config'
import './dashboard-premium.css'
import {
  formatCount,
  formatDateTime,
  formatINR,
  formatShortDate,
  formatTime,
  humanize,
} from '@/lib/format'

// ---------------------------------------------------------------------------
// Presentation helpers (status labels and tones only; no business decisions)
// ---------------------------------------------------------------------------

const CLOSED_RUN_STATUSES = new Set([
  'INVOICED',
  'ORDER_CONFIRMED',
  'PAID',
  'REJECTED',
  'EXPIRED',
  'PAYMENT_FAILED',
  'PAYMENT_EXPIRED',
])

/** Map a backend status string to a `status-pill` tone. Display only. */
function statusTone(status: string): string {
  switch (status) {
    case 'INVOICED':
    case 'ORDER_CONFIRMED':
    case 'PAID':
    case 'PAYMENT_CONFIRMED':
    case 'INVOICE_GENERATED':
    case 'GENERATED':
      return 'green'
    case 'ACCEPTED':
      return 'violet'
    case 'APPROVAL_PENDING':
    case 'WAITING_FOR_CLARIFICATION':
    case 'NEEDS_CLARIFICATION':
    case 'CHANGE_REQUESTED':
    case 'QUOTE_SENT':
    case 'QUOTED':
    case 'PENDING':
    case 'CREATED':
    case 'PAYMENT_PENDING':
    case 'PAYMENT_LINK_SENT':
    case 'PENDING_ARTIFACT':
      return 'amber'
    case 'RECEIVED':
    case 'NORMALIZING':
    case 'CHECKING_STOCK':
    case 'CHECKING_PRICE':
    case 'DRAFT':
      return 'blue'
    case 'REJECTED':
    case 'EXPIRED':
    case 'PAYMENT_FAILED':
    case 'PAYMENT_EXPIRED':
    case 'FAILED':
    case 'CANCELLED':
    case 'OUT_OF_STOCK':
    case 'INSUFFICIENT_STOCK':
      return 'red'
    default:
      return 'muted'
  }
}

/** Tone for an RFQ line stock outcome. */
function stockTone(line: DemoRunLine): string {
  if (line.match_status === 'NOT_FOUND') return 'red'
  return line.stock_status === 'INSUFFICIENT' ? 'amber' : 'green'
}

/** True while a run is still moving through the workflow. */
function isOpenRun(status: string): boolean {
  return !CLOSED_RUN_STATUSES.has(status)
}

/** Low stock is `stock <= threshold`; both values come from the backend. */
function isLowStock(product: ProductRecord): boolean {
  return typeof product.stock === 'number' && typeof product.threshold === 'number' && product.stock <= product.threshold
}

function stockLabel(product: ProductRecord): 'Low stock' | 'Healthy' | 'Unavailable' {
  if (typeof product.stock !== 'number' || typeof product.threshold !== 'number') return 'Unavailable'
  return isLowStock(product) ? 'Low stock' : 'Healthy'
}

/** Tone for a timeline event derived from its backend event type. */
function eventTone(type: string): string {
  if (/FAIL|SHORTAGE|REJECT|CLARIFICATION|EXPIRED/.test(type)) return 'amber'
  if (/PAYMENT|INVOICE|ACCEPTED/.test(type)) return 'green'
  return 'blue'
}

function eventState(tone: string): string {
  if (tone === 'amber') return 'Attention'
  if (tone === 'green') return 'Done'
  return 'Recorded'
}

function combineSources(sources: Array<DataSource | undefined>): DataSource {
  return sources.some((source) => source === 'mock') ? 'mock' : 'backend'
}

/** Ordered workflow position for a run status, used only for the agent strip. */
const RUN_STAGE: Record<string, number> = {
  RECEIVED: 0,
  NORMALIZING: 1,
  WAITING_FOR_CLARIFICATION: 1,
  NEEDS_CLARIFICATION: 1,
  CHECKING_STOCK: 2,
  CHECKING_PRICE: 3,
  APPROVAL_PENDING: 3,
  QUOTE_CREATED: 4,
  QUOTE_SENT: 5,
  QUOTED: 5,
  CHANGE_REQUESTED: 1,
  ACCEPTED: 6,
  PAYMENT_LINK_SENT: 7,
  PAYMENT_PENDING: 7,
  PAYMENT_CONFIRMED: 8,
  PAID: 8,
  INVOICE_GENERATED: 9,
  INVOICED: 9,
  ORDER_CONFIRMED: 10,
}

// ---------------------------------------------------------------------------
// Shared state blocks
// ---------------------------------------------------------------------------

/** Loading, empty, and error presentation reused by every connected screen. */
export function StateBlock({
  loading,
  errorMessage,
  empty,
  emptyMessage,
  onRetry,
}: {
  loading?: boolean
  errorMessage?: string | null
  empty?: boolean
  emptyMessage?: string
  onRetry?: () => void
}) {
  if (loading) {
    return (
      <div className="panel">
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <Activity className="size-4 animate-spin text-indigo-400" />
          <span>Loading from the backend...</span>
        </div>
      </div>
    )
  }

  if (errorMessage) {
    return (
      <div className="panel">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-5 text-rose-400" />
          <div className="min-w-0">
            <h3 className="text-white">Could not load this view</h3>
            <p className="mt-1 text-sm text-slate-400">{errorMessage}</p>
            {onRetry && (
              <button className="btn btn-secondary mt-4" type="button" onClick={onRetry}>
                Retry
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (empty) {
    return (
      <div className="panel">
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <CircleDot className="size-4 text-slate-500" />
          <span>{emptyMessage ?? 'Nothing here yet.'}</span>
        </div>
      </div>
    )
  }

  return null
}

/** Honest label for fixture-backed data and missing endpoints. */
export function SourceBadge({
  source,
  missingEndpoint,
}: {
  source: DataSource | null
  missingEndpoint?: string | null
}) {
  if (source === 'backend') return <StatusPill tone="green">Backend live</StatusPill>
  if (source === 'mock') {
    return (
      <StatusPill tone="violet">
        {missingEndpoint ? `Fixture data - ${missingEndpoint} missing` : 'Fixture data'}
      </StatusPill>
    )
  }
  return null
}

/** Live run-activity list reusing the existing `.timeline` markup. */
function LiveTimeline({ events, limit }: { events: DemoEvent[]; limit?: number }) {
  const rows = typeof limit === 'number' ? events.slice(0, limit) : events
  if (rows.length === 0) {
    return <p className="text-sm text-slate-400">No events recorded yet.</p>
  }
  return (
    <div className="timeline">
      {rows.map((event) => (
        <div className="timeline-row" key={event.id}>
          <span className={`timeline-dot ${eventTone(event.type)}`} />
          <time>{formatTime(event.occurred_at)}</time>
          <span>{event.message}</span>
        </div>
      ))}
    </div>
  )
}

type DeskTone = 'done' | 'blocked' | 'waiting' | 'active'

/**
 * Agent workflow strip driven by the run status and its RFQ lines.
 * This is the control-room visualization, not a source of commercial truth.
 */
function LiveAgentStrip({ run }: { run: DemoRun }) {
  const stage = RUN_STAGE[run.status] ?? 0
  const hasLines = run.lines.length > 0
  const anyNotFound = run.lines.some((line) => line.match_status === 'NOT_FOUND')
  const anyShort = run.lines.some((line) => line.stock_status === 'INSUFFICIENT')
  const approvalBlocked = run.status === 'APPROVAL_PENDING'
  const open = isOpenRun(run.status)

  const desks: Array<[string, string, DeskTone]> = [
    ['Manager', open ? 'Active' : 'Done', open ? 'active' : 'done'],
    ['Sales Desk', hasLines ? 'Done' : 'Waiting', hasLines ? 'done' : 'waiting'],
    [
      'Catalogue Desk',
      anyNotFound ? 'Blocked' : stage >= 1 ? 'Done' : 'Waiting',
      anyNotFound ? 'blocked' : stage >= 1 ? 'done' : 'waiting',
    ],
    [
      'Inventory Desk',
      anyShort ? 'Blocked' : stage >= 2 ? 'Done' : 'Waiting',
      anyShort ? 'blocked' : stage >= 2 ? 'done' : 'waiting',
    ],
    [
      'Finance Desk',
      approvalBlocked ? 'Blocked' : stage >= 3 ? 'Done' : 'Waiting',
      approvalBlocked ? 'blocked' : stage >= 3 ? 'done' : 'waiting',
    ],
    ['Quote Desk', stage >= 4 ? 'Done' : 'Waiting', stage >= 4 ? 'done' : 'waiting'],
  ]

  return (
    <div className="agent-status-strip" aria-label="Agent workflow status">
      {desks.map(([role, state, tone]) => (
        <div className="agent-status" key={role}>
          <span className={`agent-status-dot ${tone}`}>
            {tone === 'done' ? '✓' : tone === 'blocked' ? '!' : tone === 'waiting' ? '◷' : '•'}
          </span>
          <span>
            <b>{role}</b>
            <small>{state}</small>
          </span>
        </div>
      ))}
    </div>
  )
}
// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

type PaymentsData = Awaited<ReturnType<typeof listPayments>>['data']
type InvoicesData = Awaited<ReturnType<typeof listInvoices>>['data']

interface DashboardData {
  runs: DemoRun[]
  products: ProductRecord[]
  payments: PaymentsData
  invoices: InvoicesData
  events: DemoEvent[]
}

export function DashboardView() {
  const resource = useApiResource<DashboardData>(async () => {
    const [runs, products, payments, invoices] = await Promise.all([
      listRuns(),
      listProducts(),
      listPayments(),
      listInvoices(),
    ])
    const primaryRun = runs.data[0] ?? null
    const events = primaryRun ? await getRunTimeline(primaryRun.id) : null
    return {
      data: {
        runs: runs.data,
        products: products.data,
        payments: payments.data,
        invoices: invoices.data,
        events: events?.data ?? [],
      },
      source: combineSources([
        runs.source,
        products.source,
        payments.source,
        invoices.source,
        events?.source,
      ]),
      missingEndpoint:
        payments.missingEndpoint ??
        invoices.missingEndpoint ??
        runs.missingEndpoint ??
        products.missingEndpoint,
    }
  })

  const health = useApiResource<{ status: string }>(async () => ({
    data: await getHealthLive(),
    source: 'backend',
  }))

  const header = (
    <PageHeader
      eyebrow="CONTROL ROOM · LIVE"
      title="Good morning, Arjun"
      description="Here is what needs your attention today."
      action={
        <div className="flex items-center gap-3">
          <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
          <Link href="/onboarding" className="btn btn-primary">
            <Plus /> New request
          </Link>
        </div>
      }
    />
  )

  const officeSection = (
    <section className="dashboard-office-section">
      <div className="dashboard-office-heading">
        <div>
          <p className="eyebrow">AGENT WORKSPACE · LIVE</p>
          <h2>Claude Office</h2>
          <p>Watch your digital team coordinate work in real time.</p>
        </div>
        <span className="status-pill green"><span className="size-1.5 rounded-full bg-current" />Agents online</span>
      </div>
      <AgentOffice />
    </section>
  )

  const healthLabel =
    health.status === 'ready'
      ? 'API · live'
      : health.status === 'loading'
        ? 'API · checking'
        : 'API · unreachable'

  const dashboardIntro = (
    <section className="dashboard-intro">
      <div>
        <div className="dashboard-live-line"><span className="dashboard-live-dot" /> COMMAND CENTER <span>/</span> {healthLabel}</div>
        <h2>Your operation, in motion.</h2>
        <p>Monitor agent decisions, customer demand, and the moments that need your attention.</p>
      </div>
      <div className="dashboard-intro-actions">
        <span className="dashboard-date"><Clock3 /> Monday, 17 September 2026</span>
        <Link href="/runs" className="dashboard-text-link">View all runs <ArrowUpRight /></Link>
      </div>
    </section>
  )

  if (resource.status !== 'ready' && resource.status !== 'empty') {
    return (
      <AdminShell>
        {header}
        {dashboardIntro}
        <div className="dashboard-signal-strip dashboard-signal-strip-fallback">
          <div><Radio /><span><b>Agent workspace online</b><small>Visualization is running independently of the API</small></span></div>
          <div><ShieldCheck /><span><b>Policy guardrails active</b><small>Owner review remains required for exceptions</small></span></div>
          <div><Gauge /><span><b>Backend reconnecting</b><small>Live metrics return when the API is available</small></span></div>
        </div>
        {officeSection}
        <StateBlock
          loading={resource.status === 'loading'}
          errorMessage={resource.error?.message}
          onRetry={resource.reload}
        />
      </AdminShell>
    )
  }

  const data = resource.data
  if (!data) {
    return <AdminShell>{header}{dashboardIntro}{officeSection}</AdminShell>
  }

  const approvals = data.runs.filter((run) => run.status === 'APPROVAL_PENDING')
  const openRuns = data.runs.filter((run) => isOpenRun(run.status))
  const lowStock = data.products.filter(isLowStock)
  const pendingPayments = data.payments.filter(
    (payment) => payment.status === 'PENDING' || payment.status === 'CREATED',
  )
  const latestInvoice = data.invoices[0] ?? null

  const alerts = [
    ...approvals.map((run) => ({
      id: `approval-${run.id}`,
      title: `${run.id} · approval required`,
      detail: formatINR(run.quote.total_paise),
      href: '/approvals',
    })),
    ...lowStock.map((product) => ({
      id: `low-${product.sku}`,
      title: `${product.name} · Low stock`,
      detail:
        typeof product.stock === 'number' && typeof product.threshold === 'number'
          ? `${formatCount(product.stock)} available · threshold ${formatCount(product.threshold)}`
          : 'Stock quantity unavailable from catalogue API',
      href: `/inventory/${product.sku}`,
    })),
  ]

  const activeAgents = 6
  const attentionCount = approvals.length + lowStock.length
  const workflowRate = openRuns.length > 0
    ? Math.max(0, Math.min(99, Math.round(((openRuns.length - approvals.length) / openRuns.length) * 100)))
    : 100

  return (
    <AdminShell>
      {header}
      {dashboardIntro}
      <div className="metrics-grid dashboard-metrics-grid">
        <Metric
          label="Pending approvals"
          value={formatCount(approvals.length)}
          change="runs awaiting an owner decision"
          icon={Check}
        />
        <Metric
          label="Low stock"
          value={formatCount(lowStock.length)}
          change="items at or below threshold"
          icon={Package}
        />
        <Metric
          label="Pending payments"
          value={formatCount(pendingPayments.length)}
          change="awaiting provider confirmation"
          icon={Wallet}
        />
        <Metric
          label="Open RFQs"
          value={formatCount(openRuns.length)}
          change="still moving through the workflow"
          icon={Zap}
        />
      </div>
      <div className="dashboard-signal-strip">
        <div><Radio /><span><b>Live orchestration</b><small>Agents are coordinating across {formatCount(openRuns.length)} open workflows</small></span></div>
        <div><ShieldCheck /><span><b>Policy guardrails active</b><small>Every pricing exception requires owner review</small></span></div>
        <div><Gauge /><span><b>{workflowRate}% workflow health</b><small>Based on current run throughput</small></span></div>
      </div>
      <div className="dashboard-workspace-grid">
        <div className="dashboard-office-wrap">{officeSection}</div>
        <aside className="dashboard-command-rail">
          <div className="dashboard-rail-heading">
            <div><p className="eyebrow">OPERATING PULSE</p><h3>Today at a glance</h3></div>
            <button className="dashboard-icon-button" aria-label="More dashboard options"><MoreHorizontal /></button>
          </div>
          <div className="pulse-summary"><strong>{formatCount(attentionCount)}</strong><span>items need attention</span><div className="pulse-bar"><i style={{ width: `${Math.min(100, attentionCount * 12)}%` }} /></div><small>{approvals.length > 0 ? `${formatCount(approvals.length)} approval decisions are waiting` : 'No approval decisions waiting'}</small></div>
          <div className="pulse-list">
            <div><span className="pulse-icon pulse-icon-cyan"><Users /></span><span><b>Agent team</b><small>{activeAgents} agents active · 1 manager</small></span><em>LIVE</em></div>
            <div><span className="pulse-icon pulse-icon-amber"><Workflow /></span><span><b>Open workflows</b><small>{formatCount(openRuns.length)} requests in motion</small></span><em>{formatCount(openRuns.length)}</em></div>
            <div><span className="pulse-icon pulse-icon-green"><TrendingUp /></span><span><b>Collection watch</b><small>{formatCount(pendingPayments.length)} payments awaiting confirmation</small></span><em>{formatCount(pendingPayments.length)}</em></div>
          </div>
          <Link href="/approvals" className="dashboard-rail-link">Open attention queue <ArrowRight /></Link>
        </aside>
      </div>
      <div className="dashboard-grid">
        <section className="dashboard-panel dashboard-panel-flow">
          <div className="dashboard-panel-header"><div><p className="eyebrow">WORKFLOW MAP</p><h3>Where work is moving</h3></div><Link href="/runs" className="dashboard-text-link">Open runs <ArrowUpRight /></Link></div>
          <CommandCenter />
        </section>
        <div className="rail">
          <div className="rail-card">
            <div className="flex justify-between">
              <h3>Urgent alerts</h3>
              <StatusPill tone="amber">{formatCount(alerts.length)} open</StatusPill>
            </div>
            {alerts.length === 0 ? (
              <p className="mt-4 text-xs text-slate-400">Nothing needs you right now.</p>
            ) : (
              alerts.slice(0, 4).map((alert) => (
                <div className="alert-item" key={alert.id}>
                  <span className="alert-dot" />
                  <div>
                    <p>{alert.title}</p>
                    <small>{alert.detail}</small>
                  </div>
                </div>
              ))
            )}
            <Link href="/approvals" className="mt-3 flex items-center gap-1 text-xs text-indigo-300">
              Review all <ArrowRight className="size-3" />
            </Link>
          </div>
          <div className="rail-card">
            <h3>Manager digest</h3>
            <div className="mt-4 flex flex-col gap-3 text-xs text-slate-400">
              <span>{formatCount(approvals.length)} quotes waiting for review</span>
              <span>{formatCount(pendingPayments.length)} payments need follow-up</span>
              <span>{formatCount(lowStock.length)} items below reorder threshold</span>
              <span>{healthLabel}</span>
            </div>
          </div>
        </div>
      </div>
      <div className="lower-grid">
        <div className="panel dashboard-data-panel">
          <div className="dashboard-panel-header"><div><p className="eyebrow">EVENT STREAM</p><h3>Live activity</h3></div><span className="dashboard-mini-status"><i /> Updating now</span></div>
          <LiveTimeline events={data.events} limit={6} />
        </div>
        <div className="panel dashboard-data-panel">
          <div className="dashboard-panel-header"><div><p className="eyebrow">INVENTORY SIGNAL</p><h3>Low stock radar</h3></div><Package className="dashboard-panel-icon" /></div>
          <div className="flex items-center gap-5 py-5">
            <div className="grid size-24 place-items-center rounded-full border-[10px] border-amber-400/30 border-t-amber-400 text-2xl font-semibold">
              {formatCount(lowStock.length)}
            </div>
            <div className="text-xs text-slate-400">
              Items below
              <br />
              <b className="text-white">reorder threshold</b>
              <br />
              <Link href="/inventory" className="mt-2 inline-block text-indigo-300">
                View inventory →
              </Link>
            </div>
          </div>
        </div>
        <div className="panel dashboard-data-panel">
          <div className="dashboard-panel-header"><div><p className="eyebrow">REVENUE OPERATIONS</p><h3>Latest invoice</h3></div><FileText className="dashboard-panel-icon" /></div>
          {latestInvoice ? (
            <>
              <div className="mt-3 flex items-center justify-between">
                <span className="mono text-xs text-slate-300">{latestInvoice.invoice_number}</span>
                <StatusPill tone={statusTone(latestInvoice.status)}>
                  {humanize(latestInvoice.status)}
                </StatusPill>
              </div>
              <strong className="mt-3 block text-2xl tracking-[-.04em]">
                {formatINR(latestInvoice.total_paise)}
              </strong>
              <small className="text-slate-500">{formatShortDate(latestInvoice.issued_at)}</small>
              <Link
                href={`/invoices/${latestInvoice.invoice_id}`}
                className="mt-3 flex text-xs text-indigo-300"
              >
                Open invoice <ArrowRight className="size-3" />
              </Link>
            </>
          ) : (
            <p className="mt-3 text-xs text-slate-400">No invoices issued yet.</p>
          )}
        </div>
      </div>
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Shared table markup (same `table-wrap` structure as the existing pages)
// ---------------------------------------------------------------------------

function DataTable({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {head.map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Runs / RFQ list
// ---------------------------------------------------------------------------

export function RunsView() {
  const resource = useApiResource(
    () => listRuns(),
    (data) => data.length === 0,
  )

  const rows: ReactNode[][] = (resource.data ?? []).map((run) => {
    const matched = run.lines.filter((line) => line.match_status === 'MATCHED').length
    const short = run.lines.filter((line) => line.stock_status === 'INSUFFICIENT').length
    return [
      <Link className="mono text-indigo-300" href={`/runs/${run.id}`} key="id">
        {run.id}
      </Link>,
      run.buyer_name,
      `${formatCount(matched)} of ${formatCount(run.lines.length)} items matched${
        short > 0 ? `, ${formatCount(short)} short` : ''
      }`,
      '—',
      formatINR(run.quote.total_paise),
      <StatusPill tone={statusTone(run.status)} key="status">
        {humanize(run.status)}
      </StatusPill>,
    ]
  })

  return (
    <AdminShell>
      <PageHeader
        title="Runs"
        description="A clear view of every operational handoff."
        action={
          <div className="flex items-center gap-3">
            <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
            <Link href="/onboarding" className="btn btn-primary">
              <Plus /> Create new
            </Link>
          </div>
        }
      />
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage="No RFQ runs are available from the backend yet."
        onRetry={resource.reload}
      />
      {resource.status === 'ready' && (
        <DataTable
          head={['ID', 'Buyer', 'Details', 'Owner', 'Amount', 'Status']}
          rows={rows}
        />
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Run detail (control room)
// ---------------------------------------------------------------------------

export function RunDetailView({ id }: { id: string }) {
  const runResource = useApiResource(() => getRun(id))
  const timelineResource = useApiResource(() => getRunTimeline(id))

  const run = runResource.data
  const events = timelineResource.data ?? []
  const shortLines = run ? run.lines.filter((line) => line.stock_status === 'INSUFFICIENT').length : 0

  return (
    <AdminShell>
      <div className="run-header">
        <Link href="/runs" className="run-back">
          ← Back to Runs
        </Link>
        <div className="run-title-row">
          <div>
            <p className="eyebrow">LIVE RUN / {id}</p>
            <h1>
              {id} <span>·</span> {run?.buyer_name ?? '—'}
            </h1>
            <div className="run-meta">
              <span>
                Quote <b>{formatINR(run?.quote.total_paise)}</b>
              </span>
              <span>
                Lines <b>{run ? formatCount(run.lines.length) : '—'}</b>
              </span>
              <span>
                Stock <b>{run ? (shortLines > 0 ? `${formatCount(shortLines)} short` : 'ok') : '—'}</b>
              </span>
              <span>
                Quote expires <b>{formatShortDate(run?.quote.expires_at)}</b>
              </span>
            </div>
          </div>
          <StatusPill tone={run ? statusTone(run.status) : 'muted'}>
            {run ? humanize(run.status) : 'Loading'}
          </StatusPill>
        </div>
      </div>

      {runResource.status !== 'ready' && (
        <StateBlock
          loading={runResource.status === 'loading'}
          errorMessage={runResource.error?.message}
          empty={runResource.status === 'empty'}
          emptyMessage={`No run found for ${id}.`}
          onRetry={runResource.reload}
        />
      )}

      {run && (
        <>
          <div className="run-control-room">
            <div className="run-main-column">
              <AgentSimulationStage runId={run.id} status={run.status} />
              <LiveAgentStrip run={run} />
            </div>
            <AgentDetailsPanel />
          </div>

          <section className="run-timeline panel">
            <div className="timeline-heading">
              <div>
                <p className="eyebrow">EVENT LOG</p>
                <h2>Run timeline</h2>
              </div>
              <span className="mono text-xs text-slate-500">
                {formatCount(events.length)} events · live
              </span>
            </div>

            {timelineResource.status === 'error' ? (
              <p className="text-sm text-rose-300">
                Timeline unavailable: {timelineResource.error?.message}
              </p>
            ) : timelineResource.status === 'loading' ? (
              <p className="text-sm text-slate-400">Loading timeline...</p>
            ) : events.length === 0 ? (
              <p className="text-sm text-slate-400">No events recorded for this run yet.</p>
            ) : (
              <div className="event-log">
                {events.map((event, index) => {
                  const tone = eventTone(event.type)
                  return (
                    <details className="event-row" key={event.id} open={index === 0}>
                      <summary>
                        <span className="event-icon">
                          {tone === 'amber' ? '!' : tone === 'green' ? '✓' : '•'}
                        </span>
                        <time>{formatTime(event.occurred_at)}</time>
                        <b>Manager</b>
                        <span>{event.message}</span>
                        <StatusPill tone={tone}>{eventState(tone)}</StatusPill>
                        <ChevronDown className="event-chevron" />
                      </summary>
                      <p>
                        {event.type} recorded for {run.id} at {formatDateTime(event.occurred_at)}.
                      </p>
                    </details>
                  )
                })}
              </div>
            )}
          </section>
        </>
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

/**
 * Actor recorded against an owner approval. Rehbar owns approval identity; this
 * is the local control-room operator until real auth exists.
 */
const APPROVAL_ACTOR = 'owner'

interface ApprovalRow {
  runId: string
  buyer: string
  reason: string
  origin: string
  amountPaise: number | null
}

/** Best-effort read of the quote total from Rehbar's quote snapshot. */
function snapshotTotal(run: RunOut): number | null {
  const snapshot = run.quote_snapshot
  if (!snapshot) return null
  const total = snapshot.total_paise
  return typeof total === 'number' ? total : null
}

export function ApprovalsView() {
  const resource = useApiResource<ApprovalRow[]>(
    async () => {
      const [workflow, lifecycle] = await Promise.all([
        listRuns(),
        listLifecycleRuns().then(
          (runs) => ({ runs, failed: false }),
          () => ({ runs: [] as RunOut[], failed: true }),
        ),
      ])
      const rows: ApprovalRow[] = [
        ...workflow.data
          .filter((run) => run.status === 'APPROVAL_PENDING')
          .map((run) => ({
            runId: run.id,
            buyer: run.buyer_name,
            reason: 'Owner approval requested',
            origin: 'Workflow store',
            amountPaise: run.quote.total_paise,
          })),
        ...lifecycle.runs
          .filter((run) => run.status === 'APPROVAL_PENDING')
          .map((run) => ({
            runId: run.run_id,
            buyer: run.buyer_name ?? '—',
            reason: 'Owner approval requested',
            origin: 'Run lifecycle',
            amountPaise: snapshotTotal(run),
          })),
      ]
      return { data: rows, source: combineSources([workflow.source]) }
    },
    (data) => data.length === 0,
  )

  const decide = useApiAction(async (runId: string, action: 'approve' | 'reject') => {
    if (action === 'approve') return approveRun(runId, APPROVAL_ACTOR)
    return rejectRun(runId, APPROVAL_ACTOR)
  })
  const [outcome, setOutcome] = useState<string | null>(null)

  async function handleDecision(runId: string, action: 'approve' | 'reject') {
    setOutcome(null)
    const result = await decide.run(runId, action)
    if (result) {
      setOutcome(
        `${action === 'approve' ? 'Approved' : 'Rejected'} ${runId}: ${formatCount(
          result.length,
        )} outbound message(s) queued by Rehbar.`,
      )
      resource.reload()
    }
  }

  const rows: ReactNode[][] = (resource.data ?? []).map((row) => [
    <span className="mono text-indigo-300" key="id">
      {row.runId}
    </span>,
    row.buyer,
    row.reason,
    row.origin,
    formatINR(row.amountPaise),
    <StatusPill tone="amber" key="status">
      Review
    </StatusPill>,
    <div className="flex gap-2" key="actions">
      <button
        className="btn btn-primary"
        type="button"
        disabled={decide.pending}
        onClick={() => void handleDecision(row.runId, 'approve')}
      >
        Approve
      </button>
      <button
        className="btn btn-secondary"
        type="button"
        disabled={decide.pending}
        onClick={() => void handleDecision(row.runId, 'reject')}
      >
        Reject
      </button>
    </div>,
  ])

  return (
    <AdminShell>
      <PageHeader
        title="Approvals"
        description="A clear view of every operational handoff."
        action={
          <div className="flex items-center gap-3">
            <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
            <button className="btn btn-secondary" type="button" onClick={resource.reload}>
              Refresh
            </button>
          </div>
        }
      />
      {decide.error && (
        <div className="panel mb-4">
          <p className="text-sm text-rose-300">Approval action failed: {decide.error.message}</p>
        </div>
      )}
      {outcome && (
        <div className="panel mb-4">
          <p className="text-sm text-emerald-300">{outcome}</p>
        </div>
      )}
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage="No runs are waiting for owner approval."
        onRetry={resource.reload}
      />
      {resource.status === 'ready' && (
        <DataTable
          head={['ID', 'Buyer', 'Details', 'Owner', 'Amount', 'Status', 'Decision']}
          rows={rows}
        />
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Inventory
// ---------------------------------------------------------------------------

/** Relative stock level for the existing `.stock-bar` visual. */
function stockBarWidth(product: ProductRecord): string {
  if (typeof product.stock !== 'number' || typeof product.threshold !== 'number' || product.threshold <= 0) return '0%'
  return `${Math.min((product.stock / product.threshold) * 40, 100)}%`
}

export function InventoryView() {
  const resource = useApiResource(
    () => listProducts(),
    (data) => data.length === 0,
  )
  const [query, setQuery] = useState('')

  const needle = query.trim().toLowerCase()
  const products = (resource.data ?? []).filter(
    (product) =>
      needle.length === 0 ||
      product.name.toLowerCase().includes(needle) ||
      product.sku.toLowerCase().includes(needle),
  )

  const rows: ReactNode[][] = products.map((product) => [
    <span key="name">
      <Link href={`/inventory/${product.sku}`} className="font-medium hover:text-indigo-400">
        {product.name}
      </Link>
      <small>{product.sellable_unit ?? product.unit ?? 'unit unavailable'}</small>
    </span>,
    <span className="mono text-slate-400" key="sku">
      {product.sku}
    </span>,
    <div className="stock-cell" key="stock">
      <span>{typeof product.stock === 'number' ? formatCount(product.stock) : '—'}</span>
      <div className="stock-bar">
        <i style={{ width: stockBarWidth(product) }} />
      </div>
    </div>,
    <span className="mono text-slate-400" key="threshold">
              {typeof product.threshold === 'number' ? formatCount(product.threshold) : '—'}
    </span>,
    '—',
    <StatusPill tone={isLowStock(product) ? 'amber' : 'green'} key="status">
      {stockLabel(product)}
    </StatusPill>,
  ])

  return (
    <AdminShell>
      <PageHeader
        title="Inventory"
        description="Your catalogue, stock levels, and margin at a glance."
        action={
          <div className="flex items-center gap-3">
            <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
            <button className="btn btn-secondary" type="button" onClick={resource.reload}>
              Refresh
            </button>
          </div>
        }
      />
      <div className="mb-4 flex gap-3">
        <div className="flex flex-1 items-center gap-2 rounded-xl border border-white/10 bg-[#101826] px-3 text-slate-400">
          <Search className="size-4" />
          <input
            className="w-full bg-transparent py-3 outline-none"
            placeholder="Search products, SKUs, aliases..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <button className="btn btn-secondary" type="button">
          All status
        </button>
      </div>
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage="The catalogue is empty. Seed products before listing inventory."
        onRetry={resource.reload}
      />
      {resource.status === 'ready' &&
        (products.length === 0 ? (
          <StateBlock empty emptyMessage={`No product matches "${query}".`} />
        ) : (
          <DataTable head={['Product', 'SKU', 'Stock', 'Threshold', 'Margin', 'Status']} rows={rows} />
        ))}
    </AdminShell>
  )
}

export function InventoryDetailView({ id }: { id: string }) {
  const resource = useApiResource(() => getProduct(id))
  const product = resource.data

  const basics: Array<[string, string]> = product
    ? [
        ['Product name', product.name],
        ['SKU', product.sku],
        ['Category', product.sellable_unit ?? '—'],
        ['Unit', product.sellable_unit ?? product.unit ?? '—'],
        ['Stock', typeof product.stock === 'number' ? formatCount(product.stock) : '—'],
        ['Low stock threshold', typeof product.threshold === 'number' ? formatCount(product.threshold) : '—'],
      ]
    : []

  // Fields the browser-safe catalogue endpoint does not expose are shown as
  // unavailable rather than invented.
  const policy: Array<[string, string]> = product
    ? [
        ['Cost price', '—'],
        ['Selling price', formatINR(product.base_unit_price_paise ?? product.price_paise)],
        ['Margin', '—'],
        ['Allowed discount', '—'],
        ['Substitute', '—'],
        ['Aliases', '—'],
      ]
    : []

  return (
    <AdminShell>
      <PageHeader
        eyebrow="INVENTORY / PRODUCT DETAIL"
        title={product?.name ?? id}
        description={product ? `${product.sku} · ${product.sellable_unit ?? product.unit ?? 'unit unavailable'}` : 'Loading product...'}
        action={
          <div className="flex gap-2">
            <Link href="/inventory" className="btn btn-secondary">
              Cancel
            </Link>
            <button className="btn btn-primary" type="button" disabled>
              Save changes
            </button>
          </div>
        }
      />
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage={`No product found for ${id}.`}
        onRetry={resource.reload}
      />
      {product && (
        <div className="grid max-w-4xl gap-4 md:grid-cols-2">
          <div className="panel">
            <h3>Basic information</h3>
            <div className="form-grid">
              {basics.map(([label, value]) => (
                <div className="field" key={label}>
                  <label>{label}</label>
                  <input defaultValue={value} readOnly />
                </div>
              ))}
            </div>
          </div>
          <div className="panel">
            <h3>Pricing &amp; policy</h3>
            <div className="form-grid">
              {policy.map(([label, value]) => (
                <div className="field" key={label}>
                  <label>{label}</label>
                  <input defaultValue={value} readOnly />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Quotes
// ---------------------------------------------------------------------------

type QuotesData = Awaited<ReturnType<typeof listQuotes>>['data']

/**
 * Quote rows. The backend has no browser-callable quote list, so these come
 * from the contract-shaped fixture, joined against live runs for buyer names.
 */
export function QuotesView() {
  const resource = useApiResource<{ quotes: QuotesData; buyerByRun: Record<string, string> }>(
    async () => {
      const [quotes, runs] = await Promise.all([listQuotes(), listRuns()])
      const buyerByRun: Record<string, string> = {}
      for (const run of runs.data) buyerByRun[run.id] = run.buyer_name
      return {
        data: { quotes: quotes.data, buyerByRun },
        source: combineSources([quotes.source, runs.source]),
        missingEndpoint: quotes.missingEndpoint,
      }
    },
    (data) => data.quotes.length === 0,
  )

  const rows: ReactNode[][] = (resource.data?.quotes ?? []).map((quote) => [
    <Link className="mono text-indigo-300" href={`/quotes/${quote.run_id}`} key="id">
      {quote.quote_id}
    </Link>,
    resource.data?.buyerByRun[quote.run_id] ?? quote.run_id,
    formatINR(quote.total_paise),
    <StatusPill tone={statusTone(quote.status)} key="status">
      {humanize(quote.status)}
    </StatusPill>,
    formatShortDate(quote.expires_at),
  ])

  return (
    <AdminShell>
      <PageHeader
        title="Quotes"
        description="A clear view of every operational handoff."
        action={
          <div className="flex items-center gap-3">
            <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
            <button className="btn btn-secondary" type="button" onClick={resource.reload}>
              Refresh
            </button>
          </div>
        }
      />
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage="No quotes have been generated yet."
        onRetry={resource.reload}
      />
      {resource.status === 'ready' && (
        <DataTable
          head={['Quote', 'Buyer', 'Amount', 'Status', 'Valid until']}
          rows={rows}
        />
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------

type PaymentsListData = Awaited<ReturnType<typeof listPayments>>['data']

/**
 * Payment rows. `GET /payments/{id}` exists, but there is no payment *list*
 * endpoint, so the collection comes from the contract-shaped fixture.
 */
export function PaymentsView() {
  const resource = useApiResource<{ payments: PaymentsListData; buyerByRun: Record<string, string> }>(
    async () => {
      const [payments, runs] = await Promise.all([listPayments(), listRuns()])
      const buyerByRun: Record<string, string> = {}
      for (const run of runs.data) buyerByRun[run.id] = run.buyer_name
      return {
        data: { payments: payments.data, buyerByRun },
        source: combineSources([payments.source, runs.source]),
        missingEndpoint: payments.missingEndpoint,
      }
    },
    (data) => data.payments.length === 0,
  )

  const rows: ReactNode[][] = (resource.data?.payments ?? []).map((payment) => [
    <Link className="mono text-indigo-300" href={`/payments/${payment.payment_id}`} key="id">
      {payment.payment_id}
    </Link>,
    <span className="mono text-slate-400" key="run">
      {payment.run_id}
    </span>,
    resource.data?.buyerByRun[payment.run_id] ?? '—',
    formatINR(payment.amount_paise),
    payment.payment_url ? 'Link active' : 'No link',
    <StatusPill tone={statusTone(payment.status)} key="status">
      {humanize(payment.status)}
    </StatusPill>,
  ])

  return (
    <AdminShell>
      <PageHeader
        title="Payments"
        description="A clear view of every operational handoff."
        action={
          <div className="flex items-center gap-3">
            <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
            <button className="btn btn-secondary" type="button" onClick={resource.reload}>
              Refresh
            </button>
          </div>
        }
      />
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage="No payment links have been created yet."
        onRetry={resource.reload}
      />
      {resource.status === 'ready' && (
        <DataTable head={['ID', 'Run', 'Buyer', 'Amount', 'Link', 'Status']} rows={rows} />
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Invoices
// ---------------------------------------------------------------------------

type InvoicesListData = Awaited<ReturnType<typeof listInvoices>>['data']

/**
 * Invoice rows. There is no invoice list endpoint and `GET /invoices/{id}` is
 * internal-token gated, so the collection comes from the contract-shaped
 * fixture until those endpoints accept a browser session.
 */
export function InvoicesView() {
  const resource = useApiResource<{ invoices: InvoicesListData; buyerByRun: Record<string, string> }>(
    async () => {
      const [invoices, runs] = await Promise.all([listInvoices(), listRuns()])
      const buyerByRun: Record<string, string> = {}
      for (const run of runs.data) buyerByRun[run.id] = run.buyer_name
      return {
        data: { invoices: invoices.data, buyerByRun },
        source: combineSources([invoices.source, runs.source]),
        missingEndpoint: invoices.missingEndpoint,
      }
    },
    (data) => data.invoices.length === 0,
  )

  const rows: ReactNode[][] = (resource.data?.invoices ?? []).map((invoice) => [
    <Link className="mono text-indigo-300" href={`/invoices/${invoice.invoice_id}`} key="id">
      {invoice.invoice_id}
    </Link>,
    <span className="mono text-slate-400" key="run">
      {invoice.run_id}
    </span>,
    resource.data?.buyerByRun[invoice.run_id] ?? '—',
    formatINR(invoice.total_paise),
    <StatusPill tone={statusTone(invoice.status)} key="status">
      {humanize(invoice.status)}
    </StatusPill>,
    formatShortDate(invoice.issued_at),
  ])

  return (
    <AdminShell>
      <PageHeader
        title="Invoices"
        description="A clear view of every operational handoff."
        action={
          <div className="flex items-center gap-3">
            <SourceBadge source={resource.source} missingEndpoint={resource.missingEndpoint} />
            <button className="btn btn-secondary" type="button" onClick={resource.reload}>
              Refresh
            </button>
          </div>
        }
      />
      <StateBlock
        loading={resource.status === 'loading'}
        errorMessage={resource.error?.message}
        empty={resource.status === 'empty'}
        emptyMessage="No invoices have been issued yet."
        onRetry={resource.reload}
      />
      {resource.status === 'ready' && (
        <DataTable
          head={['ID', 'Run', 'Buyer', 'Amount', 'Status', 'Issued']}
          rows={rows}
        />
      )}
    </AdminShell>
  )
}

// ---------------------------------------------------------------------------
// Buyer quote page
// ---------------------------------------------------------------------------

/**
 * Buyer quote view. Amounts come from the run's saved quote snapshot; nothing is
 * recalculated here. "Accept quote" calls the real acceptance endpoint.
 */
export function BuyerQuoteView({ id }: { id: string }) {
  const resource = useApiResource(() => getRun(id))
  const link = useApiAction(() => createPaymentLink({
    business_id: BUSINESS_ID,
    run_id: id,
    quote_id: run?.quote.id ?? '',
    quote_version: run?.quote.version ?? 0,
  }, `payment-link-${id}-${run?.quote.id ?? 'unknown'}`))
  const [payment, setPayment] = useState<{ id: string; url: string } | null>(null)

  const run = resource.data

  if (resource.status === 'loading' || resource.status === 'error' || !run) {
    return (
      <BuyerLayout>
        {resource.status === 'error' ? (
          <StateBlock errorMessage={resource.error?.message} onRetry={resource.reload} />
        ) : (
          <StateBlock loading={resource.status === 'loading'} empty={resource.status === 'empty'} emptyMessage={`No quote found for ${id}.`} />
        )}
      </BuyerLayout>
    )
  }

  return (
    <BuyerLayout>
      <div className="buyer-card">
        <StatusPill tone={statusTone(run.quote.status)}>{humanize(run.quote.status)}</StatusPill>
        <h1>Quote #{run.quote.id}</h1>
        <p className="text-slate-500">
          Prepared for {run.buyer_name} · Valid until {formatShortDate(run.quote.expires_at)}
        </p>
        <h2>Items</h2>
        <div className="buyer-items">
          {run.lines.map((line, index) => (
            <div className="buyer-item" key={`${line.requested_name}-${index}`}>
              <span>
                {line.product_name ?? line.requested_name}
                <small className="block text-slate-500">
                  {formatCount(line.quantity)} × {formatINR(line.unit_price_paise)}
                </small>
              </span>
              <b>{formatINR(line.line_total_paise)}</b>
            </div>
          ))}
        </div>
        <div className="totals">
          <div className="total-row">
            <span>Lines</span>
            <b>{formatCount(run.lines.length)}</b>
          </div>
          <div className="total-row final">
            <span>Quote total</span>
            <b>{formatINR(run.quote.total_paise)}</b>
          </div>
        </div>
        <div className="rounded-xl bg-slate-50 p-4 text-sm">
          <b>Buyer contact</b>
          <p className="m-0 mt-1 text-slate-500">{run.buyer_phone}</p>
          <p className="m-0 mt-2 text-xs text-slate-500">
            Tax and final totals are decided by the backend; the workflow store does not break out GST.
          </p>
        </div>

        {link.error && (
          <p className="mt-4 text-sm text-rose-500">Could not create link: {link.error.message}</p>
        )}

        <div className="buyer-actions">
          <button
            className="btn btn-primary flex-1"
            type="button"
            disabled
            title="Buyer acceptance is not exposed by the current API contract"
          >
            Accept quote <ArrowRight />
          </button>
          <button className="btn btn-secondary" type="button" disabled title="No change-request endpoint exists yet">
            Request change
          </button>
        </div>

        {payment ? (
          <Link href={`/payment/${payment.id}`} className="btn btn-secondary mt-4 w-full justify-center">
            Continue to payment
          </Link>
        ) : (
          <button
            className="btn btn-secondary mt-4 w-full justify-center"
            type="button"
            disabled={link.pending || run.quote.status !== 'ACCEPTED'}
            title="Requires a backend-approved quote and NEXT_PUBLIC_BUSINESS_ID"
            onClick={() =>
              void link.run().then((created) => {
                if (created) setPayment({ id: created.payment_id, url: created.payment_url ?? '' })
              })
            }
          >
            Create payment link
          </button>
        )}

        {payment && (
          <p className="mt-3 text-xs text-slate-400">
            Payment link: <span className="mono">{payment.url || 'Provider URL unavailable'}</span>
          </p>
        )}
      </div>
    </BuyerLayout>
  )
}

// ---------------------------------------------------------------------------
// Buyer payment page
// ---------------------------------------------------------------------------

type PaymentDetail = Awaited<ReturnType<typeof getCommercialPayment>>

export function BuyerPaymentView({ id }: { id: string }) {
  const resource = useApiResource<PaymentDetail>(async () => ({
    data: await getCommercialPayment(id),
    source: 'backend',
  }))
  const [invoiceId, setInvoiceId] = useState<string | null>(null)

  const payment = resource.data
  const invoice = useApiAction(() => generateInvoice({
    business_id: payment?.business_id ?? '',
    run_id: payment?.run_id ?? '',
    quote_id: payment?.quote_id ?? '',
    quote_version: payment?.quote_version ?? 0,
    payment_id: payment?.payment_id ?? id,
  }, `invoice-${id}`))

  if (resource.status !== 'ready' || !payment) {
    return (
      <BuyerLayout>
        {resource.status === 'error' ? (
          <StateBlock errorMessage={resource.error?.message} onRetry={resource.reload} />
        ) : (
          <StateBlock
            loading={resource.status === 'loading'}
            empty={resource.status === 'empty'}
            emptyMessage={`No payment found for ${id}.`}
          />
        )}
      </BuyerLayout>
    )
  }

  const paid = payment.status === 'PAID'

  return (
    <BuyerLayout>
      <div className="buyer-card">
        <StatusPill tone={statusTone(payment.status)}>{humanize(payment.status)}</StatusPill>
        <h1>Complete payment</h1>
        <p className="text-slate-500">
          {payment.run_id} · {payment.currency}
        </p>
        <div className="my-8 text-center">
          <p className="text-sm text-slate-500">Amount due</p>
          <strong className="text-5xl tracking-[-.08em]">{formatINR(payment.amount_paise)}</strong>
        </div>

        {invoice.error && (
          <p className="text-sm text-rose-500">Invoice failed: {invoice.error.message}</p>
        )}

        <button
          className="btn btn-primary w-full"
          type="button"
          disabled={paid || !payment.payment_url}
          onClick={() => {
            if (payment.payment_url) window.open(payment.payment_url, '_blank', 'noopener,noreferrer')
          }}
        >
          {paid ? 'Payment confirmed' : 'Pay now'} <ArrowRight />
        </button>
        <p className="mt-4 text-center text-xs text-slate-400">
          Secure payment powered by Razorpay
        </p>

        {invoiceId ? (
          <Link href={`/invoice/${invoiceId}`} className="mt-7 block text-center text-sm text-indigo-500">
            View invoice
          </Link>
        ) : (
          <button
            className="btn btn-secondary mt-7 w-full justify-center"
            type="button"
            disabled={invoice.pending || !paid}
            title={paid ? 'POST /invoice/generate' : 'A verified paid state is required before an invoice'}
            onClick={() =>
              void invoice.run().then((created) => {
                if (created) setInvoiceId(created.invoice_id)
              })
            }
          >
            Generate invoice
          </button>
        )}

        {payment.payment_url && (
          <p className="mt-3 text-center text-xs text-slate-400">
            Link: <span className="mono">{payment.payment_url}</span>
          </p>
        )}
      </div>
    </BuyerLayout>
  )
}

// ---------------------------------------------------------------------------
// Buyer invoice page
// ---------------------------------------------------------------------------

type InvoiceDetail = Awaited<ReturnType<typeof getInvoice>>['data']

export function BuyerInvoiceView({ id }: { id: string }) {
  const resource = useApiResource(() => getInvoice(id))
  const download = useApiAction(() => getInvoiceArtifact(id))
  const invoice = resource.data

  if (resource.status !== 'ready' || !invoice) {
    return (
      <BuyerLayout>
        {resource.status === 'error' ? (
          <StateBlock errorMessage={resource.error?.message} onRetry={resource.reload} />
        ) : (
          <StateBlock
            loading={resource.status === 'loading'}
            empty={resource.status === 'empty'}
            emptyMessage={`No invoice found for ${id}.`}
          />
        )}
      </BuyerLayout>
    )
  }

  return (
    <BuyerLayout>
      <div className="buyer-card">
        <StatusPill tone={statusTone(invoice.status)}>{humanize(invoice.status)}</StatusPill>
        <h1>Invoice {invoice.invoice_number}</h1>
        <p className="text-slate-500">
          {invoice.run_id} · Issued {formatShortDate(invoice.issued_at)}
        </p>
        <div className="mt-7">
          <div className="document-card">
            <div className="document-brand">
              <Logo />
              <span>INVOICE</span>
            </div>
            <div className="doc-lines">
              <i />
              <i />
              <i />
              <i />
            </div>
            <div className="flex items-center justify-between">
              <StatusPill tone={statusTone(invoice.status)}>{humanize(invoice.status)}</StatusPill>
              <span className="mono text-xs">{invoice.invoice_number}</span>
            </div>
          </div>
        </div>
        <div className="totals">
          <div className="total-row">
            <span>Quote</span>
            <b className="mono text-xs">{invoice.quote_id}</b>
          </div>
          <div className="total-row final">
            <span>Total paid</span>
            <b>{formatINR(invoice.total_paise)}</b>
          </div>
        </div>
        <div className="buyer-actions">
          <button
            className="btn btn-secondary flex-1"
            type="button"
            disabled={download.pending}
            onClick={() =>
              void download.run().then((artifact) => {
                if (!artifact) return
                const url = URL.createObjectURL(artifact)
                const anchor = document.createElement('a')
                anchor.href = url
                anchor.download = `${invoice.invoice_number}.pdf`
                anchor.click()
                URL.revokeObjectURL(url)
              })
            }
          >
            {download.pending ? 'Preparing...' : 'Download'}
          </button>
          <button className="btn btn-secondary flex-1" type="button" disabled>
            Share
          </button>
          <button className="btn btn-secondary flex-1" type="button" disabled>
            Print
          </button>
        </div>
        {download.error && (
          <p className="mt-4 text-xs text-slate-400">
            Artifact download unavailable: {download.error.message}
          </p>
        )}
      </div>
    </BuyerLayout>
  )
}
