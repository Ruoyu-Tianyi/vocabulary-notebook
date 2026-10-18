import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { createWord, fetchWord, retryWordEnrichment } from '../api'
import { useBooks } from '../Books'
import { useSSE } from '../useSSE'

function useProviderLabel() {
  const [label, setLabel] = useState('模型')
  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(d => {
        const p = d.provider
        setLabel(p === 'deepseek' ? 'DeepSeek' : p || '模型')
      })
      .catch(() => {})
  }, [])
  return label
}

export default function WordNew() {
  const [word, setWord] = useState('')
  const { books, active } = useBooks()
  const [bookId, setBookId] = useState(active || 'default')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const [addedWords, setAddedWords] = useState([])
  const addedRef = useRef([])
  const inputRef = useRef(null)
  const navigate = useNavigate()
  const providerLabel = useProviderLabel()
  useEffect(() => { addedRef.current = addedWords }, [addedWords])
  const updateAdded = useCallback(result => {
    setAddedWords(previous => previous.map(entry => {
      if (entry.word.id !== result.word.id) return entry
      if (entry.word.definition && !result.word.definition) return entry
      return { ...entry, ...result }
    }))
  }, [])
  const handleEnriched = useCallback((id, fields) => {
    setAddedWords(previous => previous.map(entry => entry.word.id === id
      ? { ...entry, word: { ...entry.word, ...fields }, enrichment: { status: 'ready' } } : entry))
    window.dispatchEvent(new Event('review-stats-changed'))
  }, [])
  const handleFailed = useCallback((id, _word, reason) => {
    setAddedWords(previous => previous.map(entry => entry.word.id === id
      ? { ...entry, enrichment: { status: 'failed', error: reason } } : entry))
  }, [])
  useSSE({ onEnriched: handleEnriched, onEnrichFailed: handleFailed })
  const hasPending = addedWords.some(entry => ['queued', 'processing'].includes(entry.enrichment?.status))
  useEffect(() => {
    if (!hasPending) return
    let alive = true
    let running = false
    async function refresh() {
      if (running) return
      running = true
      try {
        const pending = addedRef.current.filter(entry => ['queued', 'processing'].includes(entry.enrichment?.status))
        const results = await Promise.allSettled(pending.map(async entry => {
          try { return await fetchWord(entry.word.id) }
          catch (err) {
            if (err.status === 404) return { ...entry, enrichment: { status: 'deleted' } }
            throw err
          }
        }))
        if (alive) results.forEach(result => { if (result.status === 'fulfilled') updateAdded(result.value) })
      } finally { running = false }
    }
    // Polling also recovers the result when SSE disconnects or another tab consumes an event.
    const timer = setInterval(refresh, 2000)
    return () => { alive = false; clearInterval(timer) }
  }, [hasPending, updateAdded])

  async function retry(entry) {
    updateAdded({ ...entry, enrichment: { status: 'queued' } })
    try { updateAdded(await retryWordEnrichment(entry.word.id)) }
    catch (err) { updateAdded({ ...entry, enrichment: { status: 'failed', error: err.message } }) }
  }

  function showRecent(result) {
    setAddedWords(previous => [result, ...previous.filter(entry => entry.word.id !== result.word.id)].slice(0, 10))
  }

  function clearSubmitted(submitted) {
    setWord(current => current.trim() === submitted ? '' : current)
    inputRef.current?.focus()
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!word.trim()) return
    const submitted = word.trim()
    setLoading(true)
    try {
      const result = await createWord(submitted, '', bookId)
      showRecent(result)
      clearSubmitted(submitted)
      window.dispatchEvent(new Event('library-changed'))
      window.dispatchEvent(new Event('review-stats-changed'))
      setToast({ type: 'info', msg: `「${result.word.word}」已保存` })
      setTimeout(() => setToast(null), 2000)
    } catch (err) {
      if (err.status === 409 && err.details?.word?.id) {
        showRecent({ word: err.details.word, enrichment: err.details.enrichment, existing: true })
        clearSubmitted(submitted)
        setToast({ type: 'info', msg: err.message })
      } else if (err.status === 409) {
        setToast({ type: 'warn', msg: err.message })
      } else {
        setToast({ type: 'error', msg: err.message })
      }
      setTimeout(() => setToast(null), 3000)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Escape') {
      e.preventDefault()
      navigate(-1)
    }
  }

  return (
    <div>
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
      <h2 style={{ marginBottom: 20 }}>添加单词</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group"><label htmlFor="new-word-book">保存到</label>
          <select id="new-word-book" value={bookId} onChange={e => setBookId(e.target.value)}>
            {books.map(book => <option key={book.id} value={book.id}>{book.name}</option>)}
          </select></div>
        <div className="form-group">
          <label htmlFor="new-word">单词</label>
          <input
            id="new-word"
            ref={inputRef}
            maxLength={200}
            type="text"
            value={word}
            onChange={e => setWord(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入英文单词，回车保存"
            autoFocus
          />
        </div>
        <div className="btn-group">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? '保存中…' : '保存'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => navigate(-1)}>
            取消
          </button>
        </div>
        <p style={{ marginTop: 14, fontSize: 12, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
          Enter 保存 · Esc 返回 · 释义由 {providerLabel} API 补充，生成后显示在下方；离线也能保存
          <br />新词首字母统一大写，其余字符保持输入的大小写；已有词条不改名。
        </p>
      </form>
      {addedWords.length > 0 && <section className="added-words" aria-labelledby="added-words-heading">
        <h3 id="added-words-heading">刚刚添加 · 即时记忆</h3>
        <p className="book-description">本页展示最近添加或再次查看的 10 个单词，重复输入会直接显示已有内容。</p>
        <div aria-live="polite" aria-relevant="additions text">
          {addedWords.map(entry => {
            const current = entry.word
            const status = entry.enrichment?.status
            const pending = ['queued', 'processing'].includes(status)
            return <article className="added-word-card" key={current.id}>
              <div className="added-word-head"><h4>{current.word}</h4>
                {entry.existing && <span className="existing-word-badge">单词本中已有</span>}
                {current.phonetic && <span>{current.phonetic}</span>}
                <span className="book-description">{books.find(book => book.id === current.notebook_id)?.name}</span></div>
              {current.definition ? <p className="added-definition">{current.definition}</p>
                : <p className="book-description">{pending ? '已保存，正在生成释义…'
                  : status === 'not_configured' ? '单词已保存，请先配置 DeepSeek API Key，再重试补全。'
                    : status === 'deleted' ? '这个单词已被删除。'
                      : entry.enrichment?.error || '单词已保存，释义尚未生成。'}</p>}
              {current.example && <blockquote className="added-example">{current.example}</blockquote>}
              <div className="btn-group">
                {!current.definition && status !== 'deleted' && <button type="button" className="btn btn-secondary" disabled={pending} onClick={() => retry(entry)}>{pending ? '生成中…' : '重试补全'}</button>}
                {status === 'not_configured' && <Link className="btn btn-ghost" to="/settings">配置 API Key</Link>}
                {status !== 'deleted' && <Link className="btn btn-ghost" to={`/word/${current.id}`}>查看 / 编辑</Link>}
              </div>
            </article>
          })}
        </div>
      </section>}
    </div>
  )
}
