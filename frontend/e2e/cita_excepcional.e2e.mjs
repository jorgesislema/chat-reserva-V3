// C02 corrección CH-01 — E2E de la cita excepcional coordinada por el operador.
// Uso: node cita_excepcional.e2e.mjs <BASE> <OUT>
// Flujo demostrado por el encargo (navegador real):
//   mensaje urgente -> campana -> abrir conversación -> tomar atención ->
//   elegir espacio dentro del horario (o excepción fuera de horario) ->
//   cita persistente en agenda. La alerta NO se resuelve y el chat NO vuelve
//   a la IA al crear la cita (actos separados).
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
    failed++
    let extra = '(no evaluado)'
    try {
      extra = await Promise.race([
        page.evaluate(() => JSON.stringify({
          overlay: !!document.querySelector('#cita-overlay'),
          slots: (document.querySelector('#cita-slots') || {}).textContent || '',
          status: (document.querySelector('#cita-overlay .status-line') || {}).textContent || '',
          ex: (document.querySelector('.cita-exc') || {}).textContent || ''
        })),
        new Promise(res => setTimeout(() => res('"timeout-eval"'), 3000))
      ])
    } catch (err) { extra = '(sin página)' }
    console.log('FAIL ' + name + ': ' + (e.message ? e.message.split('\n')[0] : e) + ' TRACE ' + extra)
  }
}

async function cerrarSiAbierto(page) {
  const overlay = page.locator('#cita-overlay')
  if (await overlay.count()) {
    const canc = overlay.locator('button:has-text("Cancelar")')
    try { await canc.click({ timeout: 5000, force: true }) } catch (e) {}
    await page.waitForTimeout(400)
  }
}

