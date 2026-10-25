import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { shuffle } from '../lib/shuffle'

export default function AllWordsReview({ words, notebookNames }) {
  const [order, setOrder] = useState('alpha')
  const [randomSeed, setRandomSeed] = useState(() => Math.floor(Math.random() * 0x100000000))
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState(false)
  const actionsRef = useRef(null)
  const answerId = useId()

  const deck = useMemo(() => {
    const alphabetic = [...words].sort((a, b) => a.word.localeCompare(b.word, 'en'))
    return order === 'random' ? shuffle(alphabetic, randomSeed) : alphabetic
  }, [order, randomSeed, words])

  useEffect(() => {
    setIndex(0)
    setFlipped(false)
    setDone(false)
  }, [deck])

  const current = deck[index]

  useEffect(() => {
    if (flipped) {
      const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
      actionsRef.current?.scrollIntoView({ behavior, block: 'nearest' })
    }
  }, [flipped])

  const goPrevious = useCallback(() => {
    if (index <= 0) return
    setIndex(previous => previous - 1)
    setFlipped(false)
  }, [index])

  const goNext = useCallback(() => {
    if (!flipped || !current) return
    if (index + 1 >= deck.length) {
      setDone(true)
      return
    }
    setIndex(previous => previous + 1)
    setFlipped(false)
  }, [current, deck.length, flipped, index])

  const restart = useCallback(() => {
    if (order === 'random') setRandomSeed(seed => seed + 1)
    setIndex(0)
    setFlipped(false)
    setDone(false)
  }, [order])

  useEffect(() => {
    function handleKey(event) {
      if (done || event.defaultPrevented || event.isComposing) return
      const tagName = event.target?.tagName
      if (['INPUT', 'TEXTAREA', 'SELECT', 'A', 'SUMMARY'].includes(tagName) || event.target?.isContentEditable) return
      if (event.ctrlKey || event.metaKey || event.altKey) return

      if ((event.key === ' ' || event.key === 'Enter') && current && !flipped) {
        if (tagName === 'BUTTON') return
        event.preventDefault()
        setFlipped(true)
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        goPrevious()
      } else if (event.key === 'ArrowRight' && flipped) {
        event.preventDefault()
        goNext()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [current, done, flipped, goNext, goPrevious])

  if (done) {
    return (
      <section className="srs-done" aria-live="polite">
        <div className="srs-done-mark">✓</div>
        <h2>全部浏览完成</h2>
        <p>本轮共翻阅 {deck.length} 个单词，不影响每日复习计划。</p>
        <button type="button" className="btn btn-primary" onClick={restart}>
          重新开始
        </button>
      </section>
    )
  }

  if (!current) return null

  function changeOrder(nextOrder) {
    // 排序变化与翻面状态必须在同一帧重置，避免新单词沿用旧卡背面。
    setIndex(0)
    setFlipped(false)
    setDone(false)
    if (nextOrder === 'random') setRandomSeed(seed => seed + 1)
    setOrder(nextOrder)
  }

  return (
    <div className="srs-container all-review-container">
      <div className="all-review-toolbar">
        <div className="order-switch" role="group" aria-label="单词顺序" onKeyDown={event => { if (!['/', '?'].includes(event.key)) event.stopPropagation() }}>
          <button
            type="button"
            aria-pressed={order === 'alpha'}
            className={order === 'alpha' ? 'active' : ''}
            onClick={() => changeOrder('alpha')}
          >
            A–Z 顺序
          </button>
          <button
            type="button"
            aria-pressed={order === 'random'}
            className={order === 'random' ? 'active' : ''}
            onClick={() => changeOrder('random')}
          >
            {order === 'random' ? '重新随机' : '随机顺序'}
          </button>
        </div>
        <div className="srs-progress">
          第 {index + 1} / {deck.length} 个 · 空格翻面 · ← → 切换
        </div>
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
          key={`${order}-${randomSeed}-${index}-${current.id}`}
          className={`flashcard-inner ${flipped ? 'flipped' : ''}`}
        >
          <span className="flashcard-front" aria-hidden={flipped}>
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

      <div ref={actionsRef} className="all-review-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={goPrevious}
          disabled={index === 0}
        >
          ← 上一个
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={goNext}
          disabled={!flipped}
        >
          {index + 1 >= deck.length ? '完成本轮' : '下一个 →'}
        </button>
      </div>
    </div>
  )
}
