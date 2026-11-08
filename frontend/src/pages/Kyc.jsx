import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n.jsx'

const SLOTS = ['gst', 'udyam', 'id', 'address']
const ICON = { pass: '✓', warn: '!', fail: '✕' }
const VERDICT_KEY = { verified: 'verified', action_needed: 'action', manual_review: 'review', blocked: 'blocked' }

function Consent({ onAnswer }) {
  const { t } = useT()
  return (
    <div className="card consent">
      <h2>🔒 {t('kyc.consent.title')}</h2>
      <ul className="consent-list">
        <li>{t('kyc.consent.purpose')}</li>
        <li>{t('kyc.consent.data')}</li>
        <li>{t('kyc.consent.retain')}</li>
        <li>{t('kyc.consent.rights')}</li>
      </ul>
      <div className="row">
        <button className="btn ghost" onClick={() => onAnswer(false)}>{t('kyc.consent.decline')}</button>
        <button className="btn primary" onClick={() => onAnswer(true)}>{t('kyc.consent.agree')}</button>
      </div>
    </div>
  )
}

function Lookup({ kind, value, setValue }) {
  const { t } = useT()
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const go = async () => {
    if (!value.trim()) return
    setBusy(true)
    try { setRes(await (kind === 'gstin' ? api.gstin(value) : api.udyam(value))) } finally { setBusy(false) }
  }
  const name = res?.legal_name || res?.name
  return (
    <div className="lookup">
      <label>{t(kind === 'gstin' ? 'kyc.gstin' : 'kyc.udyam')}</label>
      <div className="row tight">
        <input value={value} onChange={(e) => { setValue(e.target.value.toUpperCase()); setRes(null) }}
          placeholder={kind === 'gstin' ? '27ABCDE1234F1Z5' : 'UDYAM-MH-00-1234567'} spellCheck={false} autoCapitalize="characters" />
        <button className="btn small" onClick={go} disabled={busy || !value.trim()}>{t('kyc.lookup')}</button>
      </div>
      {res && (res.found ? (
        <div className={`found ${res.status && res.status !== 'Active' ? 'bad' : 'good'}`}>
          ✓ {t('kyc.found', { name })}
          {res.status && <b> · {t('kyc.status', { status: res.status })}</b>}
        </div>
      ) : <div className="found bad">✕ {t('kyc.notfound')}</div>)}
    </div>
  )
}

function Slot({ slot, state, onFile, disabled }) {
  const { t } = useT()
  const ref = useRef(null)
  const info = state?.info
  const status = state?.status
  return (
    <div className={`slot ${status || ''} ${state?.needsFix ? 'fix' : ''}`}>
      <div className="slot-head">
        <b>{t(`kyc.doc.${slot}`)}</b>
        {status === 'uploading' && <span className="spin" aria-label={t('kyc.checking')} />}
        {status === 'done' && <span className="ok">{info.blurry ? '✕' : '✓'}</span>}
      </div>
      {status === 'done' && (
        <div className="slot-info">
          {info.blurry && <div className="warn-line">Too blurry (sharpness {info.sharpness})</div>}
          {info.deskewed_deg ? <div className="note-line">↻ Straightened {Math.abs(info.deskewed_deg)}°</div> : null}
          {info.corrections?.map((c, i) => <div key={i} className="note-line">≈ {c.read_as} → {c.corrected_to}</div>)}
          {!info.blurry && <div className="muted small">{Object.values(info.fields).filter(Boolean).slice(0, 2).join(' · ')}</div>}
        </div>
      )}
      {status === 'error' && <div className="warn-line">{state.error}</div>}
      <input ref={ref} type="file" accept="image/*" hidden onChange={(e) => e.target.files[0] && onFile(slot, e.target.files[0])} />
      <button className="btn small ghost" disabled={disabled || status === 'uploading'} onClick={() => ref.current.click()}>
        {status === 'done' ? t('kyc.replace') : t('kyc.upload')}
      </button>
    </div>
  )
}

