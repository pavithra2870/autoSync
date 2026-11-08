import { useEffect, useRef, useState } from 'react'
import { api, rupees } from '../api'
import { useT } from '../i18n.jsx'
import { ITEM_ICON, PAIN_ICON } from '../icons.js'

/** The pack fills up while the owner answers: they see value before they are asked for anything. */
function PackCard({ session, done }) {
  const { t } = useT()
  const seen = useRef(new Set())
  const preview = session?.preview
  const items = preview?.items || []
  const fresh = new Set(items.filter((i) => seen.current.size && !seen.current.has(i.id)).map((i) => i.id))
  useEffect(() => { seen.current = new Set(items.map((i) => i.id)) }, [preview]) // eslint-disable-line
  const total = session?.total || 8
  const left = done ? 0 : session?.left ?? total
  const pct = Math.round((100 * (total - left)) / total)
  return (
    <div className="pack" aria-live="polite">
      <div className="pack-head">
        <span>🎒 {t('chat.pack')}</span>
        {preview && <b key={preview.monthly} className="pack-price">{t('chat.about')} {rupees(preview.monthly)}<small>{t('common.per_month')}</small></b>}
      </div>
      {items.length ? (
        <div className="pack-items">
          {items.map((i) => (
            <span key={i.id} className={`pi ${fresh.has(i.id) ? 'new' : ''}`}>
              {ITEM_ICON[i.why] || '•'} {t(`item.${i.why}`)}{i.qty > 1 ? ` ×${i.qty}` : ''}
            </span>
          ))}
        </div>
      ) : <div className="pack-empty">{t('chat.pack_empty')}</div>}
      <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${pct}%` }} /></div>
      {!done && left > 0 && <div className="pack-left">{left === 1 ? t('chat.left1') : t('chat.left', { n: left })}</div>}
    </div>
  )
}

function Understood({ profile }) {
  const { t } = useT()
  if (!profile) return null
  const tags = []
  if (profile.business_type) tags.push(profile.business_type)
  else if (profile.segment) tags.push(t(`seg.${profile.segment}`))
  if (profile.city) tags.push(profile.city)
  if (profile.employees) tags.push(`${profile.employees} 👥`)
  if (profile.sites) tags.push(`${profile.sites} 📍`)
  if (profile.has_gstin === true) tags.push('GST ✓')
  else if (profile.has_udyam === true) tags.push('Udyam ✓')
  if (!tags.length) return null
  return <div className="understood">{tags.map((x, i) => <span key={i} className="tag">{x}</span>)}</div>
}

export default function Chat({ lang, session, setSession, onDone }) {
  const { t } = useT()
  const [msgs, setMsgs] = useState([])
  const [question, setQuestion] = useState(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [text, setText] = useState('')
  const [picked, setPicked] = useState([])
  const [error, setError] = useState(null)
  const bottom = useRef(null)
  const started = useRef(false)

  const apply = (r, userText) => {
    setSession(r)
    setMsgs((m) => {
      const next = userText ? [...m, { role: 'user', text: userText }] : [...m]
      r.messages.forEach((x) => next.push(x))
      if (r.question) next.push({ role: 'bot', text: r.question.text, q: true })
      return next
    })
    setQuestion(r.question)
    setDone(r.done)
    setPicked([])
  }

  useEffect(() => {
    if (started.current || session) return
    started.current = true
    setBusy(true)
    api.newSession(lang).then((r) => apply(r)).catch((e) => setError(e.message)).finally(() => setBusy(false))
  }, []) // eslint-disable-line

  useEffect(() => {
    // restoring an in-progress session when coming back from the quote screen
    if (session && !msgs.length) {
      setMsgs([{ role: 'bot', text: t('chat.done') }])
      setDone(true)
    }
  }, []) // eslint-disable-line

  // keep the latest question visible above the dock, however tall the chips make it
  const dock = useRef(null)
  const [dockH, setDockH] = useState(150)
  useEffect(() => {
    if (!dock.current || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(([e]) => setDockH(Math.ceil(e.target.getBoundingClientRect().height)))
    ro.observe(dock.current)
    return () => ro.disconnect()
  }, [done])

  useEffect(() => {
    const id = requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' }))
    return () => cancelAnimationFrame(id)
  }, [msgs, busy, dockH])

  const send = async (body, shown) => {
    setBusy(true)
    setError(null)
    try {
      apply(await api.answer(session.session_id, body), shown)
    } catch (e) {
      setError(t('err.generic'))
    } finally {
      setBusy(false)
    }
  }

  const chip = (c) => {
    if (busy) return
    if (question.multi) {
      setPicked((p) => (p.includes(c.value) ? p.filter((x) => x !== c.value) : [...p, c.value]))
    } else {
      send({ slot: question.slot, value: c.value }, c.label)
    }
  }
  const submitText = (e) => {
    e.preventDefault()
    const v = text.trim()
    if (!v || busy) return
    setText('')
    send({ text: v }, v)
  }

  return (
    <section className="chat">
      <PackCard session={session} done={done} />
      <Understood profile={session?.profile} />
      <div className="bubbles" role="log" aria-live="polite" style={{ paddingBottom: dockH + 16 }}>
        {msgs.map((m, i) => <div key={i} className={`bubble ${m.role}`}>{m.text}</div>)}
        {busy && <div className="bubble bot typing"><i /><i /><i /><span className="sr">{t('chat.typing')}</span></div>}
        {error && <div className="bubble bot err">{error}</div>}
        <div ref={bottom} />
      </div>

      {done ? (
        <div className="dock" ref={dock}>
          <button className="btn primary block glow" onClick={onDone}>🎁 {t('chat.see_plan')} →</button>
        </div>
      ) : (
        <div className="dock" ref={dock}>
          {question && !busy && (
            <div className={`chips ${question.multi ? 'multi' : ''}`} data-slot={question.slot}>
              {question.chips.map((c) => (
                <button key={c.value} data-value={c.value} className={`chip ${picked.includes(c.value) ? 'on' : ''}`} onClick={() => chip(c)}>
                  {question.slot === 'needs' && PAIN_ICON[c.value] ? `${PAIN_ICON[c.value]} ` : ''}{c.label}
                </button>
              ))}
              {question.multi && (
                <button className="chip go" onClick={() => send({ slot: question.slot, value: picked.length ? picked : ['none'] },
                  picked.length ? question.chips.filter((c) => picked.includes(c.value)).map((c) => c.label).join(', ') : t('need.none'))}>
                  {t('common.continue')} →
                </button>
              )}
              {question.skippable && !question.multi && (
                <button className="chip ghost" onClick={() => send({ skip: true }, t('common.skip'))}>{t('common.skip')}</button>
              )}
            </div>
          )}
          <form className="composer" onSubmit={submitText}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('common.type_here')}
              aria-label={t('common.type_here')} disabled={busy || !session} />
            <button className="btn primary" disabled={busy || !text.trim()}>{t('common.send')}</button>
          </form>
        </div>
      )}
    </section>
  )
}
