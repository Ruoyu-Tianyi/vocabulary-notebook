import { useEffect, useRef, useState } from 'react'

async function request(path, options = {}) {
  const response = await fetch(`/api/model-settings${path}`, {
    ...options, headers: { 'Content-Type': 'application/json' },
  })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '配置格式不正确')
  return data
}

export default function ModelSettings() {
  const [settings, setSettings] = useState(null)
  const [models, setModels] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [modelError, setModelError] = useState('')
  const [message, setMessage] = useState('')
  const generation = useRef(0)

  async function refreshModels(apiKey = '') {
    const id = ++generation.current
    setLoading(true)
    setModels(null)
    setModelError('')
    try {
      const data = await request('/deepseek-models', { method: 'POST', body: JSON.stringify({ api_key: apiKey }) })
      if (id === generation.current) setModels(data.models)
    } catch (err) {
      if (id === generation.current) setModelError(err.message)
    } finally {
      if (id === generation.current) setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    const requests = generation
    request('').then(data => {
      if (!active) return
      setSettings({ ...data, deepseek: { ...data.deepseek, api_key: '' } })
      if (data.deepseek.api_key_configured) refreshModels()
    }).catch(err => { if (active) setError(err.message) })
    return () => { active = false; requests.current++ }
  }, [])

  function update(section, key, value) {
    setMessage('')
    setSettings(current => ({ ...current, [section]: { ...current[section], [key]: value } }))
    if (key === 'api_key') {
      generation.current++
      setLoading(false)
      setModels(null)
      setModelError('密钥已修改，请刷新模型列表。')
    }
  }

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const data = await request('', { method: 'PUT', body: JSON.stringify(settings) })
      setSettings({ ...data, deepseek: { ...data.deepseek, api_key: '' } })
      setMessage('配置已保存并立即生效。')
      window.dispatchEvent(new Event('model-settings-changed'))
      window.dispatchEvent(new Event('ai-settings-changed'))
    } catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }

  if (!settings) return <div role="status">{error || '正在加载模型配置…'}</div>
  const ds = settings.deepseek
  const unavailable = models !== null && ds.model && !models.includes(ds.model)
  return (
    <section className="model-settings">
      <h2>模型设置</h2>
      <p className="settings-note">选择用于补充音标、释义和例句的模型，保存后立即生效。{settings.deepseek.environment_key ? '当前环境变量优先于设置页填写的值。' : ''}</p>
      <form onSubmit={save}>
        <fieldset disabled={saving}>
          <div className="settings-panel">
          <h3>DeepSeek API 词汇补全</h3>
          <p className="settings-note">音标、中文释义和课程例句使用 DeepSeek；词库与学习记录仍通过 Drive 同步。</p>
            <div className="form-group"><label htmlFor="deepseek-key">DeepSeek API Key</label>
              <input id="deepseek-key" type="password" autoComplete="new-password" value={ds.api_key} onChange={e => update('deepseek', 'api_key', e.target.value)} placeholder={ds.api_key_configured ? '已配置；留空保留现有密钥' : '输入 API Key'} /></div>
            <p className="settings-note">密钥仅保存在本机 .secrets，不回传、不进入 Drive 或 Git。第二台电脑分别配置。</p>
            <div className="model-list-heading"><div><h4 id="model-list-label">可用模型</h4><p>点击下方选项选择模型</p></div>
              <button className="settings-refresh" type="button" onClick={() => refreshModels(ds.api_key)} disabled={loading}><span aria-hidden="true">↻ </span>{loading ? '获取中…' : '刷新列表'}</button>
            </div>
            <div className="model-options" role="radiogroup" aria-labelledby="model-list-label" aria-busy={loading}>
              {loading && <div className="model-list-empty" role="status">正在从 DeepSeek 获取可用模型…</div>}
              {!loading && !models && <div className="model-list-empty">{ds.api_key_configured || ds.api_key ? '点击「刷新列表」获取可用模型' : '填写 API Key 后，点击「刷新列表」获取模型'}</div>}
              {models?.map(model => <label key={model} className={`model-option ${ds.model === model ? 'is-selected' : ''}`}>
                <input type="radio" name="deepseek-model" value={model} checked={ds.model === model} onChange={() => update('deepseek', 'model', model)} />
                <span className="model-option-name">{model}</span><span className="model-option-status">{ds.model === model ? '已选择' : '可用'}</span>
              </label>)}
            </div>
            {ds.model && !models?.includes(ds.model) && <div className={`configured-model ${unavailable ? 'is-unavailable' : ''}`}><span>当前配置</span><strong>{ds.model}</strong><span className="settings-tag">{unavailable ? '已不可用' : '待核验'}</span></div>}
            {unavailable && <p className="settings-error" role="alert">模型「{ds.model}」已不在 DeepSeek 当前可用模型列表中，可能已下线或更名。请选择可用模型后保存。</p>}
            {modelError && <p className="settings-error" role="alert">{modelError}</p>}
          </div>
          <div className="settings-actions"><span>保存后用于后续单词补充</span><button type="submit" disabled={saving || (settings.provider === 'deepseek' && (loading || !models || !models.includes(ds.model)))}>{saving ? '正在保存…' : '保存配置'}</button></div>
        </fieldset>
      </form>
      {error && <p className="settings-error" role="alert">{error}</p>}
      {message && <p className="settings-success" role="status">{message}</p>}
    </section>
  )
}
