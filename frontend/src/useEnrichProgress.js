import { useState, useEffect, useRef } from 'react'

/**
 * 轮询 /api/enrich/progress，驱动 EnrichProgress 渲染。
 * 完成条件：批次已开始 + 没有处理中的单词 + 队列为空 → 触发 onComplete（仅一次）
 * onComplete 用来让上游把 active 翻 false，让 polling 自然停止
 */
export function useEnrichProgress(enabled = false, onComplete) {
  const [progress, setProgress] = useState({
    queue_size: 0,
    current_word: null,
    batch_total: 0,
    batch_done: 0,
    total_missing: 0,
    is_processing: false,
  })

  const completedRef = useRef(false)
  const onCompleteRef = useRef(onComplete)
  useEffect(() => { onCompleteRef.current = onComplete })

  useEffect(() => {
    if (!enabled) {
      // 下次重新启用时允许再次触发 onComplete
      completedRef.current = false
      return
    }

    const controller = new AbortController()
    let running = false

    async function poll() {
      if (running || controller.signal.aborted) return
      running = true
      try {
        const res = await fetch('/api/enrich/progress', { signal: controller.signal })
        if (res.ok) {
          const data = await res.json()
          if (controller.signal.aborted) return
          setProgress(data)
          if (
            data.batch_total > 0 &&
            !data.is_processing &&
            data.queue_size === 0 &&
            !completedRef.current
          ) {
            completedRef.current = true
            onCompleteRef.current?.()
          }
        }
      } catch {
        // 短暂断连留待下轮重试，主动退出不更新状态。
      } finally { running = false }
    }

    poll()
    const timer = setInterval(poll, 2000)
    return () => { clearInterval(timer); controller.abort() }
  }, [enabled])

  return progress
}
