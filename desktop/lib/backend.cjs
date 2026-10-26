'use strict'

const { spawn } = require('node:child_process')
const { EventEmitter } = require('node:events')
const { createInterface } = require('node:readline')
const { backendOrigin } = require('./policy.cjs')

class BackendProcess extends EventEmitter {
  constructor(command, args, options, dependencies = {}) {
    super()
    this.command = command
    this.args = args
    this.options = options
    this.spawn = dependencies.spawn || spawn
    this.startTimeout = dependencies.startTimeout || 30000
    this.stopTimeout = dependencies.stopTimeout || 7000
    this.platform = dependencies.platform || process.platform
    this.child = null
    this.stopping = false
    this.ready = false
  }

  start() {
    return new Promise((resolve, reject) => {
      let settled = false
      const fail = error => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        reject(error)
      }
      const timer = setTimeout(() => fail(new Error('本地服务启动超时，请退出后重试。')), this.startTimeout)
      try {
        this.child = this.spawn(this.command, this.args, { ...this.options, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true })
      } catch {
        fail(new Error('无法启动本地服务，请检查应用安装或开发环境。'))
        return
      }
      this.child.stdin.on('error', () => {})
      // 配置校验的 traceback 可能带用户数据；不把子进程原始输出写入桌面日志。
      this.child.stderr.resume()
      const lines = createInterface({ input: this.child.stdout })
      lines.on('line', line => {
        if (settled || line.length > 4096) return
        let message
        try { message = JSON.parse(line) } catch { return }
        if (message.type !== 'ready') return
        try {
          const origin = backendOrigin(message.url)
          settled = true
          this.ready = true
          clearTimeout(timer)
          resolve(origin)
        } catch (error) { fail(error) }
      })
      this.child.once('error', () => fail(new Error('无法启动本地服务，请检查应用安装或开发环境。')))
      this.child.once('exit', code => {
        lines.close()
        if (!settled) fail(new Error(`本地服务未能启动（退出码 ${code ?? '未知'}）。请检查数据目录中的配置文件。`))
        else if (this.ready && !this.stopping) this.emit('unexpected-exit')
      })
    })
  }

  stop() {
    if (this.stopPromise) return this.stopPromise
    this.stopping = true
    const child = this.child
    if (!child || !Number.isInteger(child.pid) || child.exitCode !== null || child.signalCode !== null) return Promise.resolve()
    this.stopPromise = new Promise(resolve => {
      let finished = false
      let finalTimer
      const done = () => {
        if (finished) return
        finished = true
        clearTimeout(timer)
        clearTimeout(finalTimer)
        resolve()
      }
      child.once('exit', done)
      const timer = setTimeout(() => {
        if (this.platform === 'win32') {
          // 仅终止本次启动的 PID；PyInstaller 子进程也随进程树收尾。
          const killer = this.spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' })
          killer.once('error', () => child.kill())
        } else child.kill('SIGKILL')
        if (!finished) finalTimer = setTimeout(done, 2000)
      }, this.stopTimeout)
      if (child.stdin.writable) child.stdin.end('shutdown\n')
      else child.kill()
    })
    return this.stopPromise
  }
}

module.exports = { BackendProcess }
