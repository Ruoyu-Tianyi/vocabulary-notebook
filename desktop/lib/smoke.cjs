'use strict'

// 此函数整体在沙箱 renderer 中运行，必须只使用浏览器 API。
async function rendererSmoke() {
  function check(condition, message) { if (!condition) throw new Error(message) }
  async function request(url, method = 'GET', body) {
    const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
    check(response.ok, `请求未成功：${method} ${url} (${response.status})`)
    return response
  }
  async function json(url, method, body) { return (await request(url, method, body)).json() }
  const deadline = Date.now() + 10000
  while (!document.querySelector('#root a') && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 50))
  check(document.title === 'Vocove' && document.querySelector('#root a'), '界面未渲染')
  check(typeof require === 'undefined' && typeof process === 'undefined', 'renderer Node 权限未关闭')
  check((await json('/api/desktop/health')).status === 'ok', '后端未就绪')
  check((await json('/api/words')).total === 0, '冒烟词库不是空词库')
  const streamController = new AbortController()
  const stream = await fetch('/api/events', { signal: streamController.signal })
  const firstEvent = await stream.body.getReader().read()
  check(new TextDecoder().decode(firstEvent.value).includes('connected'), 'SSE 事件流未连接')
  streamController.abort()
  const created = await json('/api/words', 'POST', { word: 'desktop-smoke', definition: 'n. isolated desktop test' })
  const wordPath = `/api/words/${encodeURIComponent(created.word.id)}`
  check(created.enrichment.status === 'ready', '有释义词条不应调用模型')
  await json(wordPath, 'PUT', { definition: 'n. updated isolated desktop test' })
  const reviewed = await json(`${wordPath}/review`, 'POST', { rating: 3 })
  check(reviewed.word.srs.reps === 1, '复习记录未保存')
  const backup = await json('/api/library/export')
  check(backup.words.length === 1 && backup.operations.length > 0, '完整备份缺少词条或操作记录')
  await json('/api/library/import', 'POST', backup)
  check((await json(wordPath)).word.srs.reps === 1, '完整备份导入改变了复习记录')
  const csv = await (await request('/api/words/export?format=csv')).text()
  check(csv.includes('Desktop-smoke') && csv.includes('updated isolated desktop test'), 'CSV 导出内容不正确')
  const pdf = new Uint8Array(await (await request('/api/words/export?format=pdf')).arrayBuffer())
  check(new TextDecoder().decode(pdf.slice(0, 5)) === '%PDF-', 'PDF 导出内容不正确')
  const portable = await json('/api/words/export?format=json')
  await json(wordPath, 'DELETE')
  check((await json('/api/words')).total === 0, '删除词条失败')
  await json('/api/library/import', 'POST', portable)
  const restored = await json('/api/words')
  check(restored.total === 1 && restored.words[0].srs.reps === 1, '便携备份未恢复词条与复习进度')
  return { title: document.title, rendered: true, health: 'ok', initialEmpty: true, nodeUnavailable: true, sse: true, crud: true, review: true, backupImport: true, csvExport: true, jsonExport: true, pdfExport: true }
}

async function waitForSmokePaint() {
  // DOM 文本已出现时入场动画可能仍停在 opacity:0；截图必须等待合成帧可见。
  const deadline = Date.now() + 5000
  const frame = () => new Promise(resolve => requestAnimationFrame(resolve))
  while (Date.now() < deadline) {
    await frame()
    const card = [...document.querySelectorAll('.word-card')].find(item => item.innerText.includes('Desktop-smoke'))
    if (!card) continue
    const bounds = card.getBoundingClientRect()
    let visible = bounds.width > 0 && bounds.height > 0 && bounds.top >= 0 && bounds.top < innerHeight
    for (let element = card; element; element = element.parentElement) {
      const style = getComputedStyle(element)
      if (Number(style.opacity) < 0.99 || style.visibility !== 'visible' || style.display === 'none') visible = false
    }
    const animations = document.getAnimations().filter(animation => Number.isFinite(animation.effect?.getComputedTiming().endTime))
    if (!visible || animations.some(animation => animation.playState === 'running' || animation.pending)) continue
    const hit = document.elementFromPoint(bounds.left + bounds.width / 2, bounds.top + Math.min(bounds.height / 2, 10))
    if (!hit || !card.contains(hit)) continue
    await frame()
    await frame()
    return true
  }
  throw new Error('词条已载入但未完成可见绘制')
}

module.exports = { rendererSmoke, waitForSmokePaint }
