import { useState } from 'react'
import { api, rupees } from '../api'
import { useT } from '../i18n.jsx'

export default function Confirm({ session, kyc, onBack, onOrder }) {
  const { t } = useT()
  const q = kyc.quote
  const s = q.sell
  const [name, setName] = useState('')
  const [agree, setAgree] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const items = q.lines.filter((l) => l.selected)
  const held = q.removed?.filter((r) => r.reason === 'ineligible') || []

  const place = async () => {
    setBusy(true)
    setError(null)
    try {
      onOrder(await api.checkout(session.session_id, { signed_name: name, agree }))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <section className="confirm">
      <h2>{t('confirm.title')}</h2>
      <div className="card">
        <ul className="lines compact">
          {items.map((l) => (
            <li key={l.product_id} className="line">
              <div className="line-main"><b>{l.name}</b><span className="muted">× {l.qty}</span></div>
              <div className="line-side price">{rupees(l.line_monthly)}</div>
            </li>
          ))}
        </ul>
        {held.length > 0 && (
          <div className="note-line">{t('confirm.held')}: {held.map((h) => h.product_id).join(', ')}</div>
        )}
        <div className="sum-row"><span>{t('quote.monthly')}</span><b>{rupees(q.totals.monthly)}</b></div>
        <div className="sum-row"><span>{t('quote.setup')}</span><b>{rupees(q.totals.setup)}</b></div>
        {s && <>
          <div className="sum-row offer-row"><span>🎁 {t('confirm.first_month')}</span>
            <b>{s.first_month_pay < q.totals.monthly && <s>{rupees(q.totals.monthly)}</s>} {rupees(s.first_month_pay)}</b></div>
          {q.totals.setup > 0 && (
            <div className="sum-row offer-row"><span>🎁 {t('confirm.setup_after')}</span>
              <b>{s.setup_pay < q.totals.setup && <s>{rupees(q.totals.setup)}</s>} {rupees(s.setup_pay)}</b></div>
          )}
        </>}
        <div className="sum-row"><span>{t('quote.contract')}</span><b>{t('quote.months', { n: q.contract_months })}</b></div>
        <div className="muted small">{t('quote.excl')}</div>
      </div>

      <div className="card">
        <label className="field">
          <span>{t('confirm.sign')}</span>
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </label>
        <label className="confirm-box"><input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} /> {t('confirm.agree')}</label>
        {error && <div className="warn-line">{error}</div>}
      </div>

      <div className="dock sticky">
        <button className="btn ghost" onClick={onBack}>{t('common.back')}</button>
        <button className="btn primary" disabled={busy || !agree || name.trim().length < 3} onClick={place}>{t('confirm.place')}</button>
      </div>
    </section>
  )
}
