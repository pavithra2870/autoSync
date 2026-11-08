async function j(r) {
  if (!r.ok) {
    let detail
    try { detail = (await r.json()).detail } catch { /* not json */ }
    throw new Error(typeof detail === 'string' ? detail : r.statusText)
  }
  return r.json()
}
const get = (url) => fetch(url).then(j)
const send = (method, url, body) =>
  fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) }).then(j)

export const api = {
  health: () => get('/api/health'),
  i18n: (lang) => get(`/api/i18n/${lang}`),
  newSession: (language) => send('POST', '/api/session', { language }),
  answer: (sid, body) => send('POST', `/api/session/${sid}/answer`, body),
  quote: (sid) => get(`/api/session/${sid}/quote`),
  setQuote: (sid, selections, contract_months) => send('POST', `/api/session/${sid}/quote`, { selections, contract_months }),
  explanation: (sid) => get(`/api/session/${sid}/explanation`),
  gstin: (n) => get(`/api/registry/gstin/${encodeURIComponent(n)}`),
  udyam: (n) => get(`/api/registry/udyam/${encodeURIComponent(n)}`),
  consent: (sid, granted) => send('POST', `/api/session/${sid}/consent`, { granted }),
  upload: (sid, slot, file) => {
    const fd = new FormData()
    fd.append('slot', slot)
    fd.append('file', file)
    return fetch(`/api/session/${sid}/kyc/document`, { method: 'POST', body: fd }).then(j)
  },
  removeDoc: (sid, slot) => send('DELETE', `/api/session/${sid}/kyc/document/${slot}`),
  verify: (sid, body) => send('POST', `/api/session/${sid}/kyc/verify`, body),
  specimens: () => get('/api/kyc/specimens'),
  specimenUrl: (k, slot) => `/api/kyc/specimen/${k}/${slot}`,
  checkout: (sid, body) => send('POST', `/api/session/${sid}/checkout`, body),
  order: (id) => get(`/api/orders/${id}`),
  advance: (id) => send('POST', `/api/orders/${id}/advance`),
  adminLeads: (q = '') => get(`/api/admin/leads?${q}`),
  adminModel: () => get('/api/admin/model'),
  adminInsights: () => get('/api/admin/insights'),
  adminHandoffs: () => get('/api/admin/handoffs'),
}

export const rupees = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN')
