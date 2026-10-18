import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { libraryRequest } from '../api'

export default function CloudStatus() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)
  const pulled = useRef(undefined)
  useEffect(() => {
    let alive = true
    async function refresh() {
      try {
        const next = await libraryRequest('/sync/status')
        if (!alive) return
        setStatus(next)
        setError('')
        if (pulled.current !== undefined && pulled.current !== next.last_pulled_at) {
          window.dispatchEvent(new Event('cloud-data-changed'))
          window.dispatchEvent(new Event('library-changed'))
        }
        pulled.current = next.last_pulled_at
      } catch (err) { if (alive) setError(err.message) }
    }
    refresh()
    const timer = setInterval(refresh, 3000)
    return () => { alive = false; clearInterval(timer) }
  }, [])
  async function sync() {
    setRunning(true)
    try {
      await libraryRequest('/sync/run', 'POST')
      setStatus(await libraryRequest('/sync/status'))
      setError('')
    } catch (err) { setError(err.message) }
    finally { setRunning(false) }
  }
  const problem = error || status?.error
  const syncing = status?.syncing || running
  const label = problem ? 'Drive 需检查' : syncing ? 'Drive 同步中…' : status?.connected ? 'Drive 已连接' : status ? '本地保存' : '检查连接…'
  const detail = problem || (status?.connected
    ? `${status.pending} 条变更待${status.provider === 'drive_folder' ? '写入文件夹；实际上传请查看 Drive 桌面版' : '同步'}${status.last_synced_at ? ` · 上次 ${new Date(status.last_synced_at).toLocaleTimeString()}` : ''}`
    : '连接 Google Drive 后，两台电脑可同步词汇与学习记录')
  return <aside className={`cloud-status ${problem ? 'has-error' : status?.connected ? 'connected' : ''}`} aria-label="云端同步状态">
    <Link to="/settings" className="cloud-status-label" title={detail}>
      <span className="status-dot" aria-hidden="true" />
      <span aria-live="polite">{label}{!problem && !syncing && status?.connected && status.pending > 0 ? ` · 待处理 ${status.pending}` : ''}</span>
    </Link>
    {status?.connected && <button type="button" className="status-action" disabled={syncing} onClick={sync} title={detail} aria-label="立即同步">同步</button>}
    {problem && <span className="cloud-warning" role="status">{problem}</span>}
  </aside>
}
