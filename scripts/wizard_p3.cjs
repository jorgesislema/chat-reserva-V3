/* Wizard E2E de navegador — Punto 3 (productos reales, sin simulaciones).
   Escenarios recorridos en un navegador real:
   1) Cargar documento de oficina -> previsualizar -> guardar borrador -> publicar.
   2) Consultar contenido en el chat y comprobar que muestra fuentes.
   3) Editar/publicar otra versión y comprobar la actualización.
   4) Desactivar documento y comprobar que deja de recuperarse.
   5) Importar inventario válido (cantidades verificadas en BD por el harness).
   6) Importar lote inválido y comprobar rechazo con CERO cambios (harness).
   7) Usuario sin permisos no obtiene borradores (cubierto por tests HTTP).
   8) Modo operativo sin proveedor: el chat no simula (fase p3noconfig).
   Uso: node wizard_p3.cjs BASE OUT DOCX1 DOCX2 CSV_OK CSV_BAD
*/
const { chromium } = require(process.cwd() + '/frontend/node_modules/@playwright/test');
const path = require('path');

(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage();
  const base = process.argv[2], out = process.argv[3];
  const docx1 = path.resolve(process.argv[4]);
  const docx2 = path.resolve(process.argv[5]);
  const csvOk = path.resolve(process.argv[6]);
  const csvBad = path.resolve(process.argv[7]);
  const fails = [];
  const check = (name, cond) => { console.log(cond ? name + '_PASS' : name + '_FAIL'); if (!cond) fails.push(name); };

  const importarCSV = async (ruta, esperaTexto) => {
    const btn = p.locator('#c02-inventory-zone button').first();
    await btn.waitFor({ state: 'visible', timeout: 15000 });
    const fc = p.waitForEvent('filechooser', { timeout: 15000 });
    await btn.click();
    await (await fc).setFiles(ruta);
    await p.getByRole('button', { name: 'Siguiente: asociar columnas', exact: true }).click();
    await p.getByRole('button', { name: 'Previsualizar cambios', exact: true }).click();
    await p.locator('#c02-inventory-zone').getByText(esperaTexto).waitFor({ timeout: 15000 });
  };

  try {
    await p.goto(base + '/login');
    await p.fill('input[name=email]', 'admin@fixture.local');
    await p.fill('input[name=password]', 'fixture-password-123');
    await p.getByRole('button', { name: /Ingresar/ }).click();
    await p.waitForURL(u => !u.pathname.includes('login'));
    await p.goto(base + '/?tab=catalog');

    // ==== 1) Documento: cargar .docx -> previsualizar -> borrador -> publicar ====
    await p.click('#c02-kb-new');
    const fc1 = p.waitForEvent('filechooser');
    await p.click('#c02-kb-file');
    await (await fc1).setFiles(docx1);
    await p.click('#c02-kb-preview');
    await p.locator('#c02-kb-preview-box .kb-preview-body').getByText(/lunes a viernes/).waitFor({ timeout: 20000 });
    await p.fill('#c02-kb-name', 'Horarios E2E');
    await p.click('#c02-kb-form button[type=submit]');
    await p.locator('#c02-catalog-app .status-line').getByText(/guardado como borrador/).waitFor({ timeout: 20000 });
    const row = () => p.locator('#c02-kb-table tbody tr', { hasText: 'Horarios E2E' });
    await row().getByText('Borrador').waitFor({ timeout: 10000 });
    check('P3_DOC_DRAFT', true);
    await p.screenshot({ path: out + '/p3-doc-draft.png', fullPage: true });
    await row().getByRole('button', { name: 'Publicar' }).click();
    await row().getByText('Publicado').waitFor({ timeout: 10000 });
    check('P3_DOC_PUBLICADO', true);
    await p.screenshot({ path: out + '/p3-doc-publicado.png', fullPage: true });

    const preguntar = async (pregunta, textoRe) => {
      // Espera la RESPUESTA del servidor en el log: los mensajes del usuario
      // son `.out` y la propia pregunta podría matchear el regex (falso
      // positivo); por eso se filtra a mensajes que NO son de salida.
      const n = await p.locator('#c02-chat-log .inbox-message:not(.out)').count();
      await p.fill('#c02-chat-input', pregunta);
      await p.click('#c02-chat-send');
      await p.waitForFunction(([re, idx]) => {
        return Array.from(document.querySelectorAll('#c02-chat-log .inbox-message:not(.out)'))
          .slice(idx).some(m => re.test(m.textContent || ''));
      }, [textoRe, n], { timeout: 20000 });
    };

    // ==== 2) Consultar contenido y comprobar fuentes ====
    await preguntar('¿atiende de lunes a viernes?', /lunes a viernes/);
    const fuente1 = await p.locator('#c02-chat-fuente').textContent() || '';
    check('P3_CHAT_FUENTE_KB', /Conocimiento/.test(fuente1));
    const notas1 = await p.locator('#c02-chat-log .note').allTextContents();
    check('P3_CHAT_SOURCES_V1', notas1.some(t => /Horarios E2E/.test(t) && /v1/.test(t)));
    await p.screenshot({ path: out + '/p3-chat-v1.png', fullPage: true });

    // ==== 3) Editar y publicar otra versión; comprobar actualización ====
    await row().getByRole('button', { name: 'Editar' }).click();
    await p.waitForSelector('#c02-kb-dialog[open]');
    await p.waitForFunction(() => {
      const v = document.getElementById('c02-kb-body').value || '';
      return v.includes('lunes a viernes');
    }, null, { timeout: 15000 });
    await p.fill('#c02-kb-body', (await p.inputValue('#c02-kb-body')) + ' Los sábados de 9:00 a 13:00.');
    await p.click('#c02-kb-form button[type=submit]');
    await p.locator('#c02-catalog-app .status-line').getByText(/guardado como borrador/).waitFor({ timeout: 20000 });
    await row().getByRole('button', { name: 'Publicar' }).click();
    await row().getByText('Publicado').waitFor({ timeout: 10000 });
    // Espera el re-render con la versión nueva (v2): la tabla muestra la
    // versión como número simple en la celda 4 (no 'v2').
    await p.waitForFunction(() => {
      const r = Array.from(document.querySelectorAll('#c02-kb-table tbody tr'))
        .find(x => (x.textContent || '').includes('Horarios E2E'));
      return r && (r.children[3]?.textContent || '').trim() === '2';
    }, null, { timeout: 10000 });
    check('P3_DOC_V2', true);
    await preguntar('¿atiende el sabado?', /9:00 a 13:00/);
    const notas2 = await p.locator('#c02-chat-log .note').allTextContents();
    check('P3_CHAT_SOURCES_V2', notas2.some(t => /Horarios E2E/.test(t) && /v2/.test(t)));
    await p.screenshot({ path: out + '/p3-chat-v2.png', fullPage: true });

    // ==== 4) Desactivar y comprobar que deja de recuperarse ====
    await row().getByRole('button', { name: 'Desactivar' }).click();
    await row().getByText(/Inactivo|desactivado/).waitFor({ timeout: 10000 });
    check('P3_DOC_DESACTIVADO', true);
    const notasAntes3 = await p.locator('#c02-chat-log .note').count();
    await preguntar('¿atiende el sabado?', /No encontré|no hay información|absten/);
    // Compara contra las notas NUEVAS (después de la última pregunta), no el
    // historial de la v2.
    const notas3 = await p.locator('#c02-chat-log .note').allTextContents();
    check('P3_CHAT_DESACTIVADO_SIN_FUENTES', !notas3.slice(notasAntes3).join(' ').includes('Horarios E2E'));
    await p.screenshot({ path: out + '/p3-chat-desactivado.png', fullPage: true });

    // ==== 5) Importar inventario VÁLIDO ====
    await importarCSV(csvOk, /Nuevas: 1/);
    p.once('dialog', d => d.accept());
    await p.getByRole('button', { name: 'Aplicar importación', exact: true }).click();
    await p.locator('#c02-inventory-zone').getByText(/quedó registrada/).waitFor({ timeout: 20000 });
    check('P3_INV_VALIDO_APLICADO', true);
    await p.screenshot({ path: out + '/p3-inv-valido.png', fullPage: true });

    // ==== 6) Importar lote INVÁLIDO -> rechazo completo ====
    await importarCSV(csvBad, /Errores: 1/);
    p.once('dialog', d => d.accept());
    await p.getByRole('button', { name: 'Aplicar importación', exact: true }).click();
    await p.locator('#c02-inventory-zone .status-line.error').getByText(/rechazó completa/).waitFor({ timeout: 20000 });
    check('P3_INV_INVALIDO_RECHAZADO', true);
    await p.screenshot({ path: out + '/p3-inv-rechazado.png', fullPage: true });

    console.log(fails.length ? 'P3_WIZARD_FAIL ' + fails.join(',') : 'P3_WIZARD_OK');
  } finally {
    await b.close();
  }
})().catch(e => { console.error('P3_WIZARD_ERROR', e.message); process.exitCode = 1; });
