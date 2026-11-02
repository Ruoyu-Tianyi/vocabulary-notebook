import { useEffect, useRef, useState } from 'react'

const REPO_URL = 'https://github.com/Eric-Zhou-0302/vocove'
const RELEASE_VERSION = '1.5.1'
const RELEASE_URL = `${REPO_URL}/releases/tag/v${RELEASE_VERSION}`
const DOWNLOAD_BASE_URL = `${REPO_URL}/releases/download/v${RELEASE_VERSION}`
const DOWNLOAD_URLS = {
  macArm: `${DOWNLOAD_BASE_URL}/Vocove-${RELEASE_VERSION}-mac-arm64.dmg`,
  macIntel: `${DOWNLOAD_BASE_URL}/Vocove-${RELEASE_VERSION}-mac-x64.dmg`,
  windows: `${DOWNLOAD_BASE_URL}/Vocove-${RELEASE_VERSION}-win-x64.exe`,
}
const ISSUE_URL = `${REPO_URL}/issues/new/choose`

function Icon({ name, size = 20, className = '' }) {
  const icons = {
    arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
    arrowUp: <><path d="M7 17 17 7"/><path d="M7 7h10v10"/></>,
    download: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    github: <path d="M15 22v-3.9c.04-1-.35-1.96-1.1-2.6 3.6-.4 7.1-1.8 7.1-7.4 0-1.6-.6-2.9-1.5-4 .2-.4.7-1.9-.1-3.9 0 0-1.2-.4-4.1 1.5a14 14 0 0 0-7.5 0C4.9-.2 3.7.2 3.7.2c-.8 2-.3 3.5-.1 3.9-.9 1.1-1.5 2.4-1.5 4 0 5.6 3.5 7 7.1 7.4-.7.6-1.1 1.5-1.2 2.5V22M8 19c-3 .9-3-1.5-4-2"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    plus: <><path d="M12 5v14"/><path d="M5 12h14"/></>,
    spark: <><path d="m12 3-1.6 4.4L6 9l4.4 1.6L12 15l1.6-4.4L18 9l-4.4-1.6L12 3Z"/><path d="m5 16-.8 2.2L2 19l2.2.8L5 22l.8-2.2L8 19l-2.2-.8L5 16Z"/><path d="m19 14-.8 2.2L16 17l2.2.8L19 20l.8-2.2L22 17l-2.2-.8L19 14Z"/></>,
    layers: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></>,
    review: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    cloud: <path d="M17.5 19H6a4 4 0 0 1-.5-8 6.5 6.5 0 0 1 12.4-1.6A4.8 4.8 0 0 1 17.5 19Z"/>,
    keyboard: <><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M10 13h.01M14 13h.01M18 13h.01M8 16h8"/></>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    folder: <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
    apple: <><path d="M16.7 13.1c0-2.2 1.8-3.3 1.9-3.4-1-1.5-2.6-1.7-3.2-1.7-1.4-.1-2.7.8-3.4.8-.7 0-1.8-.8-3-.8-1.5 0-3 .9-3.8 2.3-1.6 2.8-.4 7 1.2 9.3.8 1.1 1.7 2.4 2.9 2.4 1.2-.1 1.6-.8 3-.8s1.8.8 3 .8c1.2 0 2-1.1 2.8-2.3.9-1.3 1.2-2.5 1.2-2.6-.1 0-2.6-1-2.6-4Z"/><path d="M14.2 6.1c.6-.8 1.1-1.9 1-3.1-1 0-2.2.7-2.9 1.5-.6.7-1.2 1.9-1 3 1.1.1 2.2-.6 2.9-1.4Z"/></>,
    windows: <><path d="m3 5 8-1v8H3V5ZM13 3.8 21 3v9h-8V3.8ZM3 14h8v8l-8-1v-7ZM13 14h8v9l-8-1v-8Z"/></>,
  }

  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {icons[name]}
    </svg>
  )
}

