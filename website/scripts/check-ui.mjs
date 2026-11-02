import { spawn } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const root = fileURLToPath(new URL('../', import.meta.url))
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
if (!existsSync(chromePath)) throw new Error('Set CHROME_PATH to a local Chrome executable')
mkdirSync(`${root}artifacts`, { recursive: true })

const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '7100', '--strictPort'], {
  cwd: root,
  stdio: ['ignore', 'pipe', 'pipe'],
})
let serverOutput = ''
server.stdout.on('data', (chunk) => { serverOutput += chunk })
server.stderr.on('data', (chunk) => { serverOutput += chunk })

async function waitForServer() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch('http://127.0.0.1:7100/')
      if (response.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`Vite did not start:\n${serverOutput}`)
}

let browser
try {
  await waitForServer()
  browser = await chromium.launch({ executablePath: chromePath, headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 })
  const errors = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('pageerror', (error) => errors.push(error.message))
  const revealPage = async () => {
    await page.evaluate(async () => {
      document.documentElement.style.scrollBehavior = 'auto'
      for (let y = 0; y < document.body.scrollHeight; y += 500) {
        window.scrollTo(0, y)
        await new Promise((resolve) => setTimeout(resolve, 80))
      }
      window.scrollTo(0, 0)
    })
    await page.waitForTimeout(300)
  }

  await page.goto('http://127.0.0.1:7100/', { waitUntil: 'networkidle' })
  await page.screenshot({ path: `${root}artifacts/desktop-hero.png` })
  const desktopOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  await page.getByRole('button', { name: /显示释义/ }).first().click()
  await page.waitForTimeout(700)
  const flipWorks = await page.locator('.hero .word-card').evaluate((card) => card.classList.contains('is-flipped')
    && card.querySelector('.word-card-front').getAttribute('aria-hidden') === 'true'
    && getComputedStyle(card.querySelector('.word-card-inner')).transform !== 'none')
  await page.getByRole('button', { name: /良好/ }).first().click()
  const ratingVisible = await page.getByText(/已选择「良好」/).isVisible()
  await page.getByRole('tab', { name: /补全理解/ }).click()
  const enrichVisible = await page.getByText('AI 内容补全', { exact: true }).isVisible()
  // 等待点击触发的平滑滚动结束，避免滚动监听覆盖紧接着的键盘切换。
  await page.waitForTimeout(700)
  await page.getByRole('tab', { name: /补全理解/ }).focus()
  await page.keyboard.press('ArrowDown')
  const keyboardFlowWorks = await page.getByRole('tab', { name: /适时复习/ }).getAttribute('aria-selected') === 'true'
  await page.waitForTimeout(700)
  await page.locator('#flow-tab-1').evaluate((element) => window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.38))
  await page.waitForTimeout(700)
  const scrollFlowWorks = await page.locator('#flow-tab-1').getAttribute('aria-selected') === 'true'
  await page.locator('#faq details').nth(1).locator('summary').click()
  const faqVisible = await page.getByText(/已有词库的浏览和复习可以在本机进行/).isVisible()
  await page.waitForTimeout(200)
  const navStateWorks = await page.locator('.main-nav a[href="#faq"]').getAttribute('aria-current') === 'location'
  await revealPage()
  await page.screenshot({ path: `${root}artifacts/desktop-full.png`, fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('http://127.0.0.1:7100/', { waitUntil: 'networkidle' })
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  await page.screenshot({ path: `${root}artifacts/mobile-hero.png` })
  await page.getByRole('button', { name: '打开菜单' }).click()
  await page.getByRole('link', { name: '学习流程' }).waitFor({ state: 'visible' })
  const menuVisible = await page.getByRole('link', { name: '学习流程' }).isVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '打开菜单' }).waitFor({ state: 'visible' })
  const menuEscapeWorks = await page.getByRole('button', { name: '打开菜单' }).isVisible()
  await page.getByRole('button', { name: '打开菜单' }).click()
  await page.getByRole('link', { name: '学习流程' }).click()
  await page.getByRole('button', { name: '打开菜单' }).waitFor({ state: 'visible' })
  const menuClosed = await page.getByRole('button', { name: '打开菜单' }).isVisible()
  await revealPage()
  await page.screenshot({ path: `${root}artifacts/mobile-full.png`, fullPage: true })

  const responsiveOverflows = []
  for (const width of [320, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('http://127.0.0.1:7100/', { waitUntil: 'networkidle' })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
    if (overflow) responsiveOverflows.push(width)
  }
  const brokenAnchors = await page.evaluate(() => [...document.querySelectorAll('a[href^="#"]')]
    .map((link) => link.getAttribute('href'))
    .filter((href) => href !== '#' && !document.getElementById(href.slice(1))))
  const expectedDownloads = [
    'https://github.com/Eric-Zhou-0302/vocove/releases/download/v1.5.1/Vocove-1.5.1-mac-arm64.dmg',
    'https://github.com/Eric-Zhou-0302/vocove/releases/download/v1.5.1/Vocove-1.5.1-mac-x64.dmg',
    'https://github.com/Eric-Zhou-0302/vocove/releases/download/v1.5.1/Vocove-1.5.1-win-x64.exe',
  ]
  const actualDownloads = await page.locator('.platform-actions a').evaluateAll((links) => links.map((link) => link.href))
  const downloadLinksValid = expectedDownloads.every((url) => actualDownloads.includes(url)) && actualDownloads.length === expectedDownloads.length

  const reducedPage = await browser.newPage({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' })
  await reducedPage.goto('http://127.0.0.1:7100/', { waitUntil: 'networkidle' })
  await reducedPage.evaluate(() => window.scrollTo(0, 500))
  await reducedPage.waitForTimeout(100)
  const reducedMotionWorks = await reducedPage.evaluate(() => [...document.querySelectorAll('[data-reveal]')].every((element) => element.classList.contains('is-visible'))
    && !document.querySelector('.hero').style.getPropertyValue('--hero-scroll'))
  await reducedPage.close()

  const result = { desktopOverflow, mobileOverflow, responsiveOverflows, brokenAnchors, downloadLinksValid, flipWorks, ratingVisible, enrichVisible, keyboardFlowWorks, scrollFlowWorks, faqVisible, navStateWorks, menuVisible, menuEscapeWorks, menuClosed, reducedMotionWorks, consoleErrors: errors }
  console.log(JSON.stringify(result, null, 2))
  if (desktopOverflow || mobileOverflow || responsiveOverflows.length || brokenAnchors.length || !downloadLinksValid || !flipWorks || !ratingVisible || !enrichVisible || !keyboardFlowWorks || !scrollFlowWorks || !faqVisible || !navStateWorks || !menuVisible || !menuEscapeWorks || !menuClosed || !reducedMotionWorks || errors.length) process.exitCode = 1
} finally {
  if (browser) await browser.close()
  server.kill('SIGTERM')
}
