import { useEffect, useState } from 'react'
import { libraryRequest } from '../api'
import ModelSettings from './ModelSettings'

export default function Settings() {
  const [status, setStatus] = useState(null)
  const [message, setMessage] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [folderPath, setFolderPath] = useState('')
  useEffect(() => {
    let alive = true
    const refresh = () => libraryRequest('/sync/status').then(next => { if (alive) setStatus(next) }).catch(err => { if (alive) setMessage(err.message) })
    refresh()
    const timer = setInterval(refresh, 2000)
    return () => { alive = false; clearInterval(timer) }
  }, [])
  async function act(operation) {
    setBusy(true)
    setMessage('')
    try { await operation(); setStatus(await libraryRequest('/sync/status')) }
    catch (err) { setMessage(err.message) }
    finally { setBusy(false) }
  }
  async function readJSON(file, limit) {
    if (!file || file.size > limit) throw new Error('文件过大或未选择文件')
    try { return JSON.parse(await file.text()) }
    catch { throw new Error('文件不是有效的 JSON') }
  }
  return <div className="settings-page">
    <h2>同步与备份</h2>
    {message && <p className="settings-message" role="status">{message}</p>}
    <ModelSettings />
    <section className="settings-card">
      <h3>方式一：Google Drive 同步文件夹（推荐）</h3>
      <p>无需 OAuth 客户端。两台电脑安装并登录 Google Drive 桌面版，在云端硬盘中新建专用文件夹，然后分别填写它在本机的路径。</p>
      <form onSubmit={event => { event.preventDefault(); act(async () => {
        await libraryRequest('/sync/folder', 'POST', { folder_path: folderPath })
        await libraryRequest('/sync/run', 'POST')
        setMessage('同步文件夹已连接。请等待 Google Drive 桌面版完成上传。')
      }) }}>
        <div className="form-group"><label htmlFor="sync-folder-path">同步文件夹的绝对路径</label>
          <input id="sync-folder-path" type="text" value={folderPath} onChange={e => setFolderPath(e.target.value)} placeholder={status?.folder_path || '例如：G:\\我的云端硬盘\\Drive Vocabulary Book'} required /></div>
        <button className="btn btn-primary" disabled={busy || status?.syncing || status?.auth_pending}>连接同步文件夹</button>
      </form>
      {status?.folder_enabled && <p>已连接：{status.folder_path}</p>}
      {status?.folder_enabled && <button className="btn btn-secondary" disabled={busy || status.syncing} onClick={() => act(async () => {
        await libraryRequest('/sync/disconnect', 'POST'); setMessage('此电脑已断开同步文件夹，词库与云端数据保留。')
      })}>断开同步文件夹</button>}
      <p className="settings-note">请将此文件夹设为“可离线使用”。应用把变更写入文件夹，实际上传与下载由 Google Drive 桌面版负责；关闭电脑前同时确认 Drive 已完成同步。程序、模型、words.json 缓存应各自保存在两台电脑的本地目录。</p>
    </section>
    <section className="settings-card">
      <h3>方式二：Google Drive API 直连（可选）</h3>
      <p>使用你已有的 Drive 空间。两台电脑使用同一个 Google 账号、同一个桌面 OAuth 客户端，各自授权。</p>
      <p>Drive 只申请自己的隐藏数据区权限；DeepSeek API Key 与 Drive 授权信息分别保存在本机。</p>
      <ol className="setup-steps">
        <li>在 <a href="https://console.cloud.google.com/apis/library/drive.googleapis.com" target="_blank" rel="noreferrer">Google Cloud</a> 启用 Google Drive API。</li>
        <li>配置 OAuth 同意屏幕，创建“桌面应用”客户端，下载客户端 JSON。个人测试时，将自己的账号加入测试用户。</li>
        <li>导入客户端文件，然后连接 Google Drive。第二台电脑重复这一步。</li>
      </ol>
      <label className="file-action">导入 OAuth 客户端 JSON
        <input aria-label="导入 OAuth 客户端 JSON" type="file" accept=".json,application/json" disabled={busy || status?.connected || status?.auth_pending}
          onChange={event => { const file = event.target.files[0]; if (file) act(async () => {
            await libraryRequest('/sync/credentials', 'POST', await readJSON(file, 50000)); setMessage('客户端已导入，可以连接 Google Drive。')
          }); event.target.value = '' }} /></label>
      <div className="btn-group">
        <button className="btn btn-primary" disabled={busy || !status?.configured || status?.auth_pending || status?.syncing || status?.folder_enabled} onClick={() => act(async () => {
          const result = await libraryRequest('/sync/connect', 'POST'); setUrl(result.authorization_url)
        })}>{status?.auth_pending ? '等待 Google 授权…' : status?.connected && !status.folder_enabled ? '重新授权' : '连接 Google Drive'}</button>
        {status?.connected && !status.folder_enabled && <button className="btn btn-secondary" disabled={busy || status.syncing || status.auth_pending} onClick={() => act(async () => {
          await libraryRequest('/sync/disconnect', 'POST'); setUrl(''); setMessage('此电脑已断开连接。本地词库和云端数据均保留。')
        })}>断开此电脑</button>}
      </div>
      {url && status?.auth_pending && <p><a className="btn btn-primary" href={url} target="_blank" rel="noreferrer">继续 Google 授权 ↗</a></p>}
      {status?.connected && !status.folder_enabled && <p>当前账号：{status.account} · 每 {status.interval_seconds} 秒自动同步</p>}
      {status?.error && <p role="alert" className="settings-error">{status.error}</p>}
      <p className="settings-note">API 模式的数据在 Drive 网页中不可见，可通过下方完整备份导出。离线时先保存本地，联网后自动合并。</p>
    </section>
    <section className="settings-card">
      <h3>完整备份与导入</h3>
      <p>完整备份包含所有单词本、词汇和每次复习记录。导入会合并记录，已有数据会保留。</p>
      <a className="btn btn-secondary" href="/api/library/export">下载完整备份</a>
      <label className="file-action">导入词库备份（也支持原项目 words.json）
        <input aria-label="导入词库备份" type="file" accept=".json,application/json" disabled={busy}
          onChange={event => { const file = event.target.files[0]; if (file) act(async () => {
            const result = await libraryRequest('/library/import', 'POST', await readJSON(file, 64 * 1024 * 1024))
            setMessage(result.message); window.dispatchEvent(new Event('library-changed')); window.dispatchEvent(new Event('cloud-data-changed'))
          }); event.target.value = '' }} /></label>
    </section>
  </div>
}
