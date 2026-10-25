// 导入和同步得到的 ID 只作为一个路径片段，不能让斜杠或反斜杠改变导航目标。
export function wordDetailPath(id) {
  return `/word/${encodeURIComponent(id)}`
}

export function wordApiPath(id) {
  return `/words/${encodeURIComponent(id)}`
}
