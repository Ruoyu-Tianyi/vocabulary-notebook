import { wordApiPath } from './lib/wordPaths.js'

const BASE = '/api'

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

export async function fetchWords({ q = '', date = '', page = 1, size = 20, sort = '', letter = '', notebook_id = '' } = {}) {
  const params = new URLSearchParams({ q, date, page, size, sort, letter, notebook_id })
  const res = await request(`/words?${params}`)
  return res.json()
}

export async function fetchDates(notebook_id = '') {
  const res = await request(`/dates?${new URLSearchParams({ notebook_id })}`)
  return res.json()
}

export async function fetchWord(id) {
  const res = await request(wordApiPath(id))
  return res.json()
}

export async function createWord(word, definition = '', notebook_id = 'default') {
  const res = await request('/words', {
    method: 'POST',
    body: JSON.stringify({ word, definition, notebook_id }),
  })
  const result = await res.json()
  notifyLibraryChanged()
  return result
}

export async function updateWord(id, data) {
  const res = await request(wordApiPath(id), {
    method: 'PUT',
    body: JSON.stringify(data),
  })
  const result = await res.json()
  notifyLibraryChanged()
  return result
}

export async function deleteWord(id) {
  await request(wordApiPath(id), { method: 'DELETE' })
  notifyLibraryChanged()
}

export function exportUrl(format, { q = '', date = '', sort = '', letter = '', notebook_id = '' } = {}) {
  const params = new URLSearchParams({ format, q, date, sort, letter, notebook_id })
  return `${BASE}/words/export?${params}`
}

export async function enrichMissing(notebook_id = '') {
  const res = await request(`/words/enrich-missing?${new URLSearchParams({ notebook_id })}`, { method: 'POST' })
  return res.json()
}

export async function fetchReviewStats(notebook_id = '', options = {}) {
  const res = await request(`/review/stats?${new URLSearchParams({ notebook_id })}`, options)
  return res.json()
}

export async function fetchReviewDue(limit = 20, notebook_id = '') {
  const params = new URLSearchParams({ limit: String(limit), notebook_id })
  const res = await request(`/review/due?${params}`)
  return res.json()
}

export async function rateWord(wordId, rating) {
  const res = await request(`${wordApiPath(wordId)}/review`, {
    method: 'POST',
    body: JSON.stringify({ rating }),
  })
  const result = await res.json()
  window.dispatchEvent(new Event('review-stats-changed'))
  return result
}

export async function libraryRequest(path, method = 'GET', body) {
  return (await request(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })).json()
}


function notifyLibraryChanged() {
  window.dispatchEvent(new Event('notebooks-changed'))
  window.dispatchEvent(new Event('review-stats-changed'))
}

export async function fetchNotebooks() {
  return (await request('/notebooks')).json()
}

export async function createNotebook(data) {
  const result = await libraryRequest('/notebooks', 'POST', data)
  notifyLibraryChanged()
  return result
}

export async function updateNotebook(id, data) {
  const result = await libraryRequest(`/notebooks/${encodeURIComponent(id)}`, 'PUT', data)
  notifyLibraryChanged()
  return result
}

export async function deleteNotebook(id) {
  const result = await libraryRequest(`/notebooks/${encodeURIComponent(id)}`, 'DELETE')
  notifyLibraryChanged()
  return result
}

export async function moveWords(word_ids, notebook_id) {
  const result = await libraryRequest('/words/move', 'POST', { word_ids, notebook_id })
  notifyLibraryChanged()
  return result
}

export async function copyWords(word_ids, notebook_id) {
  const result = await libraryRequest('/words/copy', 'POST', { word_ids, notebook_id })
  notifyLibraryChanged()
  return result
}