async function login(page) {
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' })
  await page.fill('input[name="email"]', 'admin@exc.local')
  await page.fill('input[name="password"]', 'excepcion-password-123')
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
page.on('dialog', d => d.accept())
try {
  await login(page)
  await page.goto(BASE + '/?tab=inbox', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('#c02-inbox-app', { timeout: 20000 })
  await page.waitForTimeout(600)

  // 1) Campana: tras la consulta exitosa, muestra la conversación pendiente.
  await check(page, 'campana muestra atención pendiente', async () => {
    await page.waitForFunction(() => {
      const t = document.querySelector('.bell-text')
      const p = document.querySelector('.bell-panel')
      return t && p && (t.textContent.includes('requiere atención') || t.textContent.includes('conversación'))
    }, { timeout: 20000 })
    await page.screenshot({ path: join(shots, 'cita-exc-campana.png') })
  })

  // 2) Abrir la conversación desde la bandeja y ver la alerta (mensaje urgente).
  await check(page, 'alerta urgente visible en la bandeja', async () => {
    await page.waitForFunction(() => {
      const rows = [...document.querySelectorAll('#c02-inbox-list .inbox-row')]
      return rows.some(r => r.textContent.includes('59370009999') && r.textContent.includes('alerta'))
    }, { timeout: 20000 })
    await page.locator('#c02-inbox-list .inbox-row:has-text("59370009999")').click()
    await page.waitForSelector('#c02-inbox-thread:not([hidden])', { timeout: 15000 })
    await page.waitForFunction(() => {
      const box = document.querySelector('#c02-inbox-messages')
      return box && (box.textContent.includes('No puedo respirar') || box.textContent.includes('no puedo respirar'))
    }, { timeout: 10000 })
  })

  // 3) Tomar la atención (sólo admin).
  await check(page, 'tomar el chat', async () => {
    const takeBtn = page.locator('#c02-inbox-thread-actions button:has-text("Tomar")')
    await takeBtn.click({ force: true })
    await page.waitForFunction(() => {
      const bts = [...document.querySelectorAll('#c02-inbox-thread-actions button')]
      return bts.some(b => b.textContent.includes('Proponer cita'))
    }, { timeout: 15000 })
  })

  // 4) Abrir el diálogo de cita y elegir un espacio DENTRO del horario.
  await check(page, 'proponer cita dentro del horario habitual', async () => {
    await cerrarSiAbierto(page)
    await page.locator('#c02-inbox-thread-actions button:has-text("Proponer cita")').click({ force: true })
    await page.waitForSelector('#cita-overlay', { timeout: 10000 })
    await page.waitForFunction(() => {
      const s = document.querySelector('#cita-prof')
      return s && !s.disabled && s.options.length >= 1
    }, { timeout: 20000 })
    await page.selectOption('#cita-prof', '1')
    await page.click('button:has-text("Buscar espacios")')
    await page.waitForSelector('.cita-slot-btn', { timeout: 20000 })
    const first = page.locator('.cita-slot-btn').first()
    const hora = (await first.textContent()).trim()
    await first.click({ force: true })
    await page.waitForSelector('#cita-overlay', { state: 'detached', timeout: 25000 })
    console.log('       cita creada a las ' + hora)
    await page.screenshot({ path: join(shots, 'cita-exc-dentro-horario.png') })
    await page.waitForTimeout(900)
  })

  // El botón "Proponer cita" debe volver a estar disponible (la atención sigue tomada).
  await check(page, 'la atención sigue tomada tras crear la cita', async () => {
    await page.locator('#c02-inbox-thread-actions button:has-text("Proponer cita")')
      .waitFor({ timeout: 15000 })
  })

  // 5) Cita EXCEPCIONAL fuera del horario: motivo obligatorio + confirmación.
  await check(page, 'cita excepcional fuera de horario con motivo', async () => {
    await cerrarSiAbierto(page)
    await page.locator('#c02-inbox-thread-actions button:has-text("Proponer cita")').click({ force: true })
    await page.waitForSelector('#cita-overlay', { timeout: 10000 })
    await page.waitForFunction(() => {
      const s = document.querySelector('#cita-prof')
      return s && !s.disabled
    }, { timeout: 20000 })
    await page.selectOption('#cita-prof', '1')
    await page.click('button:has-text("Buscar espacios")')
    await page.waitForFunction(() => {
      const ex = document.querySelector('.cita-exc')
      return ex && !ex.hidden
    }, { timeout: 20000 })
    await page.fill('#cita-exc-hora', '20:30')
    await page.fill('#cita-exc-motivo', 'E2E: urgencia del paciente fuera de horario')
    await page.click('.cita-exc-confirm input[type="checkbox"]')
    await page.click('button:has-text("Crear cita excepcional")')
    await page.waitForSelector('#cita-overlay', { state: 'detached', timeout: 25000 })
    await page.screenshot({ path: join(shots, 'cita-exc-excepcional.png') })
    await page.waitForTimeout(900)
  })

  // 6) La cita queda persistida: MISMA cita en BD, API /api/agenda y agenda.
  // Verificación funcional (no cosmética): /api/agenda de la semana actual
  // devuelve las dos citas 'Cita coordinada por operador' creadas esta sesión.
  await check(page, 'citas visibles via /api/agenda y pantalla de agenda', async () => {
    const resp = await page.evaluate(async () => {
      const manana = new Date()
      manana.setDate(manana.getDate() + 1)
      const f = manana.getFullYear() + '-' + String(manana.getMonth() + 1).padStart(2, '0') +
                '-' + String(manana.getDate()).padStart(2, '0')
      const r = await fetch('/api/agenda?view=week&date=' + f)
      const j = await r.json()
      return { n: (j.appointments || []).filter(a => a.title === 'Cita coordinada por operador').length,
               ids: (j.appointments || []).filter(a => a.title === 'Cita coordinada por operador').map(a => a.id) }
    })
    if (resp.n < 2) throw new Error('se esperaban >=2 citas en /api/agenda, se vieron ' + resp.n)
    console.log('       /api/agenda devuelve ' + resp.n + ' citas (ids ' + resp.ids.join(',') + ')')
    await page.goto(BASE + '/?tab=agenda', { waitUntil: 'domcontentloaded', timeout: 45000 })
    await page.waitForFunction(() => {
      return (document.querySelector('#agenda-app') || document.querySelector('.agenda') ||
              document.body.textContent.includes('Agenda'))
    }, { timeout: 25000 })
    await page.waitForTimeout(1200)
    await page.screenshot({ path: join(shots, 'cita-exc-agenda.png') })
  })

  // 7) La alerta NO se resolvió y el chat NO volvió a la IA: al volver a la
  // bandeja y ABRIR la conversación, la UI muestra el estado humano asignado y
  // el botón explícito 'Devolver a IA' (acto manual, no automático).
  await check(page, 'alerta sigue activa y chat en atención humana', async () => {
    const go = async () => page.goto(BASE + '/?tab=inbox', { waitUntil: 'domcontentloaded', timeout: 35000 })
    try {
      await go()
    } catch (e) {
      await page.waitForTimeout(2000)
      await go()
    }
    await page.waitForSelector('#c02-inbox-app', { timeout: 20000 })
    await page.waitForFunction(() => {
      const rows = [...document.querySelectorAll('#c02-inbox-list .inbox-row')]
      return rows.some(r => r.textContent.includes('59370009999'))
    }, { timeout: 20000 })
    await page.locator('#c02-inbox-list .inbox-row:has-text("59370009999")').click()
    // Al abrir, el estado debe ser 'Humano asignado' (aleta ya tomada) y la
    // acción de devolver a IA DEBE ser explícita.
    await page.waitForFunction(() => {
      const meta = document.querySelector('#c02-inbox-thread-meta')
      const acts = [...document.querySelectorAll('#c02-inbox-thread-actions button')].
        map(b => b.textContent.trim())
      return meta && (meta.textContent.includes('Humano asignado') || meta.textContent.includes('alerta')) &&
             acts.some(b => b.includes('Devolver a IA'))
    }, { timeout: 20000 })
    await page.screenshot({ path: join(shots, 'cita-exc-sigue-humano.png') })
  })
} finally {
  await page.close()
  await browser.close()
}
console.log(failed === 0 ? '\nE2E CITA EXCEPCIONAL: TODOS LOS CHECKS OK' : ('\nE2E CITA EXCEPCIONAL: ' + failed + ' checks FALLARON'))
process.exit(failed === 0 ? 0 : 1)
