'use strict'

const { app, BrowserWindow, Menu, dialog, session, shell } = require('electron')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const { randomBytes } = require('node:crypto')
const { BackendProcess } = require('./lib/backend.cjs')
const { TOKEN_HEADER, isBackendUrl, isExportUrl, isAllowedExternalUrl, authenticatedHeaders } = require('./lib/policy.cjs')
const { sanitizePreferences } = require('./lib/preferences.cjs')
const { rendererSmoke, waitForSmokePaint } = require('./lib/smoke.cjs')
const { SESSION_PARTITION, LEGACY_SORT_KEY, environmentValue, clearEnvironmentValue } = require('./lib/compat.cjs')
const { profilePlan, prepareProfile } = require('./lib/profile.cjs')
const { backendLaunch } = require('./lib/backend-launch.cjs')
const { DesktopUpdates } = require('./lib/updates.cjs')

const smokeTest = process.argv.includes('--smoke-test')
const root = path.resolve(__dirname, '..')
const brandingDirectory = app.isPackaged ? path.join(process.resourcesPath, 'branding') : path.join(__dirname, 'resources')
app.setName(app.isPackaged ? 'Vocove' : 'Vocove Dev')
const override = environmentValue('VOCOVE_DESKTOP_USER_DATA_DIR')
const smokeDirectory = smokeTest && !override ? fs.mkdtempSync(path.join(os.tmpdir(), 'vocove-desktop-smoke-')) : undefined
const launch = backendLaunch({ packaged: app.isPackaged, resourcesPath: process.resourcesPath, root })
let plan
let ownsInstanceLock = false
try {
  plan = profilePlan({ appData: app.getPath('appData'), packaged: app.isPackaged, override, smokeDirectory })
  ownsInstanceLock = prepareProfile(app, plan, launch)
} catch (error) {
  dialog.showErrorBox('Vocove', error.message)
  app.exit(1)
}
const userData = plan.userData
const screenshotPath = environmentValue('VOCOVE_DESKTOP_SMOKE_SCREENSHOT')
const dataDirectory = path.join(userData, 'data')
const preferencesFile = path.join(userData, 'desktop-preferences.json')
const token = randomBytes(32).toString('hex')
let backend
let origin
let mainWindow
let desktopSession
let quitting = false
let finalExit = false
let exitCode = 0
let failing = false
let updates
let updateTimer

function readPreferences() {
  try { return sanitizePreferences(JSON.parse(fs.readFileSync(preferencesFile, 'utf8'))) }
  catch { return {} }
}

async function savePreferences() {
  if (!mainWindow || mainWindow.isDestroyed() || !isBackendUrl(mainWindow.webContents.getURL(), origin)) return
  try {
    const snapshot = await Promise.race([
      mainWindow.webContents.executeJavaScript(`({theme: localStorage.getItem('theme'), 'vocove-word-sort': localStorage.getItem('vocove-word-sort') ?? localStorage.getItem(${JSON.stringify(LEGACY_SORT_KEY)})})`),
      new Promise(resolve => setTimeout(() => resolve(null), 1000)),
    ])
    if (snapshot === null) return
    const temporary = `${preferencesFile}.tmp`
    fs.writeFileSync(temporary, `${JSON.stringify(sanitizePreferences(snapshot))}\n`, { mode: 0o600 })
    fs.renameSync(temporary, preferencesFile)
  } catch { /* 偏好写入失败不阻止本地服务正常退出。 */ }
}

async function fail(message) {
  if (failing || quitting) return
  failing = true
  exitCode = 1
  if (smokeTest) console.error(`DESKTOP_SMOKE_FAILED ${message}`)
  else await dialog.showMessageBox({ type: 'error', title: 'Vocove', message, detail: `数据目录：${dataDirectory}\n词库不会因此删除。`, buttons: ['退出'] })
  app.quit()
}

function openExternal(url) {
  if (isAllowedExternalUrl(url)) shell.openExternal(url).catch(() => {
    if (!smokeTest) dialog.showErrorBox('无法打开浏览器', '请检查系统默认浏览器后重试。')
  })
}

function download(url) {
  if (mainWindow && isExportUrl(url, origin)) {
    mainWindow.webContents.downloadURL(url, { headers: { [TOKEN_HEADER]: token } })
  }
}

