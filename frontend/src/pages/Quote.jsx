import { useEffect, useRef, useState } from 'react'
import { api, rupees } from '../api'
import { LANGUAGES, useT } from '../i18n.jsx'
import { ITEM_ICON, OFFER_ICON, PAIN_ORDER, PAIN_PRODUCT, inr } from '../icons.js'

const selectionsOf = (q) => Object.fromEntries(q.lines.filter((l) => l.selected).map((l) => [l.product_id, l.qty]))
const revealed = new Set() // play the "building your plan" moment once per session
const CONNECTIVITY = new Set(['internet_core', 'leased', 'mobile_lines', 'alt_internet'])

function LockReason({ line }) {
  const { t } = useT()
  if (line.locked?.length) {
    return <span className="lock">🔒 {line.locked.map((r) => t(`lock.${r.code}`, r.params)).join(' · ')}</span>
  }
  if (line.pending_gst) return <span className="pending">{t('quote.pending')}</span>
  return null
}

/** A short, real "labour" moment: the owner sees the work that went into their plan. */
function Reveal({ n }) {
  const { t } = useT()
  return (
    <div className="reveal" role="status">
      <div className="reveal-card">
        <div className="reveal-spin" aria-hidden>🎒</div>
        <h2>{t('reveal.title')}</h2>
        <ul>
          <li style={{ animationDelay: '.2s' }}>✓ {t('reveal.1')}</li>
          <li style={{ animationDelay: '.8s' }}>✓ {t('reveal.2', { n: n ?? '…' })}</li>
          <li style={{ animationDelay: '1.4s' }}>✓ {t('reveal.3')}</li>
        </ul>
      </div>
    </div>
  )
}

