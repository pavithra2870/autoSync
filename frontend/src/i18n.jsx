import { createContext, useContext } from 'react'

export const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'hi', name: 'हिन्दी' },
  { code: 'ta', name: 'தமிழ்' },
  { code: 'mr', name: 'मराठी' },
  { code: 'te', name: 'తెలుగు' },
  { code: 'bn', name: 'বাংলা' },
  { code: 'gu', name: 'ગુજરાતી' },
  { code: 'kn', name: 'ಕನ್ನಡ' },
  { code: 'ml', name: 'മലയാളം' },
  { code: 'pa', name: 'ਪੰਜਾਬੀ' },
]

export const I18nContext = createContext({ strings: {}, lang: 'en' })

/** t('quote.months', {n: 12}) -> "12 months". Falls back to `fallback`, then to the key itself. */
export function useT() {
  const { strings, lang } = useContext(I18nContext)
  const t = (key, params, fallback) => {
    let s = strings[key] ?? fallback ?? key
    if (params) for (const [k, v] of Object.entries(params)) s = s.split(`{${k}}`).join(String(v))
    return s
  }
  return { t, lang }
}
