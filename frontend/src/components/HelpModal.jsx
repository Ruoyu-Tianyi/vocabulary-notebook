import { useEffect, useRef } from 'react'
import { isShortcutEvent } from '../lib/keyboard'

const SHORTCUT_GROUPS = [
  {
    title: '通用与搜索',
    shortcuts: [
      { keys: ['/'], desc: '搜索单词', note: '返回单词列表，聚焦并选中搜索内容；保留已选单词本（如有）。' },
      { keys: ['N'], desc: '添加单词', note: '保留已选单词本（如有）。' },
      { keys: ['?'], desc: '打开或关闭快捷键帮助', note: '通常通过 Shift + / 输入问号；帮助内也可按 Esc 关闭。' },
      { keys: ['Esc'], desc: '清空搜索，再按一次移出焦点', note: '仅在单词列表的搜索框中生效。' },
    ],
  },
  {
    title: '今日复习',
    hint: '先显示答案，再按记忆程度评分。',
    shortcuts: [
      { keys: ['Space', 'Enter'], desc: '显示当前卡片的答案' },
      { keys: ['1'], desc: '重来' },
      { keys: ['2'], desc: '困难' },
      { keys: ['3'], desc: '良好' },
      { keys: ['4'], desc: '简单' },
    ],
  },
  {
    title: '全部单词',
    shortcuts: [
      { keys: ['Space', 'Enter'], desc: '显示当前卡片的答案' },
      { keys: ['←'], desc: '上一张', note: '有上一张卡片时可用。' },
      { keys: ['→'], desc: '下一张，或完成本轮', note: '先显示当前卡片的答案。' },
    ],
  },
  {
    title: '添加与编辑',
    shortcuts: [
      { keys: ['Enter'], desc: '保存单词', note: '在新增单词或编辑弹窗的文本输入框中。' },
      { keys: ['Esc'], desc: '返回或取消编辑', note: '新增页单词输入框中返回；编辑弹窗中取消，保存时不可取消。' },
    ],
  },
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
    if ((event.key === 'Escape' && isShortcutEvent(event)) ||
      (event.key === '?' && isShortcutEvent(event, { allowShift: true }))) {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab' || event.ctrlKey || event.metaKey || event.altKey) return
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
      <div className="help-modal-content" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="keyboard-help-title" aria-describedby="keyboard-help-scope">
        <button type="button" className="help-modal-close" ref={closeRef} onClick={onClose} aria-label="关闭快捷键帮助">×</button>
        <h2 className="help-modal-title" id="keyboard-help-title">键盘快捷键</h2>
        <p className="help-modal-intro">按使用场景查看按键和生效条件。</p>
        {SHORTCUT_GROUPS.map(group => (
          <section className="shortcut-section" key={group.title}>
            <h3>{group.title}</h3>
            {group.hint && <p className="shortcut-section-hint">{group.hint}</p>}
            <ul className="shortcut-list">
              {group.shortcuts.map(shortcut => (
                <li key={`${shortcut.keys.join('-')}-${shortcut.desc}`}>
                  <span className="shortcut-keys">
                    {shortcut.keys.map((key, index) => <span className="shortcut-key-option" key={key}>
                      {index > 0 && <span className="shortcut-key-separator">或</span>}
                      <kbd>{key === 'Space' ? '空格' : key}</kbd>
                    </span>)}
                  </span>
                  <span className="shortcut-desc">
                    {shortcut.desc}
                    {shortcut.note && <span className="shortcut-note">{shortcut.note}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <div className="help-modal-hint" id="keyboard-help-scope">
          <p>输入框、下拉框和可编辑区域内，不会触发导航或复习快捷键。弹窗打开时只操作当前弹窗；输入法确认或取消候选时，不会保存或退出编辑。</p>
          <p>按住快捷键不会连续触发；Ctrl / Cmd / Alt 组合键保留浏览器行为。</p>
          <p><kbd>Tab</kbd> / <kbd>Shift</kbd> + <kbd>Tab</kbd> 移动焦点；<kbd>Enter</kbd> 打开链接或激活按钮，<kbd>空格</kbd> 激活按钮。<kbd>Esc</kbd> 关闭当前菜单或弹窗。</p>
        </div>
      </div>
    </div>
  )
}
