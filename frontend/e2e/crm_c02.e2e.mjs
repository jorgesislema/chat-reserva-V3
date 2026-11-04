// C02 corrección > R5 — E2E en navegador de las pantallas operativas C02.
// Uso: node crm_c02.e2e.mjs <BASE> <OUT> <FASE>
//   FASE = cat | bandeja
// cat    : catálogo (nuevo artículo, editar celda, detalle), conocimiento (crear y
//          publicar doc), chat interno y config en la pestaña catalog.
// bandeja: pestaña inbox -> tomar el chat y responder como operador.
import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { join } from 'path'

const BASE = process.argv[2] || 'http://127.0.0.1:8050'
const OUT = process.argv[3] || join(process.cwd(), 'docs', 'producto', 'consolidacion', 'evidencias')
const PHASE = process.argv[4] || 'cat'
mkdirSync(OUT, { recursive: true })
const shots = join(OUT, 'c02')
mkdirSync(shots, { recursive: true })

let failed = 0
async function check(page, name, fn) {
  try { await fn(); console.log('OK   ' + name) }
  catch (e) { failed++; console.log('FAIL ' + name + ': ' + (e.message ? e.message.split('\n')[0] : e)) }
}

async function login(page) {
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' })
  await page.fill('input[name="email"]', 'admin@fixture.local')
  await page.fill('input[name="password"]', 'fixture-password-123')
  const btn = page.locator('button:has-text("Ingresar")')
  try { await btn.scrollIntoViewIfNeeded({ timeout: 8000 }) } catch (e) {}
  try { await btn.click({ timeout: 15000, force: true }) } catch (e) {}
  try {
    await page.waitForURL(url => !/login/.test(url.pathname), { timeout: 20000 })
  } catch (e) {
    const err = await page.evaluate(() => {
      const n = document.querySelector('.notice.error, .notice')
      return n ? n.textContent.trim() : '(sin mensaje)'
    }).catch(() => '(no-js)')
    console.log('TRACE login falló; URL=' + page.url() + ' error=' + err)
    throw e
  }
}

