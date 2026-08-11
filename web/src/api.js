async function request(path, options) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ? JSON.stringify(body.detail) : `HTTP ${response.status}`)
  }
  return response.status === 204 ? null : response.json()
}

export const listProfiles = () => request('/api/profiles')
export const createProfile = (profile) =>
  request('/api/profiles', { method: 'POST', body: JSON.stringify(profile) })
export const deleteProfile = (id) => request(`/api/profiles/${id}`, { method: 'DELETE' })
export const getChart = (id, vargas = '1,9,10') =>
  request(`/api/profiles/${id}/chart?vargas=${vargas}`)
export const getDashas = (id, depth = 2) =>
  request(`/api/profiles/${id}/dashas?depth=${depth}`)
export const getTransits = (id, months = 24) =>
  request(`/api/profiles/${id}/transits?months=${months}`)
export const getLifeStages = (id, years = 12) =>
  request(`/api/profiles/${id}/life-stages?years=${years}`)
export const getRemedies = (id) => request(`/api/profiles/${id}/remedies`)
export const reportUrl = (id, years = 10) =>
  `/api/profiles/${id}/report?years=${years}`
export const getSynastry = (first, second) =>
  request(`/api/synastry?first=${first}&second=${second}`)
export const getPanchanga = (id) => request(`/api/profiles/${id}/panchanga`)
export const askQuestion = (id, question) =>
  request(`/api/profiles/${id}/ask`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
// The same answer, read as it is written. `onEvent` sees {type: 'lookup'|'token'|
// 'answer'|'error'} in the order the server produced them.
export async function askStreaming(id, question, onEvent, history = []) {
  const response = await fetch(`/api/profiles/${id}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, history }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // Server-sent events are separated by a blank line; a chunk can split one.
    const parts = buffer.split('\n\n')
    buffer = parts.pop()
    for (const part of parts) {
      const line = part.split('\n').find((l) => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
  }
}

export const searchPlaces = (q) =>
  request(`/api/places?q=${encodeURIComponent(q)}`)
export const getGlossary = () => request('/api/glossary')
export const getHouse = (id, house, varga = 'D1') =>
  request(`/api/profiles/${id}/houses/${house}?varga=${varga}`)
export const getReading = (id) => request(`/api/profiles/${id}/reading`)
export const startReading = (id, sections = '') =>
  request(`/api/profiles/${id}/reading${sections ? `?sections=${sections}` : ''}`, {
    method: 'POST',
  })
export const corpusWorks = () => request('/api/corpus/works')
export const corpusSearch = (q) =>
  request(`/api/corpus/search?q=${encodeURIComponent(q)}`)
export const corpusPassage = (ref) => {
  const params = new URLSearchParams({ work: ref.work })
  if (ref.chapter) params.set('chapter', ref.chapter)
  if (ref.verse) params.set('verse', ref.verse)
  if (ref.page) params.set('page', ref.page)
  return request(`/api/corpus/passage?${params}`)
}
export const lookupTimezone = (latitude, longitude) =>
  request(`/api/timezone?latitude=${latitude}&longitude=${longitude}`)
