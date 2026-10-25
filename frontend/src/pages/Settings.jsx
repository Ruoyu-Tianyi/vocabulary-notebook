import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { libraryRequest } from '../api'
import NavigationIcon from '../components/NavigationIcon'
import './SyncSettings.css'
import './SettingsPolish.css'

function FileButton({ label, disabled, onFile }) {
  const input = useRef(null)
  return <>
    <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => input.current.click()}>{label}</button>
    <input ref={input} type="file" accept=".json,application/json" hidden aria-label={label} disabled={disabled}
      onChange={event => { const file = event.target.files[0]; event.target.value = ''; if (file) onFile(file) }} />
  </>
}

function formatTime(value) {
  if (!value) return '尚未同步'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '尚未同步' : date.toLocaleString('zh-CN', { hour12: false })
}

export default function Settings() {
  const [status, setStatus] = useState(null)
  const [connectionError, setConnectionError] = useState('')
  const [feedback, setFeedback] = useState(null)
  const [busy, setBusy] = useState('')
  const [method, setMethod] = useState(null)
  const [folderPath, setFolderPath] = useState('')
  const requestVersion = useRef(0)
  const mounted = useRef(false)

  async function refresh() {
    const version = ++requestVersion.current
    try {
      const next = await libraryRequest('/sync/status')
      if (mounted.current && version === requestVersion.current) { setStatus(next); setConnectionError('') }
    } catch (err) {
      if (mounted.current && version === requestVersion.current) setConnectionError(err.message)
    }
  }
  useEffect(() => {
    mounted.current = true
    refresh()
    const timer = setInterval(refresh, 3000)
    return () => { mounted.current = false; clearInterval(timer) }
  }, [])

  async function act(name, operation) {
    setBusy(name)
    setFeedback(null)
    try {
      const message = await operation()
      if (mounted.current && message) setFeedback({ text: message, error: false })
    } catch (err) {
      if (mounted.current) setFeedback({ text: err.message, error: true })
    } finally {
      // 部分成功（例如连接成功但首次同步失败）也必须刷新实际连接状态。
      await refresh()
      window.dispatchEvent(new Event('sync-status-changed'))
      if (mounted.current) setBusy('')
    }
  }
  async function readJSON(file, limit) {
    if (file.size > limit) throw new Error('文件过大，请选择较小的 JSON 文件')
    try { return JSON.parse(await file.text()) }
    catch { throw new Error('文件不是有效的 JSON') }
  }
  async function syncNow() {
    const result = await libraryRequest('/sync/run', 'POST')
    if (result.busy) return '已有同步或授权正在进行，请稍候。'
    window.dispatchEvent(new Event('cloud-data-changed'))
    window.dispatchEvent(new Event('library-changed'))
    return status?.folder_enabled ? '已与本机同步文件夹合并，请在 Drive 桌面版确认上传进度。' : `同步完成：接收 ${result.pulled} 条、发送 ${result.pushed} 条变更。`
  }
  const selected = method || (status?.folder_enabled ? 'folder' : status?.connected || status?.auth_pending || status?.configured ? 'api' : 'folder')
  const locked = Boolean(busy || !status || connectionError || status?.syncing || status?.auth_pending)
  const activeOther = status?.connected && (status.folder_enabled ? selected === 'api' : selected === 'folder')
  const problem = connectionError || status?.error
  const stateText = connectionError ? '暂时无法获取状态' : !status ? '正在读取连接状态' : status.auth_pending ? '等待 Google 授权' : status.syncing || busy === 'sync' ? '正在同步' : problem ? '同步需要处理' : status.connected ? status.folder_enabled ? '已连接同步文件夹' : '已连接 Google Drive' : '仅在本机保存'

  return <div className="sync-page">
    <header className="sync-heading">
      <h2>同步与备份</h2>
      <p>在不同电脑间接续学习，让词汇与复习记录保持一致。</p>
    </header>
    <nav className="settings-page-nav" aria-label="设置页面">
      <Link to="/settings"><NavigationIcon name="model" />模型设置</Link>
      <Link to="/sync-settings" aria-current="page"><NavigationIcon name="cloud" />同步与备份</Link>
    </nav>

    <section className={`sync-overview ${problem ? 'is-error' : ''}`} aria-label="当前同步状态">
      <div className="sync-overview-top">
        <div className="sync-state-heading"><span className="sync-state-icon"><NavigationIcon name="cloud" /></span><div><span className="sync-kicker">当前状态</span><h3 aria-live="polite">{stateText}</h3></div></div>
        {status?.connected && <button className="btn btn-primary" disabled={locked} onClick={() => act('sync', syncNow)}>{busy === 'sync' || status.syncing ? '同步中…' : '立即同步'}</button>}
      </div>
      {status?.connected ? <>
        <p className="sync-account">{status.folder_enabled ? status.folder_path : status.account || 'Google Drive 账号'}</p>
        <dl className="sync-metrics">
          <div><dt>{status.folder_enabled ? '待写入文件夹' : '待上传变更'}</dt><dd>{status.pending ?? 0}<small> 条</small></dd></div>
          <div><dt>{status.folder_enabled ? '上次文件夹同步' : '上次成功同步'}</dt><dd className="sync-time">{formatTime(status.last_synced_at)}</dd></div>
          <div><dt>自动同步</dt><dd className="sync-time">每 {status.interval_seconds} 秒</dd></div>
        </dl>
        {status.folder_enabled && <p className="sync-hint">文件夹写入完成后，上传与下载由 Google Drive 桌面版继续处理。</p>}
      </> : <p className="sync-hint">{status?.auth_pending ? '请在 Google 页面完成授权，返回后连接状态会自动更新。' : '词汇与复习记录保存在本机。选择下方一种方式，即可开启同步。'}</p>}
      {problem && <p className="sync-alert" role="alert">{problem}</p>}
      {connectionError && <button className="btn btn-secondary" onClick={refresh}>重新读取状态</button>}
      {status?.auth_pending && <div className="sync-actions">
        {status.authorization_url && <a className="btn btn-primary" href={status.authorization_url} target="_blank" rel="noreferrer">继续 Google 授权 ↗</a>}
        <button className="btn btn-secondary" disabled={Boolean(busy)} onClick={() => act('cancel', async () => { await libraryRequest('/sync/cancel-auth', 'POST'); return '已取消本次授权。' })}>取消授权</button>
      </div>}
      {status?.connected && <div className="sync-disconnect"><button className="sync-text-button" disabled={locked} onClick={() => act('disconnect', async () => {
        await libraryRequest('/sync/disconnect', 'POST'); return '已断开此电脑，本地词库与云端数据保留。'
      })}>断开此电脑</button><span>保留本地与云端记录</span></div>}
    </section>

    {feedback && <div className={`sync-feedback ${feedback.error ? 'is-error' : ''}`} role={feedback.error ? 'alert' : 'status'}>{feedback.text}</div>}

    <section className="sync-setup" aria-labelledby="sync-method-title">
      <div className="sync-section-title"><h3 id="sync-method-title">选择同步方式</h3><span>两台电脑使用同一种方式</span></div>
      <div className="sync-methods" role="group" aria-label="同步方式">
        <button type="button" className={`sync-method ${selected === 'folder' ? 'is-selected' : ''}`} aria-pressed={selected === 'folder'} onClick={() => setMethod('folder')}>
          <span className="sync-method-top"><strong>桌面同步文件夹</strong><span className="sync-tag">推荐</span></span>
          <span>已有 Drive 桌面版，无需创建开发者配置。</span>
        </button>
        <button type="button" className={`sync-method ${selected === 'api' ? 'is-selected' : ''}`} aria-pressed={selected === 'api'} onClick={() => setMethod('api')}>
          <span className="sync-method-top"><strong>Google Drive 直连</strong><span className="sync-tag">进阶</span></span>
          <span>无需桌面版，通过 Google 账号授权同步。</span>
        </button>
      </div>
      <div className="sync-panel">
        {activeOther && <p className="sync-notice">当前已连接{status.folder_enabled ? '桌面同步文件夹' : 'Google Drive 直连'}。请先在上方断开此电脑，再切换方式。</p>}
        {selected === 'folder' ? <>
          <h4>连接你的同步文件夹</h4>
          <p>在 Google Drive 中准备一个专用文件夹，并设为“可离线使用”。两台电脑分别填写它在本机的路径。</p>
          <form onSubmit={event => { event.preventDefault(); act('folder', async () => {
            await libraryRequest('/sync/folder', 'POST', { folder_path: folderPath.trim() || status?.folder_path })
            await libraryRequest('/sync/run', 'POST')
            window.dispatchEvent(new Event('cloud-data-changed'))
            return '同步文件夹已连接。请在 Drive 桌面版确认上传已完成。'
          }) }}>
            <label htmlFor="sync-folder-path">本机文件夹路径</label>
            <input type="text" id="sync-folder-path" aria-describedby="sync-folder-help" value={folderPath} disabled={locked || activeOther} onChange={event => setFolderPath(event.target.value)} placeholder={status?.folder_path || '粘贴 Google Drive 专用文件夹的完整路径'} autoComplete="off" spellCheck={false} />
            <p id="sync-folder-help" className="sync-field-help">支持 macOS 和 Windows 路径。请选择专用文件夹，不要选择程序或词库所在目录。</p>
            <button className="btn btn-primary" disabled={locked || activeOther || !(folderPath.trim() || status?.folder_path)}>{busy === 'folder' ? '正在连接…' : status?.folder_enabled ? '更新文件夹' : '连接文件夹'}</button>
          </form>
          <details className="sync-guide"><summary>第一次使用？查看连接步骤</summary><ol>
            <li>两台电脑安装 Google Drive 桌面版，登录同一账号。</li>
            <li>在云端硬盘中新建专用文件夹，设为“可离线使用”。</li>
            <li>第一台连接后，等待桌面版上传完成；第二台连接已完整下载的同一个文件夹。</li>
          </ol></details>
        </> : <>
          <h4>连接 Google 账号</h4>
          <p>两台电脑使用同一个桌面 OAuth 客户端和 Google 账号，分别授权。只访问本应用的隐藏数据区。</p>
          <details className="sync-guide"><summary>如何获取 OAuth 客户端文件？</summary><ol>
            <li>在 <a href="https://console.cloud.google.com/apis/library/drive.googleapis.com" target="_blank" rel="noreferrer">Google Cloud ↗</a> 启用 Google Drive API。</li>
            <li>配置 OAuth 同意屏幕，将自己的账号加入测试用户。</li>
            <li>创建“桌面应用”客户端，下载 JSON 文件后在下方导入。</li>
          </ol></details>
          <div className="sync-client-row"><span className="sync-step">1</span><div><strong>导入客户端文件</strong><p>{status?.configured ? '客户端已就绪，可以进行 Google 授权。' : '选择 Google Cloud 下载的桌面客户端 JSON。'}</p></div>
            <FileButton label={status?.configured ? '更换客户端' : '选择 JSON 文件'} disabled={locked || status?.connected} onFile={file => act('credentials', async () => {
              await libraryRequest('/sync/credentials', 'POST', await readJSON(file, 50000)); return '客户端已导入，请继续连接 Google Drive。'
            })} />
          </div>
          <div className="sync-client-row"><span className="sync-step">2</span><div><strong>授权 Google Drive</strong><p>连接后会显示授权链接，请在浏览器中完成。</p></div>
            <button className="btn btn-primary" disabled={locked || !status?.configured || activeOther} onClick={() => act('connect', async () => {
              await libraryRequest('/sync/connect', 'POST'); return '请点击上方“继续 Google 授权”完成连接。'
            })}>{busy === 'connect' ? '准备授权…' : status?.connected && !status.folder_enabled ? '重新授权' : '连接 Google Drive'}</button>
          </div>
          <p className="sync-hint">直连数据不会显示在 Drive 普通文件列表中，可通过下方完整备份导出。</p>
        </>}
      </div>
    </section>

    <section className="sync-backup" aria-labelledby="sync-backup-title">
      <div className="sync-section-title"><h3 id="sync-backup-title">完整备份</h3><span>无需连接云端</span></div>
      <p>保存词汇、单词本和每次复习记录。导入时合并记录，保留现有数据。</p>
      <div className="sync-actions">
        <a className="btn btn-secondary" href="/api/library/export">下载完整备份</a>
        <FileButton label={busy === 'import' ? '正在导入…' : '导入备份'} disabled={Boolean(busy)} onFile={file => act('import', async () => {
          const result = await libraryRequest('/library/import', 'POST', await readJSON(file, 64 * 1024 * 1024))
          window.dispatchEvent(new Event('library-changed')); window.dispatchEvent(new Event('cloud-data-changed'))
          return result.message
        })} />
      </div>
      <p className="sync-hint">支持完整备份 JSON，也兼容原有 words.json。</p>
    </section>
  </div>
}
