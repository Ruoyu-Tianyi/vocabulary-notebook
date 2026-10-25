import { useState, useRef, useEffect, useId } from 'react'
import { exportUrl } from '../api'
import NavigationIcon from './NavigationIcon'

export default function ExportMenu({ q, date, sort, letter, notebook_id }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const triggerRef = useRef(null)
  const panelId = useId()

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', handleClick)
    document.addEventListener('focusin', handleClick)
    return () => {
      document.removeEventListener('pointerdown', handleClick)
      document.removeEventListener('focusin', handleClick)
    }
  }, [])

  function doExport(format) {
    window.open(exportUrl(format, { q, date, sort, letter, notebook_id }), '_blank')
    setOpen(false)
  }

  return (
    <div className="export-wrapper" ref={ref} onKeyDown={event => {
      if (event.key === 'Escape' && open) {
        event.preventDefault()
        event.stopPropagation()
        setOpen(false)
        triggerRef.current?.focus()
      }
    }}>
      <button ref={triggerRef} type="button" className="btn btn-secondary" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
        <NavigationIcon name="download" />导出<NavigationIcon name="chevron" />
      </button>
      {open && (
        <div className="export-menu" id={panelId} role="group" aria-label="导出格式">
          <button onClick={() => doExport('json')}>JSON <span>完整数据</span></button>
          <button onClick={() => doExport('csv')}>CSV <span>电子表格</span></button>
          <button onClick={() => doExport('pdf')}>PDF <span>打印与阅读</span></button>
        </div>
      )}
    </div>
  )
}
