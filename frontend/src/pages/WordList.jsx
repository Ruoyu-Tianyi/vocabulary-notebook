import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchWords, fetchDates, enrichMissing, moveWords, copyWords } from '../api'
import { useSSE } from '../useSSE'
import { useNotebooks } from '../useNotebooks'
import { useTransientMessage } from '../useTransientMessage'
import WordCard from '../components/WordCard'
import ExportMenu from '../components/ExportMenu'
import EnrichProgress from '../components/EnrichProgress'
import NavigationIcon from '../components/NavigationIcon'
import { readLegacyWordSort } from '../lib/compat'
import { isShortcutEvent } from '../lib/keyboard'

export default function WordList({ searchInputRef }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawPage = Number(searchParams.get('page') || 1)
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1
  const notebookId = searchParams.get('notebook_id') || ''
  const { notebooks, error: notebookError, refresh: refreshNotebooks } = useNotebooks()
  const currentBook = notebooks.find(book => book.id === notebookId)
  const addUrl = `/word/new${notebookId ? `?notebook_id=${encodeURIComponent(notebookId)}` : ''}`
  const setPage = useCallback(newPage => {
    setSearchParams(previous => {
      const next = new URLSearchParams(previous)
      next.set('page', String(newPage))
      return next
    })
  }, [setSearchParams])

  const [words, setWords] = useState([])
  const [dates, setDates] = useState([])
  const [q, setQ] = useState('')
  const [date, setDate] = useState('')
  const [sort, setSort] = useState(() => {
    try {
      const saved = localStorage.getItem('vocove-word-sort') ?? readLegacyWordSort(localStorage)
      // 旧版默认顺序按添加时间升序展示，迁移时保留这一偏好。
      if (saved === '') return 'created_asc'
      return ['created_desc', 'created_asc', 'alpha_asc', 'alpha_desc'].includes(saved) ? saved : 'created_desc'
    } catch { return 'created_desc' }
  })
  useEffect(() => {
    try { localStorage.setItem('vocove-word-sort', sort) } catch { /* Storage may be unavailable. */ }
  }, [sort])
  const [letter, setLetter] = useState('')
  const [availableLetters, setAvailableLetters] = useState([])
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageInput, setPageInput] = useState(String(page))
  const [organizing, setOrganizing] = useState(false)
  const [selected, setSelected] = useState([])
  const [destination, setDestination] = useState('')
  const [moving, setMoving] = useState(false)

  // 页码跟随 URL，浏览器前进后退时保持筛选范围一致。
  useEffect(() => {
    setPageInput(String(page))
  }, [page])
  useEffect(() => { setSelected([]) }, [q, date, sort, letter, page, notebookId])

  // page 切换函数，同时更新 URL
  function goToPage(newPage) {
    setPage(newPage)
  }

  function changeNotebook(id) {
    setSearchParams(previous => {
      const next = new URLSearchParams(previous)
      if (id) next.set('notebook_id', id)
      else next.delete('notebook_id')
      next.set('page', '1')
      return next
    })
    setDate('')
    setLetter('')
  }

  async function organizeWords(copy) {
    if (!destination || !selected.length || moving) return
    setMoving(true)
    try {
      const result = copy ? await copyWords(selected, destination) : await moveWords(selected, destination)
      setToast(copy ? `已加入 ${result.copied_count} 个单词${result.skipped_count ? `，跳过 ${result.skipped_count} 个已有单词` : ''}` : `已移动 ${result.moved_count} 个单词，复习进度已保留`)
      setSelected([])
      setLibraryVersion(v => v + 1)
    } catch (err) { setToast(err.message) }
    finally { setMoving(false) }
  }

  // 页码输入框提交：把字符串解析为正整数并 clamp 到 [1, totalPages]
  function commitPageInput(raw) {
    const n = parseInt(raw, 10)
    if (Number.isFinite(n) && n >= 1 && n <= totalPages) {
      if (n !== page) goToPage(n)
      else setPageInput(String(page))
    } else {
      setPageInput(String(page))
    }
  }
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [enriching, setEnriching] = useState(false)
  const [toast, setToast] = useTransientMessage()
  const [sseDisconnected, setSseDisconnected] = useState(false)
  const [libraryVersion, setLibraryVersion] = useState(0)

  useEffect(() => {
    let alive = true
    setDates([])
    fetchDates(notebookId).then(d => { if (alive) setDates(d.dates) }).catch(() => {})
    return () => { alive = false }
  }, [libraryVersion, notebookId])

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    setWords([])
    fetchWords({ q, date, page, sort, letter, notebook_id: notebookId })
      .then(data => {
        if (!alive) return
        setWords(data.words)
        setTotalPages(data.pages)
        setTotal(data.total)
        setAvailableLetters(data.available_letters || [])
        if (page > Math.max(1, data.pages)) setPage(Math.max(1, data.pages))
      })
      .catch(err => { if (alive) setError(err.message || '加载失败，请确认后端服务是否运行') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [q, date, page, sort, letter, libraryVersion, notebookId, setPage])

  function toggleLetter(l) {
    setLetter(prev => (prev === l ? '' : l))
    setPage(1)
  }

  // SSE 实时更新 — 模型补充数据后无需刷新
  const handleEnriched = useCallback((wordId, data) => {
    setWords(prev => prev.map(w =>
      w.id === wordId ? { ...w, ...data } : w
    ))
  }, [])

  // SSE: enrich 校验失败 — toast 提示用户
  const handleEnrichFailed = useCallback((wordId, word, reason, detail) => {
    if (detail?.removed) {
      setWords(previous => previous.filter(w => w.id !== wordId))
      setLibraryVersion(previous => previous + 1)
      refreshNotebooks()
      window.dispatchEvent(new Event('review-stats-changed'))
    }
    // 简化 reason 文本(去掉引号和括号内的细节)
    const cleanReason = String(reason || '请稍后重试').replace(/['"()（）]/g, '').slice(0, 60)
    setToast(`自动补全失败: ${word} — ${cleanReason}`, 5000)
  }, [refreshNotebooks, setToast])

  useSSE({
    onEnriched: handleEnriched,
    onEnrichFailed: handleEnrichFailed,
    onDisconnect: () => setSseDisconnected(true),
  })

  const hasMissing = !loading && words.some(w => !w.definition)
  const hasFilters = Boolean(q || date || letter)

  function clearFilters() {
    setQ('')
    setDate('')
    setLetter('')
    setPage(1)
  }

  async function handleEnrichMissing() {
    if (!hasMissing) {
      setToast('当前列表没有需要补全的单词', 3000)
      return
    }
    setEnriching(true)
    setSseDisconnected(false)
    setToast('')
    try {
      const result = await enrichMissing(notebookId)
      setToast(result.message, 4000)
      // 不在这里 setEnriching(false) — 后端可能还要跑很久。
      // 由 EnrichProgress 通过 useEnrichProgress 检测到后端完成时回调
    } catch {
      setToast('补全请求失败，请确认后端运行中', 4000)
      setEnriching(false)  // 请求失败：没东西可补，关掉 bar
    }
  }

  // 后端报"批次已完成"时关掉进度条
  const handleEnrichComplete = useCallback(() => {
    setEnriching(false)
  }, [])

  return (
    <div className="word-list-page">
      {toast && <div className="toast toast-info" role="status">{toast}</div>}
      {sseDisconnected && (
        <div className="toast toast-warn">
          实时连接已断开，补全进度可能不会自动更新
       </div>
      )}
      <section className="notebook-scope" aria-label="单词本范围">
        <div className="notebook-scope-title">
          <h2>{currentBook?.name || (notebookId ? '单词本' : '全部单词')}</h2>
          <p>{currentBook?.description || '收录每一次遇见，让词汇成为积累。'}</p>
        </div>
        <div className="notebook-actions">
          <select aria-label="选择单词本" value={notebookId} onChange={e => changeNotebook(e.target.value)} disabled={moving}>
            <option value="">全部单词本</option>
            {notebookId && !currentBook && <option value={notebookId}>当前单词本</option>}
            {notebooks.map(book => <option key={book.id} value={book.id}>{book.name}（{book.word_count}）</option>)}
          </select>
          <Link className="btn btn-ghost" to="/notebooks">管理单词本</Link>
          {notebookId && <Link className="btn btn-secondary" to={`/review?notebook_id=${encodeURIComponent(notebookId)}`}>复习本书</Link>}
        </div>
        {notebookError && <p className="notebook-error" role="alert">{notebookError} <button className="btn btn-ghost" onClick={refreshNotebooks}>重试</button></p>}
      </section>
      <section className="library-tools" aria-label="查找单词">
      <div className="library-search">
        <NavigationIcon name="search" />
        <input
          ref={searchInputRef}
          type="text"
          aria-label="搜索英文单词或中文译文"
          aria-keyshortcuts="/ Escape"
          placeholder="搜索英文单词或中文译文…"
          autoComplete="off"
          spellCheck={false}
          value={q}
          onChange={e => { setQ(e.target.value); setLetter(''); setPage(1) }}
          onKeyDown={event => {
            if (event.key !== 'Escape' || !isShortcutEvent(event)) return
            event.preventDefault()
            if (q) { setQ(''); setPage(1) }
            else event.currentTarget.blur()
          }}
        />
        {q ? <button type="button" className="search-clear" aria-label="清除搜索" onClick={() => { setQ(''); setPage(1); searchInputRef.current?.focus() }}><NavigationIcon name="close" /></button> : <kbd aria-hidden="true">/</kbd>}
      </div>
      <div className="toolbar">
        <div className="library-filters">
        <select aria-label="添加日期" value={date} onChange={e => { setDate(e.target.value); setPage(1) }}>
          <option value="">全部日期</option>
          {dates.map(d => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          value={sort}
          onChange={e => { setSort(e.target.value); setPage(1) }}
          title="排序方式"
          aria-label="排序方式"
        >
          <option value="created_desc">添加时间：最新在前</option>
          <option value="created_asc">添加时间：最早在前</option>
          <option value="alpha_asc">首字母 A→Z</option>
          <option value="alpha_desc">首字母 Z→A</option>
        </select>
        </div>
        <div className="library-actions">
        <button
          className="btn btn-secondary"
          onClick={handleEnrichMissing}
          disabled={enriching || !hasMissing}
          title={!hasMissing ? '当前列表所有单词已补全' : undefined}
        >
          {enriching ? '补全中…' : '补全缺失'}
        </button>
        <ExportMenu q={q} date={date} sort={sort} letter={letter} notebook_id={notebookId} />
        </div>
      </div>
      </section>

      <nav className="alphabet-nav" aria-label="按首字母筛选">
        <button type="button" className={`alpha alpha-all${!letter ? ' active' : ''}`} aria-pressed={!letter} onClick={() => { setLetter(''); setPage(1) }}>全部</button>
        {Array.from('abcdefghijklmnopqrstuvwxyz').map(l => {
          const has = availableLetters.includes(l)
          const active = letter === l
          const stateClass = active ? 'active' : has ? 'has-match' : 'empty'
          return (
            <button
              key={l}
              type="button"
              className={`alpha ${stateClass}`}
              aria-pressed={active}
              onClick={() => (active || has) && toggleLetter(l)}
              disabled={!active && !has}
              title={
                active ? `清除首字母 ${l.toUpperCase()} 筛选`
                  : has ? `查看以 ${l.toUpperCase()} 开头的单词`
                  : `无 ${l.toUpperCase()} 开头的单词`
              }
            >
              {l.toUpperCase()}
            </button>
          )
        })}
      </nav>

      {hasFilters && <div className="active-filters" aria-label="当前筛选">
        <span>筛选</span>
        {q && <button onClick={() => { setQ(''); setPage(1) }} aria-label={`清除搜索 ${q}`}>“{q}” <NavigationIcon name="close" /></button>}
        {date && <button onClick={() => { setDate(''); setPage(1) }} aria-label={`清除日期 ${date}`}>{date}<NavigationIcon name="close" /></button>}
        {letter && <button onClick={() => { setLetter(''); setPage(1) }} aria-label={`清除首字母 ${letter.toUpperCase()}`}>首字母 {letter.toUpperCase()}<NavigationIcon name="close" /></button>}
        <button className="clear-filters" onClick={clearFilters}>清除全部</button>
      </div>}

      <EnrichProgress active={enriching} onComplete={handleEnrichComplete} />

      <div className="word-organize-toggle">
        <p className="list-summary" role="status">{loading ? '正在读取词库…' : error ? '词库加载失败' : <><strong>{total.toLocaleString()}</strong> 个单词{hasFilters && '符合筛选'}<span>{totalPages > 1 && `第 ${page} / ${totalPages} 页`}</span></>}</p>
        <button className="btn btn-ghost" disabled={moving} aria-expanded={organizing} onClick={() => { setOrganizing(v => !v); setSelected([]) }}>
          <NavigationIcon name="organize" />
          {organizing ? '完成整理' : '整理单词'}
        </button>
      </div>
      {organizing && <section className="word-organize" aria-label="批量整理单词">
        <div className="notebook-actions">
          <label className="word-check"><input type="checkbox" aria-label="全选本页" disabled={moving || loading || !words.length}
            checked={words.length > 0 && words.every(w => selected.includes(w.id))}
            onChange={e => setSelected(e.target.checked ? words.map(w => w.id) : [])} />全选本页</label>
          <span aria-live="polite">已选 {selected.length} 个</span>
          <select aria-label="目标单词本" value={destination} disabled={moving} onChange={e => setDestination(e.target.value)}>
            <option value="">选择目标单词本</option>
            {notebooks.map(book => <option key={book.id} value={book.id}>{book.name}</option>)}
          </select>
          <button className="btn btn-primary" disabled={moving || loading || Boolean(error) || !selected.length || !destination} onClick={() => organizeWords(true)}>加入单词本</button>
          <button className="btn btn-secondary" disabled={moving || loading || Boolean(error) || !selected.length || !destination} onClick={() => organizeWords(false)}>{moving ? '处理中…' : '移动到此本'}</button>
        </div>
        <p>加入会保留原词，在目标本从新词开始；移动会带上原有复习进度。目标本已有的词不会被覆盖。</p>
      </section>}

      {error && <div className="empty-state" role="alert"><p>{error}</p><button className="btn btn-secondary" onClick={() => setLibraryVersion(v => v + 1)}>重新加载</button></div>}
      {error ? null : loading ? (
        <div className="word-skeletons" aria-label="正在加载单词" aria-busy="true">{[0, 1, 2].map(i => <div className="word-skeleton" key={i} aria-hidden="true"><span /><span /><span /></div>)}</div>
      ) : words.length === 0 ? (
        <div className="empty-state">
          <svg className="empty-icon" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="6" width="28" height="36" rx="3" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M13 14h18M13 20h18M13 26h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <circle cx="36" cy="36" r="9" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M33 36h6M36 33v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <p>
            {q || date || letter
              ? `无匹配单词${letter ? `（首字母 ${letter.toUpperCase()}）` : ''}`
              : '还没有单词'}
          </p>
          {q || date || letter ? (
            <button className="btn btn-ghost" onClick={clearFilters}>
              清除筛选
            </button>
          ) : (
            <Link to={addUrl}>去添加第一个单词</Link>
          )}
        </div>
      ) : (
        <>
          {words.map(w => <div className={`word-entry${organizing ? ' is-selectable' : ''}`} key={w.id}>
            {organizing && <label className="word-check"><input type="checkbox" aria-label={`选择 ${w.word}`} checked={selected.includes(w.id)} disabled={moving}
              onChange={e => setSelected(ids => e.target.checked ? [...ids, w.id] : ids.filter(id => id !== w.id))} /></label>}
            <div className="word-entry-content">
              <WordCard word={w} q={q} notebookName={!notebookId ? notebooks.find(book => book.id === w.notebook_id)?.name || '默认单词本' : undefined} />
            </div>
          </div>)}
          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => goToPage(page - 1)}
              >
                上一页
              </button>
              <span className="page-jump">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  className="page-input"
                  value={pageInput}
                  onChange={e => setPageInput(e.target.value.replace(/\D/g, ''))}
                  onBlur={e => commitPageInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && isShortcutEvent(e)) {
                      e.preventDefault()
                      e.currentTarget.blur()
                    }
                  }}
                  aria-label="跳转到页码"
                />
                <span> / {totalPages}</span>
              </span>
              <button
                className="btn btn-secondary"
                disabled={page >= totalPages}
                onClick={() => goToPage(page + 1)}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