function Brand({ light = false }) {
  return (
    <a className={`brand ${light ? 'brand--light' : ''}`} href="#top" aria-label="Vocove 首页">
      <img src="/vocove-icon.png" alt="" width="38" height="38" />
      <span>Vocove</span>
    </a>
  )
}

const NAV_ITEMS = [
  { id: 'how', label: '学习流程' },
  { id: 'features', label: '产品功能' },
  { id: 'local', label: '本地优先' },
  { id: 'faq', label: '常见问题' },
]

function Header() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [activeSection, setActiveSection] = useState('')
  const navRef = useRef(null)
  const toggleRef = useRef(null)

  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      setScrolled(window.scrollY > 24)
      const probe = window.scrollY + window.innerHeight * 0.38
      let current = ''
      NAV_ITEMS.forEach(({ id }) => {
        const section = document.getElementById(id)
        if (section && section.offsetTop <= probe) current = id
      })
      setActiveSection(current)
    }
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  useEffect(() => {
    document.body.classList.toggle('menu-open', menuOpen)
    if (!menuOpen) return () => document.body.classList.remove('menu-open')

    navRef.current?.querySelector('a')?.focus({ preventScroll: true })
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        toggleRef.current?.focus()
      }
    }
    const onResize = () => {
      if (window.innerWidth > 860) setMenuOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('resize', onResize)
    return () => {
      document.body.classList.remove('menu-open')
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('resize', onResize)
    }
  }, [menuOpen])

  const closeMenu = () => setMenuOpen(false)

  return (
    <header className={`site-header ${scrolled ? 'is-scrolled' : ''}`}>
      <div className="header-inner">
        <Brand light />
        <nav ref={navRef} className={`main-nav ${menuOpen ? 'is-open' : ''}`} aria-label="主导航">
          {NAV_ITEMS.map(({ id, label }) => (
            <a className={activeSection === id ? 'is-active' : ''} href={`#${id}`} aria-current={activeSection === id ? 'location' : undefined} key={id} onClick={closeMenu}>{label}</a>
          ))}
          <a className="nav-github" href={REPO_URL} target="_blank" rel="noreferrer" onClick={closeMenu}>
            GitHub <Icon name="arrowUp" size={14} />
          </a>
        </nav>
        <a className="header-download" href="#download">下载 Vocove <Icon name="download" size={16} /></a>
        <button ref={toggleRef} className="menu-toggle" type="button" aria-label={menuOpen ? '关闭菜单' : '打开菜单'} aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>
          <Icon name={menuOpen ? 'close' : 'menu'} size={24} />
        </button>
      </div>
    </header>
  )
}

