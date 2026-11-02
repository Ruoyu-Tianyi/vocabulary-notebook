import test from 'node:test'
import assert from 'node:assert/strict'
import { builtinProvider, selectProvider } from '../src/lib/modelSettingsState.js'

function settings(provider = 'anthropic') {
  return { provider, catalog: ['ollama', 'deepseek', 'anthropic', 'custom'].map(id => ({ id })),
    providers: { anthropic: { model: 'claude', api_key: 'draft-only' }, custom: { model: 'local' } } }
}

test('saved builtin survives round trips through the custom tab with drafts intact', () => {
  const original = settings()
  let current = original
  for (let i = 0; i < 3; i++) {
    current = selectProvider(current, 'custom')
    assert.equal(builtinProvider(current), 'anthropic')
    current = selectProvider(current, builtinProvider(current))
    assert.equal(current.provider, 'anthropic')
    assert.deepEqual(current.providers, original.providers)
  }
})

test('most recently selected builtin wins even before saving', () => {
  const current = selectProvider(selectProvider(settings(), 'ollama'), 'custom')
  assert.equal(builtinProvider(current), 'ollama')
})

test('custom loaded from server restores remembered builtin and handles older configs', () => {
  assert.equal(builtinProvider({ ...settings('custom'), last_builtin_provider: 'ollama' }), 'ollama')
  assert.equal(builtinProvider({ ...settings('custom'), last_builtin_provider: 'invalid' }), 'anthropic')
  assert.equal(builtinProvider({ ...settings('custom'), providers: {} }), 'ollama')
})

test('clicking the selected tab leaves the draft unchanged', () => {
  const current = settings()
  assert.equal(selectProvider(current, 'anthropic'), current)
})
