import { useState, useEffect } from 'react'
import NavigationIcon from './NavigationIcon'
import { normalizeThemePreference, resolveTheme } from '../lib/theme'

const systemThemeQuery = '(prefers-color-scheme: dark)'
const options = [
  { value: 'system', label: '跟随系统', icon: 'settings' },
  { value: 'light', label: '浅色', icon: 'sun' },
  { value: 'dark', label: '深色', icon: 'moon' },
]

function getSystemDark() {
  return window.matchMedia(systemThemeQuery).matches
}

export default function ThemeToggle() {
  const [preference, setPreference] = useState(() => {
    try { return normalizeThemePreference(localStorage.getItem('theme')) }
    catch { return 'system' }
  })
  const [systemDark, setSystemDark] = useState(getSystemDark)
  const theme = resolveTheme(preference, systemDark)

  useEffect(() => {
    const media = window.matchMedia(systemThemeQuery)
    const followSystem = event => setSystemDark(event.matches)
    setSystemDark(media.matches)
    media.addEventListener('change', followSystem)
    return () => media.removeEventListener('change', followSystem)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', preference) } catch { /* 存储不可用时仍保留本次选择。 */ }
  }, [preference, theme])

  return (
    <div className="theme-settings">
      <div className="theme-settings-heading">
        <span className="utility-title">外观主题</span>
        <span className="utility-description">{preference === 'system' ? `跟随系统 · 当前${theme === 'dark' ? '深色' : '浅色'}` : '使用手动选择的主题'}</span>
      </div>
      <div className="theme-options" role="group" aria-label="外观主题">
        {options.map(option => (
          <button
            key={option.value}
            type="button"
            className={`theme-option${preference === option.value ? ' active' : ''}`}
            aria-pressed={preference === option.value}
            onClick={() => setPreference(option.value)}
          >
            <NavigationIcon name={option.icon} />
            <span>{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
