'use strict'

const fs = require('node:fs/promises')
const path = require('node:path')
const { createHash } = require('node:crypto')
const semver = require('semver')

const RELEASES_API = 'https://api.github.com/repos/Eric-Zhou-0302/vocove/releases?per_page=100'
const RELEASE_PREFIX = 'https://github.com/Eric-Zhou-0302/vocove/releases/download/'
const ASSET_HOSTS = new Set(['github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'github-releases.githubusercontent.com'])
const METADATA_LIMIT = 8 * 1024 * 1024
const MAX_INSTALLER_SIZE = 2 * 1024 * 1024 * 1024

function assetUrl(asset, tag, name) {
  const expected = `${RELEASE_PREFIX}${encodeURIComponent(tag)}/${encodeURIComponent(name)}`
  let actual
  try { actual = new URL(asset.browser_download_url) } catch { throw new Error('更新安装包地址无效。') }
  if (actual.protocol !== 'https:' || actual.hostname !== 'github.com' || actual.username || actual.password || actual.port || actual.search || actual.hash || decodeURI(actual.pathname) !== decodeURI(new URL(expected).pathname)) {
    throw new Error('更新安装包必须来自 Vocove 官方 GitHub 仓库。')
  }
  return expected
}

function allowedRedirect(value) {
  const url = new URL(value)
  return url.protocol === 'https:' && ASSET_HOSTS.has(url.hostname) && !url.username && !url.password && !url.port
}

async function boundedText(response, limit) {
  if (!response.body) throw new Error('更新服务器返回了空内容。')
  const chunks = []
  let size = 0
  for await (const chunk of response.body) {
    size += chunk.length
    if (size > limit) throw new Error('更新服务器返回的内容过大。')
    chunks.push(Buffer.from(chunk))
  }
  return Buffer.concat(chunks).toString('utf8')
}

class GitHubDmgUpdateSource {
  constructor({ currentVersion, arch, cacheDir, fetchImpl = globalThis.fetch }) {
    if (!semver.valid(currentVersion) || !['arm64', 'x64'].includes(arch)) throw new Error('当前应用版本或架构不支持检查更新。')
    this.currentVersion = currentVersion
    this.arch = arch
    this.cacheDir = cacheDir
    this.fetch = fetchImpl
    this.selected = null
    this.controller = null
  }

  async operation(timeout, work) {
    if (this.controller) throw new Error('更新任务正在进行中。')
    const controller = new AbortController()
    this.controller = controller
    const timer = setTimeout(() => controller.abort(new Error('更新请求超时，请稍后重试。')), timeout)
    try { return await work(controller.signal) }
    finally {
      clearTimeout(timer)
      if (this.controller === controller) this.controller = null
    }
  }

  async request(url, signal, api = false) {
    for (let redirects = 0; redirects <= 5; redirects++) {
      const response = await this.fetch(url, {
        signal, redirect: 'manual',
        headers: api ? { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Vocove-Desktop' } : { 'User-Agent': 'Vocove-Desktop' },
      })
      if ([301, 302, 303, 307, 308].includes(response.status)) {
        const location = response.headers.get('location')
        await response.body?.cancel()
        if (api || !location || redirects === 5) throw new Error('更新服务器重定向无效。')
        const next = new URL(location, url).href
        if (!allowedRedirect(next)) throw new Error('更新下载被重定向到了非官方地址。')
        url = next
        continue
      }
      if (!response.ok) {
        await response.body?.cancel()
        if (response.status === 403 || response.status === 429) throw new Error('GitHub 暂时限制了更新请求，请稍后重试。')
        throw new Error(`无法获取更新文件（HTTP ${response.status}），请稍后重试。`)
      }
      return response
    }
  }

  async check() {
    this.selected = null
    return this.operation(30000, async signal => {
      const response = await this.request(RELEASES_API, signal, true)
      const releases = JSON.parse(await boundedText(response, METADATA_LIMIT))
      if (!Array.isArray(releases)) throw new Error('更新服务器返回的版本列表无效。')
      const allowPrerelease = semver.prerelease(this.currentVersion) !== null
      const candidates = releases.flatMap(release => {
        const tag = release?.tag_name
        if (release?.draft || typeof tag !== 'string' || !/^v?\d/.test(tag) || /\s/.test(tag)) return []
        const version = tag.replace(/^v/, '')
        if (!semver.valid(version) || (!allowPrerelease && (release.prerelease || semver.prerelease(version))) || !semver.gt(version, this.currentVersion)) return []
        return [{ release, tag, version }]
      }).sort((a, b) => semver.rcompare(a.version, b.version))
      if (!candidates.length) return null
      const { release, tag, version } = candidates[0]
      const name = `Vocove-${version}-mac-${this.arch}.dmg`
      const assets = Array.isArray(release.assets) ? release.assets : []
      const asset = assets.find(entry => entry.name === name && entry.state === 'uploaded')
      if (!asset) throw new Error(`发现新版 ${version}，但尚未提供适用于本机 ${this.arch} 的 macOS 安装包。`)
      if (!Number.isSafeInteger(asset.size) || asset.size < 1 || asset.size > MAX_INSTALLER_SIZE) throw new Error('更新安装包大小无效。')
      const url = assetUrl(asset, tag, name)
      let sha256
      if (asset.digest != null) {
        const match = /^sha256:([a-f0-9]{64})$/i.exec(asset.digest)
        if (!match) throw new Error('更新安装包校验信息无效。')
        sha256 = match[1].toLowerCase()
      } else {
        const checksum = assets.find(entry => entry.name === `${name}.sha256` && entry.state === 'uploaded')
        if (!checksum) throw new Error('新版安装包缺少 SHA256 校验信息，请等待发布者补齐。')
        const checksumUrl = assetUrl(checksum, tag, `${name}.sha256`)
        const checksumResponse = await this.request(checksumUrl, signal)
        const text = await boundedText(checksumResponse, 1024)
        const match = /^([a-f0-9]{64})  ([^\r\n]+)\r?\n?$/i.exec(text)
        if (!match || match[2] !== name) throw new Error('更新安装包校验信息无效。')
        sha256 = match[1].toLowerCase()
      }
      this.selected = { version, name, url, size: asset.size, sha256 }
      return { ...this.selected }
    })
  }

  async download(onProgress = () => {}) {
    const selected = this.selected
    if (!selected) throw new Error('请先检查是否有可用更新。')
    return this.operation(15 * 60 * 1000, async signal => {
      await fs.mkdir(this.cacheDir, { recursive: true, mode: 0o700 })
      const directory = await fs.mkdtemp(path.join(this.cacheDir, 'download-'))
      const temporary = path.join(directory, `${selected.name}.part`)
      let file
      try {
        const response = await this.request(selected.url, signal)
        if (!response.body) throw new Error('更新服务器返回了空安装包。')
        const hash = createHash('sha256')
        file = await fs.open(temporary, 'wx', 0o600)
        let received = 0
        for await (const chunk of response.body) {
          signal.throwIfAborted()
          received += chunk.length
          if (received > selected.size) throw new Error('更新安装包大小与发布信息不符。')
          hash.update(chunk)
          await file.writeFile(chunk)
          onProgress({ percent: Math.min(100, received / selected.size * 100) })
        }
        signal.throwIfAborted()
        if (received !== selected.size || hash.digest('hex') !== selected.sha256) throw new Error('更新安装包完整性校验失败，请重新下载。')
        await file.close()
        file = null
        const destination = path.join(directory, selected.name)
        await fs.rename(temporary, destination)
        return destination
      } catch (error) {
        await file?.close().catch(() => {})
        await fs.rm(directory, { recursive: true, force: true })
        throw error
      }
    })
  }

  cancel() { this.controller?.abort(new Error('更新已取消。')) }
}

module.exports = { GitHubDmgUpdateSource }
