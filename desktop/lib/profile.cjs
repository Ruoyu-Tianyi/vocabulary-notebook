'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')
const { legacyProfileName } = require('./compat.cjs')

function profilePlan({ appData, packaged, override, smokeDirectory }, filesystem = fs) {
  const explicit = override || smokeDirectory
  if (explicit && !path.isAbsolute(explicit)) throw new Error('VOCOVE_DESKTOP_USER_DATA_DIR 必须是绝对路径')
  const userData = explicit || path.join(appData, packaged ? 'Vocove' : 'Vocove Dev')
  // 显式目录和冒烟验证不得探测默认目录，更不能触发真实数据迁移。
  if (explicit) return { userData, lockDirectory: userData, migrationSource: null }
  if (filesystem.existsSync(userData)) return { userData, lockDirectory: userData, migrationSource: null }
  const legacy = path.join(appData, legacyProfileName(packaged))
  if (!filesystem.existsSync(legacy)) return { userData, lockDirectory: userData, migrationSource: null }
  if (!filesystem.lstatSync(legacy).isDirectory()) throw new Error('旧版数据目录不是普通目录，请先检查数据位置。')
  return { userData, lockDirectory: legacy, migrationSource: legacy }
}

function prepareProfile(app, plan, launch, dependencies = {}) {
  const filesystem = dependencies.fs || fs
  const run = dependencies.spawnSync || spawnSync
  filesystem.mkdirSync(plan.lockDirectory, { recursive: true, mode: 0o700 })
  app.setPath('userData', plan.lockDirectory)
  if (!app.requestSingleInstanceLock()) return false
  try {
    if (plan.migrationSource) {
      // 同步执行保持 app ready 前的边界，防止 Chromium 先创建新目录。
      // 迁移阶段暂占旧实例锁，Python 助手另外持有词库的跨进程锁。
      const result = run(launch.command, [...launch.args, '--migrate-user-data', plan.migrationSource, plan.userData], {
        encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
        timeout: 120000, maxBuffer: 1024 * 1024,
      })
      let report
      try { report = JSON.parse(result.stdout?.trim() || '{}') } catch { report = {} }
      if (result.error || result.status !== 0 || report.type !== 'migration' || !['migrated', 'existing'].includes(report.status)) {
        throw new Error('数据迁移未完成，原目录已保留。请退出旧版应用后重试；若仍失败，请检查磁盘空间和目录权限。')
      }
      if (!filesystem.statSync(plan.userData).isDirectory()) throw new Error('迁移目标目录不可用，原数据目录已保留。')
    }
    if (plan.migrationSource) app.releaseSingleInstanceLock()
    app.setPath('userData', plan.userData)
    app.setPath('sessionData', plan.userData)
    // 迁移后仅管理新 profile；若另一新实例抢先启动，则正常交还单实例控制权。
    return plan.migrationSource ? app.requestSingleInstanceLock() : true
  } catch (error) {
    app.releaseSingleInstanceLock()
    throw error
  }
}

module.exports = { profilePlan, prepareProfile }