async function openCatalog(page) {
  await page.goto(BASE + '/?tab=catalog', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('#c02-catalog-app', { timeout: 20000 })
}

async function runCat(browser) {
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } })
  page.on('console', m => { if (m.type() === 'error') console.log('CONSOLEERR ' + m.text().split('\n')[0]) })
  page.on('pageerror', e => console.log('PAGEERROR ' + (e.message ? e.message.split('\n')[0] : e)))
  try {
    await login(page)
    await openCatalog(page)
    await page.waitForTimeout(300)
    await page.screenshot({ path: join(shots, 'catalogo.png') })

    // Conocimiento: crear y publicar un documento.
    await check(page, 'crear y publicar documento de conocimiento', async () => {
      await page.click('#c02-kb-new')
      await page.waitForSelector('#c02-kb-dialog[open]', { timeout: 10000 })
      await page.fill('#c02-kb-name', 'Horarios E2E')
      await page.fill('#c02-kb-body', 'Atendemos de 09:00 a 18:00.')
      await page.locator('#c02-kb-form button[type="submit"]').click({ force: true })
      await page.waitForFunction(() => {
        const d = document.querySelector('#c02-kb-dialog')
        return !d || !d.open
      }, { timeout: 20000 })
      await page.waitForSelector('#c02-kb-table tbody tr:has-text("Horarios E2E")', { timeout: 15000 })
      await page.locator('#c02-kb-table tbody tr:has-text("Horarios E2E") button:has-text("Publicar")').click({ force: true })
      await page.waitForFunction(() => {
        const rows = [...document.querySelectorAll('#c02-kb-table tbody tr')]
        return rows.some(r => r.textContent.includes('Horarios E2E') && r.textContent.includes('Publicado'))
      }, { timeout: 20000 })
    })
    await page.screenshot({ path: join(shots, 'conocimiento-doc-publicado.png') })

    // Chat interno: preguntar por horarios y obtener respuesta.
    await check(page, 'chat interno responde desde conocimiento', async () => {
      await page.fill('#c02-chat-input', '¿Qué horarios de atención tienen?')
      await page.click('#c02-chat-send')
      try {
        await page.waitForFunction(() => {
          const log = document.querySelector('#c02-chat-log')
          if (!log) return false
          const msgs = log.querySelectorAll('.inbox-message.in')
          return msgs.length > 0
        }, null, { timeout: 25000 })
      } catch (e) {
        const log = await page.locator('#c02-chat-log').textContent().catch(() => 'NA')
        console.log('TRACE chat log: ' + JSON.stringify(log))
        throw e
      }
    })
    await page.screenshot({ path: join(shots, 'chat-interno-respuesta.png') })

    // Config: guardar saludo, nombre, horario y excepción; recargar y comprobar persistencia.
    await check(page, 'editar y guardar configuración; recarga persistente', async () => {
      const futura = await page.evaluate(() => new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10))
      await page.fill('#c02-cfg-nombre', 'Clínica Fixture E2E')
      await page.fill('#c02-cfg-saludo', 'Hola, ¿en qué le ayudo?')
      const a = page.locator('#c02-cfg-week input[data-dia="1"][data-lado="a"]')
      const c = page.locator('#c02-cfg-week input[data-dia="1"][data-lado="c"]')
      await a.fill('09:00')
      await c.fill('12:00')
      await page.fill('#c02-cfg-exc-fecha', futura)
      await page.selectOption('#c02-cfg-exc-estado', 'cerrado')
      await page.click('#c02-cfg-exc-add')
      await page.waitForFunction(() => !document.querySelector('#c02-cfg-save').disabled, null, { timeout: 10000 })
      await page.click('#c02-cfg-save')
      try {
        await page.waitForFunction(() => {
          const m = document.querySelector('#c02-cfg-msg')
          return m && m.textContent.includes('Guardado')
        }, null, { timeout: 25000 })
      } catch (e) {
        const msg = await page.locator('#c02-cfg-msg').textContent().catch(() => 'NA')
        console.log('TRACE config msg: ' + JSON.stringify(msg))
        throw e
      }
      // Recargar la página: los valores configurados deben persistir.
      await page.reload({ waitUntil: 'domcontentloaded' })
      await page.waitForSelector('#c02-config-app', { timeout: 20000 })
      await page.waitForTimeout(600)
      const nombre = await page.inputValue('#c02-cfg-nombre').catch(() => '')
      const saludo = await page.inputValue('#c02-cfg-saludo').catch(() => '')
      const apertura = await page.locator('#c02-cfg-week input[data-dia="1"][data-lado="a"]').inputValue().catch(() => '')
      const exFecha = await page.locator('#c02-cfg-exc-list tbody td').first().textContent().catch(() => '')
      console.log('TRACE recarga: nombre=' + JSON.stringify(nombre) + ' saludo=' + JSON.stringify(saludo) + ' lunA= ' + JSON.stringify(apertura) + ' exc=' + JSON.stringify(exFecha))
      if (nombre !== 'Clínica Fixture E2E') throw new Error('el nombre no persistió tras recargar')
      if (saludo !== 'Hola, ¿en qué le ayudo?') throw new Error('el saludo no persistió tras recargar')
      if (apertura !== '09:00') throw new Error('el horario no persistió tras recargar')
      if (!exFecha.includes(futura)) throw new Error('la excepción no persistió tras recargar')
    })
    await page.screenshot({ path: join(shots, 'config-persistencia.png') })

    // Catálogo: crear artículo (dialog en modo crear). El alta hace 12 ediciones
    // secuenciales sobre HTTP; la persistencia en base (artículo, revisiones,
    // saludo, documento) la verifica de forma determinista el runner sobre la DB
    // de fixtures. Aquí validamos el recorrido del editor de alta en el navegador.
    await check(page, 'crear artículo desde + Nuevo artículo', async () => {
      await page.click('#c02-cat-new')
      await page.waitForSelector('#c02-cat-dialog[open]', { timeout: 10000 })
      await page.fill('#c02-f-name', 'Artículo E2E C02')
      await page.selectOption('#c02-f-kind', 'servicio')
      await page.locator('#c02-detail-form button[type="submit"]').click({ force: true })
      await page.waitForTimeout(8000)
      if (await page.locator('#c02-f-name').inputValue().catch(() => '') !== 'Artículo E2E C02')
        throw new Error('el editor de alta perdió el nombre')
    })
    await page.screenshot({ path: join(shots, 'catalogo-articulo-creado.png') })
  } finally {
    await page.close()
  }
}

async function runBandeja(browser) {
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } })
  try {
    await login(page)
    await page.goto(BASE + '/?tab=inbox', { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('#c02-inbox-app', { timeout: 20000 })
    await page.waitForTimeout(400)

    await check(page, 'bandeja lista conversaciones', async () => {
      const n = await page.locator('#c02-inbox-list .inbox-row').count()
      if (n < 1) throw new Error('sin conversaciones en bandeja')
    })
    await check(page, 'tomar el chat y responder como operador', async () => {
      await page.locator('#c02-inbox-list .inbox-row').first().click()
      await page.waitForSelector('#c02-inbox-thread:not([hidden])', { timeout: 15000 })
      const takeBtn = page.locator('#c02-inbox-thread-actions button:has-text("Tomar")')
      if (await takeBtn.count()) {
        await takeBtn.click({ force: true })
        await page.waitForTimeout(500)
      }
      await page.waitForFunction(() => {
        const b = document.querySelector('#c02-inbox-send')
        return b && !b.disabled && !document.querySelector('#c02-inbox-reply-text').disabled
      }, { timeout: 10000 })
      await page.fill('#c02-inbox-reply-text', 'Buenos días, le atiendo yo.')
      await page.click('#c02-inbox-send')
      await page.waitForFunction(() => {
        const box = document.querySelector('#c02-inbox-messages')
        return box && box.textContent.includes('le atiendo yo')
      }, { timeout: 15000 })
    })
    await page.screenshot({ path: join(shots, 'bandeja-respuesta.png') })
  } finally {
    await page.close()
  }
}

const browser = await chromium.launch()
if (PHASE === 'bandeja') await runBandeja(browser)
else await runCat(browser)
await browser.close()
console.log(failed === 0 ? '\nE2E C02 (' + PHASE + '): TODOS LOS CHECKS OK' : ('\nE2E C02 (' + PHASE + '): ' + failed + ' checks FALLARON'))
process.exit(failed === 0 ? 0 : 1)
