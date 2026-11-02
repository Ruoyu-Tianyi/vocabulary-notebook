'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const { PassThrough } = require('node:stream')
const { createUpdateFetch } = require('../lib/electron-update-fetch.cjs')

function fixture() {
  const request = new EventEmitter()
  request.end = () => {}
  request.abort = () => { request.aborted = true; request.emit('error', new Error('Redirect was cancelled')) }
  let options
  const fetch = createUpdateFetch({ request: settings => { options = settings; return request } })
  return { request, fetch, options: () => options }
}

function respond(request) {
  const response = new PassThrough()
  response.statusCode = 200
  response.headers = { 'content-type': 'application/octet-stream' }
  request.emit('response', response)
  return response
}

test('surfaces redirect without following it and tolerates Electron cancellation error', async () => {
  const f = fixture()
  const pending = f.fetch('https://github.com/test', { redirect: 'manual' })
  f.request.emit('redirect', 302, 'GET', 'https://untrusted.example/file')
  const result = await pending
  assert.equal(result.status, 302)
  assert.equal(result.headers.get('location'), 'https://untrusted.example/file')
  assert.equal(f.request.aborted, true)
  assert.equal(f.options().redirect, 'manual')
  assert.equal(f.options().credentials, 'omit')
})

test('streams response bytes', async () => {
  const f = fixture()
  const pending = f.fetch('https://github.com/test', { redirect: 'manual' })
  const incoming = respond(f.request)
  incoming.end(Buffer.from('installer'))
  assert.equal(await (await pending).text(), 'installer')
})

test('aborts before headers and during response streaming', async () => {
  for (const streaming of [false, true]) {
    const f = fixture()
    const controller = new AbortController()
    const pending = f.fetch('https://github.com/test', { redirect: 'manual', signal: controller.signal })
    let result
    if (streaming) { respond(f.request); result = await pending }
    const rejected = assert.rejects(streaming ? result.text() : pending, /test timeout/)
    controller.abort(new Error('test timeout'))
    await rejected
    assert.equal(f.request.aborted, true)
  }
})

test('body cancellation terminates the underlying request', async () => {
  const f = fixture()
  const pending = f.fetch('https://github.com/test', { redirect: 'manual' })
  respond(f.request)
  await (await pending).body.cancel()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(f.request.aborted, true)
})

test('propagates interrupted response and request failures', async () => {
  const f = fixture()
  const pending = f.fetch('https://github.com/test', { redirect: 'manual' })
  const incoming = respond(f.request)
  const rejected = assert.rejects((await pending).text(), /中断/)
  incoming.emit('aborted')
  await rejected
  const g = fixture()
  const failed = g.fetch('https://github.com/test', { redirect: 'manual' })
  g.request.emit('error', new Error('network unavailable'))
  await assert.rejects(failed, /network unavailable/)
})
