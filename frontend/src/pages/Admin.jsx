import { useEffect, useState } from 'react'
import { api, rupees } from '../api'

const REASON = {
  wants_human: 'Asked for a person',
  advisor_stuck: 'Advisor could not understand after 2 tries',
  city_unverified: 'City outside the service list',
  kyc_blocked: 'KYC blocked (e.g. GSTIN cancelled)',
  kyc_manual_review: 'KYC needs a human check',
}
const NEXT = {
  wants_human: 'Call within 1 working hour in their language',
  advisor_stuck: 'Call; the chat could not capture their needs',
  city_unverified: 'Partner confirms coverage, then quote',
  kyc_blocked: 'Offer the Udyam-only starter plan; check GST status with owner',
  kyc_manual_review: 'Verify documents in person or by video call',
}

function Bar({ value, max, label }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar"><i style={{ width: `${Math.max(2, (value / max) * 100)}%` }} /></div>
      <span className="bar-val">{value.toLocaleString('en-IN')}</span>
    </div>
  )
}

function Leads() {
  const [rows, setRows] = useState(null)
  const [model, setModel] = useState(null)
  const [owner, setOwner] = useState('')
  const [segment, setSegment] = useState('')

  useEffect(() => { api.adminModel().then(setModel) }, [])
  useEffect(() => {
    setRows(null)
    const q = new URLSearchParams({ limit: 40, ...(owner && { owner }), ...(segment && { segment }) })
    api.adminLeads(q.toString()).then(setRows)
  }, [owner, segment])

  return (
    <div>
      {model && (
        <div className="model-card">
          <div><b>{model.auc}</b><span>AUC (held-out)</span></div>
          <div><b>{model.top_decile_lift}×</b><span>top-10% lift</span></div>
          <div><b>{(model.base_rate * 100).toFixed(1)}%</b><span>base activation</span></div>
          <div className="drivers">
            <span>▲ {model.drivers_up.slice(0, 3).map((d) => d[0]).join(' · ')}</span>
            <span>▼ {model.drivers_down.slice(0, 3).map((d) => d[0]).join(' · ')}</span>
          </div>
        </div>
      )}
      <div className="filters">
        <select value={owner} onChange={(e) => setOwner(e.target.value)}>
          <option value="">All owners</option><option>Field sales</option><option>Channel partner</option><option>Digital nudge</option>
        </select>
        <select value={segment} onChange={(e) => setSegment(e.target.value)}>
          <option value="">All segments</option><option value="micro">Micro retail</option><option value="prof">Professional offices</option>
          <option value="multi">Multi-site</option><option value="mfg">Manufacturers</option>
        </select>
        <span className="muted small">Dropped leads ranked by chance to convert × typical bundle value</span>
      </div>
      {!rows ? <p className="muted">Loading…</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Lead</th><th>Score</th><th>Exp. ₹/mo</th><th>Why this score</th><th>Dropped because</th><th>Next best action</th><th>Owner</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.lead_id}>
                  <td><b>{r.business}</b><div className="muted small">{r.business_type} · {r.city} · {r.language}</div></td>
                  <td><div className="score"><i style={{ width: `${r.score * 100 * 1.6}%` }} /></div><span className="small">{(r.score * 100).toFixed(0)}%</span></td>
                  <td>{rupees(r.expected_mrr)}</td>
                  <td className="small">{r.why.map((w, i) => <div key={i} className={w[0] === '+' ? 'pos' : 'neg'}>{w}</div>)}</td>
                  <td className="small">{r.drop_reason}<div className="muted">{r.stage}</div></td>
                  <td><b>{r.action}</b><div className="muted small">{r.how}</div></td>
                  <td><span className={`owner ${r.owner.split(' ')[0].toLowerCase()}`}>{r.owner}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Handoffs() {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    const load = () => api.adminHandoffs().then(setRows)
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])
  if (!rows) return <p className="muted">Loading…</p>
  if (!rows.length) return <p className="muted">No hand-offs yet. Run the advisor, say "I want to talk to a person", or try applicant K01 or K07 in KYC.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>When</th><th>Why it needs a human</th><th>Who</th><th>Language</th><th>Suggested next step</th></tr></thead>
        <tbody>
          {rows.map((h) => {
            const p = h.summary.profile || {}
            return (
              <tr key={h.id}>
                <td className="small">{h.ts.replace('T', ' ').slice(0, 16)}</td>
                <td><b>{REASON[h.reason] || h.reason}</b></td>
                <td className="small">{p.business_type || p.segment || '—'}<div className="muted">{p.city || '—'} · {p.employees || '?'} people</div></td>
                <td>{h.summary.language}</td>
                <td className="small">{NEXT[h.reason]}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Insights() {
  const [d, setD] = useState(null)
  useEffect(() => { api.adminInsights().then(setD) }, [])
  if (!d) return <p className="muted">Loading…</p>
  const maxF = d.funnel[0].leads
  const maxD = d.drop_reasons[0].count
  return (
    <div className="insights">
      <div className="callout">Leads with a GSTIN activate at <b>{d.gstin.with}%</b>, without at <b>{d.gstin.without}%</b>. Udyam-only KYC opens a path for the rest.</div>
      <h3>Segments (Apr–Jun 2026, ranked by first-year revenue per ₹ of acquisition cost)</h3>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Segment</th><th>Share of leads</th><th>Converts</th><th>Avg ₹/mo</th><th>CAC per activation</th><th>6-mo churn</th><th>Days to activate</th></tr></thead>
          <tbody>
            {d.segments.map((s) => (
              <tr key={s.key}><td><b>{s.segment}</b></td><td>{s.share}%</td><td>{s.conversion}%</td><td>{rupees(s.avg_monthly_value)}</td>
                <td>{rupees(s.cac)}</td><td>{s.churn}%</td><td>{s.days_to_activate}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="two-col">
        <div><h3>Funnel</h3>{d.funnel.map((f) => <Bar key={f.stage} label={f.stage} value={f.leads} max={maxF} />)}</div>
        <div><h3>Top drop reasons</h3>{d.drop_reasons.map((f) => <Bar key={f.reason} label={f.reason} value={f.count} max={maxD} />)}</div>
      </div>
    </div>
  )
}

export default function Admin() {
  const [tab, setTab] = useState('leads')
  return (
    <div className="admin">
      <header className="admin-top">
        <a href="#/" className="brand">● <b>Accel</b> Business · Sales &amp; partner view</a>
        <nav>
          {[['leads', 'Who to call'], ['handoffs', 'Live hand-offs'], ['insights', 'Insights']].map(([k, label]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>
          ))}
        </nav>
      </header>
      <main className="admin-body">
        {tab === 'leads' && <Leads />}
        {tab === 'handoffs' && <Handoffs />}
        {tab === 'insights' && <Insights />}
      </main>
    </div>
  )
}
