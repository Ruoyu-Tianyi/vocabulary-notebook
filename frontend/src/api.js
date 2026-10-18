const BASE = '/api'

export function activeNotebookId() {
  return localStorage.getItem('vocabulary-notebook-id') ?? 'default'
}

function scoped(url) {
  return `${url}${url.includes('?') ? '&' : '?'}notebook_id=${encodeURIComponent(activeNotebookId())}`
}

async function request(url, options = {}) {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const error = new Error(typeof err.detail === 'string' ? err.detail : err.detail?.message || '请求失败')
    error.status = res.status
    error.details = err.detail
    throw error
  }
  return res
}

export async function fetchWords({ q = '', date = '', page = 1, size = 20, sort = '', letter = '' } = {}) {
  const params = new URLSearchParams({ q, date, page, size, sort, letter })
  const res = await request(scoped(`/words?${params}`))
  return res.json()
}

export async function fetchDates() {
  const res = await request(scoped('/dates'))
  return res.json()
}

export async function fetchWord(id) {
  const res = await request(`/words/${id}`)
  return res.json()
}

export async function createWord(word, definition = '', notebook_id = activeNotebookId() || 'default') {
  const res = await request('/words', {
    method: 'POST',
    body: JSON.stringify({ word, definition, notebook_id }),
  })
  return res.json()
}

export async function retryWordEnrichment(id) {
  const result = await request(`/words/${id}/enrich`, { method: 'POST' })
  return result.json()
}

export async function updateWord(id, data) {
  const res = await request(`/words/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
  return res.json()
}

export async function deleteWord(id) {
  await request(`/words/${id}`, { method: 'DELETE' })
}

export function exportUrl(format, { q = '', date = '', sort = '' } = {}) {
  const params = new URLSearchParams({ format, q, date, sort })
  return BASE + scoped(`/words/export?${params}`)
}

export async function enrichMissing() {
  const res = await request(scoped('/words/enrich-missing'), { method: 'POST' })
  return res.json()
}

export async function fetchReviewStats() {
  const res = await request(scoped('/review/stats'))
  return res.json()
}

export async function fetchReviewDue(limit = 20) {
  const params = new URLSearchParams({ limit: String(limit) })
  const res = await request(scoped(`/review/due?${params}`))
  return res.json()
}

export async function rateWord(wordId, rating) {
  const res = await request(`/words/${wordId}/review`, {
    method: 'POST',
    body: JSON.stringify({ rating }),
  })
  const result = await res.json()
  window.dispatchEvent(new Event('review-stats-changed'))
  return result
}

export async function libraryRequest(path, method = 'GET', body) {
  const result = await request(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
  return result.json()
}
