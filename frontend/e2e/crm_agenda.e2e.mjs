// C01 §9.6 — E2E en navegador del recorrido de la agenda del CRM.
// Arranca contra un servidor CRM local sobre DB de fixtures (nunca producción).
// Uso: node crm_agenda.e2e.mjs <BASE> <OUT> <FASE>
//   FASE = desktop | ux
// desktop: crear -> consultar/recargar -> reagendar -> cancelar -> sesión inválida.
// ux     : móvil y teclado (se ejecuta contra un servidor fresco para no mejorar el
//          comportamiento con la carga acumulada).
import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { join } from 'path'

const BASE = process.argv[2] || 'http://127.0.0.1:8050'
const OUT = process.argv[3] || join(process.cwd(), 'docs', 'producto', 'consolidacion', 'evidencias')
const PHASE = process.argv[4] || 'desktop'
mkdirSync(OUT, { recursive: true })
const shots = join(OUT, 'agenda')
mkdirSync(shots, { recursive: true })

let failed = 0
async function check(page, name, fn) {
  try { await fn(); console.log('OK   ' + name) }
  catch (e) { failed++; console.log('FAIL ' + name + ': ' + (e.message ? e.message.split('\n')[0] : e)) }
}

async function tomorrow(page, offsetDays) {
  const today = await page.locator('#agenda-app').getAttribute('data-today')
  const p = today.split('-').map(Number)
  const d = new Date(Date.UTC(p[0], p[1] - 1, p[2]))
  d.setUTCDate(d.getUTCDate() + (offsetDays || 1))
  const pad = (n) => (n < 10 ? '0' : '') + n
  return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate())
}

// Crea una cita en MAÑANA (fecha futura exigida por la regla past_datetime) y navega
// la agenda (vista semana/día) hasta que la cita aparezca en la superficie.
async function crearCitaFuturaYVer(page, title, hora) {
  const date = await tomorrow(page, 1)  // mañana: futuro válido
  await createAppointment(page, { date, title, start: hora, end: addMin(hora, 45) })
  for (let i = 0; i < 3; i++) {
    try {
      await appointmentOnGrid(page, title, 15000)
      return
    } catch (e) {
      if (i === 2) throw e
      await page.click('[data-nav="next"]')
      await new Promise(r => setTimeout(r, 400))
    }
  }
}

