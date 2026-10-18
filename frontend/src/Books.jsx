import { createContext, useContext, useCallback, useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { activeNotebookId, libraryRequest } from './api'

const BooksContext = createContext(null)
export const useBooks = () => useContext(BooksContext)

export function BooksProvider({ children }) {
  const [books, setBooks] = useState([])
  const [active, setActive] = useState(activeNotebookId)
  const [error, setError] = useState('')
  const reload = useCallback(async () => {
    try {
      const result = await libraryRequest('/notebooks')
      setBooks(result.notebooks)
      setError('')
      setActive(previous => {
        if (previous && !result.notebooks.some(book => book.id === previous)) {
          localStorage.setItem('vocabulary-notebook-id', 'default')
          return 'default'
        }
        return previous
      })
    } catch (err) { setError(err.message) }
  }, [])
  useEffect(() => {
    reload()
    window.addEventListener('library-changed', reload)
    return () => window.removeEventListener('library-changed', reload)
  }, [reload])
  function select(id) {
    localStorage.setItem('vocabulary-notebook-id', id)
    setActive(id)
    window.dispatchEvent(new Event('review-stats-changed'))
  }
  return <BooksContext.Provider value={{ books, active, select, reload, error }}>{children}</BooksContext.Provider>
}

export function BookPicker() {
  const { books, active, select, reload, error } = useBooks()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const actionsRef = useRef(null)
  useEffect(() => {
    function closeActions(event) {
      if (actionsRef.current && !actionsRef.current.contains(event.target)) actionsRef.current.open = false
    }
    document.addEventListener('pointerdown', closeActions)
    return () => document.removeEventListener('pointerdown', closeActions)
  }, [])
  const current = books.find(book => book.id === active)
  function open(book) {
    if (actionsRef.current) actionsRef.current.open = false
    setEditing(book || {})
    setName(book?.name || '')
    setDescription(book?.description || '')
    setMessage('')
  }
  async function save(event) {
    event.preventDefault()
    setSaving(true)
    try {
      const result = await libraryRequest(editing.id ? `/notebooks/${editing.id}` : '/notebooks',
        editing.id ? 'PUT' : 'POST', { name, description })
      await reload()
      select(result.notebook.id)
      navigate('/')
      setEditing(null)
    } catch (err) { setMessage(err.message) }
    finally { setSaving(false) }
  }
  return <>
    <div className="book-toolbar">
      <div className="book-choice">
        <label htmlFor="active-book">当前单词本</label>
        <select id="active-book" value={active} onChange={event => { select(event.target.value); navigate('/') }}>
          <option value="">全部单词本</option>
          {books.map(book => <option key={book.id} value={book.id}>{book.name} · {book.word_count}</option>)}
        </select>
      </div>
      <details className="book-actions" ref={actionsRef} onKeyDown={event => {
        if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus() }
      }}>
        <summary aria-label="单词本管理">管理</summary>
        <div className="book-actions-menu">
          {current?.description && <p className="book-description">{current.description}</p>}
          <button type="button" onClick={() => open(null)}>＋ 新建单词本</button>
          {current && <button type="button" onClick={() => open(current)}>编辑当前单词本</button>}
        </div>
      </details>
      {error && <p className="book-description settings-error" role="alert">{error}</p>}
    </div>
    {editing && <div className="book-overlay" onKeyDown={event => { if (event.key === 'Escape' && !saving) setEditing(null) }}>
      <section className="book-dialog" role="dialog" aria-modal="true" aria-labelledby="book-dialog-title">
        <h2 id="book-dialog-title">{editing.id ? '编辑单词本' : '新建单词本'}</h2>
        <form onSubmit={save}>
          <div className="form-group"><label htmlFor="book-name">名称</label>
            <input id="book-name" type="text" autoFocus required maxLength={80} placeholder="例如：法律英语、金融课程" value={name} onChange={e => setName(e.target.value)} /></div>
          <div className="form-group"><label htmlFor="book-description">课程或领域说明</label>
            <textarea id="book-description" maxLength={500} rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="例如：合同法课程中的术语、课堂例句" /></div>
          {message && <p role="alert">{message}</p>}
          <div className="btn-group"><button className="btn btn-primary" disabled={saving || !name.trim()}>{saving ? '保存中…' : '保存'}</button>
            <button type="button" className="btn btn-secondary" disabled={saving} onClick={() => setEditing(null)}>取消</button></div>
        </form>
      </section>
    </div>}
  </>
}
