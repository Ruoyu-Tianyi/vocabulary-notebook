'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { backendOrigin, isBackendUrl, isExportUrl, isAllowedExternalUrl, authenticatedHeaders, TOKEN_HEADER } = require('../lib/policy.cjs')

const origin = 'http://127.0.0.1:41235'

test('readiness accepts only a canonical loopback HTTP origin with an allocated port', () => {
  assert.equal(backendOrigin(`${origin}/`), origin)
  for (const bad of ['http://localhost:41235', 'http://127.0.0.1:0', 'http://127.0.0.1:65536', 'http://127.0.0.1:080', 'http://127.0.0.1:41235/api', 'https://127.0.0.1:41235', 'http://127.0.0.1:41235@evil.example', null]) {
    assert.throws(() => backendOrigin(bad))
  }
})

test('request authentication never leaks across origins, including a redirected header', () => {
  const headers = { Accept: 'application/json', 'x-vocove-desktop-token': 'old-secret' }
  const local = authenticatedHeaders(`${origin}/api/words`, headers, origin, 'new-secret')
  assert.deepEqual(local, { Accept: 'application/json', [TOKEN_HEADER]: 'new-secret' })
  for (const url of ['https://accounts.google.com/o/oauth2/v2/auth', 'http://127.0.0.1:41236/api', 'http://127.0.0.1:41235.evil.example', 'file:///etc/passwd', `${origin.replace('http://', 'http://user:pass@')}/api`]) {
    assert.equal(isBackendUrl(url, origin), false)
    assert.deepEqual(authenticatedHeaders(url, local, origin, 'new-secret'), { Accept: 'application/json' })
  }
  assert.equal(headers['x-vocove-desktop-token'], 'old-secret')
})

test('only known backend exports can invoke a native save dialog', () => {
  assert.equal(isExportUrl(`${origin}/api/words/export?format=pdf`, origin), true)
  assert.equal(isExportUrl(`${origin}/api/library/export`, origin), true)
  for (const url of [`${origin}/api/words`, `${origin}/api/library/export/other`, 'https://example.com/api/words/export']) assert.equal(isExportUrl(url, origin), false)
})

test('system browser links are restricted to the existing Google UI destinations', () => {
  assert.equal(isAllowedExternalUrl('https://accounts.google.com/o/oauth2/v2/auth?state=test'), true)
  assert.equal(isAllowedExternalUrl('https://console.cloud.google.com/apis/library/drive.googleapis.com'), true)
  for (const url of ['javascript:alert(1)', 'file:///tmp/a', 'https://accounts.google.com.evil.example/o/oauth2/v2/auth', 'https://user:pass@accounts.google.com/o/oauth2/v2/auth', 'https://accounts.google.com:444/o/oauth2/v2/auth', 'http://accounts.google.com/o/oauth2/v2/auth', 'https://accounts.google.com/unrelated', 'https://example.com']) assert.equal(isAllowedExternalUrl(url), false)
})
