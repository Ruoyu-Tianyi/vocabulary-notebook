import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchWords, fetchDates, enrichMissing } from '../api'
import { useSSE } from '../useSSE'
import WordCard from '../components/WordCard'
import ExportMenu from '../components/ExportMenu'
import EnrichProgress from '../components/EnrichProgress'

export default function WordList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const pageParam = parseInt(searchParams.get('page') || '1', 10)

  const [words, setWords] = useState([])
  const [dates, setDates] = useState([])
  const [q, setQ] = useState('')
  const [date, setDate] = useState('')
  const [sort, setSort] = useState(() => {
    const saved = localStorage.getItem('vocabulary-word-sort')
    return ['created_desc', 'created_asc', 'alpha_asc', 'alpha_desc'].includes(saved) ? saved : 'created_desc'
  })
  const [letter, setLetter] = useState('')
  const [availableLetters, setAvailableLetters] = useState([])
  const [page, setPage] = useState(pageParam)
  const [totalPages, setTotalPages] = useState(1)
  const [pageInput, setPageInput] = useState(String(pageParam))

  // page 变化时同步到 URL
  useEffect(() => {
    setSearchParams(p => {
      const next = new URLSearchParams(p)
      next.set('page', String(page))
      return next
    })
    setPageInput(String(page))
  }, [page, setSearchParams])

  // page 切换函数，同时更新 URL
  function goToPage(newPage) {
    setPage(newPage)
    setSearchParams(p => {
      const next = new URLSearchParams(p)
      next.set('page', String(newPage))
      return next
    })
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
  const [toast, setToast] = useState('')
  const [sseDisconnected, setSseDisconnected] = useState(false)
  const [libraryVersion, setLibraryVersion] = useState(0)

  useEffect(() => { fetchDates().then(d => setDates(d.dates)).catch(() => {}) }, [libraryVersion])

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError('')
    fetchWords({ q, date, page, sort, letter })
      .then(data => {
        if (!alive) return
        setWords(data.words)
        setTotalPages(data.pages)
        setAvailableLetters(data.available_letters || [])
        if (page > Math.max(1, data.pages)) setPage(Math.max(1, data.pages))
      })
      .catch(() => { if (alive) setError('加载失败，请确认后端服务是否运行') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [q, date, page, sort, letter, libraryVersion])

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
  const handleEnrichFailed = useCallback((wordId, word, reason, result = {}) => {
    if (result.removed) {
      setWords(previous => previous.filter(entry => entry.id !== wordId))
      setLibraryVersion(previous => previous + 1)
      window.dispatchEvent(new Event('library-changed'))
      window.dispatchEvent(new Event('review-stats-changed'))
    }
    // 简化 reason 文本(去掉引号和括号内的细节)
    const cleanReason = reason.replace(/['"()（）]/g, '').slice(0, 60)
    setToast(`自动补全失败: ${word} — ${cleanReason}`)
    setTimeout(() => setToast(''), 5000)
  }, [])

  useSSE({
    onEnriched: handleEnriched,
    onEnrichFailed: handleEnrichFailed,
    onDisconnect: () => setSseDisconnected(true),
  })

  const hasMissing = !loading && words.some(w => !w.definition)

  async function handleEnrichMissing() {
    if (!hasMissing) {
      setToast('当前列表没有需要补全的单词')
      setTimeout(() => setToast(''), 3000)
      return
    }
    setEnriching(true)
    setSseDisconnected(false)
    setToast('')
    try {
      const result = await enrichMissing()
      setToast(result.message)
      setTimeout(() => setToast(''), 4000)
      // 不在这里 setEnriching(false) — 后端可能还要跑很久。
      // 由 EnrichProgress 通过 useEnrichProgress 检测到后端完成时回调
    } catch {
      setToast('补全请求失败，请确认后端运行中')
      setTimeout(() => setToast(''), 4000)
      setEnriching(false)  // 请求失败：没东西可补，关掉 bar
    }
  }

  // 后端报"批次已完成"时关掉进度条
  const handleEnrichComplete = useCallback(() => {
    setEnriching(false)
  }, [])

  return (
    <div>
      {toast && <div className="toast toast-info">{toast}</div>}
      {sseDisconnected && (
        <div className="toast toast-warn">
          实时连接已断开，补全进度可能不会自动更新
       </div>
      )}
      <div className="toolbar">
        <input
          type="text"
          placeholder="搜索英文单词或中文译文，如：合同…"
          aria-label="搜索英文单词或中文译文"
          value={q}
          onChange={e => { setQ(e.target.value); setLetter(''); setPage(1) }}
        />
        <select value={date} onChange={e => { setDate(e.target.value); setPage(1) }}>
          <option value="">全部日期</option>
          {dates.map(d => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          value={sort}
          onChange={e => { setSort(e.target.value); localStorage.setItem('vocabulary-word-sort', e.target.value); setPage(1) }}
          title="排序方式"
        >
          <option value="created_desc">添加时间：最新在前</option>
          <option value="created_asc">添加时间：最早在前</option>
          <option value="alpha_asc">首字母 A→Z</option>
          <option value="alpha_desc">首字母 Z→A</option>
        </select>
        <button
          className="btn btn-secondary"
          onClick={handleEnrichMissing}
          disabled={enriching || !hasMissing}
          title={!hasMissing ? '当前列表所有单词已补全' : undefined}
        >
          {enriching ? '补全中…' : '补全缺失'}
        </button>
        <ExportMenu q={q} date={date} sort={sort} />
        <Link to="/word/new" className="btn btn-primary">+ 添加</Link>
      </div>

      <nav className="alphabet-nav" aria-label="按首字母筛选">
        {Array.from('abcdefghijklmnopqrstuvwxyz').map(l => {
          const has = availableLetters.includes(l)
          const active = letter === l
          const stateClass = active ? 'active' : has ? 'has-match' : 'empty'
          return (
            <button
              key={l}
              type="button"
              className={`alpha ${stateClass}`}
              onClick={() => (active || has) && toggleLetter(l)}
              disabled={!active && !has}
              title={
                active ? `清除首字母 ${l.toUpperCase()} 筛选`
                  : has ? `查看以 ${l.toUpperCase()} 开头的单词`
                  : `无 ${l.toUpperCase()} 开头的单词`
              }
            >
              {l}
            </button>
          )
        })}
      </nav>

      <EnrichProgress active={enriching} onComplete={handleEnrichComplete} />

      {error && <div className="empty-state"><p>{error}</p></div>}
      {!error && loading ? (
        <div className="loading">加载中…</div>
      ) : !error && words.length === 0 ? (
        <div className="empty-state">
          <svg className="empty-icon" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="6" width="28" height="36" rx="3" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M1314h18M13 20h18M13 26h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <circle cx="36" cy="36" r="9" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M3336h6M36 33v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <p>
            {q || date || letter
              ? `无匹配单词${letter ? `（首字母 ${letter.toUpperCase()}）` : ''}`
              : '还没有单词'}
          </p>
          {q || date || letter ? (
            <button className="btn btn-ghost" onClick={() => { setQ(''); setDate(''); setLetter('') }}>
              清除筛选
            </button>
          ) : (
            <Link to="/word/new">去添加第一个单词</Link>
          )}
        </div>
      ) : (
        <>
          {words.map((w, i) => <WordCard key={w.id} word={w} index={i} />)}
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
                    if (e.key === 'Enter') {
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
