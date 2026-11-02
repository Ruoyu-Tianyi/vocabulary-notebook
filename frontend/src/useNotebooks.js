import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchNotebooks } from './api'

export function useNotebooks() {
  const [notebooks, setNotebooks] = useState([])
  const [contexts, setContexts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const requestId = useRef(0)

  const refresh = useCallback(async () => {
    const current = ++requestId.current
    setLoading(true)
    setError('')
    try {
      const result = await fetchNotebooks()
      if (current === requestId.current) {
        setNotebooks(result.notebooks)
        setContexts(result.contexts || [])
      }
    } catch (requestError) {
      if (current === requestId.current) setError(requestError.message || '单词本加载失败')
    } finally {
      if (current === requestId.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    window.addEventListener('notebooks-changed', refresh)
    window.addEventListener('cloud-data-changed', refresh)
    return () => {
      requestId.current += 1
      window.removeEventListener('notebooks-changed', refresh)
      window.removeEventListener('cloud-data-changed', refresh)
    }
  }, [refresh])

  return { notebooks, contexts, loading, error, refresh }
}

export default useNotebooks
