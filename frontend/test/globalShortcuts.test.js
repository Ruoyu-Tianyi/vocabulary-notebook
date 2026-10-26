import test from 'node:test'
import assert from 'node:assert/strict'
import { getGlobalShortcutAction, shortcutDestination } from '../src/lib/globalShortcuts.js'

const keyEvent = (key, extra = {}) => ({ key, target: { tagName: 'BODY', closest: () => null }, ...extra })

test('global shortcuts distinguish Shift+/ help from search and allow N with either case', () => {
  assert.equal(getGlobalShortcutAction(keyEvent('/')), 'search')
  assert.equal(getGlobalShortcutAction(keyEvent('?', { shiftKey: true })), 'help')
  assert.equal(getGlobalShortcutAction(keyEvent('n')), 'add')
  assert.equal(getGlobalShortcutAction(keyEvent('N', { shiftKey: true })), 'add')
  assert.equal(getGlobalShortcutAction(keyEvent('ArrowRight')), null)
})

test('global shortcuts leave editing, modal dialogs, browser commands and repeated keys alone', () => {
  for (const key of ['/', '?', 'n']) {
    for (const extra of [
      { repeat: true }, { isComposing: true }, { keyCode: 229 },
      { defaultPrevented: true }, { ctrlKey: true }, { metaKey: true }, { altKey: true },
      { target: { tagName: 'INPUT', closest: selector => selector.includes('input') ? {} : null } },
      { target: { isContentEditable: true } },
      { target: { closest: selector => selector.includes('dialog') ? {} : null } },
    ]) assert.equal(getGlobalShortcutAction(keyEvent(key, extra)), null, `${key}: ${JSON.stringify(extra)}`)
  }
})

test('navigation shortcuts retain only the notebook scope and encode special notebook IDs', () => {
  const search = '?page=8&notebook_id=book%2F%26%20%E4%B8%AD&q=old'
  assert.equal(shortcutDestination('search', search), '/?notebook_id=book%2F%26+%E4%B8%AD')
  assert.equal(shortcutDestination('add', search), '/word/new?notebook_id=book%2F%26+%E4%B8%AD')
  assert.equal(shortcutDestination('search'), '/')
  assert.equal(shortcutDestination('add', '?page=4'), '/word/new')
})
