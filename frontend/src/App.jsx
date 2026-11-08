import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { I18nContext, LANGUAGES, useT } from './i18n.jsx'
import Chat from './pages/Chat.jsx'
import Quote from './pages/Quote.jsx'
import Kyc from './pages/Kyc.jsx'
import Confirm from './pages/Confirm.jsx'
import Track from './pages/Track.jsx'
import Admin from './pages/Admin.jsx'

const STEPS = ['chat', 'quote', 'kyc', 'confirm', 'track']

function useHash() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const on = () => setHash(window.location.hash)
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return hash
}

function Stepper({ step }) {
  const { t } = useT()
  const idx = STEPS.indexOf(step)
  return (
    <ol className="stepper" aria-label="progress">
      {STEPS.map((s, i) => (
        <li key={s} className={i < idx ? 'done' : i === idx ? 'now' : ''}>
          <span className="dot">{i < idx ? '✓' : i + 1}</span>
          <span className="lbl">{t(`step.${s}`)}</span>
        </li>
      ))}
    </ol>
  )
}

function LanguagePicker({ onPick }) {
  return (
    <div className="lang-screen">
      <div className="brand-hero">
        <div className="logo-mark" aria-hidden>●</div>
        <h1>Accel Business</h1>
        <p>Choose your language · अपनी भाषा चुनें</p>
      </div>
      <div className="lang-grid">
        {LANGUAGES.map((l) => (
          <button key={l.code} className="lang-card" onClick={() => onPick(l.code)}>{l.name}</button>
        ))}
      </div>
      <a className="admin-link" href="#/admin">Sales &amp; partner view →</a>
    </div>
  )
}

function Journey() {
  const [lang, setLang] = useState(null)
  const [strings, setStrings] = useState({})
  const [step, setStep] = useState('chat')
  const [session, setSession] = useState(null) // {session_id, profile, mode, ...}
  const [health, setHealth] = useState(null)
  const [order, setOrder] = useState(null)
  const [kyc, setKyc] = useState(null) // last verify() response
  const hash = useHash()

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth({ llm: false })) }, [])

  // open an existing order directly: #/track/AB12CD
  useEffect(() => {
    const m = hash.match(/^#\/track\/(\w+)/)
    if (!m) return
    api.order(m[1]).then(async (o) => {
      const d = await api.i18n(o.language || 'en')
      setStrings(d.strings); setLang(o.language || 'en'); setOrder(o); setStep('track')
    }).catch(() => {})
  }, [hash])

  const pickLanguage = useCallback(async (code) => {
    const d = await api.i18n(code)
    setStrings(d.strings)
    setLang(code)
    // translations for a language we have not cached are produced in the background; refresh once
    if (d.coverage < 0.9) setTimeout(() => api.i18n(code).then((x) => setStrings(x.strings)), 45000)
  }, [])

  const restart = () => { setLang(null); setSession(null); setOrder(null); setKyc(null); setStep('chat'); window.location.hash = '' }

  if (!lang) return <LanguagePicker onPick={pickLanguage} />

  return (
    <I18nContext.Provider value={{ strings, lang }}>
      <header className="topbar">
        <button className="brand" onClick={restart} title="Start over">● <b>Accel</b> Business</button>
        <span className={`mode ${health?.llm ? 'ai' : 'rules'}`}>{health?.llm ? strings['mode.ai'] : strings['mode.rules']}</span>
      </header>
      <Stepper step={step} />
      <main className="page">
        {step === 'chat' && (
          <Chat lang={lang} session={session} setSession={setSession} onDone={() => setStep('quote')} />
        )}
        {step === 'quote' && <Quote session={session} onBack={() => setStep('chat')} onAccept={() => setStep('kyc')} />}
        {step === 'kyc' && (
          <Kyc session={session} kyc={kyc} setKyc={setKyc} onBack={() => setStep('quote')} onDone={() => setStep('confirm')} />
        )}
        {step === 'confirm' && (
          <Confirm session={session} kyc={kyc} onBack={() => setStep('kyc')}
            onOrder={(o) => { setOrder(o); setStep('track'); window.location.hash = `#/track/${o.id}` }} />
        )}
        {step === 'track' && order && <Track order={order} setOrder={setOrder} onRestart={restart} />}
      </main>
    </I18nContext.Provider>
  )
}

export default function App() {
  const hash = useHash()
  return (
    <div className={hash.startsWith('#/admin') ? 'shell wide' : 'shell'}>
      {hash.startsWith('#/admin') ? <Admin /> : <Journey />}
    </div>
  )
}
