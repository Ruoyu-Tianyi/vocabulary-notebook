import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import NavigationIcon from '../components/NavigationIcon'
import { builtinProvider, selectProvider } from '../lib/modelSettingsState'
import './SettingsPolish.css'

async function request(path, options = {}) {
  const response = await fetch(`/api/model-settings${path}`, { ...options, headers: { 'Content-Type': 'application/json' } })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '配置格式不正确，请检查输入')
  return data
}

export default function ModelSettings() {
  const [settings, setSettings] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [manual, setManual] = useState('')
  const [search, setSearch] = useState('')
  const pending = useRef(null)
  useEffect(() => {
    const controller = new AbortController()
    request('', { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setSettings(data)
    }).catch(err => {
      if (!controller.signal.aborted) setError(err.message)
    })
    return () => { controller.abort(); pending.current?.abort() }
  }, [])

  function resetFeedback() {
    pending.current?.abort()
    setBusy(''); setError(''); setMessage('')
  }
  function update(key, value) {
    resetFeedback()
    setSettings(current => ({ ...current, providers: { ...current.providers,
      [current.provider]: { ...current.providers[current.provider], [key]: value,
        ...(key === 'api_key' && value.trim() ? { clear_api_key: false } : {}),
        ...(key === 'clear_api_key' && value ? { api_key: '' } : {}) } } }))
  }
  function select(provider) {
    if (provider === settings.provider) return
    resetFeedback(); setManual(''); setSearch('')
    setSettings(current => selectProvider(current, provider))
  }
  function addModel() {
    const model = manual.trim()
    if (!model) return
    resetFeedback()
    setSettings(current => {
      const profile = current.providers[current.provider]
      return { ...current, providers: { ...current.providers, [current.provider]: {
        ...profile, model, models: [...new Set([...(profile.models || []), profile.model, model].filter(Boolean))],
      } } }
    })
    setManual(''); setSearch('')
  }
  async function action(kind, event) {
    event?.preventDefault()
    resetFeedback()
    const controller = new AbortController()
    pending.current = controller
    setBusy(kind)
    const provider = settings.provider
    const profile = settings.providers[provider]
    try {
      const data = await request(kind === 'save' ? '' : `/${kind}`, {
        method: kind === 'save' ? 'PUT' : 'POST', signal: controller.signal,
        body: JSON.stringify(kind === 'save' ? { provider, providers: { [provider]: profile } } : { provider, ...profile }),
      })
      if (controller.signal.aborted) return
      if (kind === 'save') {
        setSettings(current => ({ ...current, providers: { ...current.providers, [provider]: data.providers[provider] } }))
        setMessage('配置已保存并立即生效。')
        window.dispatchEvent(new Event('model-settings-changed'))
      } else if (kind === 'models') {
        setSettings(current => ({ ...current, providers: { ...current.providers,
          [provider]: { ...current.providers[provider], models: data.models } } }))
        setMessage(data.models.length ? `已获取 ${data.models.length} 个模型，请选择文本对话模型。` : '目录为空，可以手动添加模型 ID。')
      } else setMessage('连接测试成功，所选模型已返回内容。')
    } catch (err) { if (!controller.signal.aborted) setError(err.message) }
    finally { if (!controller.signal.aborted) setBusy('') }
  }
  if (!settings) return <div role="status">{error || '正在加载模型配置…'}</div>
  const provider = settings.provider
  const preset = settings.catalog.find(item => item.id === provider)
  const profile = settings.providers[provider]
  const models = [...new Set([...(profile.models || []), profile.model].filter(Boolean))]
  const filtered = models.filter(model => model.toLowerCase().includes(search.toLowerCase()))
  const custom = provider === 'custom'
  const local = provider === 'ollama'
  return <section className="model-settings">
    <header className="model-settings-heading"><h2>模型设置</h2><p>选择用于补充音标、释义和例句的模型。各供应商配置独立保留，保存后切换生效。</p></header>
    <nav className="settings-page-nav" aria-label="设置页面">
      <Link to="/settings" aria-current="page"><NavigationIcon name="model" />模型设置</Link>
      <Link to="/sync-settings"><NavigationIcon name="cloud" />同步与备份</Link>
    </nav>
    <form onSubmit={event => action('save', event)}>
      <fieldset disabled={busy === 'save'}>
        <div className="provider-tabs" aria-label="供应商类型">
          <button type="button" aria-pressed={!custom} onClick={() => select(builtinProvider(settings))}>内置供应商</button>
          <button type="button" aria-pressed={custom} onClick={() => select('custom')}>自定义 API</button>
        </div>
        {!custom && <div className="form-group"><label htmlFor="provider">供应商</label>
          <select id="provider" value={provider} onChange={event => select(event.target.value)}>
            {settings.catalog.filter(item => item.id !== 'custom').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>}
        <div className="settings-panel">
          <h3>{preset.name}</h3>
          {custom && <div className="form-group"><label htmlFor="protocol">API 协议</label><select id="protocol" value={profile.protocol} onChange={event => update('protocol', event.target.value)}>
            <option value="openai">OpenAI Chat Completions 兼容</option><option value="anthropic">Anthropic Messages</option><option value="ollama">Ollama 原生</option>
          </select></div>}
          <div className="form-group"><label htmlFor="api-key">API 密钥{local || custom ? '（可选）' : ''}</label>
            <input id="api-key" type="password" autoComplete="new-password" value={profile.api_key || ''} onChange={event => update('api_key', event.target.value)} placeholder={profile.api_key_configured ? '已保存；留空保留现有密钥' : custom ? '输入 API Key；无需认证的服务可留空' : '输入 API Key，或使用后端环境变量'} />
          </div>
          <p className="settings-note">{preset.env_key && <>环境变量：<code>{preset.env_key}</code>（{profile.env_key_configured ? '已检测到' : '未检测到'}）。</>}密钥保存在本机配置文件，不回传浏览器。</p>
          {profile.api_key_configured && <label className="provider-clear"><input type="checkbox" checked={!!profile.clear_api_key} onChange={event => update('clear_api_key', event.target.checked)} />保存时清除已存密钥（仍可使用环境变量）</label>}
          <details className="provider-advanced" open={custom || undefined}>
            <summary>自定义设置 · API 地址与超时</summary>
            <div className="form-group"><label htmlFor="base-url">API 根地址</label>
              <input id="base-url" type="url" required value={profile.base_url || ''} onChange={event => update('base_url', event.target.value)} placeholder={preset.base_url || 'https://example.com/v1'} />
            </div>
            <p className="settings-note">保留地址中的版本路径（如 /v1）。修改地址后请重新输入密钥。不同地区及 Coding Plan 请使用对应服务地址。</p>
            <div className="form-group"><label htmlFor="timeout">生成超时（秒）</label><input id="timeout" type="number" min="5" max="600" required value={profile.timeout} onChange={event => update('timeout', Number(event.target.value))} /></div>
          </details>
          {local && <p className="settings-note">先运行 <code>ollama serve</code>，再用 <code>ollama pull 模型名称</code> 下载模型。支持填写主机地址或旧版 /api/generate 地址；远程服务可选填访问密钥。</p>}
          <div className="model-list-heading"><div><h4>模型目录</h4><p>获取目录或手动添加模型 ID</p></div>
            <button className="settings-refresh" type="button" disabled={!!busy} onClick={() => action('models')}>{busy === 'models' ? '正在获取…' : local ? '获取已安装模型' : '获取可用模型'}</button>
          </div>
          {models.length > 8 && <div className="form-group"><label htmlFor="model-search">搜索模型</label><input id="model-search" value={search} onChange={event => setSearch(event.target.value)} placeholder="按模型 ID 搜索" /></div>}
          <div className="provider-model-list">
            {filtered.length ? <div className="form-group"><label htmlFor="model-select">选择模型（{filtered.length}）</label><select id="model-select" value={filtered.includes(profile.model) ? profile.model : ''} onChange={event => update('model', event.target.value)}><option value="" disabled>请选择文本对话模型</option>{filtered.map(model => <option key={model} value={model}>{model}</option>)}</select></div>
              : <div className="model-list-empty">{search ? '没有匹配的模型' : '尚未获取模型目录。目录之外的模型 ID 也可直接使用。'}</div>}
          </div>
          <div className="form-group"><label htmlFor="manual-model">手动添加模型 ID</label><div className="provider-inline"><input id="manual-model" value={manual} spellCheck="false" onChange={event => setManual(event.target.value)} onKeyDown={event => {
            if (event.key === 'Enter' && !event.nativeEvent.isComposing) { event.preventDefault(); addModel() }
          }} placeholder="填写供应商提供的完整模型 ID" /><button type="button" disabled={!manual.trim()} onClick={addModel}>添加并选择</button></div></div>
          <p className="settings-note">当前模型：<strong>{profile.model || '尚未选择'}</strong>。目录可能包含非对话模型，实际可用性以连接测试为准。</p>
          <button type="button" disabled={!!busy || !profile.model} onClick={() => action('test')}>{busy === 'test' ? '正在测试…' : '测试连接与模型'}</button>
          <p className="settings-note">测试会发送一条简短生成请求，可能消耗少量 API 额度。</p>
        </div>
        <div className="settings-actions"><span>保存无需联网核验</span><button type="submit" disabled={!!busy || !profile.model}>{busy === 'save' ? '正在保存…' : '保存并使用'}</button></div>
      </fieldset>
    </form>
    {error && <p className="settings-error" role="alert">{error}</p>}
    {message && <p className="settings-success" role="status">{message}</p>}
  </section>
}