export default function Kyc({ session, kyc, setKyc, onBack, onDone }) {
  const { t } = useT()
  const sid = session.session_id
  const [consent, setConsent] = useState(null) // null = not asked, true, false
  const [docs, setDocs] = useState({})
  const [gstin, setGstin] = useState('')
  const [udyam, setUdyam] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState(null)
  const [sample, setSample] = useState('')
  const [specimens, setSpecimens] = useState([])

  useEffect(() => { api.specimens().then(setSpecimens).catch(() => {}) }, [])

  const answerConsent = async (ok) => {
    await api.consent(sid, ok)
    setConsent(ok)
  }

  const uploadFile = async (slot, file) => {
    setKyc(null)
    setConfirmed(false)
    setDocs((d) => ({ ...d, [slot]: { status: 'uploading' } }))
    try {
      const info = await api.upload(sid, slot, file)
      setDocs((d) => ({ ...d, [slot]: { status: 'done', info } }))
    } catch (e) {
      setDocs((d) => ({ ...d, [slot]: { status: 'error', error: e.message } }))
    }
  }

  const loadSample = async (k) => {
    setSample(k)
    if (!k) return
    const sp = specimens.find((s) => s.id === k)
    setDocs({})
    // anything we upload for a previous applicant must go, or a missing document would keep its old copy
    await Promise.all(SLOTS.map((s) => api.removeDoc(sid, s)))
    await Promise.all(sp.slots.map(async (slot) => {
      const blob = await (await fetch(api.specimenUrl(k, slot))).blob()
      return uploadFile(slot, new File([blob], `${k}_${slot}.png`, { type: 'image/png' }))
    }))
  }

  const verify = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.verify(sid, { gstin: gstin || null, udyam: udyam || null })
      setKyc(r)
      setConfirmed(false)
      const fix = new Set(r.fix_docs)
      setDocs((d) => Object.fromEntries(Object.entries(d).map(([k, v]) => [k, { ...v, needsFix: fix.has(k) }])))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (consent === false) {
    return (
      <div className="card center">
        <p>{t('kyc.consent.rights')}</p>
        <button className="btn ghost" onClick={onBack}>{t('common.back')}</button>
        <button className="btn primary" onClick={() => setConsent(null)}>{t('kyc.consent.agree')}</button>
      </div>
    )
  }
  if (consent !== true) return <Consent onAnswer={answerConsent} />

  const uploading = Object.values(docs).some((d) => d.status === 'uploading')
  const corrections = kyc?.checks.filter((c) => c.id === 'autocorrected') || []
  const canContinue = kyc && kyc.verdict !== 'action_needed' && (!corrections.length || confirmed)
  const problems = kyc ? kyc.checks.filter((c) => c.status !== 'pass') : []
  const passed = kyc ? kyc.checks.filter((c) => c.status === 'pass') : []

  return (
    <section className="kyc">
      <h2>{t('kyc.title')}</h2>

      <div className="card">
        <h3>{t('kyc.lookup.title')}</h3>
        <Lookup kind="gstin" value={gstin} setValue={setGstin} />
        <Lookup kind="udyam" value={udyam} setValue={setUdyam} />
      </div>

      <div className="card">
        {specimens.length > 0 && (
          <div className="sample">
            <select value={sample} onChange={(e) => loadSample(e.target.value)} aria-label={t('kyc.sample')}>
              <option value="">🧪 {t('kyc.sample')}…</option>
              {specimens.map((s) => <option key={s.id} value={s.id}>{s.id} ({s.slots.length}/4)</option>)}
            </select>
          </div>
        )}
        <div className="slots">
          {SLOTS.map((s) => <Slot key={s} slot={s} state={docs[s]} onFile={uploadFile} />)}
        </div>
        <button className="btn primary block" disabled={busy || uploading} onClick={verify}>
          {busy || uploading ? t('kyc.checking') : t('kyc.verify')}
        </button>
        {error && <div className="warn-line">{error}</div>}
      </div>

      {kyc && (
        <div className={`card verdict ${kyc.verdict}`}>
          <div className="verdict-head">
            <span className="v-icon">{{ verified: '✓', action_needed: '!', manual_review: '👁', blocked: '✕' }[kyc.verdict]}</span>
            <b>{t(`verdict.${VERDICT_KEY[kyc.verdict]}`)}</b>
          </div>
          {kyc.summary.business_name && (
            <div className="summary">{kyc.summary.business_name}{kyc.summary.gstin_masked ? ` · ${kyc.summary.gstin_masked}` : ''}</div>
          )}
          <ul className="checks">
            {problems.map((c, i) => (
              <li key={i} className={`check ${c.status}`}>
                <span className="ci">{ICON[c.status]}</span>
                <div><b>{t(`chk.${c.id}`, null, c.id)}</b><div className="muted small">{c.detail}</div></div>
              </li>
            ))}
          </ul>
          {passed.length > 0 && (
            <details className="passed">
              <summary>✓ {passed.length} {t('common.yes') === 'Yes' ? 'checks passed' : '✓'}</summary>
              <ul className="checks">
                {passed.map((c, i) => (
                  <li key={i} className="check pass">
                    <span className="ci">✓</span>
                    <div><b>{t(`chk.${c.id}`, null, c.id)}</b><div className="muted small">{c.detail}</div></div>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {corrections.length > 0 && (
            <label className="confirm-box"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> {t('chk.autocorrected')}</label>
          )}
          {kyc.held_products.length > 0 && <div className="note-line">{t('confirm.held')}: {kyc.held_products.join(', ')}</div>}
        </div>
      )}

      <div className="dock sticky">
        <button className="btn ghost" onClick={onBack}>{t('common.back')}</button>
        <button className="btn primary" disabled={!canContinue} onClick={onDone}>{t('common.continue')} →</button>
      </div>
    </section>
  )
}
