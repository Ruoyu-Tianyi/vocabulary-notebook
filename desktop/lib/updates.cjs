'use strict'

function failureDetail(error) {
  const text = `${error?.code || ''} ${error?.message || ''}`
  if (/ENOSPC/.test(text)) return '磁盘空间不足，请清理空间后重新下载。'
  if (/EACCES|EPERM/.test(text)) return '无法写入或打开更新文件，请检查应用目录权限后重试。'
  if (/checksum|sha256|sha512|完整性|大小与发布信息不符/i.test(text)) return '安装包完整性校验未通过，请重新下载；若仍失败，请等待发布者修复安装包。'
  if (/INVALID_SIGNATURE/.test(text)) return '安装包签名校验未通过，请等待发布者修复安装包。'
  if (/403|429|限制了更新请求/.test(text)) return 'GitHub 暂时限制了更新请求，请稍后重试。'
  if (/CHANNEL_FILE_NOT_FOUND|适用于本机|缺少|校验信息无效/.test(text)) return '新版尚未提供本机可用的安装包或完整更新信息，请稍后重试。'
  if (/timed?\s?out|ETIMEDOUT|超时/i.test(text)) return '更新请求超时，请检查网络后重试。'
  return '请检查网络和磁盘空间后重试。也可以从项目的 GitHub Releases 页面手动下载安装包。'
}

class DesktopUpdates {
  constructor({ source, currentVersion, platform, showDialog, onState = () => {}, install, enabled = true }) {
    Object.assign(this, { source, currentVersion, platform, showDialog, onState, install, enabled })
    this.state = 'idle'
    this.busy = false
    this.disposed = false
  }

  setState(state, percent) {
    if (this.disposed) return
    this.state = state
    const labels = {
      idle: '检查更新…', checking: '正在检查更新…', available: `下载 ${this.update?.version}…`,
      downloading: `正在下载更新…${Number.isFinite(percent) ? ` ${Math.floor(percent)}%` : ''}`,
      downloaded: this.platform === 'darwin' ? '打开更新安装包…' : '重启并安装更新…', installing: '正在准备安装…',
    }
    this.onState({ state, label: labels[state], enabled: !this.busy, percent })
  }

  async dialog(options) {
    if (this.disposed) return { response: 1 }
    return this.showDialog({ title: 'Vocove 更新', noLink: true, ...options })
  }

  async check({ manual = true } = {}) {
    if (this.busy || this.disposed) return
    if (!this.enabled) {
      if (manual) await this.dialog({ type: 'info', message: '请在已安装的桌面应用中检查更新', detail: '源码开发和冒烟检查不会下载或安装更新。', buttons: ['关闭'] })
      return
    }
    this.busy = true
    let phase = 'check'
    try {
      if (this.state !== 'downloaded') {
        this.setState('checking')
        this.update = await this.source.check()
        if (this.disposed) return
        if (!this.update) {
          this.setState('idle')
          if (manual) await this.dialog({ type: 'info', message: '当前已是最新版本', detail: `当前版本：${this.currentVersion}`, buttons: ['关闭'] })
          return
        }
        this.setState('available')
        const { response } = await this.dialog({
          type: 'info', message: `发现新版本 ${this.update.version}`,
          detail: `当前版本：${this.currentVersion}\n${this.platform === 'darwin' ? '下载后将打开安装包，请将 Vocove 拖入「应用程序」完成替换。' : '下载后可重启应用并通过安装向导完成更新。'}\n下载期间可以继续使用应用。`,
          buttons: ['下载更新', '稍后'], defaultId: 0, cancelId: 1,
        })
        if (response !== 0 || this.disposed) return
        phase = 'download'
        this.cancelled = false
        this.setState('downloading', 0)
        this.downloadedFile = await this.source.download(progress => {
          if (this.state === 'downloading') this.setState('downloading', Math.min(100, Math.max(0, progress.percent)))
        })
        if (this.disposed) return
        if (this.cancelled) { this.downloadedFile = null; this.setState('idle'); return }
        this.setState('downloaded')
      }
      phase = 'install'
      const { response } = await this.dialog({
        type: 'info', message: `新版本 ${this.update.version} 已下载`,
        detail: this.platform === 'darwin'
          ? '将退出 Vocove 并打开安装包。请将 Vocove 拖入「应用程序」替换旧版，完成后重新打开。词库和学习进度保存在独立的数据目录。'
          : '将保存偏好、关闭本地服务并启动安装向导。安装完成后重新打开 Vocove，词库和学习进度保存在独立的数据目录。',
        buttons: [this.platform === 'darwin' ? '退出并打开安装包' : '重启并安装', '稍后'], defaultId: 1, cancelId: 1,
      })
      if (response !== 0 || this.disposed) return
      this.setState('installing')
      await this.install(this.downloadedFile)
    } catch (error) {
      if (this.disposed) return
      this.setState(phase === 'install' && this.downloadedFile ? 'downloaded' : 'idle')
      if (this.cancelled) return
      if (manual || phase !== 'check') {
        const message = phase === 'check' ? '无法检查更新' : phase === 'download' ? '更新下载失败' : '无法启动更新安装'
        // 不将底层请求头、完整 URL 或堆栈展示给用户。
        await this.dialog({ type: 'error', message, detail: failureDetail(error), buttons: ['关闭'] })
      }
    } finally {
      this.busy = false
      if (!this.disposed) this.setState(this.state)
    }
  }

  cancel() {
    if (this.state !== 'downloading') return
    this.cancelled = true
    this.source.cancel()
  }

  dispose() {
    this.disposed = true
    this.source?.cancel()
    this.source?.dispose?.()
  }
}

module.exports = { DesktopUpdates }
