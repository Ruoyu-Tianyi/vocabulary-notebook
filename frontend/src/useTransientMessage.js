import { useCallback, useEffect, useRef, useState } from 'react'

/** 新提示替换旧提示时，同时撤销旧的清除计时，避免新消息被提前移除。 */
export function useTransientMessage(emptyValue = '') {
  const [message, setMessage] = useState(emptyValue)
  const emptyRef = useRef(emptyValue)
  const timer = useRef(null)
  const mounted = useRef(false)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; window.clearTimeout(timer.current) }
  }, [])

  const showMessage = useCallback((nextMessage, duration = 0) => {
    if (!mounted.current) return
    window.clearTimeout(timer.current)
    setMessage(nextMessage)
    if (duration > 0) timer.current = window.setTimeout(() => setMessage(emptyRef.current), duration)
  }, [])

  return [message, showMessage]
}