function installSession() {
  desktopSession = session.fromPartition(SESSION_PARTITION)
  desktopSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false))
  desktopSession.setPermissionCheckHandler(() => false)
  desktopSession.webRequest.onBeforeSendHeaders((details, callback) => {
    callback({ requestHeaders: authenticatedHeaders(details.url, details.requestHeaders, origin, token) })
  })
  desktopSession.webRequest.onHeadersReceived((details, callback) => {
    if (!isBackendUrl(details.url, origin)) { callback({}); return }
    callback({ responseHeaders: { ...details.responseHeaders, 'Content-Security-Policy': [
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-src 'none'; frame-ancestors 'none'; form-action 'self'",
    ] } })
  })
  if (smokeTest) {
    desktopSession.webRequest.onBeforeRequest((details, callback) => {
      const url = new URL(details.url)
      // 冒烟验收只访问隔离的本机服务，不连接已有 Ollama 或远端字体。
      callback({ cancel: !isBackendUrl(details.url, origin) || url.pathname === '/api/health' })
    })
  }
  desktopSession.on('will-download', (event, item) => {
    if (!isExportUrl(item.getURL(), origin)) { event.preventDefault(); return }
    if (smokeTest) {
      const downloadDirectory = path.join(userData, 'smoke-downloads')
      fs.mkdirSync(downloadDirectory, { recursive: true })
      item.setSavePath(path.join(downloadDirectory, path.basename(item.getFilename())))
    } else item.setSaveDialogOptions({ title: '导出 Vocove 词库', defaultPath: path.join(app.getPath('downloads'), path.basename(item.getFilename())) })
    item.once('done', (_event, state) => {
      if (state === 'interrupted' && !smokeTest) dialog.showErrorBox('导出未完成', '请检查保存位置后重试。')
    })
  })
}

