import { useState, useRef, useCallback, useEffect } from 'react'
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom'
import SyncSettings from './pages/Settings'
import WordList from './pages/WordList'
import WordNew from './pages/WordNew'
import WordDetail from './pages/WordDetail'
import Review from './pages/Review'
import AppHeader from './components/AppHeader'
import ModelSettings from './pages/ModelSettings'
import { useGlobalShortcuts } from './useGlobalShortcuts'
import { useDueCount } from './useDueCount'
import HelpModal from './components/HelpModal'
import Notebooks from './pages/Notebooks'
import { readPrefillMessage, replyTarget, PREFILL_ACK_TYPE } from './lib/embedPrefill'

export default function App() {
  const location = useLocation()
  const dueCount = useDueCount()
  const [cloudVersion, setCloudVersion] = useState(0)
  useEffect(() => {
    const refresh = () => { setCloudVersion(v => v + 1); window.dispatchEvent(new Event('review-stats-changed')) }
    window.addEventListener('cloud-data-changed', refresh)
    return () => window.removeEventListener('cloud-data-changed', refresh)
  }, [])
  // Embedded in another page's iframe: the parent may prefill the add-word box
  // (see lib/embedPrefill.js). Saving still needs the user's confirmation.
  const navigate = useNavigate()
  useEffect(() => {
    if (window.parent === window) return undefined
    const onMessage = event => {
      const word = readPrefillMessage(event, window.parent)
      if (!word) return
      navigate('/word/new', { state: { prefillWord: word, prefillAt: Date.now() } })
      try { event.source.postMessage({ type: PREFILL_ACK_TYPE, word }, replyTarget(event.origin)) } catch { /* Parent page closed. */ }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [navigate])

  const searchInputRef = useRef(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const toggleHelp = useCallback(() => setHelpOpen(o => !o), [])

  useGlobalShortcuts({ searchInputRef, toggleHelp })

  return (
    <div className={`app${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <AppHeader dueCount={dueCount} onOpenHelp={() => setHelpOpen(true)} sidebarCollapsed={sidebarCollapsed} onToggleSidebar={() => setSidebarCollapsed(value => !value)} />
      <main className="app-main" id="main-content" tabIndex={-1}>
        <Routes key={location.pathname.startsWith('/word/') || ['/settings', '/sync-settings'].includes(location.pathname) ? location.pathname : cloudVersion}>
          <Route path="/" element={<WordList searchInputRef={searchInputRef} />} />
          <Route path="/notebooks" element={<Notebooks />} />
          <Route path="/word/new" element={<WordNew />} />
          <Route path="/word/:id" element={<WordDetail />} />
          <Route path="/sync-settings" element={<SyncSettings />} />
          <Route path="/settings" element={<ModelSettings />} />
          <Route path="/review" element={<Review />} />
        </Routes>
      </main>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
