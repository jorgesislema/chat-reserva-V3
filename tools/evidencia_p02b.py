"""Evidencia real P02B: casos fuera de 07–20, medianoche, inactivos, mes y presentación.

Uso (raíz del repo, entorno con Flask y Playwright):
    python tools/evidencia_p02b.py

Datos ficticios, Google simulado, bases temporales en .pytest_cache. Guarda capturas y
resumen en docs/producto/evidencias/p02b/ sin tocar analitica.db ni .venv-crm.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import shutil
import sys
import threading

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

from crm import reservation_service as rs
from crm.app import create_app
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
EVIDENCE = ROOT / 'docs' / 'producto' / 'evidencias' / 'p02b'
WORK = ROOT / '.pytest_cache' / 'p02b-evidence'
PASSWORD = 'evidencia-password-123'


def local_dt(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute)


def seed(path):
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,?,?,?,?)",
                   ('admin@example.invalid', 'Operador Demo',
                    generate_password_hash(PASSWORD), 'admin'))
        for pid, name, email in ((1, 'Ana Torres', 'ana@example.invalid'),
                                 (2, 'Luis Prado', 'luis@example.invalid'),
                                 (3, 'Marta Ruiz', 'marta@example.invalid')):
            db.execute("INSERT INTO crm_professionals(id,name,specialty,email) VALUES (?,?,?,?)",
                       (pid, name, 'Odontología general', email))
        for lid, name, phone in ((1, 'Paciente Demo Uno', '593900000001'),
                                 (2, 'Paciente Demo Dos', '593900000002'),
                                 (3, 'Paciente Demo Tres', '593900000003'),
                                 (4, 'Paciente Demo Cuatro', '593900000004')):
            db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) VALUES (?,?,?,?,?)",
                       (lid, name, phone, 'x', 'x'))

    now = datetime.now(ZoneInfo(TZ))
    target = (now + timedelta(days=1)).date()
    create_day = target + timedelta(days=2)

    def create(start, minutes, prof, title, lead=1):
        start_utc = start.replace(tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)
        result = rs.save_appointment(
            str(path), professional_id=prof, start=start.isoformat(),
            end=(start + timedelta(minutes=minutes)).isoformat(), title=title,
            zone=TZ, lead_id=lead, actor=1, clock=start_utc - timedelta(hours=1))
        assert result['ok'], result
        return result['appointment']

    # Casos visuales solicitados (horas locales del negocio).
    create(local_dt(target - timedelta(days=1), 22), 180, 3, 'Antes del rango')
    create(local_dt(target, 5), 60, 1, 'Muy temprano')
    create(local_dt(target, 10), 60, 3, 'Inactivo visible')
    create(local_dt(target, 21), 60, 1, 'Muy tarde')
    create(local_dt(target, 23), 120, 2, 'Cruza medianoche')
    control = create(local_dt(target, 15), 60, 1, 'Control')
    rs.reprogram_appointment(
        str(path), appointment_id=control['id'],
        start=local_dt(target, 16).isoformat(), end=local_dt(target, 17).isoformat(),
        title=None, zone=TZ, expected_version=control['row_version'],
        reason='Cambio de evidencia', actor=1)
    rs.add_note(str(path), appointment_id=control['id'],
                body='Observación interna ficticia para la evidencia', author=1)
    create(local_dt(target, 17), 60, 2, 'Seguimiento')
    quiet = target + timedelta(days=4)
    create(local_dt(quiet - timedelta(days=1), 22), 180, 2, 'Antes de quieta')
    create(local_dt(quiet, 23), 120, 1, 'Medianoche quieta')
    with connect(path) as db:
        db.execute('UPDATE crm_professionals SET active=0 WHERE id=3')
    return {'target': target.isoformat(), 'create_day': create_day.isoformat(),
            'offset': (target - now.date()).days,
            'create_offset': (create_day - now.date()).days}


def contrast_script():
    return r"""
    (function(){
      function rgb(value){
        var m = value.match(/[\d.]+/g); if(!m) return [0,0,0];
        return [Number(m[0]),Number(m[1]),Number(m[2])];
      }
      function lum(value){
        var c = rgb(value).map(function(v){ v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055,2.4); });
        return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2];
      }
      function ratio(fg,bg){
        var a=lum(fg), b=lum(bg);
        return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
      }
      var tick = document.querySelector('.axis .tick');
      var arrow = document.querySelector('.icon-button');
      var result = {};
      if(tick){ var ts=getComputedStyle(tick); result.tick=ratio(ts.color, 'rgb(255,255,255)'); }
      if(arrow){ var as=getComputedStyle(arrow); result.arrow=ratio(as.color, 'rgb(255,255,255)'); }
      return result;
    })()
    """


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    path = WORK / 'agenda.db'
    info = seed(path)
    app = create_app({'TESTING': True, 'DATABASE': str(path), 'SECRET_KEY': 'evidence',
                      'TIMEZONE': TZ})
    server = make_server('127.0.0.1', 0, app)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{port}'

    console = []
    bad_responses = []
    failures = []
    results = {'url': base, 'target': info['target'], 'create_day': info['create_day'],
               'views': {}, 'flows': {}, 'overflow': {}}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        server.shutdown()
        raise SystemExit(f'Playwright no disponible: {exc}. Validación visual pendiente.') from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.add_init_script("""
                window.__delayWeek = false;
                window.__originalFetch = window.fetch.bind(window);
                window.fetch = function(url, options) {
                  if (window.__delayWeek && String(url).indexOf('view=week') !== -1) {
                    window.__delayWeek = false;
                    return new Promise(function(resolve){ setTimeout(resolve, 900); })
                      .then(function(){ return window.__originalFetch(url, options); });
                  }
                  return window.__originalFetch(url, options);
                };
            """)
            page.on('console', lambda msg: console.append(
                {'type': msg.type, 'text': msg.text}) if msg.type in ('error', 'warning') else None)
            page.on('pageerror', lambda error: console.append(
                {'type': 'pageerror', 'text': str(error)}))
            page.on('response', lambda response: bad_responses.append(
                (response.status, response.url)) if response.status >= 400 else None)

            page.goto(base + '/login')
            page.fill('input[name="email"]', 'admin@example.invalid')
            page.fill('input[name="password"]', PASSWORD)
            page.click('button[type="submit"], button')
            page.wait_for_url(base + '/')
            page.goto(base + '/?tab=agenda')
            page.wait_for_selector('.agenda-surface')

            target = info['target']

            def set_view(view):
                page.click(f'[data-view="{view}"]')
                page.wait_for_selector('.day-wrap, .week-wrap, .month-wrap')
                page.wait_for_timeout(250)

            def go_day(offset):
                page.click('[data-nav="today"]')
                page.wait_for_timeout(150)
                set_view('day')
                for _ in range(max(0, offset)):
                    page.click('[data-nav="next"]')
                    page.wait_for_timeout(150)
                page.wait_for_selector('.day-wrap')

            def card_bounds_ok(selector):
                return page.evaluate("""
                  (sel) => {
                    const cards = Array.from(document.querySelectorAll(sel));
                    return cards.every(card => {
                      const lane = card.closest('.day-lane, .week-body');
                      if (!lane) return false;
                      const c = card.getBoundingClientRect();
                      const l = lane.getBoundingClientRect();
                      return c.top >= l.top - 2 && c.bottom <= l.bottom + 2;
                    });
                  }
                """, selector)

            # Día objetivo: horas extremas, medianoche, inactivo y continuación.
            go_day(info['offset'])
            titles = page.locator('.appt strong').all_inner_texts()
            for expected in ('Muy temprano', 'Muy tarde', 'Cruza medianoche',
                             'Antes del rango', 'Inactivo visible'):
                if expected not in titles:
                    failures.append(f'No se ve la cita esperada en Día: {expected}')
            inactive_head = page.locator('.day-head:has-text("Marta Ruiz")')
            if not inactive_head.count() or 'inactivo' not in inactive_head.first.inner_text().lower():
                failures.append('La vista Día/Todos no muestra el carril del profesional inactivo.')
            if page.locator('[data-cell][data-professional="3"]').count():
                failures.append('Se permiten altas en un profesional inactivo desde la rejilla.')
            if not card_bounds_ok('.appt'):
                failures.append('Hay citas recortadas o fuera de su carril en Día.')
            axis = page.locator('.axis .tick').all_inner_texts()
            if '05:00' not in axis or '21:00' not in axis:
                failures.append('La rejilla no muestra franjas 05:00/21:00.')
            results['flows']['dia_horas_inactivo'] = 'ok'

            # Capturas de la rejilla con citas en 360/768/1440.
            for width in (360, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 900})
                go_day(info['offset'])
                page.screenshot(path=str(EVIDENCE / f'day-{width}.png'), full_page=True)
                results['views'].setdefault('day', []).append(f'day-{width}.png')
                page.click('[data-view="week"]')
                page.wait_for_selector('.week-wrap')
                page.wait_for_timeout(200)
                page.screenshot(path=str(EVIDENCE / f'week-{width}.png'), full_page=True)
                results['views'].setdefault('week', []).append(f'week-{width}.png')
                page.click('[data-view="month"]')
                page.wait_for_selector('.month-wrap')
                page.wait_for_timeout(200)
                page.screenshot(path=str(EVIDENCE / f'month-{width}.png'), full_page=True)
                results['views'].setdefault('month', []).append(f'month-{width}.png')
                overflow = page.evaluate(
                    'document.documentElement.scrollWidth > window.innerWidth + 2')
                results['overflow'][f'{width}'] = overflow
                if overflow:
                    failures.append(f'Desbordamiento horizontal de página a {width}px.')

            page.set_viewport_size({'width': 1440, 'height': 900})

            # Mes: intersecciones y continuaciones de medianoche.
            set_view('month')
            antes = page.locator('.month-chip:has-text("Antes de quieta")')
            medianoche = page.locator('.month-chip:has-text("Medianoche quieta")')
            if antes.count() < 2:
                failures.append('Mes no representa la cita que empieza antes de un día en ambos días.')
            if medianoche.count() < 2:
                failures.append('Mes no representa la cita de medianoche en ambos días.')
            if not page.locator('.month-chip.continuation-start').count():
                failures.append('Mes no distingue continuación desde el día anterior.')
            if not page.locator('.month-chip.continuation-end').count():
                failures.append('Mes no distingue continuación al día siguiente.')
            results['flows']['mes_intersecciones'] = 'ok'

            # Alta desde Mes: conserva fecha y exige hora explícita.
            page.set_viewport_size({'width': 360, 'height': 900})
            set_view('month')
            page.click(f'[data-day="{info["create_day"]}"]')
            page.wait_for_selector('#appointment-form-dialog[open]')
            start_date_value = page.input_value('#appointment-form-dialog input[name="start_date"]')
            end_date_value = page.input_value('#appointment-form-dialog input[name="end_date"]')
            start_value = page.input_value('#appointment-form-dialog input[name="start_time"]')
            end_value = page.input_value('#appointment-form-dialog input[name="end_time"]')
            if start_date_value != info['create_day'] or end_date_value != info['create_day']:
                failures.append('El alta desde Mes no conserva la fecha pulsada.')
            if start_value or end_value:
                failures.append('El alta desde Mes inventa una hora por defecto.')
            page.screenshot(path=str(EVIDENCE / 'month-create-360.png'))
            options = page.eval_on_selector(
                '#appointment-form-dialog select[name="professional_id"]',
                "el => Array.from(el.options).map(option => option.value)")
            if '3' in options:
                failures.append('El formulario permite elegir un profesional inactivo.')
            page.fill('#appointment-form-dialog input[name="title"]', 'Creada desde mes')
            page.select_option('#appointment-form-dialog select[name="professional_id"]', '1')
            page.fill('#appointment-form-dialog input[name="start_time"]', '14:00')
            page.fill('#appointment-form-dialog input[name="end_time"]', '15:00')
            page.click('#appointment-form-dialog button[type="submit"]')
            page.wait_for_selector('.month-chip:has-text("Creada desde mes")', timeout=8000)
            response = page.context.request.get(
                base + '/api/agenda?view=day&date=' + info['create_day'])
            payload = response.json()
            created = [item for item in payload['appointments']
                       if item['title'] == 'Creada desde mes']
            if not created or not created[0]['start_local'].startswith(info['create_day']):
                failures.append('La cita creada desde Mes no quedó en la fecha pulsada.')
            results['flows']['mes_alta_fecha'] = 'ok'

            # Cambios rápidos de vista: una respuesta antigua no debe dibujarse.
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.evaluate('window.__delayWeek = true')
            page.click('[data-view="week"]')
            page.click('[data-view="month"]')
            page.wait_for_timeout(1400)
            if page.locator('.month-wrap').count() != 1 or page.locator('.week-wrap').count():
                failures.append('Una respuesta antigua de vista sobrescribió la última solicitada.')
            results['flows']['carrera_vista'] = 'ok'

            # Historial legible y detalle con citas.
            go_day(info['offset'])
            page.click('.appt:has-text("Control")')
            page.wait_for_selector('#appointment-detail[open]')
            history_text = page.inner_text('#appointment-detail [data-history]')
            if '{' in history_text or 'operational_status' in history_text or 'before_json' in history_text:
                failures.append('El historial sigue mostrando JSON/estados internos crudos.')
            if 'Estado:' not in history_text and 'Inicio:' not in history_text:
                failures.append('El historial no traduce los cambios a campos legibles.')
            if 'Motivo:' not in history_text:
                failures.append('El historial no muestra el motivo de la reprogramación.')
            for width in (360, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 900})
                page.evaluate("document.querySelector('#appointment-detail .dialog-body').scrollTop = 99999")
                page.wait_for_timeout(150)
                page.screenshot(path=str(EVIDENCE / f'detail-history-{width}.png'))
            results['flows']['historial_legible'] = 'ok'
            page.click('#appointment-detail [data-close]')

            # Compactación móvil: la rejilla debe aparecer en la primera pantalla.
            page.set_viewport_size({'width': 360, 'height': 900})
            go_day(info['offset'])
            surface_top = page.evaluate(
                "document.querySelector('.agenda-surface').getBoundingClientRect().top")
            if surface_top > 700:
                failures.append('En móvil la agenda queda demasiado abajo en la primera pantalla.')
            if not page.locator('.appt').first.is_visible():
                failures.append('En móvil no se ve ninguna cita en la primera pantalla.')
            page.screenshot(path=str(EVIDENCE / 'mobile-first-360.png'))
            contrast = page.evaluate(contrast_script())
            results['contrast'] = contrast
            if contrast.get('tick', 0) < 4.5:
                failures.append('Contraste insuficiente en las horas de la rejilla.')
            if contrast.get('arrow', 0) < 4.5:
                failures.append('Contraste insuficiente en las flechas de navegación.')

            # Tamaño táctil de Mes.
            set_view('month')
            box = page.locator('[data-day]').first.bounding_box()
            results['month_touch'] = box
            if not box or box['height'] < 40:
                failures.append('Objetivo táctil de Mes menor de 40 px.')

            # Teclado.
            page.focus('[data-action="new"]')
            page.keyboard.press('Enter')
            page.wait_for_selector('#appointment-form-dialog[open]')
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            focused = page.evaluate(
                'document.activeElement && document.activeElement.getAttribute("data-action")')
            if focused != 'new':
                failures.append('El foco no volvió al origen tras cerrar el diálogo.')

            # Zoom 200 %.
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.evaluate("document.body.style.zoom='2'")
            page.wait_for_timeout(250)
            if page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 2'):
                failures.append('Desbordamiento horizontal con zoom 200 %.')
            page.screenshot(path=str(EVIDENCE / 'zoom-200-1440.png'))
            page.evaluate("document.body.style.zoom='1'")
            results['flows']['teclado_zoom'] = 'ok'

            browser.close()

        expected_conflict = any(status == 409 and '/api/appointments' in url
                                for status, url in bad_responses)
        real_console = [entry for entry in console
                        if 'favicon' not in entry['text'].lower()
                        and not ('409' in entry['text'] and 'CONFLICT' in entry['text'])]
        bad = [item for item in bad_responses
               if 'favicon' not in item[1].lower()
               and not (item[0] == 409 and '/api/appointments' in item[1])]
        if real_console:
            failures.append(f'Consola con {len(real_console)} mensajes no esperados.')
        if bad:
            failures.append(f'Recursos con error HTTP no esperado: {bad[:5]}')
        results['console'] = real_console
        results['bad_responses'] = bad
        results['expected_conflict'] = expected_conflict
        results['failures'] = failures
        (EVIDENCE / 'consola.json').write_text(json.dumps(
            {'console': real_console, 'bad_responses': bad,
             'expected_conflict_409': expected_conflict}, ensure_ascii=False, indent=2),
            encoding='utf-8')
        (EVIDENCE / 'RESUMEN.md').write_text(summary(results), encoding='utf-8')
        print(json.dumps({'failures': failures, 'contrast': results.get('contrast'),
                          'month_touch': results.get('month_touch'),
                          'console': len(real_console), 'bad_responses': len(bad)},
                         ensure_ascii=False, indent=2))
        if failures:
            raise SystemExit(1)
    finally:
        server.shutdown()


def summary(results):
    lines = ['# Evidencia P02B — correcciones de revisión', '',
             f'- Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
             '- Datos ficticios, base temporal en `.pytest_cache/p02b-evidence/`.',
             f'- Zona: {TZ}. URL local: {results["url"]}', '',
             '## Capturas', '']
    for view, files in results['views'].items():
        for file in files:
            lines.append(f'- `{file}` ({view})')
    lines += [f'- `detail-history-360.png`, `detail-history-768.png`, `detail-history-1440.png`',
              '- `month-create-360.png`', '- `mobile-first-360.png`', '- `zoom-200-1440.png`', '',
              '## Recorrido', '']
    for name, value in results['flows'].items():
        lines.append(f'- {name}: {value}')
    lines += ['', '## Comprobaciones', '']
    for key, value in results.get('overflow', {}).items():
        lines.append(f'- Desbordamiento {key}px: {"sí" if value else "no"}')
    if results.get('contrast'):
        lines.append(f'- Contraste horas: {results["contrast"].get("tick", 0):.2f}; '
                     f'flechas: {results["contrast"].get("arrow", 0):.2f}')
    if results.get('month_touch'):
        lines.append(f'- Objetivo táctil Mes: {results["month_touch"]["width"]:.0f}x'
                     f'{results["month_touch"]["height"]:.0f} px')
    lines += [f'- Mensajes de consola no esperados: {len(results["console"])}',
              f'- Recursos HTTP >=400 no esperados: {len(results["bad_responses"])}']
    if results['failures']:
        lines += ['', '## Fallos', ''] + [f'- {item}' for item in results['failures']]
    else:
        lines += ['', 'Sin fallos detectados en el recorrido automatizado.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    main()