function installMenu() {
  const menu = []
  const updateItems = [
    { id: 'check-updates', label: '检查更新…', click: () => updates.check() },
    { id: 'cancel-update', label: '取消下载更新', visible: false, click: () => updates.cancel() },
  ]
  if (process.platform === 'darwin') menu.push({ label: 'Vocove', submenu: [{ role: 'about' }, ...updateItems, { type: 'separator' }, { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' }, { type: 'separator' }, { role: 'quit' }] })
  menu.push({ label: '文件', submenu: [
    { label: '打开数据目录', click: () => shell.openPath(dataDirectory) },
    { type: 'separator' },
    { role: process.platform === 'darwin' ? 'close' : 'quit' },
  ] })
  menu.push({ label: '编辑', submenu: [{ role: 'undo' }, { role: 'redo' }, { type: 'separator' }, { role: 'cut' }, { role: 'copy' }, { role: 'paste' }, { role: 'selectAll' }] })
  menu.push({ label: '显示', submenu: [{ role: 'reload' }, { type: 'separator' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { type: 'separator' }, { role: 'togglefullscreen' }] })
  menu.push({ label: '窗口', submenu: [{ role: 'minimize' }, { role: 'zoom' }] })
  if (process.platform !== 'darwin') menu.push({ label: '帮助', submenu: [{ role: 'about' }, ...updateItems] })
  Menu.setApplicationMenu(Menu.buildFromTemplate(menu))
}

function installUpdates() {
  const enabled = app.isPackaged && !smokeTest && ['darwin', 'win32'].includes(process.platform)
  let source
  if (enabled && process.platform === 'win32') {
    const { NsisUpdater } = require('electron-updater')
    const { autoUpdater } = require('electron')
    const { WindowsUpdateSource } = require('./lib/windows-update.cjs')
    source = new WindowsUpdateSource(new NsisUpdater(), app.getVersion(), { quitEvents: autoUpdater })
  } else if (enabled) {
    const { net } = require('electron')
    const { GitHubDmgUpdateSource } = require('./lib/github-dmg-update.cjs')
    source = new GitHubDmgUpdateSource({
      currentVersion: app.getVersion(), arch: process.arch,
      cacheDir: path.join(userData, 'updates'), fetchImpl: (...args) => net.fetch(...args),
    })
  }
  updates = new DesktopUpdates({
    enabled, source, currentVersion: app.getVersion(), platform: process.platform,
    showDialog: options => mainWindow && !mainWindow.isDestroyed()
      ? dialog.showMessageBox(mainWindow, options) : dialog.showMessageBox(options),
    onState: ({ state, label, enabled: menuEnabled, percent }) => {
      const menu = Menu.getApplicationMenu()
      const checkItem = menu?.getMenuItemById('check-updates')
      if (checkItem) { checkItem.label = label; checkItem.enabled = menuEnabled }
      const cancelItem = menu?.getMenuItemById('cancel-update')
      if (cancelItem) cancelItem.visible = state === 'downloading'
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.setProgressBar(state === 'downloading' ? (Number.isFinite(percent) ? percent / 100 : 2) : -1)
      }
    },
    install: async file => {
      clearTimeout(updateTimer)
      await savePreferences()
      // 安装前先让 Python 落盘并释放文件；普通退出仍走原来的收尾逻辑。
      quitting = true
      try {
        await backend?.stop()
        if (process.platform === 'darwin') {
          const error = await shell.openPath(file)
          if (error) throw new Error('无法打开安装包')
          finalExit = true
          app.quit()
        } else {
          finalExit = true
          await source.install()
        }
      } catch (error) {
        // 后端已停止，失败后退出，避免留下仍能操作的失效页面。
        finalExit = true
        await dialog.showMessageBox({ type: 'error', title: 'Vocove 更新', message: '无法启动安装，请重新打开 Vocove 后重试。', buttons: ['退出'] })
        app.exit(1)
        throw error
      }
    },
  })
  return enabled
}

async function createWindow() {
  const window = new BrowserWindow({
    width: 1180, height: 820, minWidth: 480, minHeight: 600,
    title: 'Vocove', backgroundColor: '#171715', show: false,
    icon: path.join(brandingDirectory, process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    webPreferences: {
      session: desktopSession, nodeIntegration: false, contextIsolation: true, sandbox: true,
      webSecurity: true, webviewTag: false, allowRunningInsecureContent: false,
      backgroundThrottling: !smokeTest,
      preload: path.join(__dirname, 'lib', 'preferences-preload.cjs'),
      additionalArguments: [`--vocove-origin=${origin}`, `--vocove-preferences=${JSON.stringify(readPreferences())}`, `--vocove-window=${randomBytes(8).toString('hex')}`],
    },
  })
  mainWindow = window
  window.once('ready-to-show', () => { if (!smokeTest && !quitting) window.show() })
  window.on('close', event => { if (!finalExit) { event.preventDefault(); app.quit() } })
  window.on('closed', () => { mainWindow = null })
  window.webContents.on('will-attach-webview', event => event.preventDefault())
  window.webContents.on('will-navigate', (event, url) => {
    if (isExportUrl(url, origin)) { event.preventDefault(); download(url) }
    else if (!isBackendUrl(url, origin)) { event.preventDefault(); openExternal(url) }
  })
  window.webContents.on('will-redirect', (event, url) => { if (!isBackendUrl(url, origin)) event.preventDefault() })
  window.webContents.on('will-frame-navigate', event => {
    if (!event.isMainFrame && !isBackendUrl(event.url, origin)) event.preventDefault()
  })
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isExportUrl(url, origin)) download(url)
    else if (isBackendUrl(url, origin)) window.loadURL(url).catch(() => fail('页面加载失败，请重启应用。'))
    else openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.on('render-process-gone', () => { if (!quitting) fail('界面意外退出，请重启应用。') })
  window.webContents.on('did-fail-load', (_event, code, _description, _url, isMainFrame) => {
    if (isMainFrame && code !== -3 && !quitting) fail('页面加载失败，请重启应用。')
  })
  await window.loadURL(origin)
  return window
}

async function runSmokeTest(window) {
  const result = await window.webContents.executeJavaScript(`(${rendererSmoke.toString()})()`)
  const unauthenticated = await fetch(`${origin}/api/desktop/health`)
  if (![401, 403].includes(unauthenticated.status)) throw new Error('桌面服务未拒绝无令牌请求')
  result.unauthenticatedBlocked = true
  const downloaded = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('原生导出下载超时')), 15000)
    desktopSession.once('will-download', (_event, item) => {
      item.once('done', (_downloadEvent, state) => {
        clearTimeout(timer)
        if (state !== 'completed') { reject(new Error('原生导出下载未完成')); return }
        try {
          const exported = JSON.parse(fs.readFileSync(item.getSavePath(), 'utf8'))
          if (exported.words.length !== 1 || exported.words[0].word !== 'Desktop-smoke') throw new Error('原生导出内容不符合预期')
          resolve(true)
        } catch (error) { reject(error) }
      })
    })
  })
  await window.webContents.executeJavaScript("void window.open('/api/words/export?format=json', '_blank')")
  result.nativeDownload = await downloaded
  await window.loadURL(origin)
  if (screenshotPath) window.showInactive()
  result.painted = await window.webContents.executeJavaScript(`(${waitForSmokePaint.toString()})()`)
  if (screenshotPath) {
    if (!path.isAbsolute(screenshotPath)) throw new Error('冒烟截图必须使用绝对路径')
    fs.writeFileSync(screenshotPath, (await window.webContents.capturePage()).toPNG())
  }
  console.log(`DESKTOP_SMOKE_OK ${JSON.stringify(result)}`)
  app.quit()
}

