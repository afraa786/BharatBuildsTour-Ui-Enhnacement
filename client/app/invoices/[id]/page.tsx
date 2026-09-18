import { BuyerInvoiceView } from '@/components/views'
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <BuyerInvoiceView id={id}/> }
