import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { createWord, fetchWord } from '../api'
import { useSSE } from '../useSSE'
import WordCard from '../components/WordCard'
import { useNotebooks } from '../useNotebooks'
import { useTransientMessage } from '../useTransientMessage'
import NavigationIcon from '../components/NavigationIcon'
import { isShortcutEvent } from '../lib/keyboard'
import './NotebookPolish.css'

function useProviderLabel() {
  const [label, setLabel] = useState('模型')
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/health', { signal: controller.signal })
      .then(r => { if (!r.ok) throw new Error('连接检查失败'); return r.json() })
      .then(d => {
        if (controller.signal.aborted) return
        const p = d.provider
        setLabel(d.provider_name || p || '模型')
      })
      .catch(() => {})
    return () => controller.abort()
  }, [])
  return label
}

export default function WordNew() {
  const [searchParams, setSearchParams] = useSearchParams()
  const notebookId = searchParams.get('notebook_id') || 'default'
  const { notebooks, loading: booksLoading, error: booksError, refresh: refreshBooks } = useNotebooks()
  const selectedBook = notebooks.find(book => book.id === notebookId)
  const [word, setWord] = useState('')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useTransientMessage(null)
  const [addedWords, setAddedWords] = useState([])
  const addedRef = useRef([])
  const inputRef = useRef(null)
  const composingRef = useRef(false)
  const compositionSubmitRef = useRef(false)
  const navigate = useNavigate()
  const providerLabel = useProviderLabel()
  useEffect(() => { addedRef.current = addedWords }, [addedWords])
  useEffect(() => {
    // 手机端不自动唤起键盘，保留用户先选择单词本的空间。
    if (window.matchMedia('(min-width: 641px) and (pointer: fine)').matches) inputRef.current?.focus()
  }, [])

  const updateAdded = useCallback(result => {
    setAddedWords(previous => previous.map(entry => {
      if (entry.word.id !== result.word.id) return entry
      // A request started before an SSE success must not erase the displayed definition.
      if (['removed', 'deleted'].includes(entry.enrichment?.status)) return entry
      if (entry.word.definition && !result.word.definition) return entry
      return { ...entry, ...result }
    }))
  }, [])
  const handleEnriched = useCallback((id, fields) => {
    setAddedWords(previous => previous.map(entry => entry.word.id === id
      ? { ...entry, word: { ...entry.word, ...fields }, enrichment: { status: fields.definition ? 'ready' : 'idle' } } : entry))
    window.dispatchEvent(new Event('review-stats-changed'))
  }, [])
  const handleFailed = useCallback((id, _word, reason, detail) => {
    setAddedWords(previous => previous.map(entry => entry.word.id === id
      ? { ...entry, enrichment: { status: detail?.removed ? 'removed' : 'failed', error: reason } } : entry))
    if (detail?.removed) {
      window.dispatchEvent(new Event('notebooks-changed'))
      window.dispatchEvent(new Event('review-stats-changed'))
    }
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
    // Recover persisted results after a disconnected or missed SSE notification.
    const timer = setInterval(refresh, 2000)
    return () => { alive = false; clearInterval(timer) }
  }, [hasPending, updateAdded])

  function showRecent(result) {
    setAddedWords(previous => [result, ...previous.filter(entry => entry.word.id !== result.word.id)].slice(0, 10))
  }

  function clearSubmitted(submitted) {
    setWord(current => current.trim() === submitted ? '' : current)
    inputRef.current?.focus()
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (composingRef.current || compositionSubmitRef.current) return
    if (!word.trim() || loading || booksLoading || booksError || !selectedBook) return
    const submitted = word.trim()
    setLoading(true)
    try {
      const result = await createWord(submitted, '', notebookId)
      showRecent(result)
      clearSubmitted(submitted)
      setToast({ type: 'info', msg: `「${result.word.word}」已保存到「${selectedBook.name}」` }, 2000)
    } catch (err) {
      if (err.status === 409 && err.details?.word?.id) {
        showRecent({ word: err.details.word, enrichment: err.details.enrichment, existing: true })
        clearSubmitted(submitted)
        setToast({ type: 'info', msg: err.message }, 3000)
      } else if (err.status === 409) {
        setToast({ type: 'warn', msg: err.message }, 3000)
      } else {
        setToast({ type: 'error', msg: err.message }, 3000)
      }
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    const composing = composingRef.current || e.nativeEvent?.isComposing || e.nativeEvent?.keyCode === 229
    // 不阻止输入法的候选确认；只在表单提交时拦截这次 Enter 的隐式保存。
    if (e.key === 'Enter' && composing) {
      compositionSubmitRef.current = true
      return
    }
    if (!composing) compositionSubmitRef.current = false
    if (e.key === 'Enter' && e.repeat) {
      e.preventDefault()
      return
    }
    if (e.key === 'Escape' && !composing && isShortcutEvent(e)) {
      e.preventDefault()
      navigate(-1)
    }
  }

  return (
    <div className="word-new-page">
      {toast && <div className={`toast toast-${toast.type}`} role={toast.type === 'error' ? 'alert' : 'status'}>{toast.msg}</div>}
      <header className="word-new-heading">
        <h2>添加单词</h2>
        <p>记下遇见的新词，释义、音标和例句交给 {providerLabel}。</p>
      </header>
      <form className="word-new-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="new-word-notebook">保存到单词本</label>
          <div className="word-new-destination">
            <select
              id="new-word-notebook"
              className="notebook-select"
              value={notebookId}
              disabled={loading || booksLoading || Boolean(booksError)}
              onKeyDown={event => event.stopPropagation()}
              onChange={event => setSearchParams(previous => {
                const next = new URLSearchParams(previous)
                next.set('notebook_id', event.target.value)
                return next
              })}
            >
              {!selectedBook && <option value={notebookId} disabled>{booksLoading ? '加载单词本…' : '此单词本已不可用，请重新选择'}</option>}
              {notebooks.map(book => <option key={book.id} value={book.id}>{book.name}</option>)}
            </select>
            <Link className="btn btn-ghost" to="/notebooks">管理单词本</Link>
          </div>
          {booksError && <p role="alert">{booksError} <button type="button" className="btn btn-ghost" onClick={refreshBooks}>重试</button></p>}
        </div>
        <div className="form-group">
          <label htmlFor="new-word">单词</label>
          <input
            id="new-word"
            ref={inputRef}
            type="text"
            value={word}
            onChange={e => setWord(e.target.value)}
            onKeyDown={handleKeyDown}
            onKeyUp={event => { if (event.key === 'Enter') compositionSubmitRef.current = false }}
            onCompositionStart={() => { composingRef.current = true; compositionSubmitRef.current = false }}
            onCompositionEnd={() => { composingRef.current = false }}
            onBlur={() => { composingRef.current = false; compositionSubmitRef.current = false }}
            placeholder="输入英文单词…"
            aria-describedby="new-word-hint"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
          />
          <p id="new-word-hint" className="word-new-field-hint">新词首字母统一大写，其余字符保留输入时的大小写。</p>
        </div>
        <div className="btn-group">
          <button type="submit" className="btn btn-primary" disabled={loading || booksLoading || Boolean(booksError) || !selectedBook}>
            <NavigationIcon name="plus" />{loading ? '保存中…' : '保存单词'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => navigate(-1)}>
            取消
          </button>
        </div>
        <div className="word-new-form-footer">
          <span>保存后可继续输入，补全结果会显示在下方。</span>
          <span className="word-new-shortcuts">单词输入框内：<kbd>Enter</kbd> 保存 <span>·</span> <kbd>Esc</kbd> 返回</span>
        </div>
      </form>
      {addedWords.length > 0 && <section className="added-words" aria-labelledby="added-words-heading">
        <h3 id="added-words-heading">刚刚添加 · 即时记忆</h3>
        <p className="added-words-hint">本页展示最近添加或再次查看的 10 个单词，在同一本中重复输入会直接显示已有内容。</p>
        <div aria-live="polite" aria-relevant="additions text">
          {addedWords.map(entry => <article key={entry.word.id}>
            <p className="added-words-hint">
              <Link to={`/?notebook_id=${encodeURIComponent(entry.word.notebook_id || 'default')}`}>{notebooks.find(book => book.id === entry.word.notebook_id)?.name || '所属单词本'}</Link>
              {entry.existing && ' · 本中已有，已展示原记录并保留复习进度'}
            </p>
            {['removed', 'deleted'].includes(entry.enrichment?.status) ? <h4>{entry.word.word}</h4> : <WordCard word={entry.word} />}
            {!entry.word.definition && <p className="added-words-hint">
              {['queued', 'processing'].includes(entry.enrichment?.status) ? '已保存，正在生成释义…'
                : entry.enrichment?.status === 'deleted' ? '这个单词已被删除。'
                  : entry.enrichment?.error || '单词已保存，释义尚未生成，可在列表补全缺失或手动编辑。'}
            </p>}
          </article>)}
        </div>
      </section>}
    </div>
  )
}
