// Remember the notebook the user last switched to, so "add word" defaults to it
// from any page. Only the notebook ID is stored; vocabulary never leaves the server.
const KEY = 'vocove-last-notebook'
let memory = null

export function rememberNotebook(id) {
  if (!id) return
  memory = id
  try { localStorage.setItem(KEY, id) } catch { /* Storage may be unavailable. */ }
}

export function lastNotebook() {
  if (memory !== null) return memory
  try { memory = localStorage.getItem(KEY) || '' } catch { memory = '' }
  return memory
}

export function forgetNotebook(id) {
  if (lastNotebook() !== id) return
  memory = ''
  try { localStorage.removeItem(KEY) } catch { /* Storage may be unavailable. */ }
}
