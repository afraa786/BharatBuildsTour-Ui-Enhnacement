import { AdminShell, PageHeader } from '@/components/stockaware'

export default function SettingsPage() {
  return <AdminShell><PageHeader eyebrow="WORKSPACE / SETTINGS" title="Settings" description="Manage workspace preferences and approval controls." /><div className="grid max-w-3xl gap-4 md:grid-cols-2"><section className="panel"><h3>Workspace</h3><div className="form-grid"><div className="field"><label>Business name</label><input defaultValue="Sharma Electricals" /></div><div className="field"><label>Owner</label><input defaultValue="Arjun Rao" /></div></div></section><section className="panel"><h3>Approval policy</h3><p className="text-sm text-slate-400">Discounts above 7% require owner approval before a quote can be sent.</p><button className="btn btn-primary mt-5">Save preferences</button></section></div></AdminShell>
}
