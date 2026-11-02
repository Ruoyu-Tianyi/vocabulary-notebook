import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import NavigationIcon from './NavigationIcon'

export default function ModelStatus({ onProblemChange } = {}) {
  const location = useLocation()
  const [health, setHealth] = useState(null)

  useEffect(() => {
    let aborted = false
    let requestId = 0

    async function check() {
      const current = ++requestId
      try {
        const res = await fetch('/api/health')
        if (!res.ok) throw new Error('连接检查失败')
        const data = await res.json()
        if (!aborted && current === requestId) setHealth(data)
      } catch {
        if (!aborted && current === requestId) setHealth({ provider: 'unknown', status: 'disconnected' })
      }
    }

    check()
    window.addEventListener('model-settings-changed', check)
    const timer = setInterval(check, 5 * 60 * 1000) // 每 5min 检测一次
    return () => {
      aborted = true
      clearInterval(timer)
      window.removeEventListener('model-settings-changed', check)
    }
  }, [])

  const { provider, status } = health || {}
  const connected = status === 'connected'
  const problem = health !== null && !connected && status !== 'unverified'
  const providerLabel = health?.provider_name || provider || '模型服务'
  const label = health === null ? '检查连接…'
    : status === 'unverified' ? `${providerLabel} · 请在设置中测试模型`
    : status === 'model_unavailable' ? `模型 ${health.model} 已不可用 · 请重新配置`
      : connected ? `${providerLabel} 已连接` : `${providerLabel} 无法连接 · 查看设置`

  useEffect(() => { onProblemChange?.(problem) }, [problem, onProblemChange])

  return (
    <Link to="/settings"
      className={`utility-item${problem ? ' has-error' : ''}`}
      aria-current={location.pathname === '/settings' ? 'page' : undefined}
      title={problem ? `${label}；自动补全暂不可用` : label}
    >
      <NavigationIcon name="model" />
      <span className="utility-copy"><span className="utility-title">模型设置</span><span className="utility-description">{label}</span></span>
      <span className={`utility-status-dot${problem ? ' is-error' : connected ? ' is-connected' : ''}`} aria-hidden="true" />
      <NavigationIcon name="arrow" />
    </Link>
  )
}
