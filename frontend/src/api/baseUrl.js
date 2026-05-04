export const DEFAULT_API_BASE_URL = 'http://localhost:5001'

export function normalizeApiBaseURL(value = DEFAULT_API_BASE_URL) {
  const rawValue = String(value || '').trim()
  if (!rawValue) {
    return ''
  }

  return rawValue.replace(/\/+$/, '').replace(/\/api$/i, '')
}

export function resolveApiBaseURL(env = import.meta.env) {
  return normalizeApiBaseURL(env?.VITE_API_BASE_URL || DEFAULT_API_BASE_URL)
}