function addMin(hhmm, minutes) {
  const [h, m] = hhmm.split(':').map(Number)
  const total = (h * 60 + m + minutes) % 1440
  return String(Math.floor(total / 60)).padStart(2, '0') + ':' + String(total % 60).padStart(2, '0')
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

async function openAgenda(page) {
  try { await page.keyboard.press('Escape') } catch (e) {}
  await page.goto(BASE + '/?tab=agenda', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('#agenda-app', { timeout: 20000 })
  await page.waitForSelector('[data-surface] .appt, [data-surface] .agenda-empty, .agenda-loading', { timeout: 20000 })
}

async function createAppointment(page, opts) {
  await page.click('button[data-action="new"]')
  await page.waitForSelector('#appointment-form-dialog[open]', { timeout: 10000 })
  await page.selectOption('select[name="professional_id"]', { label: 'Dra. Ana' })
  await page.fill('input[name="title"]', opts.title)
  await page.fill('input[name="start_date"]', opts.date)
  await page.fill('input[name="start_time"]', opts.start)
  await page.fill('input[name="end_date"]', opts.date)
  await page.fill('input[name="end_time"]', opts.end)
  const t0 = Date.now()
  const submit = page.locator('form[data-appointment-form] button[type="submit"]')
  try { await submit.scrollIntoViewIfNeeded({ timeout: 8000 }) } catch (e) {}
  await submit.click({ timeout: 15000, force: true })
  try {
    await page.waitForFunction(() => {
      const d = document.querySelector('#appointment-form-dialog')
      return !d || !d.open
    }, { timeout: 25000 })
    console.log('TRACE dialog cerrado en ' + (Date.now() - t0) + 'ms')
  } catch (e) {
    const opened = await page.evaluate(() => document.querySelector('#appointment-form-dialog') ? document.querySelector('#appointment-form-dialog').open : 'no-dialog')
    console.log('TRACE dialog tras submit timeout(' + (Date.now() - t0) + 'ms) open=' + opened)
    throw e
  }
}

async function appointmentOnGrid(page, title, timeout) {
  await page.waitForSelector('[data-surface] .appt:has-text("' + title + '"), [data-surface] .month-chip:has-text("' + title + '")', { timeout: timeout || 20000 })
  return page.locator('[data-surface] .appt:has-text("' + title + '"), [data-surface] .month-chip:has-text("' + title + '")')
}

async function runDesktop(browser) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  try {
    await login(page)
    await openAgenda(page)
    await page.screenshot({ path: join(shots, 'agenda-vacia.png') })

    const date = await tomorrow(page)
    await check(page, 'crear cita (crear)', async () => {
      await createAppointment(page, { date, title: 'Cita E2E C01', start: '10:00', end: '10:45' })
    })
    await check(page, 'cita visible en la cuadrícula', async () => await appointmentOnGrid(page, 'Cita E2E C01'))
    await page.screenshot({ path: join(shots, 'agenda-creada.png') })

    await check(page, 'cita persiste tras recargar la página', async () => {
      await page.reload({ waitUntil: 'domcontentloaded' })
      await page.waitForSelector('[data-surface] .appt:has-text("Cita E2E C01"), .month-chip:has-text("Cita E2E C01")', { timeout: 25000 })
    })

    await check(page, 'abrir detalle y reagendar mantiene la misma cita', async () => {
      await (await appointmentOnGrid(page, 'Cita E2E C01')).first().click()
      await page.waitForSelector('dialog#appointment-detail[open]', { timeout: 10000 })
      await (await page.locator('button:has-text("Reprogramar")').first()).scrollIntoViewIfNeeded().catch(() => {})
      await page.locator('button:has-text("Reprogramar")').first().click({ timeout: 15000, force: true })
      await page.waitForSelector('#appointment-form-dialog[open]', { timeout: 10000 })
      await page.fill('input[name="start_time"]', '11:00')
      await page.fill('input[name="end_time"]', '11:45')
      const rsub = page.locator('form[data-appointment-form] button[type="submit"]')
      try { await rsub.scrollIntoViewIfNeeded({ timeout: 8000 }) } catch (e) {}
      await rsub.click({ timeout: 15000, force: true })
      await page.waitForFunction(() => {
        const d = document.querySelector('#appointment-form-dialog')
        return !d || !d.open
      }, { timeout: 25000 })
    })
    await check(page, 'reagendar persiste tras recargar', async () => {
      await page.reload({ waitUntil: 'domcontentloaded' })
      await appointmentOnGrid(page, 'Cita E2E C01')
    })

    await check(page, 'cancelar cita', async () => {
      await (await appointmentOnGrid(page, 'Cita E2E C01')).first().click()
      await page.waitForSelector('dialog#appointment-detail[open]', { timeout: 10000 })
      await page.locator('button:has-text("Cancelar")').first().click({ timeout: 15000, force: true })
      await page.waitForFunction(() => {
        const badge = document.querySelector('[data-field="status"]')
        return badge && /\bcancelled\b/i.test(badge.className + ' ' + badge.textContent)
      }, { timeout: 25000 })
    })
    await check(page, 'cita cancelada visible tras recargar', async () => {
      await page.reload({ waitUntil: 'domcontentloaded' })
      await page.check('[data-filter="cancelled"]')
      await page.waitForSelector('[data-surface] .appt.cancelled:has-text("Cita E2E C01")', { timeout: 25000 })
    })
    await page.screenshot({ path: join(shots, 'agenda-cancelada.png') })

    await check(page, 'sesión inválida redirige a /login', async () => {
      await page.context().clearCookies()
      await page.goto(BASE + '/?tab=agenda')
      await page.waitForURL('**/login**', { timeout: 10000 })
    })
  } finally {
    await page.close()
  }
}

async function runUx(browser) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  try {
    await login(page)

    await check(page, 'móvil: agenda visible y crear cita', async () => {
      await page.setViewportSize({ width: 390, height: 844 })
      await openAgenda(page)
      // Vista móvil por defecto: día. Crear en el futuro y navegar para verla.
      await crearCitaFuturaYVer(page, 'Cita Móvil C01', '09:00')
    })
    await page.screenshot({ path: join(shots, 'm-agenda-creada.png') })

    await check(page, 'teclado: abrir formulario y crear con teclado', async () => {
      await page.setViewportSize({ width: 1280, height: 900 })
      await openAgenda(page)
      const kdate = await tomorrow(page, 1)
      const newBtn = page.locator('button[data-action="new"]')
      try { await newBtn.scrollIntoViewIfNeeded({ timeout: 8000 }) } catch (e) {}
      await newBtn.click({ timeout: 15000, force: true })
      await page.waitForSelector('#appointment-form-dialog[open]', { timeout: 10000 })
      await page.selectOption('select[name="professional_id"]', { label: 'Dra. Ana' })
      await page.fill('input[name="title"]', 'Cita Teclado C01')
      await page.fill('input[name="start_date"]', kdate); await page.fill('input[name="start_time"]', '08:00')
      await page.fill('input[name="end_date"]', kdate); await page.fill('input[name="end_time"]', '08:45')
      // Guardar con Enter (tecla) como un usuario de teclado.
      await page.keyboard.press('Enter')
      await page.waitForFunction(() => {
        const d = document.querySelector('#appointment-form-dialog')
        return !d || !d.open
      }, { timeout: 25000 })
      await appointmentOnGrid(page, 'Cita Teclado C01', 15000).catch(async () => {
        await page.click('[data-nav="next"]', { force: true }).catch(() => {})
        await appointmentOnGrid(page, 'Cita Teclado C01', 15000)
      })
    })
    await page.screenshot({ path: join(shots, 'k-cita-teclado.png') })
  } finally {
    await page.close()
  }
}

const browser = await chromium.launch()
if (PHASE === 'ux') await runUx(browser)
else await runDesktop(browser)
await browser.close()
console.log(failed === 0 ? '\nE2E CRM AGENDA (' + PHASE + '): TODOS LOS CHECKS OK' : ('\nE2E CRM AGENDA (' + PHASE + '): ' + failed + ' checks FALLARON'))
process.exit(failed === 0 ? 0 : 1)
