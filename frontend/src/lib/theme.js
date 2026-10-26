export const THEME_PREFERENCES = ['system', 'light', 'dark']

export function normalizeThemePreference(value) {
  return THEME_PREFERENCES.includes(value) ? value : 'system'
}

export function resolveTheme(preference, systemDark) {
  return preference === 'dark' || (preference === 'system' && systemDark) ? 'dark' : 'light'
}
