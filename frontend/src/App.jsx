import { useState, useRef, useCallback, useEffect } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import WordList from './pages/WordList'
import WordNew from './pages/WordNew'
import WordDetail from './pages/WordDetail'
import Review from './pages/Review'
import ThemeToggle from './components/ThemeToggle'
import ModelStatus from './components/ModelStatus'
import { useGlobalShortcuts } from './useGlobalShortcuts'
import { useDueCount } from './useDueCount'
import HelpModal from './components/HelpModal'
import CloudStatus from './components/CloudStatus'
import Settings from './pages/Settings'
import { BookPicker, useBooks } from './Books'

export default function App() {
  const location = useLocation()
  const { active } = useBooks()
  const dueCount = useDueCount(active)
  const [cloudVersion, setCloudVersion] = useState(0)
  useEffect(() => {
    const refresh = () => { setCloudVersion(v => v + 1); window.dispatchEvent(new Event('review-stats-changed')) }
    window.addEventListener('cloud-data-changed', refresh)
    return () => window.removeEventListener('cloud-data-changed', refresh)
  }, [])
  const searchInputRef = useRef(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const toggleHelp = useCallback(() => setHelpOpen(o => !o), [])

  useGlobalShortcuts({ searchInputRef, toggleHelp })
  const listActive = location.pathname === '/' || (location.pathname.startsWith('/word/') && location.pathname !== '/word/new')

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <h1 className="app-title">
            <Link to="/">云端词汇本</Link>
          </h1>
          <p className="app-tagline">记录新词，积累知识。</p>
        </div>
        <div className="app-utilities">
          <Link to="/settings" aria-current={location.pathname === '/settings' ? 'page' : undefined}>同步与备份</Link>
          <ThemeToggle />
        </div>
      </header>
      <nav className="app-nav" aria-label="主要功能">
          <Link to="/" className={listActive ? 'active' : ''} aria-current={listActive ? 'page' : undefined}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></svg>
            <span>单词列表</span>
          </Link>
          <Link to="/word/new" className={location.pathname === '/word/new' ? 'active' : ''} aria-current={location.pathname === '/word/new' ? 'page' : undefined}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3" /><path d="M12 7v10M7 12h10" /></svg>
            <span>添加单词</span>
          </Link>
          <Link to="/review" className={location.pathname === '/review' ? 'active' : ''} aria-current={location.pathname === '/review' ? 'page' : undefined}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 10a8 8 0 1 1 1 7M4 4v6h6" /><path d="M12 7v5l3 2" /></svg>
            <span>复习</span> {dueCount > 0 && <span className="nav-badge" aria-label={`${dueCount} 个单词待复习`}>{dueCount}</span>}
          </Link>
      </nav>
      <div className="library-statusbar" role="group" aria-label="当前单词本与连接状态">
        <BookPicker />
        <div className="status-services"><ModelStatus /><CloudStatus /></div>
      </div>
      <main className="app-main">
        <Routes key={location.pathname === '/settings' ? 'settings' : location.pathname === '/word/new' ? `add:${active}` : location.pathname.startsWith('/word/') ? location.pathname : `${active}:${cloudVersion}`}>
          <Route path="/" element={<WordList searchInputRef={searchInputRef} />} />
          <Route path="/word/new" element={<WordNew />} />
          <Route path="/word/:id" element={<WordDetail />} />
          <Route path="/review" element={<Review />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <footer className="app-footer">基于 <a href="https://github.com/Eric-Zhou-0302/vocabulary-notebook" target="_blank" rel="noreferrer">Eric Zhou / Vocabulary Notebook</a> 开发 · MIT</footer>
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  )
}
