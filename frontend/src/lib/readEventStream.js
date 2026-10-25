/** 读取 SSE data 帧；分块传输可能切开 UTF-8 字符或帧分隔符。 */
export async function readEventStream(stream, onEvent, signal) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const cancel = () => { reader.cancel().catch(() => {}) }
  signal?.addEventListener('abort', cancel, { once: true })

  try {
    while (!signal?.aborted) {
      const { done, value } = await reader.read()
      if (done || signal?.aborted) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() || ''
      for (const frame of frames) {
        if (signal?.aborted) break
        const data = frame.split(/\r?\n/)
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).replace(/^ /, ''))
          .join('\n')
        if (!data) continue
        let event
        try { event = JSON.parse(data) }
        catch { continue }
        onEvent(event)
      }
    }
  } finally {
    signal?.removeEventListener('abort', cancel)
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
