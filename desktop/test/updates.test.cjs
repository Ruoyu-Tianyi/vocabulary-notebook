'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { DesktopUpdates } = require('../lib/updates.cjs')

function fixture({ responses = [], platform = 'win32', enabled = true, source: overrides = {} } = {}) {
  const calls = []
  const source = {
    check: async () => { calls.push('check'); return { version: '1.4.0' } },
    download: async progress => { calls.push('download'); progress({ percent: 42 }); return '/isolated/update' },
    cancel: () => calls.push('cancel'), ...overrides,
  }
  const dialogs = []
  const states = []
  const updates = new DesktopUpdates({
    source, currentVersion: '1.3.0-beta', platform, enabled,
    showDialog: async options => { dialogs.push(options); return { response: responses.shift() ?? 1 } },
    onState: state => states.push(state), install: async file => calls.push(['install', file]),
  })
  return { updates, source, calls, dialogs, states }
}

test('update requires separate download and install consent and reports progress', async () => {
  const f = fixture({ responses: [0, 0] })
  await f.updates.check()
  assert.deepEqual(f.calls, ['check', 'download', ['install', '/isolated/update']])
  assert.deepEqual(f.dialogs.map(d => d.buttons[0]), ['下载更新', '重启并安装'])
  assert.equal(f.dialogs[1].defaultId, 1)
  assert.ok(f.states.some(s => s.percent === 42 && s.label.includes('42%') && !s.enabled))
})

test('startup check stays quiet offline or when no update exists; manual check reports failure', async () => {
  const f = fixture({ source: { check: async () => { throw new Error('offline') } } })
  await f.updates.check({ manual: false })
  assert.equal(f.dialogs.length, 0)
  await f.updates.check()
  assert.equal(f.dialogs[0].message, '无法检查更新')
  f.source.check = async () => null
  await f.updates.check({ manual: false })
  assert.equal(f.dialogs.length, 1)
  await f.updates.check()
  assert.equal(f.dialogs[1].message, '当前已是最新版本')
})

test('declining a download leaves the application unchanged', async () => {
  const f = fixture({ responses: [1] })
  await f.updates.check({ manual: false })
  assert.deepEqual(f.calls, ['check'])
  assert.equal(f.updates.state, 'available')
  assert.equal(f.states.at(-1).enabled, true)
})

test('postponed installation can be resumed without rechecking or downloading', async () => {
  const f = fixture({ responses: [0, 1, 0], platform: 'darwin' })
  await f.updates.check()
  assert.equal(f.updates.state, 'downloaded')
  await f.updates.check()
  assert.deepEqual(f.calls, ['check', 'download', ['install', '/isolated/update']])
  assert.equal(f.dialogs[1].buttons[0], '退出并打开安装包')
  assert.match(f.dialogs[1].detail, /拖入「应用程序」/)
})

test('a second click while checking cannot start another request or prompt', async () => {
  let finish
  const f = fixture({ source: { check: () => new Promise(resolve => { finish = resolve }) } })
  const first = f.updates.check()
  await f.updates.check()
  finish(null)
  await first
  assert.equal(f.dialogs.length, 1)
})

test('cancelled download does not install or show an error', async () => {
  let rejectDownload
  const f = fixture({ responses: [0], source: {
    download: () => new Promise((resolve, reject) => { rejectDownload = reject }),
    cancel: () => rejectDownload(new Error('cancelled')),
  } })
  const check = f.updates.check()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(f.updates.state, 'downloading')
  f.updates.cancel()
  await check
  assert.equal(f.updates.state, 'idle')
  assert.equal(f.dialogs.length, 1)
})

test('failed download never becomes installable and may be retried', async () => {
  const f = fixture({ responses: [0], source: { download: async () => { throw new Error('invalid checksum') } } })
  await f.updates.check()
  assert.equal(f.updates.state, 'idle')
  assert.equal(f.dialogs.at(-1).message, '更新下载失败')
  assert.equal(f.calls.some(c => Array.isArray(c) && c[0] === 'install'), false)
})

test('cancelling as the last download bytes arrive still suppresses installation', async () => {
  let finish
  const f = fixture({ responses: [0], source: { download: () => new Promise(resolve => { finish = resolve }) } })
  const check = f.updates.check()
  await new Promise(resolve => setImmediate(resolve))
  f.updates.cancel()
  finish('/isolated/update')
  await check
  assert.equal(f.updates.state, 'idle')
  assert.equal(f.dialogs.length, 1)
  assert.equal(f.updates.downloadedFile, null)
})

test('development and smoke modes never contact an update source', async () => {
  const f = fixture({ enabled: false })
  await f.updates.check({ manual: false })
  assert.equal(f.dialogs.length, 0)
  await f.updates.check()
  assert.equal(f.calls.length, 0)
  assert.match(f.dialogs[0].detail, /冒烟检查不会下载或安装更新/)
})

test('shutdown cancels work and suppresses late dialogs and installation', async () => {
  let finish
  const f = fixture({ source: { check: () => new Promise(resolve => { finish = resolve }) } })
  const check = f.updates.check()
  f.updates.dispose()
  finish({ version: '1.4.0' })
  await check
  assert.deepEqual(f.calls, ['cancel'])
  assert.equal(f.dialogs.length, 0)
})
