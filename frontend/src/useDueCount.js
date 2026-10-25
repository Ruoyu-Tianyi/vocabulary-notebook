import { useEffect, useState } from 'react'
import { fetchReviewStats } from './api'

/** 导航栏待复习角标：首次加载、评分后、回到页面和每 60 秒刷新。 */
export function useDueCount() {
  const [dueCount, setDueCount] = useState(0)

  useEffect(() => {
    let controller
    function refresh() {
      controller?.abort()
      const current = new AbortController()
      controller = current
      fetchReviewStats('', { signal: current.signal })
        .then(stats => { if (!current.signal.aborted) setDueCount(stats.due_today || 0) })
        .catch(() => {})
    }
    refresh()
    const timer = window.setInterval(refresh, 60_000)
    function handleVisibility() {
      if (document.visibilityState === 'visible') refresh()
    }
    window.addEventListener('review-stats-changed', refresh)
    document.addEventListener('visibilitychange', handleVisibility)
    return () => {
      window.clearInterval(timer)
      controller?.abort()
      window.removeEventListener('review-stats-changed', refresh)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])

  return dueCount
}
