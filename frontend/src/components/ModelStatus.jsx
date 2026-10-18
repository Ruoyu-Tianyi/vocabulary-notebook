import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function ModelStatus() {
  const [health, setHealth] = useState(null) // null = checking

  useEffect(() => {
    let aborted = false

    async function check() {
      try {
        const res = await fetch('/api/health')
        const data = await res.json()
        if (!aborted) setHealth(data)
      } catch {
        if (!aborted) setHealth({ provider: 'unknown', status: 'disconnected' })
      }
    }

    check()
    window.addEventListener('ai-settings-changed', check)
    const timer = setInterval(check, 5 * 60 * 1000) // 每 5min 检测一次
    return () => {
      aborted = true
      clearInterval(timer)
      window.removeEventListener('ai-settings-changed', check)
    }
  }, [])

  if (health === null) return null // 首次加载不显示

  const { provider, status } = health
  const connected = status === 'connected'
  const providerLabel = provider === 'deepseek' ? 'DeepSeek' : provider
  const label = { not_configured: '待配置 API Key', unauthorized: 'API Key 无效', model_unavailable: '模型不可用', disconnected: '连接失败' }[status] || '连接失败'

  return (
    <Link to="/settings"
      className={`model-status ${connected ? 'on' : 'off'}`}
      title={connected ? `${providerLabel} 已连接 · ${health.model}` : `${providerLabel} ${label}，请在“同步与备份”配置`}
    >
      <span className="model-dot" />
      {connected ? `${providerLabel} 已连接` : `${providerLabel} ${label}`}
    </Link>
  )
}
