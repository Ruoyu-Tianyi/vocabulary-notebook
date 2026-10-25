import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import ModelStatus from './ModelStatus'
import CloudStatus from './CloudStatus'
import ThemeToggle from './ThemeToggle'
import NavigationIcon from './NavigationIcon'

export default function AppHeader({ remote, dueCount, onOpenHelp, sidebarCollapsed, onToggleSidebar }) {
  const location = useLocation()
  const detailsRef = useRef(null)
  const summaryRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [modelProblem, setModelProblem] = useState(false)
  const [syncProblem, setSyncProblem] = useState(false)
  const isSettings = ['/settings', '/sync-settings'].includes(location.pathname)
  const adding = location.pathname === '/word/new'
  const notebookId = new URLSearchParams(location.search).get('notebook_id')
  const notebookQuery = notebookId ? `?${new URLSearchParams({ notebook_id: notebookId })}` : ''
  const inWords = location.pathname === '/' || (location.pathname.startsWith('/word/') && !adding)
  const hasProblem = modelProblem || syncProblem
  const problemLabel = [modelProblem && '模型连接需检查', syncProblem && '云端同步需检查'].filter(Boolean).join('，')

  function closeTools(restoreFocus = false) {
    if (detailsRef.current) detailsRef.current.open = false
    setOpen(false)
    if (restoreFocus) summaryRef.current?.focus()
  }

  useEffect(() => { closeTools() }, [location.pathname, location.search])

  useEffect(() => {
    if (!open) return
    function dismiss(event) {
      if (!detailsRef.current?.contains(event.target)) closeTools()
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('focusin', dismiss)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('focusin', dismiss)
    }
  }, [open])

  const links = [
    { to: '/', label: '单词列表', icon: 'words', active: inWords },
    { to: '/notebooks', label: '单词本', icon: 'notebooks', active: location.pathname === '/notebooks' },
    { to: `/review${notebookQuery}`, label: '复习', icon: 'review', active: location.pathname === '/review', badge: dueCount },
  ]

  return <header className="app-header" onKeyDown={event => {
    // 保留搜索和帮助快捷键，其余按键只操作导航，不传给背后的复习卡片。
    if (event.key === '/') return
    event.stopPropagation()
    if (event.key === 'Escape' && open) { event.preventDefault(); closeTools(true) }
    if (event.key === '?' && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault()
      closeTools(open)
      onOpenHelp()
    }
  }}>
    <button type="button" className="sidebar-toggle" aria-label={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'} title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'} aria-expanded={!sidebarCollapsed} aria-controls="learning-navigation" onClick={onToggleSidebar}>
      <NavigationIcon name={sidebarCollapsed ? 'expand' : 'collapse'} />
    </button>
    <div className="header-topline">
      <h1 className="app-title"><Link to="/" aria-label="词汇笔记本"><span className="brand-mark"><NavigationIcon name="words" /></span><span>词汇笔记本<span className="brand-caption">VOCABULARY NOTEBOOK</span></span></Link></h1>
      <details className={`header-tools${isSettings ? ' is-current' : ''}`} ref={detailsRef}
        onToggle={event => setOpen(event.currentTarget.open)}>
        <summary className="header-tools-trigger" ref={summaryRef} aria-expanded={open} aria-controls="header-tools-panel"
          aria-label={`设置与工具${hasProblem ? `，${problemLabel}` : ''}`} title={sidebarCollapsed ? '设置与工具' : undefined}>
          <NavigationIcon name="settings" />
          <span>设置与工具</span>
          {hasProblem && <span className="header-attention" aria-hidden="true" />}
          <NavigationIcon name="chevron" className="header-tools-chevron" />
        </summary>
        <div className="header-tools-panel" id="header-tools-panel">
          <div className="header-tools-heading">设置与工具<span>连接与偏好</span></div>
          <nav aria-label="应用设置" onClick={event => { if (event.target.closest('a')) closeTools() }}>
            {!remote && <ModelStatus onProblemChange={setModelProblem} />}
            {!remote && <CloudStatus onProblemChange={setSyncProblem} />}
            {remote && <><p>私人学习 · 数据保存在你的电脑</p><form method="post" action="/logout"><button type="submit" className="utility-item">退出登录</button></form></>}
          </nav>
          <div className="header-tools-preferences">
            <ThemeToggle />
            <button type="button" className="utility-item" onClick={() => { closeTools(true); onOpenHelp() }}>
              <NavigationIcon name="keyboard" />
              <span className="utility-copy"><span className="utility-title">键盘快捷键</span><span className="utility-description">搜索、翻卡与评分</span></span>
              <kbd>?</kbd>
            </button>
          </div>
        </div>
      </details>
    </div>
    <div className="header-navigation" id="learning-navigation">
      <p className="navigation-label">学习空间</p>
      <nav className="app-nav" aria-label="学习导航">
        {links.map(link => <Link key={link.icon} to={link.to} className={`primary-nav-link${link.active ? ' active' : ''}`}
          aria-current={link.active ? 'page' : undefined}
          title={sidebarCollapsed ? link.label : undefined}
          aria-label={link.badge > 0 ? `${link.label}，全部单词本共 ${link.badge} 个待复习` : link.label}>
          <NavigationIcon name={link.icon} />
          <span>{link.label}</span>
          {link.badge > 0 && <span className="nav-badge" aria-hidden="true">{link.badge > 99 ? '99+' : link.badge}</span>}
        </Link>)}
      </nav>
      <Link to={`/word/new${notebookQuery}`} className={`header-add${adding ? ' active' : ''}`} aria-label="添加单词" title={sidebarCollapsed ? '添加单词' : undefined} aria-current={adding ? 'page' : undefined}>
        <NavigationIcon name="plus" /><span>添加单词</span>
      </Link>
    </div>
  </header>
}
