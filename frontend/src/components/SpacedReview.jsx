import { useCallback, useEffect, useId, useRef, useState } from 'react'

const RATINGS = [
  { value: 1, label: '重来', className: 'rating-again' },
  { value: 2, label: '困难', className: 'rating-hard' },
  { value: 3, label: '良好', className: 'rating-good' },
  { value: 4, label: '简单', className: 'rating-easy' },
]

export default function SpacedReview({ cards, onRate, onReload, notebookNames }) {
  const [queue, setQueue] = useState([])
  const [flipped, setFlipped] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [summary, setSummary] = useState({ ratings: 0, newWords: 0, again: 0 })
  const ratingGridRef = useRef(null)
  const answerId = useId()

  useEffect(() => {
    setQueue(cards)
    setFlipped(false)
    setSubmitting(false)
    setDone(false)
    setSummary({ ratings: 0, newWords: 0, again: 0 })
  }, [cards])

  const current = queue[0]

  useEffect(() => {
    if (flipped) {
      const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
      ratingGridRef.current?.scrollIntoView({ behavior, block: 'nearest' })
    }
  }, [flipped])

  const handleRate = useCallback(async rating => {
    if (!current || !flipped || submitting) return
    setSubmitting(true)
    try {
      const result = await onRate(current.id, rating)
      const rest = queue.slice(1)
      // 使用服务端返回的最新卡片状态，避免“重来”后沿用旧间隔预览。
      if (rating === 1) rest.push(result.card)
      setQueue(rest)
      setSummary(previous => ({
        ratings: previous.ratings + 1,
        newWords: previous.newWords + (current.is_new ? 1 : 0),
        again: previous.again + (rating === 1 ? 1 : 0),
      }))
      setFlipped(false)
      if (rest.length === 0) setDone(true)
    } catch {
      // 父组件负责展示错误；卡片留在原位，允许用户重试。
      return
    } finally {
      setSubmitting(false)
    }
  }, [current, flipped, onRate, queue, submitting])

  useEffect(() => {
    function handleKey(event) {
      if (done || event.defaultPrevented || event.isComposing) return
      const tagName = event.target?.tagName
      if (['INPUT', 'TEXTAREA', 'BUTTON', 'SELECT', 'A', 'SUMMARY'].includes(tagName) || event.target?.isContentEditable) return
      if (event.ctrlKey || event.metaKey || event.altKey) return

      if ((event.key === ' ' || event.key === 'Enter') && current && !flipped) {
        event.preventDefault()
        setFlipped(true)
      } else if (flipped && ['1', '2', '3', '4'].includes(event.key)) {
        event.preventDefault()
        handleRate(Number(event.key))
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [current, done, flipped, handleRate])

  if (done) {
    return (
      <section className="srs-done" aria-live="polite">
        <div className="srs-done-mark">✓</div>
        <h2>本轮完成</h2>
        <p>
          共完成 {summary.ratings} 次评分
          {summary.newWords > 0 && ` · 新学 ${summary.newWords} 个`}
          {summary.again > 0 && ` · 重来 ${summary.again} 次`}
        </p>
        <button type="button" className="btn btn-primary" onClick={onReload}>
          查看下一批
        </button>
      </section>
    )
  }

  if (!current) return null

  return (
    <div className="srs-container">
      <div className="srs-progress" aria-live="polite">
        本轮剩余 {queue.length} 张 · 空格翻面 · 1–4 评分
      </div>
      {notebookNames && <div className="srs-progress" aria-live="polite">单词本：{notebookNames[current.notebook_id || 'default'] || '加载中…'}</div>}

      <button
        type="button"
        className="flashcard"
        onClick={() => !flipped && setFlipped(true)}
        aria-label={flipped ? `${current.word}，答案已展开` : `单词 ${current.word}，点击查看释义`}
        aria-describedby={flipped ? answerId : undefined}
        aria-pressed={flipped}
      >
        <span
          key={`${current.id}-${current.srs?.reps ?? 0}`}
          className={`flashcard-inner ${flipped ? 'flipped' : ''}`}
        >
          <span className="flashcard-front" aria-hidden={flipped}>
            {current.is_new && <span className="card-kicker">新词</span>}
            <span className="word-display">{current.word}</span>
            {current.phonetic && <span className="phonetic-display">{current.phonetic}</span>}
            <span className="flip-hint">点击或按空格查看答案</span>
          </span>
          <span className="flashcard-back" id={answerId} aria-hidden={!flipped}>
            <span className="word-display">{current.word}</span>
            {current.phonetic && <span className="phonetic-display">{current.phonetic}</span>}
            <span className="definition-display">{current.definition}</span>
            {current.example && <span className="example-display">“{current.example}”</span>}
          </span>
        </span>
      </button>

      <div
        ref={ratingGridRef}
        className={`srs-rating-grid ${flipped ? 'visible' : ''}`}
        aria-hidden={!flipped}
      >
        {RATINGS.map(rating => (
          <button
            key={rating.value}
            type="button"
            className={`srs-rating-btn ${rating.className}`}
            onClick={() => handleRate(rating.value)}
            disabled={!flipped || submitting}
          >
            <span className="rating-label">{rating.value} · {rating.label}</span>
            <span className="rating-interval">
              {current.predicted_intervals?.[String(rating.value)] || '—'}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
