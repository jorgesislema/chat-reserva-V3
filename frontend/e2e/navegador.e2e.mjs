import { chromium } from '@playwright/test'
import { mkdirSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'

const shots = join(tmpdir(), 'saas-e2e-shots')
mkdirSync(shots, { recursive: true })
const BASE = 'http://localhost:5173'
let failed = 0

async function check(page, name, fn) {
  try {
    await fn()
    console.log(`OK   ${name}`)
  } catch (e) {
    failed++
    console.log(`FAIL ${name}: ${e.message.split('\n')[0]}`)
  }
}

const browser = await chromium.launch()

// ---------- Desktop ----------
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
try {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await page.screenshot({ path: join(shots, '01-login.png') })
  await page.fill('#apiKey', 'sk-test')
  await page.click('button[type="submit"]')
  await page.waitForURL('**/dashboard', { timeout: 15000 })

  await check(page, 'dashboard visible', async () => {
    await page.waitForSelector('h1:has-text("Dashboard")', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '02-dashboard.png') })

  // Config: identidad
  await page.goto(BASE + '/config', { waitUntil: 'networkidle' })
  await check(page, 'config identidad', async () => {
    await page.waitForSelector('text=Identidad del negocio', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '03-config.png') })

  // Catalogo: crear articulo (tab Servicios)
  await page.click('text=Servicios')
  await check(page, 'tab servicios', async () => {
    await page.waitForSelector('text=Catálogo de servicios y productos', { timeout: 15000 })
  })
  await page.fill('#item_name', 'Limpieza dental')
  await page.fill('#item_desc', 'Limpieza con ultrasonidos y pulido')
  await page.fill('#item_price', '4500')
  await page.fill('#item_inventory', '10')
  await page.click('button:has-text("Nuevo artículo")')
  await check(page, 'articulo creado en catalogo', async () => {
    await page.waitForSelector('text=Limpieza dental', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '04-catalogo-creado.png') })

  // Recursos
  await page.goto(BASE + '/resources', { waitUntil: 'networkidle' })
  await check(page, 'recursos listados desde API', async () => {
    await page.waitForSelector('h1:has-text("Recursos")', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '05-recursos.png') })

  // Horarios (recurso seleccionado si hay)
  await page.goto(BASE + '/schedules', { waitUntil: 'networkidle' })
  await check(page, 'horarios visible', async () => {
    await page.waitForSelector('h1:has-text("Horarios")', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '06-horarios.png') })

  // Alertas
  await page.goto(BASE + '/alerts', { waitUntil: 'networkidle' })
  await check(page, 'alertas visible', async () => {
    await page.waitForSelector('h1:has-text("Alertas de Handoff")', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '07-alertas.png') })

  // Persistencia: recargar catalogo y comprobar que el articulo sigue
  await page.goto(BASE + '/config', { waitUntil: 'networkidle' })
  await page.click('text=Servicios')
  await check(page, 'articulo persiste tras recargar', async () => {
    await page.waitForSelector('text=Limpieza dental', { timeout: 15000 })
  })

  // 401 honesto: logout + bad request JSON desde la UI
  await page.evaluate(() => window.localStorage.clear())
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await page.fill('#apiKey', 'sk-invalida')
  await page.click('button[type="submit"]')
  await check(page, 'login rechazado con API key invalida', async () => {
    await page.waitForSelector('text=API key inválida o expirada', { timeout: 15000 })
  })
  await page.screenshot({ path: join(shots, '08-login-rechazado.png') })
} finally {
  await page.close()
}

// ---------- Movil ----------
const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
try {
  await mobile.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await mobile.fill('#apiKey', 'sk-test')
  await mobile.click('button[type="submit"]')
  await mobile.waitForURL('**/dashboard', { timeout: 15000 })
  await mobile.screenshot({ path: join(shots, 'm01-dashboard-movil.png') })
  await mobile.goto(BASE + '/alerts', { waitUntil: 'networkidle' })
  await mobile.screenshot({ path: join(shots, 'm02-alertas-movil.png') })
} finally {
  await mobile.close()
}

await browser.close()
console.log(failed === 0 ? '\nE2E: TODOS LOS CHECKS OK' : `\nE2E: ${failed} checks FALLARON`)
process.exit(failed === 0 ? 0 : 1)
