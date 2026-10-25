import { useState, useRef, useCallback, useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
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
  const searchInputRef = useRef(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const toggleHelp = useCallback(() => setHelpOpen(o => !o), [])

  useGlobalShortcuts({ searchInputRef, toggleHelp })

  return (
    <div className={`app${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <AppHeader remote={remote} dueCount={dueCount} onOpenHelp={() => setHelpOpen(true)} sidebarCollapsed={sidebarCollapsed} onToggleSidebar={() => setSidebarCollapsed(value => !value)} />
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
