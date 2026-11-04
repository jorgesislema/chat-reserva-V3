# -*- coding: utf-8 -*-
"""Verificacion del contraste del boton de tema (#theme-toggle) corregido en
la ronda que resuelve REVISION_RONDA_D_CODEX.

Reproduce la causa: en hover, la regla global button:hover (0,1,1) pintaba el
fondo #115d48 (verde oscuro) mientras .theme-toggle:hover (0,2,0) solo definia
color:var(--green) -> texto verde oscuro sobre fondo verde oscuro. La
correccion define explícitamente fondo/texto/borde y los estados
hover/focus-visible/active para claro y oscuro.

Uso (base temporal y datos ficticios del seed de la demo):
  1) Arrancar la demo:  CRM_DATABASE=%TEMP%/demo_checkpoint_20261029.db
                         CRM_PORT=8931 python run_crm.py
  2) PYTHONIOENCODING=utf-8 python scripts/verificar_boton_tema.py
Evidencia: docs/producto/consolidacion/evidencias/workspace/correccion-boton-tema/
Sin secretos: credenciales del seed ficticio de la demo local."""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8931'
OUT = pathlib.Path(r'H:\git\chat-clinica-dental - copia\chat-reserva-V3\docs\producto\consolidacion\evidencias\workspace\correccion-boton-tema')
OUT.mkdir(parents=True, exist_ok=True)
ADMIN = ('admin@demo.invalid', 'demo-abc-12345')

results = {'checks': [], 'estados': [], 'capturas': []}
MIN_RATIO = 4.5


def check(name, ok, detail=''):
    results['checks'].append({'check': name, 'ok': bool(ok), 'detail': str(detail)})
    print(('PASS ' if ok else 'FAIL ') + name + (' :: ' + str(detail) if detail else ''))


def shot(page, nombre):
    tema = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.screenshot(path=str(OUT / nombre))
    results['capturas'].append({'archivo': nombre, 'tema_verificado': tema})
    print('  captura %s (tema=%s)' % (nombre, tema))


def colores(page):
    """Estilos computados reales del boton (fondo resuelto, sin transparente)."""
    return page.evaluate("""() => {
      function lum(t){ var m=t.match(/[\\d.]+/g); if(!m||m.length<3) return null;
        var c=m.slice(0,3).map(function(v){v=+v/255;
          return v<=0.03928? v/12.92 : Math.pow((v+0.055)/1.055,2.4);});
        return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]; }
      function ratio(a,b){ var la=lum(a),lb=lum(b); if(la==null||lb==null) return null;
        var hi=Math.max(la,lb),lo=Math.min(la,lb); return (hi+0.05)/(lo+0.05); }
      var el=document.getElementById('theme-toggle');
      var cs=getComputedStyle(el);
      var bg=cs.backgroundColor;
      if (bg==='rgba(0, 0, 0, 0)') bg=getComputedStyle(document.documentElement).backgroundColor;
      return {bg: bg, fg: cs.color, border: cs.borderColor, outline: cs.outline,
              ratio: ratio(cs.color, bg),
              texto: el.textContent.trim(), tema: document.documentElement.getAttribute('data-theme')};
    }""")


def tomar_estado(page, etiqueta, estado, captura=None):
    c = colores(page)
    ok = c['ratio'] is not None and c['ratio'] >= MIN_RATIO
    results['estados'].append({'tema': c['tema'], 'estado': estado, 'etiqueta': etiqueta,
                               'bg': c['bg'], 'fg': c['fg'], 'border': c['border'],
                               'ratio': round(c['ratio'], 2) if c['ratio'] else None,
                               'ok': ok})
    check('contraste >= 4.5 :: %s' % etiqueta, ok,
          'ratio=%.2f bg=%s fg=%s texto=%s' % (c['ratio'], c['bg'], c['fg'], c['texto']))
    if captura:
        shot(page, captura)
    return c


def login(page):
    page.goto(BASE + '/login', wait_until='networkidle')
    page.fill('input[name=email]', ADMIN[0])
    page.fill('input[name=password]', ADMIN[1])
    page.click('form button')
    page.wait_for_selector('aside.sidebar', timeout=15000)
    page.wait_for_load_state('networkidle')


def foco_por_tab(page):
    """Lleva el foco real con Tab hasta #theme-toggle (activa :focus-visible)."""
    page.click('.brand')
    page.wait_for_timeout(120)
    for _ in range(25):
        activo = page.evaluate("document.activeElement && document.activeElement.id")
        if activo == 'theme-toggle':
            return True
        page.keyboard.press('Tab')
        page.wait_for_timeout(60)
    return False


def run_matriz(page, etiqueta, ancho, tema):
    """Reposo, hover, foco teclado y pulsacion en tema/tamano dados."""
    set_tema(page, tema)
    page.wait_for_timeout(200)
    prefijo = '%s-%s' % (tema, 'm' if ancho <= 414 else 'd')

    # A. Reposo: puntero fuera
    page.mouse.move(5, 5)
    page.wait_for_timeout(150)
    tomar_estado(page, etiqueta + ' reposo', 'reposo', '%s-reposo.png' % prefijo)

    # B. Hover: puntero encima
    page.hover('#theme-toggle')
    page.wait_for_timeout(180)
    tomar_estado(page, etiqueta + ' hover', 'hover', '%s-hover.png' % prefijo)

    # C. Foco de teclado (Tab, sin clic)
    ok_foco = foco_por_tab(page)
    check('foco por Tab en %s' % etiqueta, ok_foco)
    page.wait_for_timeout(120)
    toma = tomar_estado(page, etiqueta + ' foco', 'foco', '%s-foco.png' % prefijo)
    check('foco: outline perceptible en %s' % etiqueta,
          bool(toma.get('outline')) and 'none' not in toma['outline'],
          'outline=%s' % toma.get('outline'))

    # D. Pulsacion (:active)
    page.keyboard.press('Tab')  # dejar el foco
    page.hover('#theme-toggle')
    page.mouse.down()
    page.wait_for_timeout(120)
    tomar_estado(page, etiqueta + ' pulsacion', 'active', '%s-active.png' % prefijo)
    page.mouse.move(5, 5)  # soltar fuera para no disparar el clic/toggle
    page.mouse.up()
    page.wait_for_timeout(250)
    set_tema(page, tema)

    return toma


