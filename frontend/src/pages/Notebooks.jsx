import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { createNotebook, updateNotebook, deleteNotebook } from '../api'
import { useNotebooks } from '../useNotebooks'
import NavigationIcon from '../components/NavigationIcon'
import './NotebookPolish.css'

export default function Notebooks() {
  const { notebooks, loading, error, refresh } = useNotebooks()
  const [editing, setEditing] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  const [notice, setNotice] = useState('')
  const [deleting, setDeleting] = useState('')
  const formRef = useRef(null)

  function openForm(book = {}) {
    setEditing(book)
    setName(book.name || '')
    setDescription(book.description || '')
    setFormError('')
    setNotice('')
    setDeleting('')
    requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ block: 'nearest' })
      formRef.current?.querySelector('input')?.focus()
    })
  }

  async function save(e) {
    e.preventDefault()
    if (!name.trim() || busy) return
    setBusy(true)
    setFormError('')
    try {
      const fields = { name: name.trim(), description: description.trim() }
      if (editing.id) await updateNotebook(editing.id, fields)
      else await createNotebook(fields)
      setNotice(editing.id ? '单词本已更新' : `已创建「${fields.name}」，可以开始收录单词了。`)
      setEditing(null)
    } catch (err) {
      setFormError(err.message)
    } finally { setBusy(false) }
  }

  async function remove(book) {
    setBusy(true)
    setNotice('')
    try {
      await deleteNotebook(book.id)
      setDeleting('')
      setNotice(`已删除空单词本「${book.name}」`)
    } catch (err) { setNotice(err.message) }
    finally { setBusy(false) }
  }

  return <div className="notebooks-page">
    <header className="notebook-heading">
      <div>
        <div className="notebook-heading-title"><h2>我的单词本</h2>{!loading && !error && <span className="notebook-count">{notebooks.length} 本</span>}</div>
        <p>按课程、主题或目标收录，让每一份积累都有归属。</p>
      </div>
      <button className="btn btn-primary" onClick={() => openForm()} disabled={busy}><NavigationIcon name="plus" />新建单词本</button>
    </header>

    {notice && <p className="notebook-notice" role="status">{notice}</p>}
    {editing && <form ref={formRef} className="notebook-form" onSubmit={save} aria-labelledby="notebook-form-heading">
      <h3 id="notebook-form-heading">{editing.id ? '编辑单词本' : '新建单词本'}</h3>
      <div className="form-group">
        <label htmlFor="notebook-name">名称</label>
        <input id="notebook-name" value={name} onChange={e => setName(e.target.value)} type="text"
          placeholder="例如：金融英语、雅思阅读…" maxLength={80} required disabled={busy} />
      </div>
      <div className="form-group">
        <label htmlFor="notebook-description">说明（可选）</label>
        <textarea id="notebook-description" value={description} onChange={e => setDescription(e.target.value)}
          placeholder="记下这本的学习目标…" maxLength={500} rows={2} disabled={busy} />
      </div>
      {formError && <p className="notebook-error" role="alert">{formError}</p>}
      <div className="btn-group">
        <button className="btn btn-primary" disabled={busy || !name.trim()}>{busy ? '保存中…' : '保存单词本'}</button>
        <button className="btn btn-secondary" type="button" disabled={busy} onClick={() => setEditing(null)}>取消</button>
      </div>
    </form>}

    {error ? <div className="empty-state"><p>{error}</p><button className="btn btn-secondary" onClick={refresh}>重新加载</button></div>
      : loading && notebooks.length === 0 ? <div className="loading">加载单词本…</div>
        : <div className="notebook-grid">
          {notebooks.map(book => <article className="notebook-card" key={book.id}>
            <div className="notebook-card-top">
              <span className="notebook-card-icon"><NavigationIcon name="notebooks" /></span>
              <span className="notebook-word-count"><strong>{book.word_count}</strong> 个单词</span>
            </div>
            <Link className="notebook-title" to={`/?notebook_id=${encodeURIComponent(book.id)}`}><h3>{book.name}</h3></Link>
            <p className="notebook-description">{book.description || (book.word_count ? '随时回顾，按自己的节奏学习。' : '还没有单词，开始收录第一个吧。')}</p>
            <div className="notebook-actions notebook-primary-actions">
              <Link className="btn btn-primary" to={`/?notebook_id=${encodeURIComponent(book.id)}`}>查看单词<NavigationIcon name="arrow" /></Link>
              <Link className="btn btn-secondary" to={`/review?notebook_id=${encodeURIComponent(book.id)}`}><NavigationIcon name="review" />复习本书</Link>
            </div>
            <div className="notebook-card-footer">
              <span className="notebook-default-label">{book.id === 'default' ? '默认单词本' : '独立复习进度'}</span>
              <div className="notebook-actions">
                <button className="btn btn-ghost" disabled={busy} onClick={() => openForm(book)}>编辑</button>
                {book.id !== 'default' && <button className="btn btn-ghost" disabled={busy || book.word_count > 0}
                  title={book.word_count > 0 ? '请先移出或删除本中的单词，保留所需复习记录' : '删除空单词本'}
                  onClick={() => { setDeleting(book.id); setNotice('') }}>删除</button>}
              </div>
            </div>
            {deleting === book.id && <div className="notebook-delete" role="alert">
              <p>删除空单词本「{book.name}」？</p>
              <div className="notebook-actions">
                <button className="btn btn-danger" disabled={busy} onClick={() => remove(book)}>确认删除</button>
                <button className="btn btn-secondary" disabled={busy} onClick={() => setDeleting('')}>取消</button>
              </div>
            </div>}
          </article>)}
        </div>}
    <p className="notebook-footnote">同一单词可加入多本，各本独立记录复习进度，每日新词额度共用。仅可删除空单词本，默认单词本始终保留。</p>
  </div>
}
