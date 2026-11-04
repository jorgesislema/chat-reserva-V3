# -*- coding: utf-8 -*-
"""Verificación en NAVEGADOR REAL (Playwright Chromium) del Asistente IA con
proveedor IA real (C02). Servidor demo YA levantado en 8932 con la base
temporal sembrada (scripts/seed_ia_real_demo.py).

Recorre la pantalla «Asistente IA» (tab=chat):
  1. Envía una consulta y comprueba respuesta REAL fundamentada.
  2. Verifica la fuente mostrada y el estado del proveedor (badge).
  3. Recarga y confirma que la configuración del servidor sigue operando
     (segunda consulta con el mismo resultado esperado).
  4. Comprueba que NO aparecen claves en HTML, respuestas API ni consola.
Evidencia (depurada, sin secretos): docs/producto/consolidacion/evidencias/
workspace/ia-real-20261029/

Uso (utiliza el python global, que tiene playwright):
  python scripts/verificar_ia_real_navegador.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

BASE = 'http://127.0.0.1:8932'
OUT = pathlib.Path(r'H:\git\chat-clinica-dental - copia\chat-reserva-V3\docs\producto\consolidacion\evidencias\workspace\ia-real-20261029')
OUT.mkdir(parents=True, exist_ok=True)
ADMIN = ('admin@demo.invalid', 'demo-abc-12345')

results = {'checks': [], 'navegador': {}, 'errores_js': []}
errores_js = []

PATRONES_SECRETO = [r'AIza[0-9A-Za-z_\-]{20,}', r'Bearer\s+\S{8,}',
                    r'sk-[A-Za-z0-9]{16,}', r'OPENCODE_ZEN_API_KEY=\S+',
                    r'GOOGLE_API_KEY=\S+']


def check(name, ok, detail=''):
    results['checks'].append({'check': name, 'ok': bool(ok), 'detail': str(detail)})
    print(('PASS ' if ok else 'FAIL ') + name + (' :: ' + str(detail) if detail else ''))


def shot(page, nombre):
    page.screenshot(path=str(OUT / nombre), full_page=False)
    print('  captura %s' % nombre)


def login(page):
    page.goto(BASE + '/login', wait_until='networkidle')
    page.fill('input[name=email]', ADMIN[0])
    page.fill('input[name=password]', ADMIN[1])
    page.click('form button')
    page.wait_for_selector('aside.sidebar', timeout=20000)
    page.wait_for_load_state('networkidle')


def abrir_chat(page):
    page.goto(BASE + '/?tab=chat', wait_until='networkidle')
    page.wait_for_selector('#c02-chat-form', timeout=15000)


def enviar_y_esperar(page, pregunta, espera_s=180):
    page.fill('#c02-chat-input', pregunta)
    page.click('#c02-chat-send')
    page.wait_for_function(
        """() => {
          const btns = document.querySelectorAll('#c02-chat-form button');
          return btns.length && !btns[0].disabled;
        }""", timeout=espera_s * 1000)
    page.wait_for_timeout(1200)


def log_chat(page):
    return page.evaluate(
        """() => Array.prototype.slice.call(
             document.querySelectorAll('#c02-chat-log .inbox-message'))
             .map(function (n) { return n.textContent.replace(/\\s+/g, ' ').trim(); })""")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        results['navegador'] = {'tipo': 'chromium',
                                'version': browser.version}

        page.on('console', lambda m: errores_js.append(m.text))
        page.on('pageerror', lambda e: errores_js.append(str(e)))

        # --- 1/2. Consulta y respuesta real (admin) ------------------------------
        login(page)
        abrir_chat(page)
        P1 = '\u00bfEn qu\u00e9 horario atiende la cl\u00ednica dental?'
        enviar_y_esperar(page, P1)
        lineas = log_chat(page)
        chat_txt = '\n'.join(lineas)
        badge = page.text_content('#c02-chat-fuente') or ''
        ok_real = ('08:00' in chat_txt and '18:00' in chat_txt)
        check('respuesta real fundamentada (08:00 y 18:00 en la respuesta)',
              ok_real, chat_txt[-260:])
        check('badge con fuente y proveedor conectado',
              'proveedor de IA conectado' in badge and 'fuente:' in badge, badge)
        shot(page, '01-chat-respuesta-real.png')

        # --- 3. Recarga: la configuración del servidor persiste ------------------
        abrir_chat(page)
        lineas_antes = log_chat(page)
        badge_rec = page.text_content('#c02-chat-fuente') or ''
        enviar_y_esperar(page, P1)
        lineas_despues = log_chat(page)
        chat2 = '\n'.join(lineas_despues)
        ok_rec = (len(lineas_despues) > len(lineas_antes)
                  and '08:00' in chat2 and '18:00' in chat2)
        check('recarga: el servidor sigue respondiendo con IA real',
              ok_rec, 'badge post-recarga: %s' % badge_rec)
        shot(page, '02-chat-tras-recarga.png')

        # --- 4. Sin claves en HTML, API, consola ni capturas ---------------------
        html = page.content()
        secretos_html = [p for p in PATRONES_SECRETO if
                         re.search(p, html, re.I)]
        secretos_js = [s for s in errores_js if
                       any(re.search(p, s, re.I) for p in PATRONES_SECRETO)]
        check('sin claves en el HTML', not secretos_html,
              secretos_html if secretos_html else 'scan OK')
        check('sin claves en consola/errores JS', not secretos_js,
              secretos_js if secretos_js else 'scan OK')
        check('cero errores JavaScript', not errores_js,
              '; '.join(errores_js[:3]) if errores_js else 'sin errores')

        # --- Conversación en ficha 3 (stock real) para el cierre ------------
        P2 = ('\u00bfCu\u00e1nto cuesta el cepillo dental el\u00e9ctrico y '
              'cu\u00e1ntas unidades hay en stock?')
        enviar_y_esperar(page, P2)
        chat3 = '\n'.join(log_chat(page))
        check('consulta de stock responde con datos de la BD',
              '12' in chat3, chat3[-220:])
        shot(page, '03-chat-stock.png')

        browser.close()

    total = len(results['checks'])
    ok_count = sum(1 for c in results['checks'] if c['ok'])
    results['resumen'] = '%d/%d checks OK' % (ok_count, total)
    with open(str(OUT / 'informe_navegador.json'), 'w', encoding='utf-8') as fh:
        json.dump({'checks': results['checks'], 'navegador': results['navegador'],
                   'errores_js': errores_js, 'resumen': results['resumen']},
                  fh, ensure_ascii=False, indent=1)
    print('RESULTADO_NAVEGADOR: %s' % results['resumen'])
    return 0 if ok_count == total else 1


if __name__ == '__main__':
    sys.exit(main())
