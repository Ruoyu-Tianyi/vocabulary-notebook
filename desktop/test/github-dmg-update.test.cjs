'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const path = require('node:path')
const os = require('node:os')
const { createHash } = require('node:crypto')
const { GitHubDmgUpdateSource } = require('../lib/github-dmg-update.cjs')

const content = Buffer.from('isolated installer fixture')
const digest = createHash('sha256').update(content).digest('hex')
const repo = 'https://github.com/Eric-Zhou-0302/vocove/releases/download'

function release(version = '1.4.0', options = {}) {
  const name = `Vocove-${version}-mac-${options.arch || 'arm64'}.dmg`
  return { tag_name: `v${version}`, draft: false, prerelease: version.includes('-'), assets: [
    { name, state: 'uploaded', size: content.length, digest: `sha256:${digest}`, browser_download_url: `${repo}/v${version}/${name}` },
  ], ...options }
}

async function fixture(t, releases = [release()], options = {}) {
  const cacheDir = await fs.mkdtemp(path.join(os.tmpdir(), 'vocove-dmg-update-test-'))
  t.after(() => fs.rm(cacheDir, { recursive: true, force: true }))
  const requests = []
  const responses = [Response.json(releases)]
  const source = new GitHubDmgUpdateSource({ currentVersion: '1.3.0-beta', arch: 'arm64', cacheDir,
    fetchImpl: async (url, settings) => {
      requests.push([url, settings])
      const response = responses.shift()
      if (!response) throw new Error('Unexpected request in offline test')
      return typeof response === 'function' ? response(url, settings) : response
    }, ...options })
  return { source, cacheDir, requests, responses }
}

test('selects the highest semantic version and ignores drafts, old releases and invalid tags', async t => {
  const f = await fixture(t, [release('1.3.0-beta'), release('1.2.0'), release('broken'), release('9.0.0', { draft: true }), release('1.4.0'), release('1.5.0-beta.2')])
  assert.equal((await f.source.check()).version, '1.5.0-beta.2')
  assert.equal(f.requests[0][1].redirect, 'manual')
  assert.equal(Object.keys(f.requests[0][1].headers).includes('Authorization'), false)
})

test('stable clients skip prereleases while beta clients can move to stable', async t => {
  const stable = await fixture(t, [release('1.5.0-beta'), release('1.4.0')], { currentVersion: '1.3.0' })
  assert.equal((await stable.source.check()).version, '1.4.0')
  const beta = await fixture(t)
  assert.equal((await beta.source.check()).version, '1.4.0')
})

test('never downgrades or reports an equal version as available', async t => {
  const f = await fixture(t, [release('1.2.0'), release('1.3.0-beta')])
  assert.equal(await f.source.check(), null)
  await assert.rejects(f.source.download(), /先检查/)
})

test('missing compatible architecture produces a useful error instead of selecting the other installer', async t => {
  const f = await fixture(t, [release('1.4.0', { arch: 'x64' })])
  await assert.rejects(f.source.check(), /arm64.*安装包/)
})

test('rejects an asset from another repository or host before downloading', async t => {
  for (const malicious of ['https://evil.example/installer.dmg', `${repo.replace('vocove', 'another-repo')}/v1.4.0/Vocove-1.4.0-mac-arm64.dmg`]) {
    const entry = release()
    entry.assets[0].browser_download_url = malicious
    const f = await fixture(t, [entry])
    await assert.rejects(f.source.check(), /官方 GitHub 仓库/)
    assert.equal(f.requests.length, 1)
  }
})

test('streams a valid installer and returns a verified DMG with progress', async t => {
  const f = await fixture(t)
  await f.source.check()
  f.responses.push(new Response(new ReadableStream({ start(controller) {
    controller.enqueue(content.subarray(0, 5))
    controller.enqueue(content.subarray(5))
    controller.close()
  } })))
  const progress = []
  const destination = await f.source.download(value => progress.push(value.percent))
  assert.equal(path.basename(destination), 'Vocove-1.4.0-mac-arm64.dmg')
  assert.deepEqual(await fs.readFile(destination), content)
  assert.equal(progress.at(-1), 100)
  assert.equal((await fs.readdir(path.dirname(destination))).length, 1)
})

