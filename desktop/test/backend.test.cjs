'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter, once } = require('node:events')
const { PassThrough } = require('node:stream')
const { BackendProcess } = require('../lib/backend.cjs')

function fixture(options = {}) {
  const child = new EventEmitter()
  Object.assign(child, { stdin: new PassThrough(), stdout: new PassThrough(), stderr: new PassThrough(), pid: 4242, exitCode: null, signalCode: null })
  child.exit = code => { child.exitCode = code; child.emit('exit', code) }
  child.kill = signal => { child.signalCode = signal; child.emit('exit', null) }
  const calls = []
  const spawn = (...args) => { calls.push(args); return child }
  const backend = new BackendProcess('python', ['entry.py'], { cwd: '/isolated' }, { spawn, startTimeout: 1000, stopTimeout: 20, ...options })
  return { child, backend, calls }
}

test('readiness handles split stdout and startup logs; orderly shutdown closes stdin', async () => {
  const { child, backend, calls } = fixture()
  const ready = backend.start()
  child.stdout.write('[config] starting\n{"type":"rea')
  child.stdout.write('dy","url":"http://127.0.0.1:43210"}\n')
  assert.equal(await ready, 'http://127.0.0.1:43210')
  assert.equal(calls[0][2].windowsHide, true)
  const chunks = []
  child.stdin.on('data', data => chunks.push(data.toString()))
  child.stdin.once('finish', () => child.exit(0))
  let unexpected = false
  backend.on('unexpected-exit', () => { unexpected = true })
  await backend.stop()
  assert.equal(chunks.join(''), 'shutdown\n')
  assert.equal(unexpected, false)
})

test('readiness rejects remote destinations without accepting log content as configuration', async () => {
  const { child, backend } = fixture()
  const ready = backend.start()
  child.stdout.write('{"type":"ready","url":"https://example.com"}\n')
  await assert.rejects(ready, /地址无效/)
  child.exit(1)
  await backend.stop()
})

test('unexpected service exit is surfaced after startup', async () => {
  const { child, backend } = fixture()
  const ready = backend.start()
  child.stdout.write('{"type":"ready","url":"http://127.0.0.1:40000"}\n')
  await ready
  const failure = once(backend, 'unexpected-exit')
  child.exit(1)
  await failure
})

test('POSIX startup timeout terminates the owned process if it ignores shutdown', async () => {
  const { child, backend } = fixture({ startTimeout: 10, platform: 'darwin' })
  await assert.rejects(backend.start(), /启动超时/)
  await backend.stop()
  assert.equal(child.signalCode, 'SIGKILL')
})

test('an executable spawn failure never tries to terminate an unknown PID', async () => {
  const { child, backend, calls } = fixture({ platform: 'win32' })
  child.pid = undefined
  const started = backend.start()
  child.emit('error', new Error('ENOENT'))
  await assert.rejects(started, /无法启动/)
  await backend.stop()
  assert.equal(calls.length, 1)
})

test('Windows fallback targets only the owned backend process tree', async () => {
  const { child, backend, calls } = fixture({ platform: 'win32' })
  backend.spawn = (...args) => {
    calls.push(args)
    if (args[0] === 'taskkill') { setImmediate(() => child.exit(1)); return new EventEmitter() }
    return child
  }
  const ready = backend.start()
  child.stdout.write('{"type":"ready","url":"http://127.0.0.1:40000"}\n')
  await ready
  await backend.stop()
  assert.deepEqual(calls[1].slice(0, 2), ['taskkill', ['/PID', '4242', '/T', '/F']])
})
