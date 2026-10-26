'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { spawn, spawnSync } = require('node:child_process')
const { NSIS_UPGRADE_GUID } = require('../lib/compat.cjs')

if (process.platform !== 'win32' || process.env.GITHUB_ACTIONS !== 'true' ||
    process.env.RUNNER_ENVIRONMENT !== 'github-hosted' || !process.env.RUNNER_TEMP) {
  throw new Error('Installer validation runs only on GitHub-hosted Windows runners.')
}

const registryKey = `HKCU\\Software\\${NSIS_UPGRADE_GUID}`
function installedLocation() {
  const result = spawnSync('reg.exe', ['query', registryKey, '/v', 'InstallLocation', '/reg:64'], { encoding: 'utf8' })
  if (result.error) throw result.error
  if (result.status === 1) return null
  assert.equal(result.status, 0, 'Cannot inspect the installation registry key')
  return result.stdout.match(/InstallLocation\s+REG_SZ\s+(.+)/)?.[1].trim() || null
}

async function main() {
  assert.equal(installedLocation(), null, 'Refusing to replace an existing installation')
  const release = path.resolve(__dirname, '../release')
  const installers = fs.readdirSync(release).filter((name) => /^Vocove-.*\.exe$/.test(name))
  assert.equal(installers.length, 1, 'Expected exactly one generated NSIS installer')
  const root = fs.mkdtempSync(path.join(process.env.RUNNER_TEMP, 'vocove-installer-'))
  const installDir = path.join(root, 'Vocove App')
  const uninstaller = path.join(installDir, 'Uninstall Vocove.exe')
  const env = { ...process.env, VOCOVE_DESKTOP_USER_DATA_DIR: path.join(root, 'profile') }

  function run(executable, args, timeout) {
    return new Promise((resolve, reject) => {
      const child = spawn(executable, args, { cwd: root, env, argv0: `"${executable}"`, windowsVerbatimArguments: true, stdio: ['ignore', 'pipe', 'inherit'] })
      let output = ''
      const timer = setTimeout(() => {
        // 只终止本次启动的进程树，不按应用名称查杀其他进程。
        spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'inherit', timeout: 10000 })
        reject(new Error(`${path.basename(executable)} timed out`))
      }, timeout)
      child.stdout.on('data', (chunk) => { output += chunk; process.stdout.write(chunk) })
      child.once('error', (error) => { clearTimeout(timer); reject(error) })
      child.once('close', (code) => {
        clearTimeout(timer)
        if (code === 0) resolve(output)
        else reject(new Error(`${path.basename(executable)} exited with ${code}`))
      })
    })
  }

  const errors = []
  try {
    // NSIS 要求 /D= 位于末尾且不加引号，保留路径中的空格以覆盖实际安装情形。
    await run(path.join(release, installers[0]), ['/S', '/currentuser', `/D=${installDir}`], 180000)
    assert.ok(fs.existsSync(path.join(installDir, 'Vocove.exe')), 'Installed executable is missing')
    assert.ok(fs.existsSync(uninstaller), 'Installed uninstaller is missing')
    assert.equal(installedLocation()?.toLowerCase(), installDir.toLowerCase(), 'Unexpected installation registry path')
    const output = await run(path.join(installDir, 'Vocove.exe'), ['--smoke-test'], 120000)
    assert.match(output, /DESKTOP_SMOKE_OK/, 'Installed application did not complete its smoke checks')
  } catch (error) {
    errors.push(error)
  } finally {
    try {
      // initMultiUser 会重读注册表；安装中途失败时不能让卸载器回退到默认目录。
      if (installedLocation()?.toLowerCase() === installDir.toLowerCase()) {
        const copy = path.join(root, 'uninstall.exe')
        fs.copyFileSync(uninstaller, copy)
        // 与 builder 的升级卸载方式一致：外置副本 + _?=，等待实际卸载进程退出。
        await run(copy, ['/S', '/currentuser', `_?=${installDir}`], 120000)
        assert.ok(!fs.existsSync(installDir), 'Uninstaller left installed files behind')
        assert.equal(installedLocation(), null, 'Uninstaller left its registry entry behind')
      } else if (errors.length === 0) {
        throw new Error('Installation registry path changed before uninstall')
      }
    } catch (error) {
      errors.push(error)
    } finally {
      fs.rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 })
    }
  }
  if (errors.length) throw new AggregateError(errors, 'Windows installer validation failed')
  console.log('WINDOWS_INSTALLER_SMOKE_OK: installed application passed; uninstall removed files and registry entry')
}

main().catch((error) => { console.error(error); process.exitCode = 1 })