test('uses a strict same-release checksum sidecar when GitHub digest is unavailable', async t => {
  const entry = release()
  const asset = entry.assets[0]
  asset.digest = null
  entry.assets.push({ name: `${asset.name}.sha256`, state: 'uploaded', browser_download_url: `${asset.browser_download_url}.sha256` })
  const f = await fixture(t, [entry])
  f.responses.push(new Response(`${digest}  ${asset.name}\n`))
  assert.equal((await f.source.check()).sha256, digest)
  f.responses.push(new Response(content))
  assert.deepEqual(await fs.readFile(await f.source.download()), content)
})

test('fails closed when checksums are missing, malformed or refer to a different filename', async t => {
  const noDigest = release()
  delete noDigest.assets[0].digest
  const missing = await fixture(t, [noDigest])
  await assert.rejects(missing.source.check(), /缺少 SHA256/)
  const invalidDigest = release()
  invalidDigest.assets[0].digest = 'sha256:not-a-digest'
  const invalid = await fixture(t, [invalidDigest])
  await assert.rejects(invalid.source.check(), /校验信息无效/)
  const wrongSidecar = release()
  const asset = wrongSidecar.assets[0]
  asset.digest = null
  wrongSidecar.assets.push({ name: `${asset.name}.sha256`, state: 'uploaded', browser_download_url: `${asset.browser_download_url}.sha256` })
  const wrong = await fixture(t, [wrongSidecar])
  wrong.responses.push(new Response(`${digest}  other.dmg\n`))
  await assert.rejects(wrong.source.check(), /校验信息无效/)
})

test('cleans its own temporary directory after a hash, length or network failure', async t => {
  for (const response of [new Response(Buffer.alloc(content.length)), new Response('short'), new Response(Buffer.alloc(content.length + 1)), () => { throw new Error('offline') }]) {
    const f = await fixture(t)
    await fs.writeFile(path.join(f.cacheDir, 'unrelated.txt'), 'keep')
    await f.source.check()
    f.responses.push(response)
    await assert.rejects(f.source.download())
    assert.deepEqual(await fs.readdir(f.cacheDir), ['unrelated.txt'])
  }
})

test('allows official asset redirects and blocks redirects to arbitrary hosts', async t => {
  const valid = await fixture(t)
  await valid.source.check()
  valid.responses.push(new Response(null, { status: 302, headers: { location: 'https://release-assets.githubusercontent.com/github-production-release-asset/fixture?signature=test' } }), new Response(content))
  await valid.source.download()
  const blocked = await fixture(t)
  await blocked.source.check()
  blocked.responses.push(new Response(null, { status: 302, headers: { location: 'https://evil.example/installer.dmg' } }))
  await assert.rejects(blocked.source.download(), /非官方地址/)
  assert.equal(blocked.requests.length, 2)
  assert.deepEqual(await fs.readdir(blocked.cacheDir), [])
})

test('cancel aborts an in-flight download and removes partial data', async t => {
  const f = await fixture(t)
  await f.source.check()
  f.responses.push(new Response(new ReadableStream({ start(controller) {
    controller.enqueue(content.subarray(0, 5))
    controller.enqueue(content.subarray(5))
    controller.close()
  } })))
  await assert.rejects(f.source.download(() => f.source.cancel()), /更新已取消/)
  assert.deepEqual(await fs.readdir(f.cacheDir), [])
})

test('metadata and checksum response sizes are bounded', async t => {
  const f = await fixture(t)
  f.responses[0] = new Response(' '.repeat(8 * 1024 * 1024 + 1))
  await assert.rejects(f.source.check(), /内容过大/)
  const entry = release()
  const asset = entry.assets[0]
  asset.digest = null
  entry.assets.push({ name: `${asset.name}.sha256`, state: 'uploaded', browser_download_url: `${asset.browser_download_url}.sha256` })
  const sidecar = await fixture(t, [entry])
  sidecar.responses.push(new Response(' '.repeat(1025)))
  await assert.rejects(sidecar.source.check(), /内容过大/)
})

test('rate limiting is explained and a failed recheck clears the previous selection', async t => {
  const f = await fixture(t)
  await f.source.check()
  f.responses.push(new Response(null, { status: 403 }))
  await assert.rejects(f.source.check(), /限制了更新请求/)
  await assert.rejects(f.source.download(), /先检查/)
})
