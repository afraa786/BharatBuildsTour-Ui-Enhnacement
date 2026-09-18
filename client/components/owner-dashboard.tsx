'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import {
  ArrowRight, ChartNoAxesCombined, ClipboardList, Layers3, LayoutDashboard,
  LogOut, Package, Plus, Receipt, RefreshCw, Users, Zap,
} from 'lucide-react'
import {
  ownerBuyers, ownerCategories, ownerCreateBuyer, ownerCreateCategory, ownerCreateProduct,
  ownerDeleteCategory, ownerDeleteProduct, ownerEditBuyer, ownerEditCategory, ownerEditProduct,
  ownerInvoices, ownerMe, ownerProducts, ownerRun, ownerRuns, ownerSales, ownerSetDeliveryDate,
  ownerSetRunStatus, ownerSummary,
  type OwnerBuyer, type OwnerCategory, type OwnerInvoice, type OwnerProduct,
  type OwnerProductInput, type OwnerRun, type OwnerSaleDay, type OwnerSummary,
} from '@/lib/api/endpoints'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './owner-dashboard.css'
import AgentOffice from './agent-office/App'

type Tab = 'overview' | 'categories' | 'products' | 'customers' | 'orders' | 'billing' | 'reports'
const tabs = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'categories', label: 'Categories', icon: Layers3 },
  { id: 'products', label: 'Products', icon: Package },
  { id: 'customers', label: 'Customers', icon: Users },
  { id: 'orders', label: 'Orders', icon: ClipboardList },
  { id: 'billing', label: 'Billing / Invoices', icon: Receipt },
  { id: 'reports', label: 'Sales Reports', icon: ChartNoAxesCombined },
] as const
const runStatuses = ['pending', 'quoted', 'payment_pending', 'paid', 'shipped', 'delivered', 'cancelled']
const money = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(paise / 100)
const date = (value: string | null | undefined) => value ? new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not set'
const plainStatus = (value: string) => value.replaceAll('_', ' ').toLowerCase()
const emptyProduct: OwnerProductInput = { sku: '', name: '', category_id: null, cost_unit_paise: 0, base_unit_price_paise: 0, gst_rate_bps: 1800, stock_qty: 0 }

