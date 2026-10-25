"""Evidencia real P02C: intervalos completos (49h, 24h, medianoche) y formulario.

Uso:
    python tools/evidencia_p02c.py

Datos ficticios, base temporal en .pytest_cache. Guarda capturas y resumen en
docs/producto/evidencias/p02c/ sin tocar analitica.db, .venv-crm ni servicios reales.
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
EVIDENCE = ROOT / 'docs' / 'producto' / 'evidencias' / 'p02c'
WORK = ROOT / '.pytest_cache' / 'p02c-evidence'
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
                                 (2, 'Luis Prado', 'luis@example.invalid')):
            db.execute("INSERT INTO crm_professionals(id,name,specialty,email) VALUES (?,?,?,?)",
                       (pid, name, 'Odontología general', email))
        db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) "
                   "VALUES (1,'Paciente Demo','593900000001','x','x')")

    today = datetime.now(ZoneInfo(TZ)).date()
    base = today + timedelta(days=2)

    def create(start, end, prof, title):
        begin = start.replace(tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)
        result = rs.save_appointment(
            str(path), professional_id=prof, start=start.isoformat(),
            end=end.isoformat(), title=title, zone=TZ, lead_id=1, actor=1,
            clock=begin - timedelta(hours=1))
        assert result['ok'], result
        return result['appointment']

    long49 = create(local_dt(base, 10), local_dt(base + timedelta(days=2), 11), 1,
                    'Cita 49 horas')
    day24 = create(local_dt(base + timedelta(days=4), 9),
                   local_dt(base + timedelta(days=5), 9), 1, 'Cita 24 horas')
    start01 = create(local_dt(base + timedelta(days=8), 23),
                     local_dt(base + timedelta(days=9), 1), 2, 'Cita 23 a 01')
    return {
        'today': today,
        'base': base,
        'long49': long49,
        'day24': day24,
        'start01': start01,
        'free_offset': (base + timedelta(days=11) - today).days,
        'free_date': (base + timedelta(days=11)).isoformat(),
        'month_date': (base + timedelta(days=12)).isoformat(),
    }


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
    base_url = f'http://127.0.0.1:{port}'

    console = []
    bad_responses = []
    posts = []
    failures = []
    results = {'url': base_url, 'flows': {}, 'screenshots': []}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        server.shutdown()
        raise SystemExit(f'Playwright no disponible: {exc}. Validación pendiente.') from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('console', lambda msg: console.append(
                {'type': msg.type, 'text': msg.text}) if msg.type in ('error', 'warning') else None)
            page.on('pageerror', lambda error: console.append(
                {'type': 'pageerror', 'text': str(error)}))
            page.on('response', lambda response: bad_responses.append(
                (response.status, response.url)) if response.status >= 400 else None)
            page.on('request', lambda request: posts.append(request.url)
                    if request.method == 'POST' else None)

            page.goto(base_url + '/login')
            page.fill('input[name="email"]', 'admin@example.invalid')
            page.fill('input[name="password"]', PASSWORD)
            page.click('button[type="submit"], button')
            page.wait_for_url(base_url + '/')
            page.goto(base_url + '/?tab=agenda')
            page.wait_for_selector('.agenda-surface')

            def set_view(view):
                page.click(f'[data-view="{view}"]')
                page.wait_for_selector('.day-wrap, .week-wrap, .month-wrap')
                page.wait_for_timeout(200)

            def go_day(offset):
                page.click('[data-nav="today"]')
                page.wait_for_timeout(150)
                set_view('day')
                for _ in range(max(0, offset)):
                    page.click('[data-nav="next"]')
                    page.wait_for_timeout(150)
                page.wait_for_selector('.day-wrap')

            def shot(name, full=False):
                page.screenshot(path=str(EVIDENCE / name), full_page=full)
                results['screenshots'].append(name)

            def form_values():
                return {
                    'start_date': page.input_value('#appointment-form-dialog input[name="start_date"]'),
                    'start_time': page.input_value('#appointment-form-dialog input[name="start_time"]'),
                    'end_date': page.input_value('#appointment-form-dialog input[name="end_date"]'),
                    'end_time': page.input_value('#appointment-form-dialog input[name="end_time"]'),
                }

            base = info['base']
            long_expected = {
                'start_date': base.isoformat(), 'start_time': '10:00',
                'end_date': (base + timedelta(days=2)).isoformat(), 'end_time': '11:00',
            }

            # 1) Cita de 49 h: el formulario conserva fecha/hora final y guarda igual.
            go_day((base - info['today']).days)
            page.click('.appt:has-text("Cita 49 horas")')
            page.wait_for_selector('#appointment-detail[open]')
            page.set_viewport_size({'width': 1440, 'height': 900})
            shot('detail-49h-1440.png')
            page.set_viewport_size({'width': 360, 'height': 900})
            shot('detail-49h-360.png')
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.click('#appointment-detail [data-actions] button:has-text("Reprogramar")')
            page.wait_for_selector('#appointment-form-dialog[open]')
            values = form_values()
            if values != long_expected:
                failures.append(f'El formulario de 49 h no conserva ambos extremos: {values}')
            page.set_viewport_size({'width': 1440, 'height': 900})
            shot('form-49h-1440.png')
            page.set_viewport_size({'width': 360, 'height': 900})
            shot('form-49h-360.png')
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.fill('#appointment-form-dialog input[name="reason"]', 'Sin cambios')
            with page.expect_response(lambda r: '/api/appointments/' in r.url and
                                      r.url.endswith('/transition')) as response_info:
                page.click('#appointment-form-dialog button[type="submit"]')
            response = response_info.value
            payload = response.request.post_data_json
            expected_start = f"{long_expected['start_date']}T{long_expected['start_time']}"
            expected_end = f"{long_expected['end_date']}T{long_expected['end_time']}"
            if payload.get('start') != expected_start or payload.get('end') != expected_end:
                failures.append(f'Payload de 49 h incorrecto: {payload.get("start")} -> {payload.get("end")}')
            saved = response.json()['appointment']
            start_dt = datetime.fromisoformat(saved['start_local'])
            end_dt = datetime.fromisoformat(saved['end_local'])
            if end_dt - start_dt != timedelta(hours=49):
                failures.append(f'Persistencia de 49 h alterada: {end_dt - start_dt}')
            results['flows']['cita_49h'] = 'ok'

            # 2) Cita de 24 h: misma hora en días distintos.
            day24 = info['day24']
            day24_local = datetime.fromisoformat(day24['start']).astimezone(ZoneInfo(TZ)).date()
            go_day((day24_local - info['today']).days)
            page.click('.appt:has-text("Cita 24 horas")')
            page.wait_for_selector('#appointment-detail[open]')
            page.click('#appointment-detail [data-actions] button:has-text("Reprogramar")')
            page.wait_for_selector('#appointment-form-dialog[open]')
            values = form_values()
            if values['start_time'] != values['end_time']:
                failures.append('La cita de 24 h no conserva la misma hora de reloj.')
            if values['start_date'] == values['end_date']:
                failures.append('La cita de 24 h no conserva la fecha final distinta.')
            page.fill('#appointment-form-dialog input[name="reason"]', 'Sin cambios')
            with page.expect_response(lambda r: '/transition' in r.url) as response_info:
                page.click('#appointment-form-dialog button[type="submit"]')
            response = response_info.value
            saved = response.json()['appointment']
            if (datetime.fromisoformat(saved['end_local']) -
                    datetime.fromisoformat(saved['start_local'])) != timedelta(hours=24):
                failures.append('La cita de 24 h se acortó al guardar.')
            results['flows']['cita_24h'] = 'ok'

            # 3) Celda 23:00 -> fin 00:00 del día siguiente (nunca 24:00).
            free_date = info['free_date']
            start01 = info['start01']
            start01_local = datetime.fromisoformat(start01['start']).astimezone(ZoneInfo(TZ)).date()
            go_day((start01_local - info['today']).days)
            page.click(f'[data-cell="{start01_local.isoformat()}"][data-hour="23"][data-professional="1"]')
            page.wait_for_selector('#appointment-form-dialog[open]')
            values = form_values()
            if values['start_time'] != '23:00' or values['end_time'] != '00:00':
                failures.append(f'Celda 23:00 generó horas no válidas: {values}')
            if values['end_date'] != (start01_local + timedelta(days=1)).isoformat():
                failures.append('Celda 23:00 no movió la fecha final al día siguiente.')
            page.set_viewport_size({'width': 360, 'height': 900})
            shot('form-23-360.png')
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.fill('#appointment-form-dialog input[name="title"]', 'Creada 23 a 00')
            with page.expect_response(lambda r: r.url.endswith('/api/appointments')) as response_info:
                page.click('#appointment-form-dialog button[type="submit"]')
            response = response_info.value
            payload = response.request.post_data_json
            if payload.get('start') != f'{start01_local.isoformat()}T23:00' or \
                    payload.get('end') != f'{(start01_local + timedelta(days=1)).isoformat()}T00:00':
                failures.append(f'Payload 23:00–00:00 incorrecto: {payload.get("start")} -> {payload.get("end")}')
            created = response.json()['appointment']
            if (datetime.fromisoformat(created['end_local']) -
                    datetime.fromisoformat(created['start_local'])) != timedelta(hours=1):
                failures.append('La cita 23:00–00:00 no persistió una hora.')
            results['flows']['celda_23'] = 'ok'

            # 4) Cita 23:00–01:00 abierta conserva fecha final.
            start01 = info['start01']
            start01_local = datetime.fromisoformat(start01['start']).astimezone(ZoneInfo(TZ)).date()
            go_day((start01_local - info['today']).days)
            page.click('.appt:has-text("Cita 23 a 01")')
            page.wait_for_selector('#appointment-detail[open]')
            page.click('#appointment-detail [data-actions] button:has-text("Reprogramar")')
            page.wait_for_selector('#appointment-form-dialog[open]')
            values = form_values()
            if values['start_time'] != '23:00' or values['end_time'] != '01:00':
                failures.append(f'Cita 23–01 no muestra sus horas: {values}')
            if values['start_date'] == values['end_date']:
                failures.append('Cita 23–01 no conserva la fecha final siguiente.')
            page.fill('#appointment-form-dialog input[name="reason"]', 'Sin cambios')
            with page.expect_response(lambda r: '/transition' in r.url) as response_info:
                page.click('#appointment-form-dialog button[type="submit"]')
            saved = response_info.value.json()['appointment']
            if (datetime.fromisoformat(saved['end_local']) -
                    datetime.fromisoformat(saved['start_local'])) != timedelta(hours=2):
                failures.append('La cita 23–01 se alteró al guardar.')
            results['flows']['cita_23_01'] = 'ok'

            # 5) Fin inválido rechazado sin enviar POST.
            go_day(info['free_offset'])
            before_posts = len([url for url in posts if url.endswith('/api/appointments')])
            page.click('[data-action="new"]')
            page.wait_for_selector('#appointment-form-dialog[open]')
            page.fill('#appointment-form-dialog input[name="title"]', 'Fin inválido')
            page.select_option('#appointment-form-dialog select[name="professional_id"]', '1')
            page.fill('#appointment-form-dialog input[name="start_date"]', free_date)
            page.fill('#appointment-form-dialog input[name="start_time"]', '10:00')
            page.fill('#appointment-form-dialog input[name="end_date"]', free_date)
            page.fill('#appointment-form-dialog input[name="end_time"]', '10:00')
            page.click('#appointment-form-dialog button[type="submit"]')
            page.wait_for_selector('[data-form-error]:not([hidden])', timeout=5000)
            error_text = page.inner_text('#appointment-form-dialog [data-form-error]')
            if 'posterior' not in error_text.lower():
                failures.append('El fin igual no muestra un error comprensible.')
            page.wait_for_timeout(400)
            after_posts = len([url for url in posts if url.endswith('/api/appointments')])
            if after_posts != before_posts:
                failures.append('El formulario envió una reserva con fin inválido.')
            page.set_viewport_size({'width': 360, 'height': 900})
            shot('form-invalid-360.png')
            page.set_viewport_size({'width': 1440, 'height': 900})
            # Fin anterior en la misma fecha también se rechaza.
            page.fill('#appointment-form-dialog input[name="end_time"]', '09:00')
            page.click('#appointment-form-dialog button[type="submit"]')
            page.wait_for_selector('[data-form-error]:not([hidden])', timeout=5000)
            page.wait_for_timeout(300)
            if len([url for url in posts if url.endswith('/api/appointments')]) != before_posts:
                failures.append('El formulario envió una reserva con fin anterior al inicio.')
            page.click('#appointment-form-dialog [data-close]')
            results['flows']['fin_invalido'] = 'ok'

            # 6) Alta desde Mes: fechas visibles y horas explícitas.
            page.set_viewport_size({'width': 360, 'height': 900})
            set_view('month')
            page.click(f'[data-day="{info["month_date"]}"]')
            page.wait_for_selector('#appointment-form-dialog[open]')
            values = form_values()
            if values['start_date'] != info['month_date'] or values['end_date'] != info['month_date']:
                failures.append(f'Mes no conserva la fecha en ambos extremos: {values}')
            if values['start_time'] or values['end_time']:
                failures.append('Mes inventa una hora por defecto.')
            shot('form-month-360.png')
            page.fill('#appointment-form-dialog input[name="title"]', 'Creada desde Mes P02C')
            page.select_option('#appointment-form-dialog select[name="professional_id"]', '1')
            page.fill('#appointment-form-dialog input[name="start_time"]', '14:00')
            page.fill('#appointment-form-dialog input[name="end_time"]', '15:00')
            with page.expect_response(lambda r: r.url.endswith('/api/appointments')) as response_info:
                page.click('#appointment-form-dialog button[type="submit"]')
            response = response_info.value
            payload = response.request.post_data_json
            if payload.get('start') != f'{info["month_date"]}T14:00' or \
                    payload.get('end') != f'{info["month_date"]}T15:00':
                failures.append(f'Payload de Mes no usa la fecha pulsada: {payload.get("start")} -> {payload.get("end")}')
            results['flows']['mes_alta_completa'] = 'ok'

            # 7) Zoom 200 % sin desbordamiento (regresión de presentación).
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.evaluate("document.body.style.zoom='2'")
            page.wait_for_timeout(250)
            if page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 2'):
                failures.append('Desbordamiento horizontal con zoom 200 %.')
            shot('zoom-200-1440.png')
            page.evaluate("document.body.style.zoom='1'")
            results['flows']['zoom_200'] = 'ok'

            browser.close()

        real_console = [entry for entry in console
                        if 'favicon' not in entry['text'].lower()]
        bad = [item for item in bad_responses if 'favicon' not in item[1].lower()]
        if real_console:
            failures.append(f'Consola con {len(real_console)} mensajes no esperados.')
        if bad:
            failures.append(f'Recursos con error HTTP no esperado: {bad[:5]}')
        results['console'] = real_console
        results['bad_responses'] = bad
        results['failures'] = failures
        (EVIDENCE / 'consola.json').write_text(json.dumps(
            {'console': real_console, 'bad_responses': bad},
            ensure_ascii=False, indent=2), encoding='utf-8')
        (EVIDENCE / 'RESUMEN.md').write_text(summary(results), encoding='utf-8')
        print(json.dumps({'failures': failures, 'console': len(real_console),
                          'bad_responses': len(bad)}, ensure_ascii=False, indent=2))
        if failures:
            raise SystemExit(1)
    finally:
        server.shutdown()


def summary(results):
    lines = ['# Evidencia P02C — fechas completas y pruebas estables', '',
             f'- Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
             '- Datos ficticios; base temporal en `.pytest_cache/p02c-evidence/`.',
             f'- Zona: {TZ}. URL local: {results["url"]}', '',
             '## Capturas', '']
    for name in results.get('screenshots', []):
        lines.append(f'- `{name}`')
    lines += ['', '## Recorrido', '']
    for name, value in results['flows'].items():
        lines.append(f'- {name}: {value}')
    lines += ['', f'- Mensajes de consola/errores no esperados: {len(results["console"])}',
              f'- Recursos HTTP >=400 no esperados: {len(results["bad_responses"])}']
    if results['failures']:
        lines += ['', '## Fallos', ''] + [f'- {item}' for item in results['failures']]
    else:
        lines += ['', 'Sin fallos detectados en el recorrido automatizado con payload real.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    main()
