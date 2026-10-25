import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { libraryRequest } from '../api'
import NavigationIcon from './NavigationIcon'

export default function CloudStatus({ onProblemChange } = {}) {
  const location = useLocation()
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const pulled = useRef(undefined)
  useEffect(() => {
    let alive = true
    let requestId = 0
    async function refresh() {
      const current = ++requestId
      try {
        const next = await libraryRequest('/sync/status')
        if (!alive || current !== requestId) return
        setStatus(next)
        setError('')
        if (pulled.current !== undefined && pulled.current !== next.last_pulled_at) {
          window.dispatchEvent(new Event('cloud-data-changed'))
          window.dispatchEvent(new Event('library-changed'))
        }
        pulled.current = next.last_pulled_at
      } catch (err) { if (alive && current === requestId) setError(err.message) }
    }
    refresh()
    const timer = setInterval(refresh, 3000)
    window.addEventListener('sync-status-changed', refresh)
    return () => { alive = false; clearInterval(timer); window.removeEventListener('sync-status-changed', refresh) }
  }, [])
  const problem = error || status?.error
  const needsAttention = Boolean(problem || status?.auth_pending)
  const syncing = status?.syncing
  const label = problem ? 'Drive 需检查' : status?.auth_pending ? '等待 Google 授权' : syncing ? 'Drive 同步中…' : status?.connected ? 'Drive 已连接' : status ? '本地保存' : '检查连接…'
  const detail = problem || (status?.connected
    ? `${status.pending} 条变更待${status.provider === 'drive_folder' ? '写入文件夹；实际上传请查看 Drive 桌面版' : '同步'}${status.last_synced_at ? ` · 上次 ${new Date(status.last_synced_at).toLocaleTimeString()}` : ''}`
    : '连接 Google Drive 后，两台电脑可同步词汇与学习记录')
  useEffect(() => { onProblemChange?.(needsAttention) }, [needsAttention, onProblemChange])

  return <Link to="/sync-settings" className={`utility-item${problem ? ' has-error' : ''}`}
    aria-current={location.pathname === '/sync-settings' ? 'page' : undefined}
    title={detail} aria-label={`云端同步：${label}`}>
    <NavigationIcon name="cloud" />
    <span className="utility-copy"><span className="utility-title">云端同步</span><span className="utility-description">{label}</span></span>
    <span className={`utility-status-dot${problem ? ' is-error' : status?.auth_pending ? ' needs-attention' : status?.connected ? ' is-connected' : ''}`} aria-hidden="true" />
    <NavigationIcon name="arrow" />
  </Link>
}
