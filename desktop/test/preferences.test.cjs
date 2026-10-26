'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { sanitizePreferences } = require('../lib/preferences.cjs')

const preload = fs.readFileSync(path.join(__dirname, '../lib/preferences-preload.cjs'), 'utf8')

test('preference persistence drops arbitrary keys and invalid values', () => {
  assert.deepEqual(sanitizePreferences({ theme: 'light', 'vocove-word-sort': 'alpha_asc', token: 'secret' }), { theme: 'light', 'vocove-word-sort': 'alpha_asc' })
  for (const value of [null, [], 'string', { theme: '<script>', 'vocove-word-sort': {} }]) assert.deepEqual(sanitizePreferences(value), {})
})

test('sandbox preload replaces stale port preferences once per window and preserves reload changes', () => {
  const stored = new Map([['theme', 'dark']])
  const session = new Map()
  const context = {
    process: { argv: ['--vocove-origin=http://127.0.0.1:40000', '--vocove-window=window-one', '--vocove-preferences={"theme":"light","vocove-word-sort":"alpha_desc","secret":"ignored"}'] },
    location: { origin: 'http://127.0.0.1:40000' },
    localStorage: { getItem: key => stored.get(key) ?? null, setItem: (key, value) => stored.set(key, value), removeItem: key => stored.delete(key) },
    sessionStorage: { getItem: key => session.get(key) ?? null, setItem: (key, value) => session.set(key, value) },
  }
  vm.runInNewContext(preload, { ...context })
  assert.equal(stored.get('theme'), 'light')
  assert.equal(stored.get('vocove-word-sort'), 'alpha_desc')
  assert.equal(stored.has('secret'), false)
  stored.set('theme', 'dark')
  vm.runInNewContext(preload, { ...context })
  assert.equal(stored.get('theme'), 'dark')
  stored.clear()
  context.location.origin = 'https://example.com'
  vm.runInNewContext(preload, { ...context })
  assert.equal(stored.size, 0)
})
