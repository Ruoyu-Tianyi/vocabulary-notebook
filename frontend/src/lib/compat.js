// 只读取历史浏览器偏好；新设置统一写入 Vocove 的键。
export function readLegacyWordSort(storage) {
  return storage.getItem('vocabulary-word-sort')
}
