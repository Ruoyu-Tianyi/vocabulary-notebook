import { useEffect, useRef } from 'react'
import { readEventStream } from './lib/readEventStream'

/**
 * 订阅后端 SSE 事件流
 * - enriched 事件:onEnriched(wordId, data)
 * - enrich_failed 事件:onEnrichFailed(wordId, word, reason, { removed })
 * - 连接断开:onDisconnect()
 * 组件卸载时取消连接，包括尚未收到响应头的请求。
 */
export function useSSE({ onEnriched, onEnrichFailed, onDisconnect }) {
  const onEnrichedRef = useRef(onEnriched)
  const onEnrichFailedRef = useRef(onEnrichFailed)
  const onDisconnectRef = useRef(onDisconnect)
  useEffect(() => {
    onEnrichedRef.current = onEnriched
    onEnrichFailedRef.current = onEnrichFailed
    onDisconnectRef.current = onDisconnect
  })

  useEffect(() => {
    const controller = new AbortController()

    async function connect() {
      try {
        const res = await fetch('/api/events', { headers: { Accept: 'text/event-stream' }, signal: controller.signal })
        if (!res.ok || !res.body) throw new Error('实时连接失败')
        await readEventStream(res.body, event => {
          if (event?.type === 'enriched') {
            onEnrichedRef.current?.(event.word_id, {
              phonetic: event.phonetic,
              definition: event.definition,
              example: event.example,
            })
          } else if (event?.type === 'enrich_failed') {
            onEnrichFailedRef.current?.(event.word_id, event.word, event.reason, { removed: event.removed === true })
          }
        }, controller.signal)
      } catch {
        // 断连反馈统一在 finally 处理；主动退出页面不显示错误。
      } finally {
        if (!controller.signal.aborted) onDisconnectRef.current?.()
      }
    }

    connect()

    return () => controller.abort()
  }, [])
}
