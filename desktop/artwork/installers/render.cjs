'use strict'

// 使用项目已有 Electron 渲染 SVG；只导出本目录三张安装图，不安装依赖。
// 在仓库根执行：desktop/node_modules/.bin/electron desktop/artwork/installers/render.cjs
const { app, BrowserWindow } = require('electron')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')

app.commandLine.appendSwitch('force-device-scale-factor', '1')
app.setPath('userData', fs.mkdtempSync(path.join(os.tmpdir(), 'vocove-installer-artwork-')))
const outputDirectory = path.resolve(__dirname, '../../build/installer-artwork')
const targets = [
  { name: 'dmg-background', width: 540, height: 380, scale: 1 },
  { name: 'dmg-background', width: 540, height: 380, scale: 2 },
  { name: 'nsis-header', width: 150, height: 57, scale: 1 },
  { name: 'nsis-sidebar', width: 164, height: 314, scale: 1 },
]

app.whenReady().then(async () => {
  fs.mkdirSync(outputDirectory, { recursive: true })
  for (const target of targets) {
    const width = target.width * target.scale
    const height = target.height * target.scale
    const window = new BrowserWindow({ width, height, useContentSize: true, show: false, frame: false,
      webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true, backgroundThrottling: false } })
    const svg = fs.readFileSync(path.join(__dirname, `${target.name}.svg`), 'utf8')
    const html = `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}svg{display:block;width:100vw;height:100vh}</style>${svg}`
    await window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)
    await window.webContents.executeJavaScript('(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); })()')
    const image = (await window.webContents.capturePage()).resize({ width, height, quality: 'best' })
    const file = path.join(outputDirectory, `${target.name}${target.scale === 2 ? '@2x' : ''}.png`)
    fs.writeFileSync(file, image.toPNG())
    console.log(`${file} (${width}×${height})`)
    window.destroy()
  }
  app.exit(0)
}).catch(error => {
  console.error(error.message)
  app.exit(1)
})

app.on('window-all-closed', () => {})
