import test from 'node:test'
import assert from 'node:assert/strict'
import { deleteWord, fetchReviewStats, fetchWord, fetchWords, rateWord, updateWord } from '../src/api.js'

test('word search safely encodes filters and notebook identity', async t => {
  const response = { words: [], pages: 1, total: 0 }
  const mocked = t.mock.method(globalThis, 'fetch', async () => Response.json(response))
  assert.deepEqual(await fetchWords({ q: 'A&B + C?', notebook_id: '本 / 1', page: 3 }), response)
  const url = new URL(mocked.mock.calls[0].arguments[0], 'http://localhost')
  assert.equal(url.pathname, '/api/words')
  assert.equal(url.searchParams.get('q'), 'A&B + C?')
  assert.equal(url.searchParams.get('notebook_id'), '本 / 1')
  assert.equal(url.searchParams.get('page'), '3')
})

test('API failures preserve status and structured conflict details', async t => {
  const detail = { message: '当前单词本已存在', word: { id: 'existing' } }
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail }, { status: 409 }))
  await assert.rejects(fetchWord('one'), error => {
    assert.equal(error.message, detail.message)
    assert.equal(error.status, 409)
    assert.deepEqual(error.details, detail)
    return true
  })
})

test('non-JSON API errors retain an actionable message and HTTP status', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('offline', { status: 503, statusText: 'Service Unavailable' }))
  await assert.rejects(fetchWord('one'), error => error.status === 503 && error.message === 'Service Unavailable')
})

test('review stats forwards AbortSignal so superseded refreshes can be cancelled', async t => {
  const controller = new AbortController()
  const mocked = t.mock.method(globalThis, 'fetch', async () => Response.json({ due_today: 7 }))
  assert.deepEqual(await fetchReviewStats('default', { signal: controller.signal }), { due_today: 7 })
  assert.equal(mocked.mock.calls[0].arguments[1].signal, controller.signal)
})

test('all word-specific API operations keep imported IDs inside one path segment', async t => {
  const id = '../../\\evil.example?next=other#fragment'
  const expected = `/api/words/${encodeURIComponent(id)}`
  const mocked = t.mock.method(globalThis, 'fetch', async () => Response.json({}))
  const previousWindow = globalThis.window
  globalThis.window = new EventTarget()
  t.after(() => {
    if (previousWindow === undefined) delete globalThis.window
    else globalThis.window = previousWindow
  })
  await fetchWord(id)
  await updateWord(id, { definition: 'test' })
  await deleteWord(id)
  await rateWord(id, 3)
  assert.deepEqual(mocked.mock.calls.map(call => call.arguments[0]), [expected, expected, expected, `${expected}/review`])
  assert.deepEqual(mocked.mock.calls.map(call => call.arguments[1].method || 'GET'), ['GET', 'PUT', 'DELETE', 'POST'])
})
