'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { UUID } = require('builder-util-runtime')
const { environmentValue, clearEnvironmentValue, NSIS_UPGRADE_GUID } = require('../lib/compat.cjs')
const { sanitizePreferences } = require('../lib/preferences.cjs')

test('new environment names take precedence while old launch scripts still work', () => {
  const environment = { VOCAB_DESKTOP_PYTHON: 'legacy-python' }
  assert.equal(environmentValue('VOCOVE_DESKTOP_PYTHON', environment), 'legacy-python')
  environment.VOCOVE_DESKTOP_PYTHON = 'current-python'
  assert.equal(environmentValue('VOCOVE_DESKTOP_PYTHON', environment), 'current-python')
  environment.VOCOVE_DESKTOP_PYTHON = ''
  assert.equal(environmentValue('VOCOVE_DESKTOP_PYTHON', environment), '')
  clearEnvironmentValue(environment, 'VOCOVE_DESKTOP_PYTHON')
  assert.deepEqual(environment, {})
})

test('legacy preference files migrate to the new sort key without copying unknown values', () => {
  assert.deepEqual(sanitizePreferences({ theme: 'light', 'vocabulary-word-sort': 'alpha_desc', private: 'discard' }), { theme: 'light', 'vocove-word-sort': 'alpha_desc' })
  assert.equal(sanitizePreferences({ 'vocove-word-sort': 'created_asc', 'vocabulary-word-sort': 'alpha_desc' })['vocove-word-sort'], 'created_asc')
})

test('NSIS keeps the UUID derived by the locked builder for existing installations', () => {
  // app-builder-lib 26.18.0 NsisTarget 的 namespace 与原 AppID。
  const oldGuid = UUID.v5('net.ericzhou.vocabulary-notebook', UUID.parse('50e065bc-3134-11e6-9bab-38c9862bdaf3'))
  assert.equal(NSIS_UPGRADE_GUID, oldGuid)
  assert.equal(require('../electron-builder.cjs').nsis.guid, oldGuid)
})
