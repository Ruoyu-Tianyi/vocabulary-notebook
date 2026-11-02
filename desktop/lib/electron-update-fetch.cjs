'use strict'

const { Readable } = require('node:stream')

// 只供更新器 GET 请求使用。将 Electron 的 redirect 事件转换为响应，
// 交给调用方逐跳校验；net.fetch 的 manual 模式会直接拒绝重定向。
function createUpdateFetch(net) {
  return (url, { signal, headers, redirect } = {}) => new Promise((resolve, reject) => {
    if (redirect !== 'manual') return reject(new Error('更新请求必须显式检查重定向。'))
    if (signal?.aborted) return reject(signal.reason)
    const request = net.request({ url, method: 'GET', headers, redirect: 'manual', credentials: 'omit' })
    let body
    let settled = false
    let finished = false
    const cleanup = () => signal?.removeEventListener('abort', abort)
    const fail = error => {
      if (finished) return
      finished = true
      cleanup()
      if (body) body.destroy(error)
      if (!settled) reject(error)
    }
    const abort = () => {
      fail(signal.reason)
      request.abort()
    }
    signal?.addEventListener('abort', abort, { once: true })
    request.on('error', fail)
    request.on('redirect', (status, _method, location) => {
      if (finished) return
      // 不调用 followRedirect，确保未知目标在域名校验前不会被访问。
      settled = true
      finished = true
      cleanup()
      resolve(new Response(null, { status, headers: { location } }))
      request.abort()
    })
    request.on('response', response => {
      if (finished) return
      body = response
      response.on('error', fail)
      response.on('aborted', () => fail(new Error('更新下载连接已中断。')))
      response.on('end', () => { finished = true; cleanup() })
      response.on('close', () => {
        if (!finished) fail(new Error('更新下载连接提前关闭。'))
        request.abort()
      })
      const responseHeaders = new Headers()
      for (const [name, values] of Object.entries(response.headers)) {
        for (const value of Array.isArray(values) ? values : [values]) responseHeaders.append(name, value)
      }
      try {
        const stream = Readable.toWeb(response, { strategy: { highWaterMark: 64 * 1024, size: chunk => chunk.byteLength } })
        const result = new Response(stream, { status: response.statusCode, headers: responseHeaders })
        settled = true
        resolve(result)
      } catch (error) {
        fail(error)
        request.abort()
      }
    })
    request.end()
  })
}

module.exports = { createUpdateFetch }
