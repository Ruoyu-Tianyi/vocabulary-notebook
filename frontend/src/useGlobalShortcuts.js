import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getGlobalShortcutAction, shortcutDestination } from './lib/globalShortcuts'

/**
 * 全局键盘快捷键。
 * 跨页搜索等待列表挂载后再聚焦，避免快捷键只在列表页有效。
 */
export function useGlobalShortcuts({ searchInputRef, toggleHelp }) {
  const location = useLocation()
  const navigate = useNavigate()
  const pendingSearch = useRef(false)

  useEffect(() => {
    if (!pendingSearch.current || location.pathname !== '/' || !searchInputRef.current) return
    pendingSearch.current = false
    searchInputRef.current.focus()
    searchInputRef.current.select()
  }, [location.pathname, location.search, searchInputRef])

  useEffect(() => {
    function handleKey(event) {
      const action = getGlobalShortcutAction(event)
      // 保存中禁用字段可能使焦点回到 body，弹窗仍应隔离页面操作。
      if (!action || document.querySelector('[aria-modal="true"], dialog[open]')) return
      event.preventDefault()
      if (action === 'help') {
        toggleHelp()
      } else if (action === 'search') {
        if (searchInputRef.current) {
          searchInputRef.current.focus()
          searchInputRef.current.select()
        } else {
          pendingSearch.current = true
          navigate(shortcutDestination(action, location.search))
        }
      } else if (location.pathname === '/word/new') {
        document.getElementById('new-word')?.focus()
      } else {
        navigate(shortcutDestination(action, location.search))
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [location.pathname, location.search, navigate, searchInputRef, toggleHelp])
}
