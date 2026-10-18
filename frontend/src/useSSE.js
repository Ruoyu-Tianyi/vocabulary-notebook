import { useEffect, useCallback, useRef } from 'react'

/**
 * 订阅后端 SSE 事件流
 * - enriched 事件:onEnriched(wordId, data)
 * - enrich_failed 事件:onEnrichFailed(wordId, word, reason)
 * - 连接断开:onDisconnect()
 * 返回 cleanup 函数在组件卸载时断开连接
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
    let aborted = false
    let reader = null

    async function connect() {
      try {
        const res = await fetch('/api/events', { headers: { Accept: 'text/event-stream' } })
        if (!res.ok || aborted) return
        reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!aborted) {
          const { done, value } = await reader.read()
          if (done) {
            if (!aborted && onDisconnectRef.current) onDisconnectRef.current()
            break
          }
          buffer += decoder.decode(value, { stream: true })

          // 解析 SSE 帧
          const parts = buffer.split('\n\n')
          buffer = parts.pop() || ''

          for (const part of parts) {
            const lines = part.split('\n')
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const event = JSON.parse(line.slice(6))
                  if (event.type === 'enriched') {
                    onEnrichedRef.current?.(event.word_id, {
                      phonetic: event.phonetic,
                      definition: event.definition,
                      example: event.example,
                    })
                  } else if (event.type === 'enrich_failed') {
                    onEnrichFailedRef.current?.(event.word_id, event.word, event.reason, { removed: event.removed === true })
                  }
                } catch {
                  // 忽略解析失败的行
                }
              }
            }
          }
        }
      } catch {
        if (!aborted && onDisconnectRef.current) onDisconnectRef.current()
      } finally {
        if (reader) {
          try { reader.cancel() } catch {}
        }
      }
    }

    connect()

    return () => {
      aborted = true
      if (reader) {
        try { reader.cancel() } catch {}
      }
    }
  }, [])
}
