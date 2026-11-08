// One small picture per service, so owners can scan the pack without reading product names.
export const ITEM_ICON = {
  internet_core: '🌐', alt_internet: '🌐', leased: '🔗', mobile_lines: '📱', email_cloud: '✉️',
  data_security: '🛡️', backup: '☁️', failover_sites: '🔁', sdwan: '🏢', pos: '🧾', cctv: '📹',
  whatsapp: '💬', firewall: '🧱', iot: '⚙️', phone_system: '☎️', wifi: '📶', website: '🖥️',
  static_ip: '📌', fleet: '🚚',
}

export const OFFER_ICON = { setup: '🛠️', half: '½', switch: '🔄', lang: '🗣️', ontime: '⏱️', exit: '↩️', lock: '🔒' }

// Which product answers which problem the owner told us about.
export const PAIN_PRODUCT = {
  uptime: 'P09', pos: 'P19', cctv: 'P23', whatsapp: 'P15', website: 'P18', security: 'P20',
  phone: 'P12', iot: 'P24', fleet: 'P25', backup: 'P17',
}
export const PAIN_ORDER = ['uptime', 'pos', 'cctv', 'whatsapp', 'website', 'security', 'phone', 'iot', 'fleet', 'backup', 'bills']

export const PAIN_ICON = {
  uptime: '📶', pos: '🧾', cctv: '📹', whatsapp: '💬', website: '🔎', security: '🛡️',
  phone: '☎️', iot: '⚙️', fleet: '🚚', bills: '📑',
}

export const inr = (n) => Math.round(n || 0).toLocaleString('en-IN')
