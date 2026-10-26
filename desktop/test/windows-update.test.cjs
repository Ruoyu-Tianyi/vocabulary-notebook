'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const { WindowsUpdateSource } = require('../lib/windows-update.cjs')

function fixture(version = '1.3.0-beta') {
  const updater = new EventEmitter()
  const token = { cancel: () => { token.cancelled = true } }
  updater.checkForUpdates = async () => ({ isUpdateAvailable: true, updateInfo: { version: '1.4.0' }, cancellationToken: token })
  updater.downloadUpdate = async cancellation => {
    assert.equal(cancellation, token)
    updater.emit('download-progress', { percent: 50 })
    return ['/isolated/update.exe']
  }
  const calls = []
  const quitEvents = new EventEmitter()
  updater.quitAndInstall = (...args) => { calls.push(args); setImmediate(() => quitEvents.emit('before-quit-for-update')) }
  const source = new WindowsUpdateSource(updater, version, { quitEvents, installTimeout: 20 })
  return { updater, source, token, calls, quitEvents }
}

test('Windows disables unsolicited downloads/installs and downgrade; beta/stable channels follow installed version', () => {
  const { updater } = fixture()
  assert.equal(updater.autoDownload, false)
  assert.equal(updater.autoInstallOnAppQuit, false)
  assert.equal(updater.allowDowngrade, false)
  assert.equal(updater.allowPrerelease, true)
  assert.equal(updater.disableWebInstaller, true)
  assert.equal(fixture('1.3.0').updater.allowPrerelease, false)
})

test('Windows uses the checked download token, forwards progress, removes listener and installs explicitly', async () => {
  const f = fixture()
  assert.deepEqual(await f.source.check(), { version: '1.4.0' })
  const progress = []
  assert.equal(await f.source.download(p => progress.push(p.percent)), '/isolated/update.exe')
  assert.deepEqual(progress, [50])
  assert.equal(f.updater.listenerCount('download-progress'), 0)
  await f.source.install()
  assert.deepEqual(f.calls, [[false, true]])
  f.source.dispose()
  assert.equal(f.token.cancelled, true)
  assert.equal(f.updater.listenerCount('error'), 0)
})

test('Windows surfaces installation errors or missing quit signal instead of leaving a stopped backend window', async () => {
  const f = fixture()
  f.updater.quitAndInstall = () => f.updater.emit('error', new Error('spawn failed'))
  await assert.rejects(f.source.install(), /spawn failed/)
  assert.equal(f.quitEvents.listenerCount('before-quit-for-update'), 0)
  f.updater.quitAndInstall = () => {}
  await assert.rejects(f.source.install(), /未能启动/)
  assert.equal(f.quitEvents.listenerCount('before-quit-for-update'), 0)
})

test('Windows rejects invalid, equal and older available versions and tolerates emitted request errors', async () => {
  const f = fixture()
  for (const version of ['invalid', '1.3.0-beta', '1.2.0']) {
    f.updater.checkForUpdates = async () => ({ isUpdateAvailable: true, updateInfo: { version } })
    assert.equal(await f.source.check(), null)
  }
  f.updater.checkForUpdates = async () => { f.updater.emit('error', new Error('offline')); throw new Error('offline') }
  await assert.rejects(f.source.check(), /offline/)
})
