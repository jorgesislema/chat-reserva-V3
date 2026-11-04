# -*- coding: utf-8 -*-
"""Verificación navegador REAL (Playwright Chromium) de la alerta superior de
atención humana (C02).

Recorre (base demo local, datos ficticios, puerto 8931):
  1. Indicador visible desde dos secciones distintas (overview, inbox).
  2. Apertura correcta de la conversación desde la campana (deep-link).
  3. Persistencia tras recargar (el estado se relee del servidor).
  4. Tema claro y oscuro; viewport móvil 414 px.
  5. Recorrido pendiente -> En atención -> Atendida (toma y resolución reales
     desde la bandeja; la campana refleja los cambios y NO resuelve al abrir).
  6. Cero errores JavaScript (console/pageerror recogidos en el informe).

Evidencia: docs/producto/consolidacion/evidencias/workspace/atencion-humana-20261029/
Sin secretos: credenciales del seed ficticio de la demo local.
Uso (servidor demo ya levantado en 8931 con la base sembrada):
  python scripts/verificar_atencion.py
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8931'
OUT = pathlib.Path(r'H:\git\chat-clinica-dental - copia\chat-reserva-V3\docs\producto\consolidacion\evidencias\workspace\atencion-humana-20261029')
OUT.mkdir(parents=True, exist_ok=True)
ADMIN = ('admin@demo.invalid', 'demo-abc-12345')

results = {'checks': [], 'navegador': {}, 'errores_js': []}
errores_js = []


def check(name, ok, detail=''):
    results['checks'].append({'check': name, 'ok': bool(ok), 'detail': str(detail)})
    print(('PASS ' if ok else 'FAIL ') + name + (' :: ' + str(detail) if detail else ''))


def shot(page, nombre):
    tema = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.screenshot(path=str(OUT / nombre), full_page=False)
    print('  captura %s (tema=%s)' % (nombre, tema))


def login(page):
    page.goto(BASE + '/login', wait_until='networkidle')
    page.fill('input[name=email]', ADMIN[0])
    page.fill('input[name=password]', ADMIN[1])
    page.click('form button')
    page.wait_for_selector('aside.sidebar', timeout=15000)
    page.wait_for_load_state('networkidle')


def esperar_campana(page):
    page.wait_for_selector('#atencion-bell', timeout=10000)
    page.wait_for_selector('#atencion-bell .bell-count', timeout=10000)


def estado_campana(page):
    return page.evaluate("""() => {
      var root = document.getElementById('atencion-bell');
      var btn = root.querySelector('.bell-button');
      var count = root.querySelector('.bell-count');
      var text = root.querySelector('.bell-text');
      var prio = root.querySelector('.bell-prio');
      return {
        count: count.hidden ? 0 : parseInt(count.textContent, 10),
        aria: btn.getAttribute('aria-label'),
        texto: text.textContent.trim(),
        prio: prio.hidden ? null : prio.textContent.trim(),
        prioAlta: root.classList.contains('prio-alta'),
        prioNormal: root.classList.contains('prio-normal'),
        stale: root.classList.contains('stale')
      };
    }""")


def panel_flow(page):
    """Abre el panel y devuelve las filas de la campana."""
    page.click('#atencion-bell .bell-button')
    page.wait_for_timeout(300)
    return page.evaluate("""() => {
      var filas = Array.prototype.slice.call(document.querySelectorAll('#atencion-bell .bell-row'));
      return filas.map(function(li){
        var a = li.querySelector('a');
        return { href: a ? a.getAttribute('href') : null,
                 text: li.textContent.replace(/\\s+/g,' ').trim() };
      });
    }""")


def login_api():
    """Devuelve (jar, csrf): sesión HTTP autenticada con el CSRF vigente.

    El login hace session.clear() y el context_processor genera un csrf NUEVO
    en el primer GET autenticado, así que el CSRF debe leerse de una página
    posterior al login, no del formulario inicial."""
    import urllib.request
    import urllib.parse
    import http.cookiejar
    import re
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    r = op.open(BASE + '/login')
    html = r.read().decode('utf-8', 'replace')
    m = re.search(r'name="csrf-token" content="([0-9a-f]+)"', html)
    if not m:
        raise RuntimeError('No se obtuvo CSRF del meta de la pagina de login')
    data = urllib.parse.urlencode({'csrf': m.group(1), 'email': ADMIN[0],
                                   'password': ADMIN[1]}).encode()
    op.open(BASE + '/login', data=data)
    r = op.open(BASE + '/?tab=overview')
    html = r.read().decode('utf-8', 'replace')
    m2 = re.search(r'name="csrf-token" content="([0-9a-f]+)"', html)
    if not m2:
        raise RuntimeError('No se obtuvo el CSRF post-login')
    return jar, m2.group(1)


def main():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            print('ERROR lanzando Chromium:', exc)
            sys.exit(2)
        results['navegador'] = {'motor': 'chromium', 'version': browser.version}
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = ctx.new_page()
        page.on('console', lambda m: errores_js.append({'tipo': 'console', 'nivel': m.type, 'texto': m.text})
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: errores_js.append({'tipo': 'pageerror', 'texto': str(e)}))
        login(page)

        try:
            # --- 1. Indicador en dos secciones -------------------------------
            for tab, etiqueta in (('overview', 'Resumen'), ('inbox', 'Conversaciones')):
                page.goto(BASE + '/?tab=' + tab, wait_until='networkidle')
                esperar_campana(page)
                st = estado_campana(page)
                check('indicador presente en %s' % etiqueta,
                      st['count'] > 0 and 'requieren atención' in st['texto'],
                      json.dumps(st, ensure_ascii=False))
                shot(page, '01-indicador-%s.png' % tab)

            # --- 2. Apertura correcta de la conversación (deep-link) ---------
            page.goto(BASE + '/?tab=overview', wait_until='networkidle')
            esperar_campana(page)
            filas = panel_flow(page)
            abierta = [f for f in filas if f['href'] and f['href'].startswith('/?tab=inbox&conversation=')]
            check('panel lista pendientes con enlace a conversacion', len(abierta) > 0,
                  'filas=%d' % len(filas))
            shot(page, '02-panel-campana.png')
            if abierta:
                page.click('#atencion-bell .bell-row a')
                page.wait_for_timeout(1500)
                tiene_hilo = page.evaluate(
                    "!document.getElementById('c02-inbox-thread').hidden")
                check('deep-link abre la conversacion en la bandeja', tiene_hilo,
                      'url=%s' % page.url)
                shot(page, '03-bandeja-conversacion-abierta.png')

            # --- 3. Persistencia tras recargar -------------------------------
            page.goto(BASE + '/?tab=overview', wait_until='networkidle')
            esperar_campana(page)
            st1 = estado_campana(page)
            page.reload(wait_until='networkidle')
            esperar_campana(page)
            st2 = estado_campana(page)
            check('persistencia tras recargar (mismo contador)',
                  st1['count'] == st2['count'] and st1['count'] > 0,
                  'antes=%d despues=%d' % (st1['count'], st2['count']))

            # --- 4. Temas y móvil --------------------------------------------
            for tema in ('light', 'dark'):
                page.evaluate(
                    "document.documentElement.setAttribute('data-theme','%s')" % tema)
                page.wait_for_timeout(250)
                page.goto(BASE + '/?tab=overview', wait_until='networkidle')
                esperar_campana(page)
                st = estado_campana(page)
                check('campana visible en tema %s' % tema, st['count'] > 0,
                      json.dumps(st, ensure_ascii=False))
                shot(page, '04-campana-%s.png' % tema)
            page.evaluate("document.documentElement.removeAttribute('data-theme')")
            page.wait_for_timeout(200)

            mob = browser.new_context(viewport={'width': 414, 'height': 896},
                                      is_mobile=True, has_touch=True)
            pm = mob.new_page()
            pm.on('pageerror', lambda e: errores_js.append({'tipo': 'mobile-pageerror', 'texto': str(e)}))
            pm.goto(BASE + '/login', wait_until='networkidle')
            pm.fill('input[name=email]', ADMIN[0])
            pm.fill('input[name=password]', ADMIN[1])
            pm.click('form button')
            pm.wait_for_selector('aside.sidebar', timeout=15000)
            pm.wait_for_load_state('networkidle')
            esperar_campana(pm)
            stm = estado_campana(pm)
            check('campana en movil 414px', stm['count'] > 0,
                  json.dumps(stm, ensure_ascii=False))
            shot(pm, '05-campana-movil.png')
            filasm = panel_flow(pm)
            check('panel en movil con pendientes', len(filasm) >= 4,
                  'filas moviles=%d' % len(filasm))
            mob.close()

            # --- 5. Ciclo: pendiente -> en atención -> atendida --------------
            import urllib.request as urlr
            jar, csrf = login_api()
            op = urlr.build_opener(urlr.HTTPCookieProcessor(jar))
            op.addheaders = [('Accept', 'application/json'),
                             ('X-CSRF-Token', csrf)]

            with op.open(BASE + '/api/c02/atencion') as r:
                antes = json.loads(r.read().decode())
            check('panel HTTP inicial: 4 pendientes, 1 en atencion',
                  antes['total_pendientes'] == 4 and antes['total_en_atencion'] == 1,
                  json.dumps(antes))

            conv_a = next(c for c in antes['pendientes']
                          if any(a['reason'] == 'humano_explicito' for a in c['alerts']))
            take = op.open(urlr.Request(BASE + '/api/c02/inbox/%d/take' % conv_a['conversation_id'],
                                        data=b'{}', method='POST'))
            take.read()
            with op.open(BASE + '/api/c02/atencion') as r:
                medio = json.loads(r.read().decode())
            check('toma: pendientes 3 y en_atencion 2 con responsable',
                  medio['total_pendientes'] == 3 and medio['total_en_atencion'] == 2,
                  json.dumps(medio))
            page.goto(BASE + '/?tab=overview', wait_until='networkidle')
            esperar_campana(page)
            st_toma = estado_campana(page)
            check('campana refleja la toma del otro proceso',
                  st_toma['count'] == 3, json.dumps(st_toma, ensure_ascii=False))
            shot(page, '06-tras-toma.png')

            alerta_a = None
            with op.open(BASE + '/api/c02/atencion') as r:
                medio2 = json.loads(r.read().decode())
            for c in medio2['en_atencion']:
                if c['conversation_id'] == conv_a['conversation_id']:
                    alerta_a = c['alerts'][0]['alert_id']
            if alerta_a:
                mark = op.open(urlr.Request(
                    BASE + '/api/c02/inbox/alert/%d/mark' % alerta_a,
                    data=b'{"state":"resuelta"}', method='POST',
                    headers={'Content-Type': 'application/json'}))
                mark.read()
            with op.open(BASE + '/api/c02/atencion') as r:
                despues = json.loads(r.read().decode())
            check('resolucion: pendientes 3 y en_atencion 1 (solo la tomada)',
                  despues['total_pendientes'] == 3 and despues['total_en_atencion'] == 1,
                  json.dumps(despues))
            page.goto(BASE + '/?tab=overview', wait_until='networkidle')
            esperar_campana(page)
            st_res = estado_campana(page)
            check('campana apaga la atendida conservando contador',
                  st_res['count'] == 3, json.dumps(st_res, ensure_ascii=False))
            shot(page, '07-tras-resolucion.png')

            page.goto(BASE + '/?tab=overview', wait_until='networkidle')
            esperar_campana(page)
            st_abrir = estado_campana(page)
            panel_flow(page)
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            st_cerrar = estado_campana(page)
            check('abrir la campana no resuelve (contador intacto)',
                  st_abrir['count'] == st_cerrar['count'],
                  'abrir=%d cerrar=%d' % (st_abrir['count'], st_cerrar['count']))
        finally:
            browser.close()

    check('sin errores JavaScript', len(errores_js) == 0,
          json.dumps(errores_js[:5], ensure_ascii=False))
    results['errores_js'] = errores_js
    ok_total = all(c['ok'] for c in results['checks'])
    with open(OUT / 'informe.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print('INFORME', OUT / 'informe.json')
    print('RESULTADO', 'OK' if ok_total else 'FALLOS')
    sys.exit(0 if ok_total else 1)


main()
