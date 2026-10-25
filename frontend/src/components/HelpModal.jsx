import { useEffect, useRef } from 'react'

const SHORTCUTS = [
  { keys: ['/'], desc: '聚焦搜索框' },
  { keys: ['?'], desc: '显示 / 隐藏此帮助' },
  { keys: ['Esc'], desc: '关闭此帮助' },
]

/**
 * 全局键盘帮助浮层。点击遮罩或按 Esc / ? 关闭。
 */
export default function HelpModal({ open, onClose }) {
  const dialogRef = useRef(null)
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])

  function handleKey(event) {
    // 帮助层打开时，空格与评分快捷键不能传给背后的复习卡片。
    event.stopPropagation()
    if (event.key === 'Escape' || (event.key === '?' && !event.ctrlKey && !event.metaKey && !event.altKey)) {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab') return
    const controls = dialogRef.current?.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')
    if (!controls?.length) return
    const first = controls[0]
    const last = controls[controls.length - 1]
    if ((event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
      event.preventDefault()
      const nextControl = event.shiftKey ? last : first
      nextControl.focus()
    }
  }

  if (!open) return null

  return (
    <div className="help-modal-overlay" onClick={event => { if (event.target === event.currentTarget) onClose() }} onKeyDown={handleKey}>
      <div className="help-modal-content" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="keyboard-help-title">
        <button type="button" className="help-modal-close" ref={closeRef} onClick={onClose} aria-label="关闭快捷键帮助">×</button>
        <h2 className="help-modal-title" id="keyboard-help-title">键盘快捷键</h2>
        <ul className="shortcut-list">
          {SHORTCUTS.map((s, i) => (
            <li key={i}>
              <span className="shortcut-keys">
                {s.keys.map((k, j) => (
                  <kbd key={j}>{k}</kbd>
                ))}
              </span>
              <span className="shortcut-desc">{s.desc}</span>
            </li>
          ))}
        </ul>
        <p className="help-modal-hint">
          今日复习：空格翻面，数字 1–4 评分；全部单词：← → 切换
        </p>
      </div>
    </div>
  )
}
