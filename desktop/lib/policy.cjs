'use strict'

const TOKEN_HEADER = 'X-Vocove-Desktop-Token'

function backendOrigin(value) {
  if (typeof value !== 'string') throw new Error('后端启动地址无效')
  const match = /^http:\/\/127\.0\.0\.1:([1-9]\d{0,4})\/?$/.exec(value)
  if (!match || Number(match[1]) > 65535) throw new Error('后端启动地址无效')
  return `http://127.0.0.1:${match[1]}`
}

function parsedUrl(value) {
  try { return new URL(value) } catch { return null }
}

function isBackendUrl(value, origin) {
  const url = parsedUrl(value)
  return Boolean(url && !url.username && !url.password && url.origin === origin)
}

function isExportUrl(value, origin) {
  const url = parsedUrl(value)
  return isBackendUrl(value, origin) && ['/api/words/export', '/api/library/export'].includes(url.pathname)
}

function isAllowedExternalUrl(value) {
  const url = parsedUrl(value)
  if (!url || url.protocol !== 'https:' || url.username || url.password || url.port) return false
  return (url.hostname === 'accounts.google.com' && url.pathname === '/o/oauth2/v2/auth') ||
    (url.hostname === 'console.cloud.google.com' && url.pathname === '/apis/library/drive.googleapis.com')
}

function authenticatedHeaders(value, headers, origin, token) {
  // 重定向也会经过此处，先移除已有令牌，避免令牌随跨站请求泄露。
  const clean = Object.fromEntries(Object.entries(headers).filter(([key]) => key.toLowerCase() !== TOKEN_HEADER.toLowerCase()))
  if (isBackendUrl(value, origin)) clean[TOKEN_HEADER] = token
  return clean
}

module.exports = { TOKEN_HEADER, backendOrigin, isBackendUrl, isExportUrl, isAllowedExternalUrl, authenticatedHeaders }
