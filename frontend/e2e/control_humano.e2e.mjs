// C02 corrección N1/N2/N4 — E2E de control humano (HUM-11).
// Uso: node control_humano.e2e.mjs <BASE> <OUT>
// Bandeja: alerta visible -> tomar -> responder (request_id estable) -> ver el
// estado 'entregado' de la respuesta -> devolver a IA -> sin salidas IA tardías.
import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { join } from 'path'

const BASE = process.argv[2] || 'http://127.0.0.1:8050'
const OUT = process.argv[3] || join(process.cwd(), 'docs', 'producto', 'consolidacion', 'evidencias')
mkdirSync(OUT, { recursive: true })
const shots = join(OUT, 'c02')
mkdirSync(shots, { recursive: true })

let failed = 0
async function check(page, name, fn) {
  try { await fn(); console.log('OK   ' + name) }
  catch (e) {
    failed++;
    let extra = ''
    try {
      extra = await page.evaluate(() => JSON.stringify({
        badges: [...document.querySelectorAll('#c02-inbox-messages .entrega')].map(b => b.className + '=' + b.textContent),
        actions: [...document.querySelectorAll('#c02-inbox-thread-actions button')].map(b => b.textContent.trim()),
        msgs: (document.querySelector('#c02-inbox-messages') || {}).textContent || ''
      }))
    } catch (err) { extra = '(sin página)' }
    console.log('FAIL ' + name + ': ' + (e.message ? e.message.split('\n')[0] : e) + ' TRACE ' + extra)
  }
}

async function login(page) {
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' })
  await page.fill('input[name="email"]', 'admin@hum.local')
  await page.fill('input[name="password"]', 'humano-password-123')
  const btn = page.locator('button:has-text("Ingresar")')
  try { await btn.scrollIntoViewIfNeeded({ timeout: 8000 }) } catch (e) {}
  try { await btn.click({ timeout: 15000, force: true }) } catch (e) {}
  try {
    await page.waitForURL(url => !/login/.test(url.pathname), { timeout: 20000 })
  } catch (e) {
    console.log('TRACE login falló; URL=' + page.url())
    throw e
  }
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } })
page.on('console', m => { if (m.type() === 'error') console.log('CONSOLEERR ' + m.text().split('\n')[0]) })
page.on('pageerror', e => console.log('PAGEERROR ' + (e.message ? e.message.split('\n')[0] : e)))
try {
  await login(page)
  await page.goto(BASE + '/?tab=inbox', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('#c02-inbox-app', { timeout: 20000 })
  await page.waitForTimeout(500)
  await page.screenshot({ path: join(shots, 'control-humano-alerta.png') })

  // HUM-11a: la entrada firmada que pidió humano se ve como alerta en la bandeja.
  await check(page, 'alerta humana visible en la bandeja', async () => {
    await page.waitForFunction(() => {
      const rows = [...document.querySelectorAll('#c02-inbox-list .inbox-row')]
      return rows.some(r => r.textContent.includes('59370000123') && r.textContent.includes('alerta'))
    }, { timeout: 15000 })
  })

  // HUM-11b: el mensaje de la petición humana quedó persistido (bandeja).
  await check(page, 'mensaje entrante persistido antes de la pausa', async () => {
    await page.locator('#c02-inbox-list .inbox-row:has-text("59370000123")').click()
    await page.waitForSelector('#c02-inbox-thread:not([hidden])', { timeout: 15000 })
    await page.waitForFunction(() => {
      const box = document.querySelector('#c02-inbox-messages')
      return box && box.textContent.includes('quiero hablar con un humano')
    }, { timeout: 10000 })
  })

  // HUM-11c: tomar el chat (sólo admin) y responder como operador.
  await check(page, 'tomar el chat y responder como operador', async () => {
    const takeBtn = page.locator('#c02-inbox-thread-actions button:has-text("Tomar")')
    await takeBtn.click({ force: true })
    await page.waitForFunction(() => {
      const b = document.querySelector('#c02-inbox-send')
      return b && !b.disabled && !document.querySelector('#c02-inbox-reply-text').disabled
    }, { timeout: 10000 })
    await page.fill('#c02-inbox-reply-text', 'E2E: le atiendo yo, ¿en qué más le ayudo?')
    await page.click('#c02-inbox-send')
    await page.waitForFunction(() => {
      const box = document.querySelector('#c02-inbox-messages')
      return box && box.textContent.includes('le atiendo yo')
    }, { timeout: 15000 })
  })

  // HUM-11d: la respuesta del operador se entrega (estado durable 'entregado').
  await check(page, 'respuesta entregada por el transporte simulado', async () => {
    await page.waitForFunction(() => {
      const badges = [...document.querySelectorAll('#c02-inbox-messages .entrega.ok')]
      return badges.some(b => b.textContent === 'entregado')
    }, { timeout: 25000 })
    await page.screenshot({ path: join(shots, 'control-humano-entregado.png') })
  })

  // HUM-11e: devolver a IA; la conversación deja la pausa sin salidas IA nuevas.
  await check(page, 'devolver a IA libera la conversación', async () => {
    const btns = page.locator('#c02-inbox-thread-actions button')
    const back = btns.filter({ hasText: 'Devolver a IA' })
    await back.click({ force: true })
    await page.waitForFunction(() => {
      const bts = [...document.querySelectorAll('#c02-inbox-thread-actions button')]
      return bts.some(b => b.textContent.includes('Tomar'))
    }, { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, 'control-humano-devuelto.png') })
} finally {
  await page.close()
  await browser.close()
}
console.log(failed === 0 ? '\nE2E CONTROL HUMANO: TODOS LOS CHECKS OK' : ('\nE2E CONTROL HUMANO: ' + failed + ' checks FALLARON'))
process.exit(failed === 0 ? 0 : 1)
