'use strict'

// 随机端口改变 localStorage 的 origin；只恢复已知界面偏好，不暴露任何主进程 API。
const encoded = process.argv.find(argument => argument.startsWith('--vocove-preferences='))
const expectedOrigin = process.argv.find(argument => argument.startsWith('--vocove-origin='))
const windowId = process.argv.find(argument => argument.startsWith('--vocove-window='))
if (encoded && expectedOrigin && windowId && location.origin === expectedOrigin.slice('--vocove-origin='.length)) {
  try {
    const preferences = JSON.parse(encoded.slice('--vocove-preferences='.length))
    if (sessionStorage.getItem('vocove-desktop-window') !== windowId) {
      for (const key of ['theme', 'vocove-word-sort']) {
        const value = preferences[key]
        const valid = (key === 'theme' && ['light', 'dark'].includes(value)) ||
          (key === 'vocove-word-sort' && ['', 'created_asc', 'created_desc', 'alpha_asc', 'alpha_desc'].includes(value))
        if (valid) localStorage.setItem(key, value)
        else localStorage.removeItem(key)
      }
      sessionStorage.setItem('vocove-desktop-window', windowId)
    }
  } catch { /* 偏好不可用时继续使用前端默认值。 */ }
}
