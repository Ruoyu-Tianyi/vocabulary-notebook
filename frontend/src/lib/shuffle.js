/** 种子显式决定顺序，重新洗牌可以可靠地触发 React 重新计算。 */
export function shuffle(items, seed) {
  const result = [...items]
  let state = seed >>> 0
  for (let index = result.length - 1; index > 0; index -= 1) {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0
    const swapIndex = Math.floor((state / 0x100000000) * (index + 1))
    ;[result[index], result[swapIndex]] = [result[swapIndex], result[index]]
  }
  return result
}