function Offers({ sell }) {
  const { t, lang } = useT()
  const language = LANGUAGES.find((l) => l.code === lang)?.name || 'English'
  const text = (o) => {
    switch (o.key) {
      case 'setup': return [o.full ? t('offer.setup') : t('offer.setup_part', { n: inr(o.amount) }), t('offer.setup_d', { n: inr(o.amount) })]
      case 'half': return [o.full ? t('offer.half') : t('offer.half_part', { n: inr(o.amount) }), t('offer.half_d', { n: inr(o.amount) })]
      case 'lang': return [t('offer.lang', { language }), t('offer.lang_d')]
      case 'ontime': return [t('offer.ontime'), t('offer.ontime_d', { n: o.days })]
      case 'lock': return [t('offer.lock'), t('offer.lock_d', { n: o.months })]
      default: return [t(`offer.${o.key}`), t(`offer.${o.key}_d`)]
    }
  }
  return (
    <div className="offers">
      <div className="offers-head"><b>🎁 {t('offer.title')}</b><span>{t('offer.sub')}</span></div>
      <div className="tickets">
        {sell.offers.map((o) => {
          const [title, desc] = text(o)
          return (
            <div key={o.key} className={`ticket ${o.amount ? 'money' : ''}`}>
              <span className="ti" aria-hidden>{OFFER_ICON[o.key]}</span>
              <b>{title}</b>
              <small>{desc}</small>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Compare({ q }) {
  const { t } = useT()
  const s = q.sell
  const extras = q.lines.filter((l) => l.selected && !CONNECTIVITY.has(l.why)).map((l) => t(`item.${l.why}`))
  const free = s.months_free >= 2 ? t('cmp.months_free', { n: s.months_free }) : s.months_free === 1 ? t('cmp.month_free') : ''
  return (
    <div className="card cmp">
      <h3>{t('cmp.title')}</h3>
      <div className="cmp-grid">
        <span />
        <span className="cmp-h old">{t('cmp.separately')}</span>
        <span className="cmp-h new">{t('cmp.pack')}</span>

        <span className="cmp-l">💰 {t('cmp.money')}</span>
        <span className="old"><s>{rupees(s.year_separate)}</s></span>
        <span className="new"><b>{rupees(s.year_pack)}</b></span>

        {s.providers >= 2 && <>
          <span className="cmp-l">😓 {t('cmp.hassle')}</span>
          <span className="old">{t('cmp.providers', { n: s.providers })}</span>
          <span className="new"><b>{t('cmp.one')}</b></span>
        </>}

        <span className="cmp-l">⏱️ {t('cmp.time')}</span>
        <span className="old">{t('cmp.time_old', { days: s.usual_days, calls: s.usual_calls })}</span>
        <span className="new"><b>{t('cmp.time_new', { n: s.install_days })}</b></span>
      </div>
      {s.saving_year > 0 && (
        <div className="save-banner">🎉 <b>{t('cmp.save', { n: inr(s.saving_year) })}</b>{free && <span> · {free}</span>}</div>
      )}
      {s.vs_today && (
        <div className="vs-today">
          {s.vs_today.diff_month <= 0
            ? t('spend.less', { n: inr(-s.vs_today.diff_month) })
            : <>{t('spend.more', { n: inr(s.vs_today.diff_day) })}{extras.length > 0 && <> {t('spend.gets', { items: extras.slice(0, 3).join(', ') })}</>}</>}
        </div>
      )}
      <details className="how"><summary>{t('cmp.how')}</summary><p>{t('cmp.how_text')}</p></details>
    </div>
  )
}

function Fixes({ q, onAdd }) {
  const { t } = useT()
  const p = q.profile || {}
  const rows = []
  const net = q.lines.find((l) => l.selected && l.exclusive === 'internet')
  if (p.current_internet && net) {
    const label = { business_broadband: 'net.business', home_broadband: 'net.home', mobile_hotspot: 'net.hotspot',
      leased_line: 'net.leased', mixed_per_site: 'net.mixed', none: 'net.none' }[p.current_internet]
    rows.push({ key: 'net', left: t('fix.today', { x: t(label) }), right: <b>✓ {ITEM_ICON[net.why]} {net.name}</b> })
  }
  for (const pain of PAIN_ORDER.filter((x) => (p.needs || []).includes(x))) {
    if (pain === 'bills') {
      rows.push({ key: pain, left: t('pain.bills'), right: <b>✓ 🧾 {t('fix.bills')}</b> })
      continue
    }
    const line = q.lines.find((l) => l.product_id === PAIN_PRODUCT[pain])
    if (!line) continue
    let right
    if (line.selected) right = <b>✓ {ITEM_ICON[line.why]} {t(`item.${line.why}`)}</b>
    else if (line.locked.length) right = <LockReason line={line} />
    else right = <button className="btn small add" onClick={() => onAdd(line)}>+ {t('fix.add')} {t(`item.${line.why}`)} · {rupees(line.unit_price * line.qty)}</button>
    rows.push({ key: pain, left: t(`pain.${pain}`), right })
  }
  if (!rows.length) return null
  return (
    <div className="card fixes">
      <h3>{t('fix.title')}</h3>
      <ul>
        {rows.map((r) => (
          <li key={r.key}><span className="fx-pain">{r.left}</span><span className="fx-arrow" aria-hidden>→</span><span className="fx-fix">{r.right}</span></li>
        ))}
      </ul>
    </div>
  )
}

export default function Quote({ session, onBack, onAccept }) {
  const { t, lang } = useT()
  const sid = session.session_id
  const [q, setQ] = useState(null)
  const [busy, setBusy] = useState(false)
  const [why, setWhy] = useState(null)
  const [error, setError] = useState(null)
  const [revealing, setRevealing] = useState(!revealed.has(sid))
  const seq = useRef(0)

  useEffect(() => {
    api.quote(sid).then(setQ).catch(() => setError(t('err.generic')))
    api.explanation(sid).then(setWhy).catch(() => setWhy({ text: '', source: 'template' }))
    if (!revealing) return undefined
    const id = setTimeout(() => { revealed.add(sid); setRevealing(false) }, 2300)
    return () => clearTimeout(id)
  }, [sid]) // eslint-disable-line

  const update = async (sel, contract) => {
    const my = ++seq.current
    setBusy(true)
    try {
      const r = await api.setQuote(sid, sel, contract ?? q.contract_months)
      if (my === seq.current) setQ(r)
    } catch {
      if (my === seq.current) setError(t('err.generic'))
    } finally {
      if (my === seq.current) setBusy(false)
    }
  }

  if (error && !q) return <p className="warn-line center pad">{error}</p>
  if (!q || revealing) return <Reveal n={q?.sell?.proof?.segment} />

  const s = q.sell
  const p = q.profile || {}
  const sel = selectionsOf(q)
  const ids = Object.keys(sel).sort().join(',')
  const active = q.tiers.find((x) => x.ids.join(',') === ids)?.key || 'custom'
  const included = q.lines.filter((l) => l.selected)
  const swaps = q.lines.filter((l) => l.exclusive === 'internet' && !l.selected && !l.locked.length)
  const addons = q.lines.filter((l) => !l.selected && l.exclusive !== 'internet')
  const setQty = (id, d) => update({ ...sel, [id]: Math.max(1, sel[id] + d) })
  const remove = (id) => { const { [id]: _drop, ...rest } = sel; update(rest) }
  const add = (l) => update({ ...sel, [l.product_id]: l.qty })
  const swap = (l) => {
    const next = Object.fromEntries(Object.entries(sel).filter(([id]) => !q.lines.find((x) => x.product_id === id && x.exclusive === 'internet')))
    update({ ...next, [l.product_id]: l.qty })
  }
  const business = p.business_type || t(`biz.${q.segment}`)
  let held = s.held_until
  try { held = new Date(`${s.held_until}T00:00:00`).toLocaleDateString(`${lang}-IN`, { day: 'numeric', month: 'long' }) } catch { /* keep ISO */ }

  return (
    <section className={`quote ${busy ? 'busy' : ''}`}>
      <div className="price-card">
        <div className="seg-name">✨ {t('quote.made_for', { business })}{p.city ? ` ${t('quote.in_city', { city: p.city })}` : ''}</div>
        <div className="big">{rupees(q.totals.monthly)}<small>{t('common.per_month')}</small></div>
        {s.separate_monthly > q.totals.monthly && (
          <div className="was"><s>{rupees(s.separate_monthly)}</s> {t('quote.separately')}</div>
        )}
        <div className="per-day">☕ {t('quote.per_day', { n: inr(s.per_day) })}</div>
        <div className="sub">
          {q.totals.setup > 0 && <>{t('quote.setup')}: {s.setup_pay < q.totals.setup && <s>{rupees(q.totals.setup)}</s>} <b>{rupees(s.setup_pay)}</b> · </>}
          {t('quote.excl')}
        </div>
        <div className="pills" role="radiogroup" aria-label={t('quote.contract')}>
          {q.contract_options.map((m) => (
            <button key={m} role="radio" aria-checked={m === q.contract_months} className={`pill ${m === q.contract_months ? 'on' : ''}`}
              onClick={() => update(sel, m)}>{t('quote.months', { n: m })}</button>
          ))}
        </div>
        {q.contract_options.length > 1 && q.contract_months === 12 && <div className="hint">{t('quote.longer')}</div>}
        <div className="held">⏳ {t('quote.held', { date: held })}</div>
      </div>

      {s.proof.segment > 0 && (
        <div className="proof">👥 {t('proof.segment', { n: s.proof.segment })}
          {s.proof.city > 0 && <> · {t('proof.city', { n: s.proof.city, city: s.proof.city_name })}</>}
        </div>
      )}

      {q.tiers.length > 1 && <>
        <h3 className="section">{t('tier.title')}</h3>
        <div className="tiers" role="radiogroup" aria-label={t('tier.title')}>
          {q.tiers.map((x) => (
            <button key={x.key} role="radio" aria-checked={active === x.key}
              className={`tier ${active === x.key ? 'on' : ''} ${x.key === 'recommended' ? 'pop' : ''}`}
              onClick={() => active !== x.key && update(x.selections)}>
              {x.key === 'recommended' && <span className="badge">⭐ {t('tier.popular')}</span>}
              <b>{t(`tier.${x.key}`)}</b>
              <span className="tp">{rupees(x.monthly)}</span>
              <small>{t('tier.items', { n: x.count })}</small>
              <span className="ticons" aria-hidden>{x.items.map((w, i) => <i key={i}>{ITEM_ICON[w] || '•'}</i>)}</span>
            </button>
          ))}
        </div>
        {active === 'custom' && <div className="muted small custom-note">✏️ {t('tier.custom')}</div>}
      </>}

      <Fixes q={q} onAdd={add} />
      <Compare q={q} />
      <Offers sell={s} />

      <div className="why-card" aria-live="polite">
        <h3>{t('quote.why')}</h3>
        {why ? <p>{why.text}</p> : <div className="skeleton"><i /><i /></div>}
        {why?.source === 'ai' && <span className="ai-tag">AI</span>}
      </div>

      <h3 className="section">{t('quote.included')}</h3>
      <ul className="lines">
        {included.map((l) => (
          <li key={l.product_id} className="line">
            <div className="line-main">
              <b>{ITEM_ICON[l.why]} {t(`item.${l.why}`)}</b>
              <span className="muted">{t(`why.${l.why}`)}</span>
              <span className="unit">{l.name} · {rupees(l.unit_price)} {t('quote.each', { unit: l.unit.replace('per ', '') })}</span>
              {l.pending_gst && <span className="pending">{t('quote.pending')}</span>}
            </div>
            <div className="line-side">
              <div className="price">{rupees(l.line_monthly)}</div>
              <div className="stepper-qty">
                <button onClick={() => setQty(l.product_id, -1)} disabled={l.qty <= 1} aria-label="-">−</button>
                <span>{l.qty}</span>
                <button onClick={() => setQty(l.product_id, +1)} aria-label="+">+</button>
              </div>
              {l.group !== 'core' && <button className="link" onClick={() => remove(l.product_id)} aria-label="remove">✕</button>}
            </div>
          </li>
        ))}
      </ul>

      {swaps.length > 0 && (
        <details className="swap">
          <summary>{t('quote.swap')}</summary>
          {swaps.map((l) => (
            <button key={l.product_id} className="swap-row" onClick={() => swap(l)}>
              <b>{l.name}</b><span>{rupees(l.unit_price)} {t('quote.each', { unit: l.unit.replace('per ', '') })}</span>
            </button>
          ))}
        </details>
      )}

      {addons.length > 0 && <h3 className="section">{t('quote.addons')}</h3>}
      <ul className="lines addons">
        {addons.map((l) => (
          <li key={l.product_id} className={`line ${l.locked.length ? 'locked' : ''}`}>
            <div className="line-main">
              <b>{ITEM_ICON[l.why]} {t(`item.${l.why}`)}</b>
              <span className="muted">{t(`why.${l.why}`)}</span>
              <span className="unit">{l.name} · {rupees(l.unit_price)} {t('quote.each', { unit: l.unit.replace('per ', '') })}</span>
              <LockReason line={l} />
            </div>
            <div className="line-side">
              <button className="btn small" disabled={l.locked.length > 0} onClick={() => add(l)}>+ {rupees(l.unit_price * l.qty)}</button>
            </div>
          </li>
        ))}
      </ul>
      {error && <div className="warn-line">{error}</div>}

      <div className="dock sticky stack">
        <div className="dock-row">
          <div className="totals"><b>{rupees(q.totals.monthly)}</b><small>{t('common.per_month')}</small></div>
          <button className="btn ghost" onClick={onBack}>{t('common.back')}</button>
          <button className="btn primary" disabled={busy} onClick={onAccept}>{t('quote.get')} →</button>
        </div>
        <div className="reassure">🔒 {t('quote.reassure')}</div>
      </div>
    </section>
  )
}
