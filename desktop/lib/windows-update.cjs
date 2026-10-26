'use strict'

const semver = require('semver')

class WindowsUpdateSource {
  constructor(updater, currentVersion, { quitEvents, installTimeout = 10000 } = {}) {
    this.updater = updater
    this.currentVersion = currentVersion
    this.quitEvents = quitEvents
    this.installTimeout = installTimeout
    updater.autoDownload = false
    updater.autoInstallOnAppQuit = false
    updater.autoRunAppAfterInstall = true
    updater.allowPrerelease = Boolean(semver.prerelease(currentVersion))
    updater.allowDowngrade = false
    updater.disableWebInstaller = true
    // 错误由各次操作的 Promise 呈现，避免 EventEmitter 的 error 事件使主进程退出。
    this.onError = error => this.rejectInstall?.(error)
    updater.on('error', this.onError)
  }

  async check() {
    const result = await this.updater.checkForUpdates()
    this.cancellationToken = result?.cancellationToken
    if (!result?.isUpdateAvailable || !semver.valid(result.updateInfo?.version) ||
        !semver.gt(result.updateInfo.version, this.currentVersion)) return null
    return { version: result.updateInfo.version }
  }

  async download(onProgress) {
    if (!this.cancellationToken) throw new Error('请先检查更新。')
    this.updater.on('download-progress', onProgress)
    try {
      const files = await this.updater.downloadUpdate(this.cancellationToken)
      if (!files?.length) throw new Error('安装包下载未完成，请重新检查更新。')
      return files[0]
    } finally {
      this.updater.removeListener('download-progress', onProgress)
    }
  }

  install() {
    return new Promise((resolve, reject) => {
      if (!this.quitEvents) { reject(new Error('安装事件未就绪。')); return }
      const finish = error => {
        clearTimeout(timer)
        this.quitEvents.removeListener('before-quit-for-update', onQuit)
        this.rejectInstall = null
        if (error) reject(error)
        else resolve()
      }
      const onQuit = () => finish()
      const timer = setTimeout(() => finish(new Error('安装程序未能启动，请重试。')), this.installTimeout)
      this.rejectInstall = finish
      this.quitEvents.once('before-quit-for-update', onQuit)
      try { this.updater.quitAndInstall(false, true) }
      catch (error) { finish(error) }
    })
  }
  cancel() { this.cancellationToken?.cancel() }
  dispose() {
    this.cancel()
    this.updater.removeListener('error', this.onError)
  }
}

module.exports = { WindowsUpdateSource }
