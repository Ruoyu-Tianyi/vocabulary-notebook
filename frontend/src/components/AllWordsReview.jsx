import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { shuffle } from '../lib/shuffle'
import { getReviewShortcutAction } from '../lib/keyboard'
import { getGlobalShortcutAction } from '../lib/globalShortcuts'

export default function AllWordsReview({ words, notebookNames }) {
  const [order, setOrder] = useState('alpha')
  const [randomSeed, setRandomSeed] = useState(() => Math.floor(Math.random() * 0x100000000))
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState(false)
  const actionsRef = useRef(null)
  const cardRef = useRef(null)
  const completedRef = useRef(null)
  const restoreFocusRef = useRef(false)
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
    if (!restoreFocusRef.current) return
    restoreFocusRef.current = false
    const active = document.activeElement
    const inReview = active === document.body || cardRef.current?.contains(active) || actionsRef.current?.contains(active)
    if (!inReview || document.querySelector('[aria-modal="true"], dialog[open]')) return
    if (done) completedRef.current?.focus()
    else cardRef.current?.focus()
  }, [current, done])

  useEffect(() => {
    if (flipped) {
      const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
      actionsRef.current?.scrollIntoView({ behavior, block: 'nearest' })
    }
  }, [flipped])

  const goPrevious = useCallback(() => {
    if (index <= 0) return
    restoreFocusRef.current = true
    setIndex(previous => previous - 1)
    setFlipped(false)
  }, [index])

  const goNext = useCallback(() => {
    if (!flipped || !current) return
    restoreFocusRef.current = true
    if (index + 1 >= deck.length) {
      setDone(true)
      return
    }
    setIndex(previous => previous + 1)
    setFlipped(false)
  }, [current, deck.length, flipped, index])

  const restart = useCallback(() => {
    restoreFocusRef.current = true
    if (order === 'random') setRandomSeed(seed => seed + 1)
    setIndex(0)
    setFlipped(false)
    setDone(false)
  }, [order])

  useEffect(() => {
    function handleKey(event) {
      const action = getReviewShortcutAction(event, { mode: 'all', hasCard: Boolean(current), flipped, hasPrevious: index > 0, done })
      if (!action) return
      event.preventDefault()
      if (action.type === 'reveal') setFlipped(true)
      else if (action.type === 'previous') goPrevious()
      else if (action.type === 'next') goNext()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [current, done, flipped, goNext, goPrevious, index])

  if (done) {
    return (
      <section className="srs-done" aria-live="polite">
        <div className="srs-done-mark">✓</div>
        <h2>全部浏览完成</h2>
        <p>本轮共翻阅 {deck.length} 个单词，不影响每日复习计划。</p>
        <button type="button" className="btn btn-primary" ref={completedRef} onClick={restart}>
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
        <div className="order-switch" role="group" aria-label="单词顺序" onKeyDown={event => { if (!getGlobalShortcutAction(event)) event.stopPropagation() }}>
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
          第 {index + 1} / {deck.length} 个 · Space / Enter 显示答案 · ← 上一个 · → 下一个（先显示答案）
        </div>
      </div>
      {notebookNames && <div className="srs-progress" aria-live="polite">单词本：{notebookNames[current.notebook_id || 'default'] || '加载中…'}</div>}

      <button
        type="button"
        className="flashcard"
        ref={cardRef}
        data-review-shortcuts
        aria-keyshortcuts="Space Enter"
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
            <span className="flip-hint">点击或按 Space / Enter 显示答案</span>
          </span>
          <span className="flashcard-back" id={answerId} aria-hidden={!flipped}>
            <span className="word-display">{current.word}</span>
            {current.phonetic && <span className="phonetic-display">{current.phonetic}</span>}
            <span className="definition-display">{current.definition}</span>
            {current.example && <span className="example-display">“{current.example}”</span>}
          </span>
        </span>
      </button>

      <div ref={actionsRef} className="all-review-actions" data-review-shortcuts>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={goPrevious}
          aria-keyshortcuts="ArrowLeft"
          disabled={index === 0}
        >
          ← 上一个
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={goNext}
          aria-keyshortcuts="ArrowRight"
          disabled={!flipped}
        >
          {index + 1 >= deck.length ? '完成本轮' : '下一个 →'}
        </button>
      </div>
    </div>
  )
}
