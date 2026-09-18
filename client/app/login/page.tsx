'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { ArrowRight, LockKeyhole, Zap } from 'lucide-react'
import { ApiError, ownerLogin } from '@/lib/api/endpoints'
import '@/components/owner-dashboard.css'

export default function LoginPage() {
  const router = useRouter()
  const [phone, setPhone] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await ownerLogin(phone.trim())
      window.localStorage.setItem('stockaware_owner_token', result.access_token)
      router.replace('/dashboard')
    } catch (cause) {
      setError(cause instanceof ApiError && cause.status === 401
        ? 'This phone number is not registered for a StockAware workspace.'
        : cause instanceof Error ? cause.message : 'Could not sign in. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return <main className="owner-login">
    <section className="owner-login-story">
      <div className="owner-brand"><span className="owner-brand-mark"><Zap size={18} /></span>StockAware</div>
      <div>
        <p className="owner-kicker">OWNER CONTROL ROOM</p>
        <h1>Know what is moving. Decide what happens next.</h1>
        <p>Quotes, stock, payments and delivery commitments in one live view of your wholesale business.</p>
      </div>
      <span className="owner-login-foot">Built for the pace of trade.</span>
    </section>
    <section className="owner-login-panel">
      <form onSubmit={submit} className="owner-login-card">
        <span className="owner-login-lock"><LockKeyhole size={19} /></span>
        <p className="owner-kicker">WELCOME BACK</p>
        <h2>Sign in to your workspace</h2>
        <p className="owner-muted">Use the phone number linked to your business.</p>
        <label htmlFor="owner-phone">Phone number</label>
        <input id="owner-phone" name="phone" type="tel" inputMode="numeric" autoComplete="tel"
          value={phone} onChange={event => setPhone(event.target.value)} placeholder="10-digit mobile number"
          required minLength={10} maxLength={15} />
        {error && <p role="alert" className="owner-error">{error}</p>}
        <button className="owner-primary" disabled={loading} type="submit">
          {loading ? 'Signing in…' : 'Continue'} <ArrowRight size={16} />
        </button>
        <p className="owner-login-note">Demo access uses phone number only. OTP verification is required before production use.</p>
      </form>
    </section>
  </main>
}
