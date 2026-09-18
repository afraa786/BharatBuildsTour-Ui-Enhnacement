export interface Product {
  id: string
  name: string
  sku: string
  stock: number
  threshold: number
  cost: string
  margin: string
  status: 'Low stock' | 'Healthy'
  substitute: string
  category: string
}

export interface Run {
  id: string
  buyer: string
  state: string
  agent: string
  quote: string
  started: string
  status: 'Active' | 'Completed' | 'Failed'
}

export interface Quote {
  id: string
  buyer: string
  amount: string
  status: 'Pending' | 'Sent' | 'Accepted'
  date: string
}

export interface Payment {
  id: string
  rfqId: string
  buyer: string
  amount: string
  provider: string
  status: 'Pending' | 'Paid' | 'Failed'
}

export interface Invoice {
  id: string
  rfqId: string
  buyer: string
  amount: string
  status: 'Paid' | 'Pending'
  date: string
}

export const inventory: Product[] = [
  { id: 'LED-018', name: 'LED Panel 18W', sku: 'LED-018', stock: 2, threshold: 5, cost: '₹1,240', margin: '16%', status: 'Low stock', substitute: 'LED-020', category: 'Lighting' },
  { id: 'CAB-001', name: '3-core copper cable', sku: 'CAB-001', stock: 20, threshold: 5, cost: '₹3,450', margin: '18%', status: 'Healthy', substitute: '—', category: 'Cables' },
  { id: 'MCB-32A', name: 'MCB 32A', sku: 'MCB-32A', stock: 10, threshold: 4, cost: '₹620', margin: '22%', status: 'Healthy', substitute: '—', category: 'Protection' },
  { id: 'LED-020', name: 'LED Panel 20W', sku: 'LED-020', stock: 14, threshold: 5, cost: '₹1,580', margin: '19%', status: 'Healthy', substitute: '—', category: 'Lighting' },
]

export const runs: Run[] = [
  { id: 'RFQ-1042', buyer: 'Sharma Electricals', state: 'Approval required', agent: 'Finance', quote: '₹124,000', started: '14:04:02', status: 'Active' },
  { id: 'RFQ-1041', buyer: 'Kumar & Sons', state: 'Quote sent', agent: 'Quote Desk', quote: '₹86,400', started: '13:22:15', status: 'Completed' },
  { id: 'RFQ-1038', buyer: 'Brightline Infra', state: 'Stock check', agent: 'Inventory', quote: '₹42,800', started: '12:45:30', status: 'Active' },
]

export const quotes: Quote[] = [
  { id: 'RFQ-1042', buyer: 'Sharma Electricals', amount: '₹124,000', status: 'Pending', date: 'Sep 17' },
  { id: 'RFQ-1041', buyer: 'Kumar & Sons', amount: '₹86,400', status: 'Sent', date: 'Sep 16' },
]

export const payments: Payment[] = [
  { id: 'PAY-1042', rfqId: 'RFQ-1042', buyer: 'Sharma Electricals', amount: '₹124,000', provider: 'Razorpay', status: 'Pending' },
  { id: 'PAY-1041', rfqId: 'RFQ-1041', buyer: 'Kumar & Sons', amount: '₹86,400', provider: 'Razorpay', status: 'Paid' },
]

export const invoices: Invoice[] = [
  { id: 'INV-1042', rfqId: 'RFQ-1042', buyer: 'Sharma Electricals', amount: '₹124,000', status: 'Paid', date: 'Sep 17' },
  { id: 'INV-1041', rfqId: 'RFQ-1041', buyer: 'Kumar & Sons', amount: '₹86,400', status: 'Paid', date: 'Sep 16' },
]

export const timeline = [
  ['14:04:02', 'Manager received RFQ-1042', 'violet'], ['14:04:03', 'Sales normalized 4 items', 'blue'], ['14:04:04', 'Catalogue matched products', 'blue'], ['14:04:04', 'Inventory checked stock', 'green'], ['14:04:05', 'Finance blocked requested discount', 'amber'], ['14:04:06', 'Approval requested', 'amber']
]

export const agents = [
  ['Manager', 'Orchestration', 'Requesting approval', 'violet'], ['Sales Desk', 'Order intake', '4 items normalized', 'blue'], ['Catalogue Desk', 'SKU matching', '3 SKUs matched', 'blue'], ['Inventory Desk', 'Stock control', 'Shortage detected', 'amber'], ['Finance Desk', 'Margin policy', 'Policy blocked', 'red'], ['Quote Desk', 'Document creation', 'Waiting', 'muted']
]

export const nav = [
  ['Overview','/dashboard'], ['Runs','/runs'], ['Approvals','/approvals'], ['Inventory','/inventory'], ['Quotes','/quotes'], ['Payments','/payments'], ['Invoices','/invoices']
]

export const money = '₹124,000'
export const items = [{name:'3-core copper cable', qty:20, price:'₹3,450'}, {name:'MCB 32A',qty:10,price:'₹620'}, {name:'LED panel',qty:4,price:'₹1,240'}]

export function getInventory(id: string): Product { return inventory.find(item => item.id === id) ?? inventory[0] }
export function getRun(id: string): Run | undefined { return runs.find(r => r.id === id) }
export function getQuote(id: string): Quote | undefined { return quotes.find(q => q.id === id) }
export function getPayment(id: string): Payment | undefined { return payments.find(p => p.id === id) }
export function getInvoice(id: string): Invoice | undefined { return invoices.find(i => i.id === id) }
export function getTone(status: string) { return status.toLowerCase().replaceAll(' ', '-') }
