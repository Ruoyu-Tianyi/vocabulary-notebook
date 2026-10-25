import test from 'node:test'
import assert from 'node:assert/strict'
import { createPath, resolvePath } from 'react-router-dom'
import { wordApiPath, wordDetailPath } from '../src/lib/wordPaths.js'

test('word detail links cannot turn an imported ID into an external URL', () => {
  const base = 'http://localhost:1400'
  const ids = [
    '../../\\evil.example',
    '\\\\evil.example',
    '//evil.example',
    '/\\evil.example',
    'https://evil.example',
    '..%2f..%2f\\evil.example',
    'word?redirect=//evil.example#fragment',
  ]
  for (const id of ids) {
    // 经过实际安装的路由解析器，防止点段归一化重新产生外部 URL。
    const path = createPath(resolvePath(wordDetailPath(id), '/'))
    const url = new URL(path, base)
    assert.equal(url.origin, base, id)
    assert.equal(url.pathname, `/word/${encodeURIComponent(id)}`, id)
    assert.equal(url.search, '')
    assert.equal(url.hash, '')
  }
})

test('ordinary generated word IDs retain their existing detail and API routes', () => {
  const id = 'abc123def456'
  assert.equal(wordDetailPath(id), `/word/${id}`)
  assert.equal(wordApiPath(id), `/words/${id}`)
})