def set_tema(page, tema):
    for _ in range(3):
        actual = page.evaluate("document.documentElement.getAttribute('data-theme')")
        if actual == tema:
            return
        page.click('#theme-toggle')
        page.wait_for_timeout(250)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---------- Escritorio, tema claro ----------
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        errores_js = []
        page.on('pageerror', lambda e: errores_js.append(str(e)))
        login(page)
        page.evaluate("try{localStorage.removeItem('crm-theme')}catch(e){}")
        page.reload(wait_until='networkidle')
        run_matriz(page, 'escritorio claro', 1440, 'light')

        # Un clic cambia el tema una sola vez y el texto corresponde
        antes = page.evaluate("document.documentElement.getAttribute('data-theme')")
        texto_antes = page.eval_on_selector('#theme-toggle', 'function(e){return e.textContent.trim()}')
        page.click('#theme-toggle')
        page.wait_for_timeout(300)
        despues = page.evaluate("document.documentElement.getAttribute('data-theme')")
        texto_despues = page.eval_on_selector('#theme-toggle', 'function(e){return e.textContent.trim()}')
        stored = page.evaluate("localStorage.getItem('crm-theme')")
        check('un clic cambia el tema una sola vez', antes != despues,
              '%s -> %s' % (antes, despues))
        check('texto del boton corresponde al cambio ofrecido',
              (antes == 'light' and texto_antes == 'Modo oscuro' and texto_despues == 'Modo claro') or
              (antes == 'dark' and texto_antes == 'Modo claro' and texto_despues == 'Modo oscuro'),
              '%r -> %r' % (texto_antes, texto_despues))
        page.reload(wait_until='networkidle')
        check('preferencia persiste tras recargar',
              page.evaluate("document.documentElement.getAttribute('data-theme')") == despues,
              'stored=%s' % stored)
        ctx.close()

        # ---------- Escritorio, tema oscuro ----------
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        login(page)
        page.evaluate("try{localStorage.removeItem('crm-theme')}catch(e){}")
        page.reload(wait_until='networkidle')
        run_matriz(page, 'escritorio oscuro', 1440, 'dark')
        ctx.close()

        # ---------- Movil 414, claro y oscuro ----------
        for tema in ('light', 'dark'):
            ctx = browser.new_context(viewport={'width': 414, 'height': 896})
            page = ctx.new_page()
            login(page)
            page.evaluate("try{localStorage.removeItem('crm-theme')}catch(e){}")
            page.reload(wait_until='networkidle')
            run_matriz(page, 'movil %s' % tema, 414, tema)
            sc = page.evaluate('document.documentElement.scrollWidth')
            check('movil %s: sin desbordamiento global' % tema, sc <= 434, 'scrollWidth=%d' % sc)
            geo = page.evaluate("""() => {
              function g(s){ var el=document.querySelector(s); if(!el) return null;
                var r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; }
              var b=g('#theme-toggle'), u=g('.sidebar-bottom strong'), f=g('.sidebar-bottom form');
              var ov = b&&u&&f ? !(b.x+b.w<=u.x||u.x+u.w<=b.x||b.y+b.h<=u.y||u.y+u.h<=b.y) : false;
              return {overlap: ov, boton: b, user: u, form: f};
            }""")
            check('movil %s: cabecera sin solapamiento' % tema,
                  not geo['overlap'] and geo['boton'] and geo['user'] and geo['form'],
                  json.dumps({k: geo[k] for k in ('boton', 'user', 'form')}))
            shot(page, 'cabecera-movil-%s.png' % tema)
            ctx.close()

        browser.close()
        results['errores_js'] = errores_js

    n_ok = sum(1 for c in results['checks'] if c['ok'])
    n_fail = sum(1 for c in results['checks'] if not c['ok'])
    print('=' * 62)
    print('RESUMEN: %d checks, %d PASS, %d FAIL' % (len(results['checks']), n_ok, n_fail))
    print('Errores JS:', errores_js if errores_js else 'ninguno')
    print('ESTADOS MEDIDOS:')
    for e in results['estados']:
        print('  %-26s %-8s ratio=%-5s bg=%s fg=%s' % (e['etiqueta'], e['estado'], e['ratio'], e['bg'], e['fg']))
    print('CAPTURAS (%d unicas):' % len(results['capturas']))
    for c in results['capturas']:
        print('  %s (tema=%s)' % (c['archivo'], c['tema_verificado']))
    with open(str(OUT / 'resultados_boton_tema.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print('JSON en', OUT / 'resultados_boton_tema.json')
    sys.exit(0 if n_fail == 0 else 2)


if __name__ == '__main__':
    main()