function WordCardDemo({ compact = false }) {
  const [flipped, setFlipped] = useState(false)
  const [rating, setRating] = useState('')

  const chooseRating = (value) => {
    setRating(value)
    setFlipped(true)
  }

  return (
    <div className={`word-demo ${compact ? 'word-demo--compact' : ''}`}>
      <div className="word-demo-meta">
        <span><span className="status-dot" /> 今日复习</span>
        <span>08 / 20</span>
      </div>
      <div className={`word-card ${flipped ? 'is-flipped' : ''}`}>
        <div className="word-card-inner">
          <div className="word-card-face word-card-front" aria-hidden={flipped}>
            <div className="word-card-top">
              <span className="wordbook-chip">阅读拾遗</span>
              <span className="word-type">noun</span>
            </div>
            <div className="word-main">
              <p className="word-spelling">serendipity</p>
              <p className="word-phonetic">/ˌserənˈdɪpəti/</p>
              <p className="word-prompt">先在心里回忆，再翻开答案</p>
            </div>
            <button className="reveal-button" type="button" tabIndex={flipped ? -1 : 0} onClick={() => setFlipped(true)}>
              显示释义 <kbd>Space</kbd>
            </button>
          </div>
          <div className="word-card-face word-card-back" aria-hidden={!flipped}>
            <div className="word-card-top">
              <span className="wordbook-chip">阅读拾遗</span>
              <span className="word-type">noun</span>
            </div>
            <div className="word-main">
              <p className="word-spelling">serendipity</p>
              <p className="word-phonetic">/ˌserənˈdɪpəti/</p>
              <div className="word-answer">
                <p className="word-definition">意外发现美好事物的能力；机缘巧合</p>
                <p className="word-example">“Meeting her was pure serendipity.”</p>
                <p className="word-translation">与她的相遇，纯粹是一场美好的巧合。</p>
              </div>
            </div>
            {rating ? (
              <button className="rating-confirm" type="button" tabIndex={flipped ? 0 : -1} onClick={() => { setRating(''); setFlipped(false) }} aria-live="polite">
                <Icon name="check" size={17} /> 已选择「{rating}」· 再试一次
              </button>
            ) : (
              <div className="rating-row" aria-label="记忆评分">
                {['重来', '困难', '良好', '简单'].map((item, index) => (
                  <button type="button" tabIndex={flipped ? 0 : -1} key={item} onClick={() => chooseRating(item)}>
                    <span>{item}</span><kbd>{index + 1}</kbd>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      <p className="demo-caption"><span /> 可交互界面示意，试试翻开这张卡片</p>
    </div>
  )
}

function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero-orbit hero-orbit--one" />
      <div className="hero-orbit hero-orbit--two" />
      <div className="hero-grain" />
      <div className="container hero-grid">
        <div className="hero-copy" data-reveal>
          <div className="eyebrow eyebrow--gold"><span /> LOCAL-FIRST · BUILT FOR MEMORY</div>
          <h1>让单词，<br />真正<em>留下来。</em></h1>
          <p className="hero-lead">把阅读中遇到的词，交给 AI 补全理解，<br className="desktop-break" />再用科学的间隔复习，慢慢变成自己的词汇。</p>
          <div className="hero-actions">
            <a className="button button--gold" href="#download">免费下载 Vocove <Icon name="download" size={18} /></a>
            <a className="text-link text-link--light" href={REPO_URL} target="_blank" rel="noreferrer">
              <Icon name="github" size={19} /> 在 GitHub 查看 <Icon name="arrowUp" size={15} />
            </a>
          </div>
          <div className="hero-assurances" aria-label="产品特点">
            <span><Icon name="check" size={14} /> 免费开源</span>
            <span><Icon name="check" size={14} /> macOS & Windows</span>
            <span><Icon name="check" size={14} /> 数据保存在本机</span>
          </div>
        </div>
        <div className="hero-product" data-reveal>
          <div className="floating-word floating-word--one">vocabulary</div>
          <div className="floating-word floating-word--two">memory</div>
          <div className="product-window">
            <div className="window-bar">
              <div className="window-dots"><span /><span /><span /></div>
              <span>Vocove</span>
              <span className="window-version">v{RELEASE_VERSION}</span>
            </div>
            <div className="window-content">
              <aside className="demo-sidebar" aria-hidden="true">
                <img src="/vocove-icon.png" alt="" />
                <span className="side-line side-line--active" />
                <span className="side-line" />
                <span className="side-line side-line--short" />
                <div className="side-spacer" />
                <span className="side-square" />
              </aside>
              <WordCardDemo />
            </div>
          </div>
          <div className="memory-note">
            <span className="memory-note-icon"><Icon name="review" size={19} /></span>
            <span><strong>恰逢其时的复习</strong><small>由 FSRS 间隔算法安排</small></span>
          </div>
        </div>
      </div>
      <div className="hero-scroll"><span>向下探索</span><i /></div>
    </section>
  )
}

const flowSteps = [
  { number: '01', title: '随手记录', subtitle: 'Capture', description: '遇到生词就记下，按主题放入不同单词本。同一个词可以属于多本，各自保留学习进度。' },
  { number: '02', title: '补全理解', subtitle: 'Enrich', description: '接入本地 Ollama 或云端模型，补全音标、中文释义与例句。v1.5.0 支持 15 个供应商及自定义 API。' },
  { number: '03', title: '适时复习', subtitle: 'Remember', description: '先回忆，再翻面评分。FSRS 根据你的反馈安排下一次复习，把精力留给真正需要巩固的词。' },
]

function FlowVisual({ active }) {
  if (active === 0) {
    return (
      <div className="flow-panel capture-panel">
        <div className="flow-panel-header"><span>添加单词</span><span className="small-muted">N</span></div>
        <div className="capture-body">
          <label>单词或短语</label>
          <div className="fake-input fake-input--word">serendipity <span className="typing-caret" /></div>
          <label>加入单词本</label>
          <div className="notebook-select"><span><Icon name="folder" size={17} /> 阅读拾遗</span><span>⌄</span></div>
          <div className="capture-note"><Icon name="spark" size={16} /> 保存后可自动补全音标、释义与例句</div>
          <div className="fake-primary-button"><Icon name="plus" size={16} /> 保存单词</div>
        </div>
      </div>
    )
  }

  if (active === 1) {
    return (
      <div className="flow-panel enrich-panel">
        <div className="flow-panel-header"><span>AI 内容补全</span><span className="complete-chip"><Icon name="check" size={13} /> 已完成</span></div>
        <div className="enrich-word"><strong>serendipity</strong><span>/ˌserənˈdɪpəti/</span></div>
        <div className="enrich-field"><span>中文释义</span><p>意外发现美好事物的能力；机缘巧合</p></div>
        <div className="enrich-field"><span>例句</span><p>Meeting her was pure serendipity.</p><small>与她的相遇，纯粹是一场美好的巧合。</small></div>
        <div className="model-row"><span><i /> Ollama</span><span><i /> DeepSeek</span><small>v1.5.0 · 15 个供应商 + 自定义 API</small></div>
      </div>
    )
  }

  return <div className="flow-review"><WordCardDemo compact /></div>
}

function HowItWorks() {
  const [active, setActive] = useState(0)
  const gridRef = useRef(null)
  const stepRefs = useRef([])

  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      if (window.innerWidth <= 860 || !gridRef.current) return
      const bounds = gridRef.current.getBoundingClientRect()
      if (bounds.bottom < 80 || bounds.top > window.innerHeight * 0.85) return
      const target = window.innerHeight * 0.48
      let closest = 0
      let distance = Number.POSITIVE_INFINITY
      stepRefs.current.forEach((step, index) => {
        if (!step) return
        const rect = step.getBoundingClientRect()
        const nextDistance = Math.abs(rect.top + rect.height * 0.45 - target)
        if (nextDistance < distance) {
          distance = nextDistance
          closest = index
        }
      })
      setActive((current) => current === closest ? current : closest)
    }
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  const selectStep = (index, moveFocus = false) => {
    setActive(index)
    const step = stepRefs.current[index]
    if (window.innerWidth > 860) {
      step?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
    }
    if (moveFocus) step?.focus({ preventScroll: true })
  }

  const onStepKeyDown = (event, index) => {
    let next
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % flowSteps.length
    if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + flowSteps.length) % flowSteps.length
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = flowSteps.length - 1
    if (next === undefined) return
    event.preventDefault()
    selectStep(next, true)
  }

  return (
    <section className="section how-section" id="how">
      <div className="container">
        <div className="section-heading" data-reveal>
          <div><div className="eyebrow"><span /> A QUIET LEARNING RITUAL</div><h2>从遇见，到记住。<br />只需三个自然步骤。</h2></div>
          <p>不追求一天塞进多少词，<br />而是让每一次学习都有下文。</p>
        </div>
        <div className="flow-grid" data-reveal ref={gridRef}>
          <div className="flow-steps" role="tablist" aria-label="学习流程">
            {flowSteps.map((step, index) => (
              <button className={`flow-step ${active === index ? 'is-active' : ''}`} type="button" role="tab" id={`flow-tab-${index}`} aria-controls="flow-panel" aria-selected={active === index} tabIndex={active === index ? 0 : -1} key={step.number} ref={(element) => { stepRefs.current[index] = element }} onClick={() => selectStep(index)} onKeyDown={(event) => onStepKeyDown(event, index)}>
                <span className="flow-number">{step.number}</span>
                <span className="flow-step-copy"><small>{step.subtitle}</small><strong>{step.title}</strong><span>{step.description}</span></span>
                <span className="flow-chevron"><Icon name="chevron" size={18} /></span>
              </button>
            ))}
          </div>
          <div className="flow-stage" id="flow-panel" role="tabpanel" aria-labelledby={`flow-tab-${active}`}>
            <div className="stage-index">0{active + 1} <span>/ 03</span></div>
            <div className="flow-visual" key={active}><FlowVisual active={active} /></div>
            <div className="stage-progress" aria-hidden="true">{flowSteps.map((step, index) => <span className={index === active ? 'is-active' : ''} key={step.number} />)}</div>
          </div>
        </div>
      </div>
    </section>
  )
}

const features = [
  { id: 'ai', icon: 'spark', title: 'AI 补全，不停留在一个中文释义', text: '音标、释义与例句一次补齐。v1.5.0 支持 Ollama、DeepSeek、OpenAI、Claude 等 15 个供应商及自定义 API，可获取模型目录、手动添加模型并测试连接。' },
  { id: 'notebooks', icon: 'layers', title: '同一个词，读懂不同语境', text: '分类本用于日常整理，金融、法律、医药语境本优先生成专业释义与例句。同词可加入多本，内容与复习进度各自独立。' },
  { id: 'review', icon: 'review', title: '把复习交给记忆规律', text: 'FSRS-4.5 间隔复习、四档记忆评分、每日新词额度与复习间隔预览。也可以按字母或随机顺序自由翻卡。' },
  { id: 'export', icon: 'search', title: '找得到，也带得走', text: '搜索、筛选、排序，快速定位词条；按当前筛选导出 PDF、CSV 或 JSON，打印与二次整理都方便。' },
  { id: 'sync', icon: 'cloud', title: '需要时同步，始终可以备份', text: '可选 Google Drive 文件夹或 API 直连。完整备份包含学习历史，合并导入不会直接覆盖整个现有词库。' },
  { id: 'keyboard', icon: 'keyboard', title: '少一点点击，多一点心流', text: '翻卡、评分、搜索、添加，都有顺手快捷键。深浅色主题与响应式布局，让学习在不同窗口里保持舒适。' },
]

function FeatureVisual({ id }) {
  if (id === 'ai') return <div className="feature-ai-visual"><span>serendipity</span><i /><i /><i /><div><Icon name="spark" size={15} /> AI enriched</div></div>
  if (id === 'notebooks') return <div className="notebook-stack" aria-hidden="true"><span>金融语境 <b>24</b></span><span>法律语境 <b>18</b></span><span>医药语境 <b>32</b></span></div>
  if (id === 'review') return <div className="review-timeline" aria-hidden="true"><span className="is-past">今天</span><i /><span>2 天</span><i /><span>7 天</span><i /><span>21 天</span></div>
  if (id === 'export') return <div className="export-formats" aria-hidden="true"><span>PDF</span><span>CSV</span><span>JSON</span></div>
  if (id === 'sync') return <div className="sync-visual" aria-hidden="true"><span><Icon name="shield" size={19} /> 本机词库</span><i>⇄</i><span><Icon name="cloud" size={19} /> Drive</span></div>
  return <div className="key-visual" aria-hidden="true"><kbd>/</kbd><kbd>N</kbd><kbd>Space</kbd><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd><kbd>4</kbd></div>
}

function Features() {
  return (
    <section className="section features-section" id="features">
      <div className="container">
        <div className="section-heading section-heading--features" data-reveal>
          <div><div className="eyebrow"><span /> THOUGHTFUL BY DESIGN</div><h2>功能足够完整，<br />体验依然安静。</h2></div>
          <p>没有复杂的学习社区，没有无休止的打卡压力。<br />只有记录、理解、复习，以及你的词库。</p>
        </div>
        <div className="features-grid">
          {features.map((feature, index) => (
            <article className={`feature-card feature-card--${feature.id} ${index === 0 || index === 4 ? 'feature-card--wide' : ''}`} key={feature.id} data-reveal>
              <div className="feature-icon"><Icon name={feature.icon} size={22} /></div>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
              <FeatureVisual id={feature.id} />
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function LocalFirst() {
  return (
    <section className="local-section" id="local">
      <div className="container local-grid">
        <div className="local-image-wrap" data-reveal>
          <img src="/vocove-cover.jpg" alt="暖灯下，书页化作学习卡片的 Vocove 概念封面" loading="lazy" />
          <div className="local-image-caption"><span>LOCAL BY DEFAULT.</span><span>CONNECTED BY CHOICE.</span></div>
        </div>
        <div className="local-copy" data-reveal>
          <div className="eyebrow eyebrow--gold"><span /> YOUR WORDS. YOUR DATA.</div>
          <h2>你的词库，<br />先属于你。</h2>
          <p className="local-lead">Vocove 把学习数据保存在本机，不要求先注册账户。是否连接模型、是否同步云端，都由你决定。</p>
          <ul className="local-points">
            <li><span><Icon name="shield" size={21} /></span><div><strong>本地优先，而非云端绑定</strong><p>没有模型连接时，仍可浏览已有词库和继续复习。</p></div></li>
            <li><span><Icon name="cloud" size={21} /></span><div><strong>同步是一种选择</strong><p>跨电脑使用时，可主动开启 Google Drive 同步。</p></div></li>
            <li><span><Icon name="file" size={21} /></span><div><strong>完整历史，随时备份</strong><p>单词本、删除标记与评分事件都能导出，迁移不只是复制一张词表。</p></div></li>
          </ul>
          <a className="text-link text-link--light" href={`${REPO_URL}#同步与备份`} target="_blank" rel="noreferrer">了解数据与同步方式 <Icon name="arrowUp" size={15} /></a>
        </div>
      </div>
    </section>
  )
}

function DownloadSection() {
  const [platform, setPlatform] = useState('')

  useEffect(() => {
    const agent = window.navigator.userAgent
    if (agent.includes('Mac')) setPlatform('mac')
    if (agent.includes('Windows')) setPlatform('windows')
  }, [])

  return (
    <section className="section download-section" id="download">
      <div className="container">
        <div className="download-heading" data-reveal>
          <div className="eyebrow"><span /> START YOUR VOCABULARY PRACTICE</div>
          <h2>下一个遇见的单词，<br />就把它<em>留下来。</em></h2>
          <p>免费下载，无需注册。桌面版内置运行环境，安装即可使用。</p>
          <div className="version-pill"><span /> 当前版本&nbsp; {RELEASE_VERSION} <i /> 2026.10.30</div>
        </div>
        <div className="platform-grid" data-reveal>
          <article className={`platform-card ${platform === 'mac' ? 'is-recommended' : ''}`}>
            {platform === 'mac' && <span className="recommended-label">你的设备</span>}
            <div className="platform-icon"><Icon name="apple" size={30} /></div>
            <h3>macOS</h3>
            <p>适用于 Apple Silicon 与 Intel 芯片的 Mac</p>
            <ul><li><Icon name="check" size={14} /> Apple Silicon：arm64 .dmg</li><li><Icon name="check" size={14} /> Intel：x64 .dmg</li></ul>
            <div className="platform-actions">
              <a className="button button--dark" href={DOWNLOAD_URLS.macArm}>下载 Apple Silicon 版 <Icon name="download" size={17} /></a>
              <a className="button button--outline" href={DOWNLOAD_URLS.macIntel}>下载 Intel 版 <Icon name="download" size={17} /></a>
            </div>
          </article>
          <article className={`platform-card ${platform === 'windows' ? 'is-recommended' : ''}`}>
            {platform === 'windows' && <span className="recommended-label">你的设备</span>}
            <div className="platform-icon"><Icon name="windows" size={28} /></div>
            <h3>Windows</h3>
            <p>适用于 Windows x64 电脑</p>
            <ul><li><Icon name="check" size={14} /> 下载 .exe 安装包</li><li><Icon name="check" size={14} /> 双击并按提示安装</li></ul>
            <div className="platform-actions">
              <a className="button button--dark" href={DOWNLOAD_URLS.windows}>下载 Windows x64 版 <Icon name="download" size={17} /></a>
            </div>
          </article>
        </div>
        <div className="download-notes" data-reveal>
          <p><strong>macOS 首次打开：</strong>当前安装包未进行 Apple Developer ID 签名和公证。如遇验证提示，请前往「系统设置 → 隐私与安全性」，确认「仍要打开」。</p>
          <p>需要在其他环境运行？<a href={`${REPO_URL}#网页版从源码运行`} target="_blank" rel="noreferrer">查看网页版源码安装指南 <Icon name="arrowUp" size={13} /></a></p>
          <p><a href={RELEASE_URL} target="_blank" rel="noreferrer">查看全部版本与 SHA-256 校验文件 <Icon name="arrowUp" size={13} /></a></p>
        </div>
      </div>
    </section>
  )
}

const faqs = [
  { question: 'Vocove 是免费的吗？', answer: '是。Vocove 是免费开源应用，采用 MIT License。云端模型生成与连接测试产生的 API 费用由对应供应商按你的账户计费；本地 Ollama 的运行成本取决于你的设备与部署方式。' },
  { question: '必须联网才能使用吗？', answer: '已有词库的浏览和复习可以在本机进行。云端模型内容补全与 Google Drive 同步需要联网；Ollama 是否联网取决于你的服务部署位置。' },
  { question: 'AI 功能可以直接使用吗？', answer: '首次使用需要在「设置与工具 → 模型设置」中配置模型。v1.5.0 支持选择供应商、填写密钥或设置环境变量、获取目录或手动添加模型 ID，并可先测试连接再保存。未配置模型时，不影响已有词库和复习功能。' },
  { question: 'v1.5.0 支持哪些模型供应商？', answer: '内置 Ollama、DeepSeek、OpenAI、Anthropic / Claude、Google Gemini、通义千问 / 百炼、Kimi / Moonshot、智谱 GLM、硅基流动、OpenRouter、Groq、Mistral AI、Together AI、Fireworks AI 和 xAI / Grok。自定义 API 支持 OpenAI Chat Completions、Anthropic Messages 和 Ollama 原生协议；可设置地址与超时，每家配置独立保留。安装版与源码版均可使用。' },
  { question: '如何使用专业语境单词本？', answer: 'v1.4.0 起，新建单词本时可选择金融、法律或医药语境；分类本仍使用通用释义。类型创建后固定，改名不会切换语境。已有、移动或显式复制的内容不会自动改写，补全只填空缺字段。跨设备使用专业补全时，请将相关客户端更新至 v1.4.0 或更高版本。' },
  { question: '支持手机或平板吗？', answer: '桌面安装版目前支持 macOS 与 Windows。网页模式提供响应式布局，但需要先从源码在电脑上启动；Vocove 目前不是独立的手机 App，也没有开箱即用的公共云服务。' },
  { question: '换电脑时，学习进度能带走吗？', answer: '可以。你可以使用 Google Drive 同步，或在「同步与备份」中下载完整备份，再合并导入另一台电脑。完整备份会保存单词本与学习历史；普通 PDF、CSV 列表导出不能替代完整备份。' },
  { question: 'Mac 提示“Apple 无法验证”怎么办？', answer: '当前安装包未签名和公证。点击「完成」，进入「系统设置 → 隐私与安全性 → 安全性」，点击「仍要打开」并确认。请只从 Vocove 官方 GitHub Release 下载安装包。' },
]

function FAQ() {
  return (
    <section className="section faq-section" id="faq">
      <div className="container faq-grid">
        <div className="faq-heading" data-reveal>
          <div className="eyebrow"><span /> BEFORE YOU BEGIN</div>
          <h2>开始之前，<br />你可能想知道。</h2>
          <p>还有其他问题？欢迎在 GitHub 上反馈。</p>
          <a className="text-link" href={ISSUE_URL} target="_blank" rel="noreferrer">提交问题或建议 <Icon name="arrowUp" size={15} /></a>
        </div>
        <div className="faq-list" data-reveal>
          {faqs.map((item, index) => (
            <details key={item.question} open={index === 0}>
              <summary><span>{item.question}</span><i><Icon name="plus" size={18} /></i></summary>
              <p>{item.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-top">
          <div><Brand light /><p>一个安静、可靠的词汇学习空间。</p></div>
          <a className="footer-cta" href="#download">开始记住下一个单词 <Icon name="arrow" size={22} /></a>
        </div>
        <div className="footer-bottom">
          <span>© 2026 Eric Zhou · MIT License</span>
          <div><a href={REPO_URL} target="_blank" rel="noreferrer">GitHub</a><a href={ISSUE_URL} target="_blank" rel="noreferrer">问题反馈</a><a href={`${REPO_URL}/blob/main/CHANGELOG.md`} target="_blank" rel="noreferrer">更新日志</a><a href="#top">回到顶部 ↑</a></div>
        </div>
      </div>
    </footer>
  )
}

function App() {
  useEffect(() => {
    const elements = document.querySelectorAll('[data-reveal]')
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elements.forEach((element) => element.classList.add('is-visible'))
      return undefined
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer.unobserve(entry.target)
          window.setTimeout(() => entry.target.style.setProperty('--reveal-delay', '0ms'), 1200)
        }
      })
    }, { threshold: 0.1, rootMargin: '0px 0px -45px' })
    elements.forEach((element) => {
      const group = [...element.parentElement.children].filter((child) => child.hasAttribute('data-reveal'))
      const index = Math.max(0, group.indexOf(element))
      element.style.setProperty('--reveal-delay', `${Math.min(index * 75, 350)}ms`)
      observer.observe(element)
    })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const hero = document.querySelector('.hero')
    const product = document.querySelector('.hero-product')
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)')
    if (!hero || !product || reducedMotion.matches) return undefined

    let scrollFrame = 0
    let pointerFrame = 0
    const updateScroll = () => {
      scrollFrame = 0
      const progress = Math.min(Math.max(window.scrollY / (hero.offsetHeight * 0.9), 0), 1)
      hero.style.setProperty('--hero-scroll', progress.toFixed(3))
    }
    const onScroll = () => {
      if (!scrollFrame) scrollFrame = window.requestAnimationFrame(updateScroll)
    }
    const onPointerMove = (event) => {
      if (!finePointer.matches || pointerFrame) return
      pointerFrame = window.requestAnimationFrame(() => {
        const bounds = product.getBoundingClientRect()
        const x = (event.clientX - bounds.left) / bounds.width - 0.5
        const y = (event.clientY - bounds.top) / bounds.height - 0.5
        product.style.setProperty('--tilt-x', `${(-y * 2).toFixed(2)}deg`)
        product.style.setProperty('--tilt-y', `${(x * 2.6).toFixed(2)}deg`)
        pointerFrame = 0
      })
    }
    const onPointerLeave = () => {
      product.style.setProperty('--tilt-x', '0deg')
      product.style.setProperty('--tilt-y', '0deg')
    }
    updateScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    product.addEventListener('pointermove', onPointerMove)
    product.addEventListener('pointerleave', onPointerLeave)
    return () => {
      window.removeEventListener('scroll', onScroll)
      product.removeEventListener('pointermove', onPointerMove)
      product.removeEventListener('pointerleave', onPointerLeave)
      if (scrollFrame) window.cancelAnimationFrame(scrollFrame)
      if (pointerFrame) window.cancelAnimationFrame(pointerFrame)
    }
  }, [])

  return (
    <>
      <a className="skip-link" href="#main">跳到主要内容</a>
      <Header />
      <main id="main">
        <Hero />
        <div className="belief-strip"><div className="container"><p>Not just a list of words. <span>不只是收集生词，而是建立长期记忆。</span></p><i>V</i></div></div>
        <HowItWorks />
        <Features />
        <LocalFirst />
        <DownloadSection />
        <FAQ />
      </main>
      <Footer />
    </>
  )
}

export default App
