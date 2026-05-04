export function normalizeReportAgentResponse(data) {
  if (typeof data === 'string') {
    return data
  }

  if (!data || typeof data !== 'object') {
    return ''
  }

  const candidate = data.response ?? data.answer ?? data.content ?? data.text
  if (typeof candidate === 'string') {
    return candidate
  }

  if (candidate && typeof candidate === 'object') {
    const nested = candidate.response ?? candidate.answer ?? candidate.content ?? candidate.text
    return typeof nested === 'string' ? nested : ''
  }

  return ''
}
