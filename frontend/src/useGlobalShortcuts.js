import { useEffect } from 'react'

/**
 * 全局键盘快捷键。
 * - `/` 聚焦 searchInputRef.current（如果提供）
 * - `?` 切换帮助浮层（toggleHelp）
 * 输入框 / textarea 获得焦点时不触发，避免与文本编辑冲突。
 */
export function useGlobalShortcuts({ searchInputRef, toggleHelp }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.defaultPrevented || e.isComposing) return
      // 输入态不抢键
      const tag = e.target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable) {
        return
      }
      // 已经按了修饰键的不抢（让浏览器 / 其他组件处理）
      if (e.ctrlKey || e.metaKey || e.altKey) return

      if (e.key === '/') {
        if (!searchInputRef?.current) return
        e.preventDefault()
        searchInputRef?.current?.focus()
        searchInputRef?.current?.select?.()
      } else if (e.key === '?') {
        e.preventDefault()
        toggleHelp?.()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [searchInputRef, toggleHelp])
}
