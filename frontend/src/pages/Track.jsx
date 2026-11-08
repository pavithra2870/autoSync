import { useEffect, useState } from 'react'
import { api, rupees } from '../api'
import { useT } from '../i18n.jsx'

const fmt = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

export default function Track({ order, setOrder, onRestart }) {
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const active = order.stages.every((s) => s.state === 'done')

  // the owner never needs to chase: the page refreshes itself
  useEffect(() => {
    const id = setInterval(() => api.order(order.id).then(setOrder).catch(() => {}), 6000)
    return () => clearInterval(id)
  }, [order.id])

  const next = async () => {
    setBusy(true)
    try { setOrder(await api.advance(order.id)) } finally { setBusy(false) }
  }
  const last = order.stages.find((s) => s.key === 'active')

  return (
    <section className="track">
      <div className="card order-head">
        <div className="muted small">{t('track.order', { id: order.id })}</div>
        <h2>{active ? '🎉 ' + t('stage.active') : t('track.title')}</h2>
        <div className="muted">{order.business}{order.city ? ` · ${order.city}` : ''} · {rupees(order.totals.monthly)}/mo</div>
        {!active && <div className="eta">{t('track.expected', { date: fmt(last.expected) })}</div>}
      </div>

      <ol className="timeline">
        {order.stages.map((s) => (
          <li key={s.key} className={s.state}>
            <span className="node">{s.state === 'done' ? '✓' : ''}</span>
            <div>
              <b>{t(`stage.${s.key}`)}</b>
              <div className="muted small">{s.state === 'done' ? fmt(s.done_on) : t('track.expected', { date: fmt(s.expected) })}</div>
              {s.key === 'kyc' && s.state === 'current' && <div className="note-line">{t('verdict.review')}</div>}
            </div>
          </li>
        ))}
      </ol>

      {order.held?.length > 0 && (
        <div className="card"><div className="note-line">{t('confirm.held')}: {order.held.map((h) => h.name).join(', ')}</div></div>
      )}

      <div className="card wa">
        <h3>{t('track.messages')}</h3>
        {[...order.messages].reverse().map((m, i) => (
          <div key={i} className="wa-msg">
            <span className="wa-ch">{m.channel}</span>
            <span>{t(`stage.${m.stage}`)} ✓ · {t('track.order', { id: order.id })}</span>
            <span className="muted small">{fmt(m.when)}</span>
          </div>
        ))}
        <p className="muted small">{t('track.nocall')}</p>
      </div>

      <div className="dock sticky">
        <button className="btn ghost" onClick={onRestart}>↺</button>
        <button className="btn primary" disabled={busy || active} onClick={next}>{active ? t('track.done') : t('track.simulate')}</button>
      </div>
    </section>
  )
}
