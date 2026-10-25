import { useState, useEffect } from 'react'
import NavigationIcon from './NavigationIcon'

export default function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    try { return localStorage.getItem('theme') !== 'light' }
    catch { return true }
  })

  useEffect(() => {
    const theme = dark ? 'dark' : 'light'
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', theme) } catch { /* 浏览器禁用存储时仍允许本次切换。 */ }
  }, [dark])

  return (
    <button
      type="button"
      className="utility-item"
      onClick={() => setDark(value => !value)}
      aria-label={`外观主题：当前为${dark ? '深色' : '浅色'}，切换${dark ? '浅色' : '深色'}模式`}
    >
      <NavigationIcon name={dark ? 'moon' : 'sun'} />
      <span className="utility-copy"><span className="utility-title">外观主题</span><span className="utility-description">当前为{dark ? '深色' : '浅色'}</span></span>
      <span className="utility-action">切换{dark ? '浅色' : '深色'}</span>
    </button>
  )
}