export function OwnerDashboard() {
  const router = useRouter()
  const [tab, setTab] = useState<Tab>('overview')
  const [name, setName] = useState('Rehbar')
  const [summary, setSummary] = useState<OwnerSummary | null>(null)
  const [categories, setCategories] = useState<OwnerCategory[]>([])
  const [products, setProducts] = useState<OwnerProduct[]>([])
  const [buyers, setBuyers] = useState<OwnerBuyer[]>([])
  const [runs, setRuns] = useState<OwnerRun[]>([])
  const [invoices, setInvoices] = useState<OwnerInvoice[]>([])
  const [sales, setSales] = useState<OwnerSaleDay[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [categoryName, setCategoryName] = useState('')
  const [editingCategory, setEditingCategory] = useState<string | null>(null)
  const [editingCategoryName, setEditingCategoryName] = useState('')
  const [productDraft, setProductDraft] = useState<OwnerProductInput>(emptyProduct)
  const [editingProduct, setEditingProduct] = useState<string | null>(null)
  const [showProductForm, setShowProductForm] = useState(false)
  const [customerType, setCustomerType] = useState<'lead' | 'customer'>('lead')
  const [buyerName, setBuyerName] = useState('')
  const [buyerPhone, setBuyerPhone] = useState('')
  const [selectedRun, setSelectedRun] = useState<OwnerRun | null>(null)
  const [runFilter, setRunFilter] = useState('')
  const [reportPeriod, setReportPeriod] = useState<'daily' | 'weekly'>('daily')

  async function refresh() {
    const now = new Date()
    const start = new Date(now.getTime() - 45 * 86400000).toISOString()
    const [me, nextSummary, nextCategories, nextProducts, nextBuyers, nextRuns, nextInvoices, nextSales] = await Promise.all([
      ownerMe(), ownerSummary(), ownerCategories(), ownerProducts(), ownerBuyers(), ownerRuns(),
      ownerInvoices(), ownerSales(start, now.toISOString()),
    ])
    setName(me.name)
    setSummary(nextSummary)
    setCategories(nextCategories)
    setProducts(nextProducts)
    setBuyers(nextBuyers)
    setRuns(nextRuns)
    setInvoices(nextInvoices)
    setSales(nextSales)
    if (selectedRun) setSelectedRun(await ownerRun(selectedRun.run_id))
  }

  useEffect(() => {
    if (!window.localStorage.getItem('stockaware_owner_token')) {
      router.replace('/login')
      return
    }
    refresh().catch(cause => setError(cause instanceof Error ? cause.message : 'Could not load your workspace.'))
      .finally(() => setLoading(false))
    // Load the authenticated workspace once on entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function act(work: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try {
      await work()
      await refresh()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save this change.')
    } finally {
      setBusy(false)
    }
  }

  function logout() {
    window.localStorage.removeItem('stockaware_owner_token')
    router.replace('/login')
  }

  function openProduct(product?: OwnerProduct) {
    setEditingProduct(product?.id ?? null)
    setProductDraft(product ? {
      sku: product.sku, name: product.name, category_id: product.category_id,
      cost_unit_paise: product.cost_unit_paise, base_unit_price_paise: product.base_unit_price_paise,
      gst_rate_bps: product.gst_rate_bps, stock_qty: product.stock_qty,
    } : emptyProduct)
    setShowProductForm(true)
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await act(() => editingProduct ? ownerEditProduct(editingProduct, productDraft) : ownerCreateProduct(productDraft))
    setShowProductForm(false)
  }

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!categoryName.trim()) return
    await act(() => ownerCreateCategory(categoryName.trim()))
    setCategoryName('')
  }

  async function addBuyer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!buyerName.trim()) return
    await act(() => ownerCreateBuyer({ display_name: buyerName.trim(), whatsapp_e164: buyerPhone.trim() || undefined, is_customer: customerType === 'customer' }))
    setBuyerName('')
    setBuyerPhone('')
  }

  const visibleProducts = products.filter(product => product.active)
  const visibleBuyers = buyers.filter(buyer => buyer.is_customer === (customerType === 'customer'))
  const visibleRuns = runs.filter(run => !runFilter || run.status === runFilter)
  const chartRows = reportPeriod === 'daily'
    ? sales.map(row => ({ label: date(row.date), amount: row.total_paise / 100 }))
    : Object.entries(sales.reduce<Record<string, number>>((weeks, row) => {
        const day = new Date(row.date + 'T00:00:00Z')
        day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7))
        const key = day.toISOString().slice(0, 10)
        weeks[key] = (weeks[key] ?? 0) + row.total_paise
        return weeks
      }, {})).map(([label, total]) => ({ label: date(label), amount: total / 100 }))

  return <div className="owner-shell">
    <aside className="owner-sidebar">
      <div className="owner-brand"><span className="owner-brand-mark"><Zap size={18} /></span>StockAware</div>
      <div className="owner-workspace"><span className="owner-workspace-icon">R</span><span><small>WORKSPACE</small><strong>Rehbar's business</strong></span></div>
      <nav aria-label="Dashboard tabs" className="owner-nav">
        {tabs.map(({ id, label, icon: Icon }) => <button key={id} type="button"
          className={tab === id ? 'active' : ''} onClick={() => { setTab(id); setSelectedRun(null) }}>
          <Icon size={17} />{label}
        </button>)}
      </nav>
      <div className="owner-sidebar-bottom"><span className="owner-live-dot" />Connected to live business data</div>
    </aside>
    <div className="owner-content">
      <header className="owner-topbar">
        <span>OWNER WORKSPACE <span className="owner-topbar-slash">/</span> {tabs.find(item => item.id === tab)?.label}</span>
        <div><span className="owner-user">{name}</span><button type="button" onClick={logout} title="Sign out"><LogOut size={16} /> Sign out</button></div>
      </header>
      <main className="owner-main">
        <div className="owner-heading"><div><p className="owner-kicker">STOCKAWARE / {tab.toUpperCase()}</p>
          <h1>{tab === 'overview' ? `Good to see you, ${name.split(' ')[0]}.` : tabs.find(item => item.id === tab)?.label}</h1>
          <p>{tab === 'overview' ? 'A live picture of sales, customers and commitments.' : 'Your business data, ready for action.'}</p>
        </div><button className="owner-refresh" type="button" onClick={() => act(async () => {})} disabled={busy}><RefreshCw size={15} /> Refresh</button></div>
        {error && <div role="alert" className="owner-error-banner">{error}</div>}
        {tab === 'overview' && <section className="owner-agent-visual" aria-label="Agent workspace visualization">
          <AgentOffice />
        </section>}
        {loading ? <div className="owner-loading">Loading your workspace…</div> : <>
          {tab === 'overview' && summary && <>
            <section className="owner-overview-grid">
              <div className="owner-sales-card"><p className="owner-kicker">PAID SALES</p><strong>{money(summary.total_sales_paise)}</strong><span>Recorded from paid payments</span><div className="owner-sales-line" /></div>
              <div className="owner-stat"><span>Leads</span><strong>{summary.leads_count}</strong><small>Awaiting conversion</small></div>
              <div className="owner-stat"><span>Customers</span><strong>{summary.customers_count}</strong><small>Active relationships</small></div>
            </section>
            <section className="owner-two-column">
              <div className="owner-panel"><div className="owner-panel-heading"><h2>Order movement</h2><span>By current status</span></div>
                <div className="owner-status-ledger">{Object.entries(summary.runs_count_by_status).map(([status, count]) =>
                  <button key={status} onClick={() => { setRunFilter(status); setTab('orders') }}><span className={`owner-status-dot ${status}`} /><span>{plainStatus(status)}</span><strong>{count}</strong><ArrowRight size={14} /></button>)}</div>
              </div>
              <div className="owner-panel"><div className="owner-panel-heading"><h2>Upcoming deliveries</h2><span>Scheduled runs</span></div>
                {summary.upcoming_deliveries.length ? <div className="owner-delivery-list">{summary.upcoming_deliveries.map(item =>
                  <button key={item.run_id} onClick={async () => { setSelectedRun(await ownerRun(item.run_id)); setTab('orders') }}>
                    <span><strong>{item.buyer_name || item.run_id}</strong><small>{item.run_id}</small></span><time>{date(item.expected_delivery_date)}</time></button>)}</div>
                  : <p className="owner-empty">No deliveries scheduled yet.</p>}
              </div>
            </section>
          </>}
          {tab === 'categories' && <section className="owner-panel"><div className="owner-panel-heading"><h2>Product categories</h2><span>{categories.length} groups</span></div>
            <form className="owner-inline-form" onSubmit={addCategory}><input aria-label="Category name" value={categoryName} onChange={event => setCategoryName(event.target.value)} placeholder="New category name" required /><button className="owner-primary" disabled={busy}><Plus size={15} /> Add category</button></form>
            <div className="owner-list">{categories.map(category => <div className="owner-list-row" key={category.id}>
              {editingCategory === category.id ? <input aria-label="Edit category name" value={editingCategoryName} onChange={event => setEditingCategoryName(event.target.value)} /> : <strong>{category.name}</strong>}
              <span>{visibleProducts.filter(product => product.category_id === category.id).length} products</span>
              {editingCategory === category.id ? <button onClick={() => act(async () => { await ownerEditCategory(category.id, editingCategoryName); setEditingCategory(null) })} disabled={busy}>Save</button> : <button onClick={() => { setEditingCategory(category.id); setEditingCategoryName(category.name) }}>Edit</button>}
              <button onClick={() => { if (window.confirm(`Delete ${category.name}? Products will remain uncategorized.`)) act(() => ownerDeleteCategory(category.id)) }} disabled={busy}>Delete</button>
            </div>)}</div></section>}
          {tab === 'products' && <>
            <div className="owner-section-actions"><p>{visibleProducts.length} products across {categories.length} categories</p><button className="owner-primary" onClick={() => openProduct()}><Plus size={15} /> Add product</button></div>
            {showProductForm && <form className="owner-panel owner-product-form" onSubmit={saveProduct}>
              <div className="owner-panel-heading"><h2>{editingProduct ? 'Edit product' : 'Add product'}</h2><button type="button" onClick={() => setShowProductForm(false)}>Close</button></div>
              <div className="owner-form-grid">
                <label>Name<input required value={productDraft.name} onChange={event => setProductDraft({ ...productDraft, name: event.target.value })} /></label>
                <label>SKU<input required value={productDraft.sku} onChange={event => setProductDraft({ ...productDraft, sku: event.target.value })} /></label>
                <label>Category<select value={productDraft.category_id || ''} onChange={event => setProductDraft({ ...productDraft, category_id: event.target.value || null })}><option value="">Uncategorized</option>{categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                <label>Stock quantity<input type="number" min="0" step="0.001" value={productDraft.stock_qty} onChange={event => setProductDraft({ ...productDraft, stock_qty: Number(event.target.value) })} /></label>
                <label>Cost (paise)<input type="number" min="0" value={productDraft.cost_unit_paise} onChange={event => setProductDraft({ ...productDraft, cost_unit_paise: Number(event.target.value) })} /></label>
                <label>Selling price (paise)<input type="number" min="1" value={productDraft.base_unit_price_paise} onChange={event => setProductDraft({ ...productDraft, base_unit_price_paise: Number(event.target.value) })} /></label>
                <label>GST (basis points)<input type="number" min="0" max="10000" value={productDraft.gst_rate_bps} onChange={event => setProductDraft({ ...productDraft, gst_rate_bps: Number(event.target.value) })} /></label>
              </div><button className="owner-primary" disabled={busy}>Save product</button>
            </form>}
            <div className="owner-panel"><div className="owner-panel-heading"><h2>Catalog & stock</h2><span>Prices in INR</span></div>
              {categories.map(category => <div key={category.id} className="owner-product-group"><h3>{category.name}</h3>{visibleProducts.filter(product => product.category_id === category.id).map(product => <div className="owner-product-row" key={product.id}>
                <span><strong>{product.name}</strong><small>{product.sku}</small></span><span>{money(product.base_unit_price_paise)}</span><span className={product.stock_qty < 5 ? 'owner-low-stock' : ''}>{product.stock_qty} in stock</span><button onClick={() => openProduct(product)}>Edit</button><button onClick={() => { if (window.confirm(`Remove ${product.name} from active products?`)) act(() => ownerDeleteProduct(product.id)) }}>Delete</button>
              </div>)}</div>)}
              {visibleProducts.some(product => !product.category_id) && <div className="owner-product-group"><h3>Uncategorized</h3>{visibleProducts.filter(product => !product.category_id).map(product => <div className="owner-product-row" key={product.id}><span><strong>{product.name}</strong><small>{product.sku}</small></span><span>{money(product.base_unit_price_paise)}</span><span>{product.stock_qty} in stock</span><button onClick={() => openProduct(product)}>Edit</button><button onClick={() => act(() => ownerDeleteProduct(product.id))}>Delete</button></div>)}</div>}
            </div>
          </>}
          {tab === 'customers' && <section className="owner-panel"><div className="owner-panel-heading"><h2>People & businesses</h2><span>{buyers.length} contacts</span></div>
            <div className="owner-subtabs"><button className={customerType === 'lead' ? 'active' : ''} onClick={() => setCustomerType('lead')}>Leads ({buyers.filter(item => !item.is_customer).length})</button><button className={customerType === 'customer' ? 'active' : ''} onClick={() => setCustomerType('customer')}>Customers ({buyers.filter(item => item.is_customer).length})</button></div>
            <form className="owner-inline-form" onSubmit={addBuyer}><input aria-label="Contact name" required placeholder="Name or business" value={buyerName} onChange={event => setBuyerName(event.target.value)} /><input aria-label="Phone number" placeholder="Phone (optional)" value={buyerPhone} onChange={event => setBuyerPhone(event.target.value)} /><button className="owner-primary" disabled={busy}><Plus size={15} /> Add {customerType}</button></form>
            <div className="owner-list">{visibleBuyers.map(buyer => <div className="owner-list-row" key={buyer.id}><span><strong>{buyer.display_name}</strong><small>{buyer.whatsapp_e164 || buyer.source || 'No phone recorded'}</small></span><span>{buyer.last_contacted_at ? `Contacted ${date(buyer.last_contacted_at)}` : 'No contact date'}</span>{!buyer.is_customer && <button className="owner-convert" disabled={busy} onClick={() => act(() => ownerEditBuyer(buyer.id, { is_customer: true }))}>Convert to customer <ArrowRight size={14} /></button>}</div>)}</div>
            {!visibleBuyers.length && <p className="owner-empty">No {customerType}s yet. Add one above.</p>}
          </section>}
          {tab === 'orders' && <><div className="owner-section-actions"><p>{runs.length} owner orders</p><select aria-label="Filter by status" value={runFilter} onChange={event => setRunFilter(event.target.value)}><option value="">All statuses</option>{runStatuses.map(status => <option key={status} value={status}>{plainStatus(status)}</option>)}</select></div>
            <div className="owner-panel"><div className="owner-panel-heading"><h2>Orders</h2><span>Click a row for details</span></div><div className="owner-list">{visibleRuns.map(run => <button className="owner-order-row" key={run.run_id} onClick={async () => { try { setSelectedRun(await ownerRun(run.run_id)) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load order.') } }}><span><strong>{run.run_id}</strong><small>{run.buyer_name || run.buyer_wa_id}</small></span><span className={`owner-badge ${run.status}`}>{plainStatus(run.status)}</span><span>{date(run.expected_delivery_date)}</span><ArrowRight size={16} /></button>)}</div></div>
            {selectedRun && <section className="owner-panel owner-order-detail"><div className="owner-panel-heading"><h2>{selectedRun.run_id} · {selectedRun.buyer_name}</h2><button onClick={() => setSelectedRun(null)}>Close</button></div>
              <div className="owner-order-controls"><label>Status<select value={selectedRun.status} onChange={async event => { const value = event.target.value; await act(async () => setSelectedRun(await ownerSetRunStatus(selectedRun.run_id, value))) }} disabled={busy}>{runStatuses.map(status => <option key={status} value={status}>{plainStatus(status)}</option>)}</select></label>
              <label>Expected delivery<input type="date" value={selectedRun.expected_delivery_date?.slice(0, 10) || ''} onChange={async event => { const value = event.target.value ? `${event.target.value}T09:00:00Z` : null; await act(async () => setSelectedRun(await ownerSetDeliveryDate(selectedRun.run_id, value))) }} disabled={busy} /></label></div>
              <div className="owner-detail-grid"><div><span>Line items</span>{selectedRun.line_items.map((item, index) => <p key={index}>{String(item.name || item.requested_name || 'Item')} · {String(item.quantity || '')}</p>)}</div><div><span>Quote</span><p>{selectedRun.quote ? `${money(selectedRun.quote.total_paise)} · ${selectedRun.quote.status}` : 'Not issued'}</p></div><div><span>Payment</span><p>{selectedRun.payment ? `${money(selectedRun.payment.amount_paise)} · ${selectedRun.payment.status}` : 'Not started'}</p></div><div><span>Invoice</span><p>{selectedRun.invoice ? selectedRun.invoice.invoice_number : 'Not generated'}</p></div></div>
            </section>}</>}
          {tab === 'billing' && <section className="owner-panel"><div className="owner-panel-heading"><h2>Invoices</h2><span>{invoices.length} issued records</span></div><div className="owner-table-wrap"><table><thead><tr><th>Invoice</th><th>Buyer / run</th><th>Payment</th><th>Amount</th><th>Issued</th></tr></thead><tbody>{invoices.map(invoice => { const run = runs.find(item => item.run_id === invoice.run_id); return <tr key={invoice.id}><td><strong>{invoice.invoice_number}</strong><small>{invoice.status === 'GENERATED' ? 'Document ready' : 'Document pending'}</small></td><td>{run?.buyer_name || invoice.run_id}<small>{invoice.run_id}</small></td><td><span className={`owner-badge ${run?.payment?.status?.toLowerCase() || 'pending'}`}>{run?.payment?.status?.toLowerCase() === 'paid' ? 'Paid' : 'Unpaid'}</span></td><td>{money(invoice.total_paise)}</td><td>{date(invoice.issued_at)}</td></tr> })}</tbody></table></div>{!invoices.length && <p className="owner-empty">Invoices appear here after payment.</p>}</section>}
          {tab === 'reports' && <section className="owner-panel"><div className="owner-panel-heading"><div><h2>Paid sales over time</h2><p>Daily totals from completed payments</p></div><div className="owner-subtabs"><button className={reportPeriod === 'daily' ? 'active' : ''} onClick={() => setReportPeriod('daily')}>Daily</button><button className={reportPeriod === 'weekly' ? 'active' : ''} onClick={() => setReportPeriod('weekly')}>Weekly</button></div></div>
            <div className="owner-report-total"><small>LAST 45 DAYS</small><strong>{money(sales.reduce((sum, row) => sum + row.total_paise, 0))}</strong></div>
            {chartRows.length ? <div className="owner-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartRows} margin={{ top: 16, right: 12, left: 0, bottom: 0 }}><CartesianGrid vertical={false} stroke="#26364d" strokeDasharray="4 4" /><XAxis dataKey="label" stroke="#9aabc2" tickLine={false} axisLine={false} /><YAxis stroke="#9aabc2" tickLine={false} axisLine={false} tickFormatter={value => `₹${value}`} /><Tooltip formatter={value => money(Number(value) * 100)} contentStyle={{ background: '#142238', border: '1px solid #33445c', borderRadius: 12, color: '#fff' }} /><Bar dataKey="amount" fill="#7c81ff" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div> : <p className="owner-empty">No paid sales in this period yet.</p>}
          </section>}
        </>}
      </main>
    </div>
  </div>
}
