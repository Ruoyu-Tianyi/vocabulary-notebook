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
  const [remote, setRemote] = useState(true)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/access-mode', { signal: controller.signal }).then(r => r.status === 401 ? (window.location.replace('/login'), Promise.reject()) : r.ok ? r.json() : Promise.reject()).then(data => setRemote(data.remote !== false)).catch(() => {})
    return () => controller.abort()
  }, [])
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
  const toggleHelp = useCallback(() => setHelpOpen(o => !o), [])

  useGlobalShortcuts({ searchInputRef, toggleHelp })

  return (
    <div className="app top-navigation-app">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <AppHeader remote={remote} dueCount={dueCount} onOpenHelp={() => setHelpOpen(true)} />
      <main className="app-main" id="main-content" tabIndex={-1}>
        <Routes key={location.pathname.startsWith('/word/') || ['/settings', '/sync-settings'].includes(location.pathname) ? location.pathname : cloudVersion}>
          <Route path="/" element={<WordList searchInputRef={searchInputRef} />} />
          <Route path="/notebooks" element={<Notebooks />} />
          <Route path="/word/new" element={<WordNew />} />
          <Route path="/word/:id" element={<WordDetail />} />
          <Route path="/sync-settings" element={remote ? <p>同步设置请在服务器电脑上管理。</p> : <SyncSettings />} />
          <Route path="/settings" element={remote ? <p>模型设置请在服务器电脑上管理。</p> : <ModelSettings />} />
          <Route path="/review" element={<Review />} />
        </Routes>
      </main>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
