import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeThemePreference, resolveTheme } from '../src/lib/theme.js'

test('theme defaults to following the system', () => {
  assert.equal(normalizeThemePreference(null), 'system')
  assert.equal(normalizeThemePreference(''), 'system')
  assert.equal(normalizeThemePreference('unexpected'), 'system')
})

test('saved explicit theme preferences remain valid', () => {
  assert.equal(normalizeThemePreference('light'), 'light')
  assert.equal(normalizeThemePreference('dark'), 'dark')
  assert.equal(normalizeThemePreference('system'), 'system')
})

test('system preference follows the current operating system appearance', () => {
  assert.equal(resolveTheme('system', true), 'dark')
  assert.equal(resolveTheme('system', false), 'light')
})

test('explicit preferences override the operating system appearance', () => {
  assert.equal(resolveTheme('dark', false), 'dark')
  assert.equal(resolveTheme('light', true), 'light')
})
