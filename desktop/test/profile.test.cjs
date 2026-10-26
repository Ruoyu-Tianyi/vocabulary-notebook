'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { profilePlan, prepareProfile } = require('../lib/profile.cjs')
const { legacyProfileName } = require('../lib/compat.cjs')

function fixture(t, { legacy = true, current = false } = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'vocove-profile-test-'))
  t.diagnostic(`synthetic profile fixture: ${directory}; removed by test cleanup`)
  t.after(() => {
    fs.rmSync(directory, { recursive: true, force: true })
    assert.equal(fs.existsSync(directory), false)
  })
  const old = path.join(directory, legacyProfileName(true))
  const destination = path.join(directory, 'Vocove')
  if (legacy) {
    fs.mkdirSync(path.join(old, 'data'), { recursive: true })
    fs.writeFileSync(path.join(old, 'data', 'synthetic.txt'), 'original words')
  }
  if (current) {
    fs.mkdirSync(destination)
    fs.writeFileSync(path.join(destination, 'current.txt'), 'current words')
  }
  const actions = []
  let lockAvailable = true
  const app = {
    setPath: (name, value) => actions.push(['path', name, value]),
    requestSingleInstanceLock: () => { actions.push(['lock']); return lockAvailable },
    releaseSingleInstanceLock: () => actions.push(['release']),
  }
  return { directory, old, destination, app, actions, setLockAvailable: value => { lockAvailable = value }, plan: () => profilePlan({ appData: directory, packaged: true }) }
}

const launch = { command: 'synthetic-python', args: ['entry.py'] }

test('explicit and smoke profiles never inspect default user directories', () => {
  const forbidden = { existsSync: () => assert.fail('must not inspect default directories') }
  const directory = path.join(os.tmpdir(), 'synthetic-override')
  for (const choice of [{ override: directory }, { smokeDirectory: directory }]) {
    assert.deepEqual(profilePlan({ appData: 'must-not-read', packaged: true, ...choice }, forbidden), { userData: directory, lockDirectory: directory, migrationSource: null })
  }
  assert.throws(() => profilePlan({ override: 'relative' }, forbidden), /绝对路径/)
})

test('new installs use only the new profile and never invoke migration', t => {
  const f = fixture(t, { legacy: false })
  assert.equal(prepareProfile(f.app, f.plan(), launch, { spawnSync: () => assert.fail('unexpected migration') }), true)
  assert.equal(fs.statSync(f.destination).isDirectory(), true)
  assert.equal(fs.existsSync(f.old), false)
  assert.deepEqual(f.actions.filter(action => action[0] === 'lock'), [['lock']])
})

test('migration runs with the old instance lock before the target is created, then switches to the new lock', t => {
  const f = fixture(t)
  const run = (command, args) => {
    assert.equal(command, launch.command)
    assert.deepEqual(args, ['entry.py', '--migrate-user-data', f.old, f.destination])
    assert.deepEqual(f.actions, [['path', 'userData', f.old], ['lock']])
    assert.equal(fs.existsSync(f.destination), false)
    fs.cpSync(f.old, f.destination, { recursive: true })
    return { status: 0, stdout: '{"type":"migration","status":"migrated"}\n' }
  }
  assert.equal(prepareProfile(f.app, f.plan(), launch, { spawnSync: run }), true)
  assert.equal(fs.readFileSync(path.join(f.old, 'data', 'synthetic.txt'), 'utf8'), 'original words')
  assert.equal(fs.readFileSync(path.join(f.destination, 'data', 'synthetic.txt'), 'utf8'), 'original words')
  assert.deepEqual(f.actions.slice(-4), [['release'], ['path', 'userData', f.destination], ['path', 'sessionData', f.destination], ['lock']])
})

test('a running old instance prevents copying or creating a new profile', t => {
  const f = fixture(t)
  f.setLockAvailable(false)
  assert.equal(prepareProfile(f.app, f.plan(), launch, { spawnSync: () => assert.fail('must not copy while locked') }), false)
  assert.equal(fs.existsSync(f.destination), false)
})

test('existing new profiles are never overwritten and do not depend on the old directory', t => {
  const f = fixture(t, { current: true })
  const filesystem = {
    existsSync: value => { assert.equal(value, f.destination); return true },
    lstatSync: () => assert.fail('must not inspect legacy directory'),
  }
  const plan = profilePlan({ appData: f.directory, packaged: true }, filesystem)
  assert.equal(prepareProfile(f.app, plan, launch, { spawnSync: () => assert.fail('must preserve new profile') }), true)
  assert.equal(fs.readFileSync(path.join(f.destination, 'current.txt'), 'utf8'), 'current words')
  assert.equal(fs.existsSync(path.join(f.destination, 'data')), false)
})

test('failed migration releases the old instance lock without starting an empty profile', t => {
  const f = fixture(t)
  assert.throws(() => prepareProfile(f.app, f.plan(), launch, {
    spawnSync: () => ({ status: 1, stdout: '', stderr: 'synthetic failure' }),
  }), /迁移未完成/)
  assert.equal(fs.existsSync(f.destination), false)
  assert.equal(fs.readFileSync(path.join(f.old, 'data', 'synthetic.txt'), 'utf8'), 'original words')
  assert.deepEqual(f.actions.at(-1), ['release'])
})

test('a new instance winning the post-migration lock keeps control', t => {
  const f = fixture(t)
  assert.equal(prepareProfile(f.app, f.plan(), launch, {
    spawnSync: () => {
      fs.cpSync(f.old, f.destination, { recursive: true })
      f.setLockAvailable(false)
      return { status: 0, stdout: '{"type":"migration","status":"existing"}' }
    },
  }), false)
  assert.equal(fs.readFileSync(path.join(f.destination, 'data', 'synthetic.txt'), 'utf8'), 'original words')
})
