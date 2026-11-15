import test from 'node:test'
import assert from 'node:assert/strict'
import { readPrefillMessage, replyTarget, PREFILL_TYPE } from '../src/lib/embedPrefill.js'

const parent = { name: 'parent' }
const message = (data, source = parent) => ({ data, source })

test('the direct parent can prefill a normalized word', () => {
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: '  coordinate\n  system ' }), parent), 'coordinate system')
})

test('messages from other windows or with other shapes are ignored', () => {
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: 'word' }, { name: 'other' }), parent), null)
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: 'word' }), null), null)
  assert.equal(readPrefillMessage(message({ type: 'other', word: 'word' }), parent), null)
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: 42 }), parent), null)
  assert.equal(readPrefillMessage(message('vocove:prefill-word'), parent), null)
  assert.equal(readPrefillMessage(message(null), parent), null)
})

test('empty or overly long selections are not prefilled', () => {
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: '   ' }), parent), null)
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: 'a'.repeat(81) }), parent), null)
  assert.equal(readPrefillMessage(message({ type: PREFILL_TYPE, word: 'a'.repeat(80) }), parent), 'a'.repeat(80))
})

test('acknowledgements target the parent origin, or any origin for file pages', () => {
  assert.equal(replyTarget('http://localhost:8000'), 'http://localhost:8000')
  assert.equal(replyTarget('null'), '*')
  assert.equal(replyTarget(''), '*')
})
