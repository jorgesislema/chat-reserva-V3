// Diagnóstico del goto a bandeja tras agenda (check 7 del e2e cita_excepcional).
// Uso: node diag_goto_inbox.mjs <BASE>
// Reproduce: login -> bandeja -> tomar -> 2 citas (API) -> agenda -> intentar
// volver a la bandeja, registrando URL, readyState y tiempo por paso.
import { chromium } from '@playwright/test'

const BASE = process.argv[2] || 'http://127.0.0.1:8050'
const b = await chromium.launch()
const page = await b.newPage()
page.on('console', m => console.log('CONSOLE ' + m.type() + ' ' + m.text().slice(0, 140)))
page.on('pageerror', e => console.log('PAGEERROR ' + (e.message || e).slice(0, 160)))
page.on('dialog', d => d.accept())

async function paso(nombre, fn, to = 25000) {
  const t0 = Date.now()
  try {
    await fn(to)
    console.log('PASO_OK ' + nombre + ' (' + (Date.now() - t0) + 'ms)')
  } catch (e) {
    console.log('PASO_FAIL ' + nombre + ' (' + (Date.now() - t0) + 'ms): ' + (e.message || e).split('\n')[0])
  }
}

await paso('login', async to => {
  await page.goto(BASE + '/login', { timeout: to, waitUntil: 'domcontentloaded' })
  await page.fill('input[name="email"]', 'admin@exc.local')
  await page.fill('input[name="password"]', 'excepcion-password-123')
  const btn = page.locator('button:has-text("Ingresar")')
  try { await btn.click({ timeout: to, force: true }) } catch (e) {}
  await page.waitForURL(u => !/login/.test(u.pathname), { timeout: to })
  console.log('URL_TRAS_LOGIN ' + page.url())
})

// Ir directo: bandeja y ver tomar.
await paso('goto bandeja', async to => {
  await page.goto(BASE + '/?tab=inbox', { timeout: to, waitUntil: 'load' })
  await page.waitForSelector('#c02-inbox-app', { timeout: to })
})

await paso('goto agenda', async to => {
  await page.goto(BASE + '/?tab=agenda', { timeout: to, waitUntil: 'load' })
  console.log('READY_AGENDA ' + await page.evaluate(() => document.readyState))
})

await paso('evaluate en agenda', async to => {
  console.log('EVAL ' + await page.evaluate(() => location.href))
})

// 1) ¿El reload de la propia agenda funciona?
await paso('reload agenda', async to => {
  await page.reload({ timeout: to, waitUntil: 'domcontentloaded' })
  console.log('URL_TRAS_RELOAD ' + page.url())
})

// 2) ¿El goto a raíz funciona?
await paso('goto raiz', async to => {
  await page.goto(BASE + '/', { timeout: to, waitUntil: 'domcontentloaded' })
  console.log('URL_RAIZ ' + page.url())
})

// 3) ¿El goto a bandeja funciona AHORA? Miro readyState si falla el evento.
let okBandeja = false
try {
  await page.goto(BASE + '/?tab=inbox', { timeout: 25000, waitUntil: 'domcontentloaded' })
  okBandeja = true
  console.log('URL_BANDEJA2 ' + page.url() + ' READY ' + await page.evaluate(() => document.readyState))
} catch (e) {
  console.log('GOTO_BANDEJA2_FAIL: ' + (e.message || e).split('\n')[0])
  for (let i = 0; i < 6; i++) {
    await page.waitForTimeout(1500)
    let rs
    try {
      rs = await Promise.race([
        page.evaluate(() => document.readyState + '|' + location.pathname),
        new Promise(res => setTimeout(() => res('timeout-eval'), 4000))
      ])
    } catch (err) { rs = 'sin-pagina' }
    console.log('  t+' + ((i + 1) * 1500) + 'ms readyState=' + rs)
  }
}

await b.close()
console.log('DIAG_FIN okBandeja=' + okBandeja)
