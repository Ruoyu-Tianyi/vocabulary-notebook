import { useState, useEffect, useRef } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { fetchWord, updateWord, deleteWord } from '../api'
import { useNotebooks } from '../useNotebooks'

export default function WordDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [word, setWord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [editWord, setEditWord] = useState('')
  const [editDef, setEditDef] = useState('')
  const [editBook, setEditBook] = useState('default')
  const [editError, setEditError] = useState('')
  const [actionError, setActionError] = useState('')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [syncNotice, setSyncNotice] = useState('')
  const { notebooks, loading: booksLoading, error: booksError, refresh: refreshBooks } = useNotebooks()
  const editButtonRef = useRef(null)
  const modalRef = useRef(null)

  useEffect(() => {
    let active = true
    let request = 0
    async function refresh(fromCloud = false) {
      const current = ++request
      try {
        const data = await fetchWord(id)
        if (!active || current !== request) return
        setWord(data.word)
        if (fromCloud) setSyncNotice('云端内容已更新，当前未保存的编辑已保留。保存会提交编辑框中的内容。')
      } catch (requestError) {
        if (!active || current !== request) return
        if (fromCloud) setSyncNotice(requestError.status === 404
          ? '此单词已不存在，可能已在另一台电脑删除。当前编辑仍已保留，请先复制需要的内容。'
          : '暂时无法刷新此单词。当前编辑仍已保留，请检查连接后重试。')
        else setError(requestError.status === 404 ? '单词不存在' : requestError.message || '加载失败，请检查连接后重试')
      } finally {
        if (active && current === request) setLoading(false)
      }
    }
    const onCloudChange = () => refresh(true)
    window.addEventListener('cloud-data-changed', onCloudChange)
    refresh()
    return () => { active = false; window.removeEventListener('cloud-data-changed', onCloudChange) }
  }, [id])

  function startEdit() {
    setEditWord(word.word)
    setEditDef(word.definition)
    setEditBook(word.notebook_id || 'default')
    setEditError('')
    setEditing(true)
  }

  function closeEdit() {
    if (saving) return
    setEditing(false)
    editButtonRef.current?.focus()
  }

  function handleModalKey(event) {
    event.stopPropagation()
    if (event.key === 'Escape') {
      event.preventDefault()
      closeEdit()
    } else if (event.key === 'Tab') {
      const controls = modalRef.current?.querySelectorAll('input:not(:disabled), select:not(:disabled), button:not(:disabled)')
      if (!controls?.length) return
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
  }

  async function handleEdit(e) {
    e.preventDefault()
    if (saving || booksLoading || booksError || !notebooks.some(book => book.id === editBook)) return
    setSaving(true)
    setEditError('')
    try {
      const result = await updateWord(id, { word: editWord, definition: editDef, notebook_id: editBook })
      setWord(result.word)
      setEditing(false)
      setSyncNotice('')
      editButtonRef.current?.focus()
    } catch (requestError) {
      setEditError(requestError.message || '保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (deleting || !window.confirm('确认从当前单词本删除这个单词及其复习进度？其他单词本中的同词记录不受影响。')) return
    setDeleting(true)
    setActionError('')
    try {
      await deleteWord(id)
      navigate(`/?notebook_id=${encodeURIComponent(word.notebook_id || 'default')}`)
    } catch (requestError) {
      setActionError(requestError.message || '删除失败，请重试')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <div className="loading">加载中…</div>
  if (error) return (
    <div className="empty-state">
      <p>{error}</p>
      <button onClick={() => navigate(-1)}>返回列表</button>
    </div>
  )

  return (
    <div className="word-detail-page">
      <button onClick={() => navigate(-1)} className="btn btn-ghost detail-back">← 返回</button>

      {syncNotice && <p role="status">{syncNotice}</p>}
      {actionError && <p role="alert">{actionError}</p>}
      <div className="detail-card">
        <p className="detail-notebook">
          <Link to={`/?notebook_id=${encodeURIComponent(word.notebook_id || 'default')}`}>{notebooks.find(book => book.id === (word.notebook_id || 'default'))?.name || '查看所属单词本'} <span aria-hidden="true">↗</span></Link>
        </p>
        <h2 className="detail-word">{word.word}</h2>
        {word.phonetic && <div className="detail-phonetic">{word.phonetic}</div>}
        <section className="detail-section" aria-label="释义">
          <h3>释义</h3>
          <div className="detail-definition">{word.definition || '释义待补全'}</div>
        </section>
        {word.example && <section className="detail-section" aria-label="例句"><h3>例句</h3><p className="detail-example">{word.example}</p></section>}

        <footer className="detail-footer">
        <div className="detail-date">添加于 {word.created_at.slice(0, 10)}</div>
        <div className="btn-group">
          <button ref={editButtonRef} className="btn btn-primary" onClick={startEdit} disabled={deleting}>编辑</button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={deleting}>{deleting ? '删除中…' : '删除'}</button>
        </div>
        </footer>
      </div>

      {editing && (
        <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) closeEdit() }}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="edit-word-heading" ref={modalRef} onKeyDown={handleModalKey}>
            <h2 id="edit-word-heading">编辑单词</h2>
            <form onSubmit={handleEdit}>
              <div className="form-group">
                <label htmlFor="edit-word">单词</label>
                <input id="edit-word" type="text" value={editWord} onChange={e => setEditWord(e.target.value)} autoFocus required disabled={saving} />
              </div>
              <div className="form-group">
                <label htmlFor="edit-definition">释义</label>
                <input id="edit-definition" type="text" value={editDef} onChange={e => setEditDef(e.target.value)} disabled={saving} />
              </div>
              <div className="form-group">
                <label htmlFor="edit-notebook">所属单词本</label>
                <select id="edit-notebook" className="notebook-select" value={editBook} onChange={event => setEditBook(event.target.value)} disabled={saving || booksLoading || Boolean(booksError)}>
                  {!notebooks.some(book => book.id === editBook) && <option value={editBook} disabled>{booksLoading ? '加载单词本…' : '此单词本已不可用，请重新选择'}</option>}
                  {notebooks.map(book => <option key={book.id} value={book.id}>{book.name}</option>)}
                </select>
                <p className="added-words-hint">移动会保留当前记录的复习进度；目标本中已有同词时无法移动。</p>
                {booksError && <p role="alert">{booksError} <button type="button" className="btn btn-ghost" onClick={refreshBooks}>重试</button></p>}
              </div>
              {editError && <p role="alert">{editError}</p>}
              <div className="btn-group">
                <button type="submit" className="btn btn-primary" disabled={saving || booksLoading || Boolean(booksError) || !notebooks.some(book => book.id === editBook)}>{saving ? '保存中…' : '保存'}</button>
                <button type="button" className="btn btn-secondary" onClick={closeEdit} disabled={saving}>取消</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
