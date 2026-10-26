'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { createHash, randomBytes } = require('node:crypto')
const semver = require('semver')

async function generateUpdateChecksums({ directory, version, platform, arch }) {
  if (!['darwin', 'win32'].includes(platform) || !['arm64', 'x64'].includes(arch)) {
    throw new Error('更新校验文件仅支持 macOS / Windows 的 arm64 / x64。')
  }
  if (typeof version !== 'string' || semver.valid(version) !== version) {
    throw new Error('安装包版本必须是规范的语义化版本号。')
  }
  const output = path.resolve(directory)
  if (!(await fs.promises.lstat(output)).isDirectory()) throw new Error('安装包输出位置必须是普通目录。')
  const system = platform === 'darwin' ? 'mac' : 'win'
  const extensions = platform === 'darwin' ? ['dmg', 'zip'] : ['exe']
  const files = extensions.map(extension => path.join(output, `Vocove-${version}-${system}-${arch}.${extension}`))
  // 只处理本次构建的固定文件名，避免读取其他平台、旧版文件或符号链接。
  for (const file of files) {
    if (!(await fs.promises.lstat(file)).isFile()) throw new Error(`安装包不是普通文件：${path.basename(file)}`)
    try {
      if (!(await fs.promises.lstat(`${file}.sha256`)).isFile()) throw new Error('校验文件目标不是普通文件。')
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
  }
  const checksums = []
  for (const file of files) {
    const hash = createHash('sha256')
    for await (const chunk of fs.createReadStream(file)) hash.update(chunk)
    const destination = `${file}.sha256`
    const temporary = `${destination}.${randomBytes(8).toString('hex')}.tmp`
    try {
      await fs.promises.writeFile(temporary, `${hash.digest('hex')}  ${path.basename(file)}\n`, { flag: 'wx', mode: 0o600 })
      await fs.promises.rename(temporary, destination)
    } finally {
      await fs.promises.rm(temporary, { force: true })
    }
    checksums.push(destination)
  }
  return checksums
}

if (require.main === module) {
  const [platform, arch, version, directory] = process.argv.slice(2)
  generateUpdateChecksums({ directory, version, platform, arch }).then(files => {
    for (const file of files) console.log(`Update checksum: ${path.basename(file)}`)
  }).catch(error => {
    console.error(error.message)
    process.exitCode = 1
  })
}

module.exports = { generateUpdateChecksums }
