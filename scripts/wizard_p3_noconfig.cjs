/* Wizard E2E de navegador — Punto 3, escenario 8: modo operativo sin proveedor.
   Con CRM_CHAT_PROVEEDOR=abacus y SIN clave/endpoint, el chat debe responder
   «IA no configurada» y NUNCA una respuesta simulada silenciosa.
   Uso: node wizard_p3_noconfig.cjs BASE OUT
*/
const { chromium } = require(process.cwd() + '/frontend/node_modules/@playwright/test');

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage();
  const base = process.argv[2], out = process.argv[3];
  const fails = [];
  const check = (name, cond) => { console.log(cond ? name + '_PASS' : name + '_FAIL'); if (!cond) fails.push(name); };

  try {
    await p.goto(base + '/login');
    await p.fill('input[name=email]', 'admin@fixture.local');
    await p.fill('input[name=password]', 'fixture-password-123');
    await p.getByRole('button', { name: /Ingresar/ }).click();
    await p.waitForURL(u => !u.pathname.includes('login'));
    await p.goto(base + '/?tab=catalog');

    await p.fill('#c02-chat-input', '¿a qué hora abren?');
    await p.click('#c02-chat-send');
    await p.waitForFunction(() => {
      const last = Array.from(document.querySelectorAll('#c02-chat-log .inbox-message')).pop();
      return last && /IA no configurada/.test(last.textContent || '');
    }, null, { timeout: 20000 });
    const badge = await p.locator('#c02-chat-fuente').textContent() || '';
    check('P3_NO_CONFIG_AVISO', true);
    check('P3_NO_CONFIG_NOSIMULA', /IA no configurada/.test(badge));
    const todo = await p.locator('#c02-chat-log').textContent() || '';
    check('P3_NO_CONFIG_SIN_SIMULACION', !/lunes a viernes|sabado/.test(todo));
    await p.screenshot({ path: out + '/p3-noconfig.png', fullPage: true });
    console.log(fails.length ? 'P3_NOCONFIG_FAIL ' + fails.join(',') : 'P3_NOCONFIG_OK');
  } finally {
    await b.close();
  }
})().catch(e => { console.error('P3_NOCONFIG_ERROR', e.message); process.exitCode = 1; });
