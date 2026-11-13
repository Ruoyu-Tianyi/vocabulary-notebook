import { isEditableTarget, isShortcutEvent, isWithinDialog } from './keyboard.js'

export function getGlobalShortcutAction(event) {
  const key = event.key
  const allowShift = key === '?' || key === 'N'
  if (!isShortcutEvent(event, { allowShift }) || isEditableTarget(event.target) || isWithinDialog(event.target)) return null
  if (key === '?') return 'help'
  if (key === '/') return 'search'
  if (key === 'n' || key === 'N') return 'add'
  return null
}

export function shortcutDestination(action, search = '', fallbackNotebook = '') {
  // Adding a word defaults to the notebook the user last switched to.
  const notebookId = new URLSearchParams(search).get('notebook_id') || (action === 'add' ? fallbackNotebook : '')
  const query = notebookId ? `?${new URLSearchParams({ notebook_id: notebookId })}` : ''
  return `${action === 'add' ? '/word/new' : '/'}${query}`
}