async function start() {
  if (process.platform === 'darwin' && !app.isPackaged) app.dock.setIcon(path.join(brandingDirectory, 'icon.png'))
  if (process.platform === 'win32') app.setAppUserModelId('net.ericzhou.vocove')
  fs.mkdirSync(dataDirectory, { recursive: true, mode: 0o700 })
  if (smokeTest) {
    if (fs.readdirSync(dataDirectory).length) throw new Error('冒烟验收需要空数据目录，以免读取已有词库或凭据。')
    fs.writeFileSync(path.join(dataDirectory, 'config.json'), JSON.stringify({
      provider: 'ollama', ollama: { url: 'http://127.0.0.1:9/api/generate', model: 'qwen2.5:7b' },
      deepseek: { api_key: '', model: 'deepseek-chat' },
    }), { flag: 'wx', mode: 0o600 })
  }
  const environment = { ...process.env, VOCOVE_DESKTOP_DATA_DIR: dataDirectory, VOCOVE_DESKTOP_TOKEN: token, PYTHONUNBUFFERED: '1' }
  clearEnvironmentValue(environment, 'VOCOVE_DATA_FILE')
  clearEnvironmentValue(environment, 'VOCOVE_DESKTOP_ORIGIN')
  backend = new BackendProcess(launch.command, launch.args, { cwd: dataDirectory, env: environment })
  backend.on('unexpected-exit', () => fail('本地服务意外停止，请重启应用。'))
  origin = await backend.start()
  if (quitting) return
  installSession()
  const canUpdate = installUpdates()
  installMenu()
  const window = await createWindow()
  if (smokeTest && !quitting) await runSmokeTest(window)
  else if (canUpdate && !quitting) {
    // 启动后只检查一次，不自动下载；离线和无新版时保持安静。
    updateTimer = setTimeout(() => updates.check({ manual: false }), 10000)
    updateTimer.unref()
  }
}

if (!ownsInstanceLock) {
  if (plan.migrationSource && !fs.existsSync(userData)) dialog.showErrorBox('Vocove', '请先退出正在运行的桌面实例，再启动 Vocove 完成数据迁移。')
  app.quit()
}
else {
  app.on('second-instance', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })
  app.on('activate', () => {
    if (mainWindow) mainWindow.show()
    else if (origin && !quitting) createWindow().catch(() => fail('页面加载失败，请重启应用。'))
  })
  app.on('window-all-closed', () => app.quit())
  app.on('before-quit', event => {
    if (finalExit) return
    event.preventDefault()
    if (quitting) return
    quitting = true
    clearTimeout(updateTimer)
    updates?.dispose()
    ;(async () => {
      await savePreferences()
      if (mainWindow && !mainWindow.isDestroyed()) mainWindow.destroy()
      await backend?.stop()
      finalExit = true
      app.exit(exitCode)
    })().catch(() => app.exit(1))
  })
  process.on('SIGINT', () => app.quit())
  process.on('SIGTERM', () => app.quit())
  app.whenReady().then(start).catch(error => fail(error.message))
}
