'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { createHash } = require('node:crypto')
const { generateUpdateChecksums } = require('../scripts/update-checksums.cjs')

function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'vocove-update-checksums-'))
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }))
  return { directory, version: '1.4.0-beta.1', platform: 'darwin', arch: 'arm64' }
}

function createArtifacts(options, extensions = ['dmg', 'zip']) {
  const system = options.platform === 'darwin' ? 'mac' : 'win'
  return extensions.map(extension => {
    const file = path.join(options.directory, `Vocove-${options.version}-${system}-${options.arch}.${extension}`)
    fs.writeFileSync(file, `fixture ${extension}`)
    return file
  })
}

test('checksums describe current-platform artifacts and leave old/other-platform outputs unchanged', async t => {
  const options = fixture(t)
  const files = createArtifacts(options)
  const untouched = path.join(options.directory, 'Vocove-1.3.0-mac-x64.dmg.sha256')
  fs.writeFileSync(untouched, 'old checksum')
  assert.deepEqual(await generateUpdateChecksums(options), files.map(file => `${file}.sha256`))
  for (const file of files) {
    const digest = createHash('sha256').update(fs.readFileSync(file)).digest('hex')
    assert.equal(fs.readFileSync(`${file}.sha256`, 'utf8'), `${digest}  ${path.basename(file)}\n`)
  }
  assert.equal(fs.readFileSync(untouched, 'utf8'), 'old checksum')
  assert.equal(fs.readdirSync(options.directory).some(name => name.endsWith('.tmp')), false)
})

test('Windows generates only the expected NSIS installer checksum', async t => {
  const options = { ...fixture(t), platform: 'win32', arch: 'x64' }
  const [file] = createArtifacts(options, ['exe'])
  assert.deepEqual(await generateUpdateChecksums(options), [`${file}.sha256`])
  assert.equal(fs.readdirSync(options.directory).length, 2)
})

test('invalid platform, architecture or version cannot select paths outside the output directory', async t => {
  const options = fixture(t)
  for (const invalid of [{ platform: '../darwin' }, { arch: '../arm64' }, { version: '../1.4.0' }, { version: 'v1.4.0' }]) {
    await assert.rejects(generateUpdateChecksums({ ...options, ...invalid }))
  }
  assert.deepEqual(fs.readdirSync(options.directory), [])
})

test('all current artifacts must exist before any checksum is written', async t => {
  const options = fixture(t)
  createArtifacts(options, ['dmg'])
  await assert.rejects(generateUpdateChecksums(options), { code: 'ENOENT' })
  assert.equal(fs.readdirSync(options.directory).some(name => name.endsWith('.sha256')), false)
})

test('symbolic links are rejected for installers and checksum destinations', { skip: process.platform === 'win32' }, async t => {
  const options = fixture(t)
  const files = createArtifacts(options)
  const target = path.join(options.directory, 'private-file')
  fs.writeFileSync(target, 'leave untouched')
  fs.symlinkSync(target, `${files[0]}.sha256`)
  await assert.rejects(generateUpdateChecksums(options), /普通文件/)
  fs.unlinkSync(`${files[0]}.sha256`)
  fs.unlinkSync(files[0])
  fs.symlinkSync(target, files[0])
  await assert.rejects(generateUpdateChecksums(options), /普通文件/)
  assert.equal(fs.readFileSync(target, 'utf8'), 'leave untouched')
})
