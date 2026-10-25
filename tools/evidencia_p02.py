"""Evidencia real P02: arranca el CRM con datos ficticios y recorre la agenda con Chromium.

Uso (desde la raíz, con un entorno que tenga Flask y Playwright):
    python tools/evidencia_p02.py

No usa analitica.db, secretos ni servicios externos. Genera capturas y un resumen en
docs/producto/evidencias/p02/. Si Chromium no está disponible, falla con un mensaje claro;
en ese caso la validación visual queda pendiente y no debe declararse hecha.
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
EVIDENCE = ROOT / 'docs' / 'producto' / 'evidencias' / 'p02'
WORK = ROOT / '.pytest_cache' / 'p02-evidence'
PASSWORD = 'evidencia-password-123'


def local_dt(now, day_offset, hour, minute=0):
    day = (now + timedelta(days=day_offset)).date()
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
    target = local_dt(now, 1, 15)

    def create(start, minutes, prof, title, lead, clock=None):
        result = rs.save_appointment(
            str(path), professional_id=prof, start=start.isoformat(),
            end=(start + timedelta(minutes=minutes)).isoformat(), title=title,
            zone=TZ, lead_id=lead, actor=1,
            clock=clock or start.replace(tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc) - timedelta(minutes=30))
        assert result['ok'], result
        return result['appointment']

    # Ayer: una atendida y una pendiente vencida (para "Pendiente de cierre").
    yesterday = now - timedelta(days=1)
    past = local_dt(now, -1, 9)
    attended = create(past, 60, 1, 'Revisión de ayer', 1)
    rs.mark_attendance(path=str(path), appointment_id=attended['id'], outcome='attended',
                       expected_version=attended['row_version'], actor=1)
    create(local_dt(now, -1, 11), 60, 2, 'Pendiente ayer', 2)

    # Día objetivo: citas futuras (evitan 15:00-17:00 para el recorrido de alta).
    confirmed = create(target.replace(hour=9), 60, 1, 'Control de mañana', 1)
    rs.confirm_appointment(path=str(path), appointment_id=confirmed['id'],
                           expected_version=confirmed['row_version'], actor=1)
    pending = create(target.replace(hour=11), 60, 2, 'Limpieza', 2)
    rs.add_note(path=str(path), appointment_id=pending['id'],
                body='Paciente solicita recordatorio. Observación ficticia.', author=1)
    create(target.replace(hour=13), 60, 3, 'Valoración', 3)
    # Más de dos citas en un día para el "Ver más" del mes.
    more_day = target + timedelta(days=1)
    for hour, prof, lead, title in ((9, 1, 1, 'Cita compacta A'),
                                    (10, 2, 2, 'Cita compacta B'),
                                    (11, 3, 3, 'Cita compacta C')):
        create(more_day.replace(hour=hour), 45, prof, title, lead)
    return {
        'now': now,
        'target_date': target.date().isoformat(),
        'target_offset': (target.date() - now.date()).days,
        'past_date': (now - timedelta(days=1)).date().isoformat(),
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{port}'

    console = []
    failures = []
    results = {'url': base, 'target_date': info['target_date'], 'views': {}, 'flows': {}}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depende del entorno
        server.shutdown()
        raise SystemExit(f'Playwright no disponible: {exc}. Validación visual pendiente.') from exc

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except Exception as exc:  # pragma: no cover
                raise SystemExit(f'Chromium no disponible: {exc}. Validación visual pendiente.') from exc
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('console', lambda msg: console.append(
                {'type': msg.type, 'text': msg.text}) if msg.type in ('error', 'warning') else None)
            page.on('pageerror', lambda error: console.append(
                {'type': 'pageerror', 'text': str(error)}))
            bad_responses = []
            page.on('response', lambda response: bad_responses.append(
                (response.status, response.url)) if response.status >= 400 else None)

            page.goto(base + '/login')
            page.fill('input[name="email"]', 'admin@example.invalid')
            page.fill('input[name="password"]', PASSWORD)
            page.click('button[type="submit"], button')
            page.wait_for_url(base + '/')
            page.goto(base + '/?tab=agenda')
            page.wait_for_selector('.agenda-surface')

            target = info['target_date']

            def set_view(view):
                page.click(f'[data-view="{view}"]')
                page.wait_for_selector('.day-wrap, .week-wrap, .month-wrap')
                page.wait_for_timeout(250)

            def go_target_day():
                page.click('[data-nav="today"]')
                page.wait_for_timeout(200)
                set_view('day')
                for _ in range(max(0, info['target_offset'])):
                    page.click('[data-nav="next"]')
                    page.wait_for_timeout(200)
                page.wait_for_selector(f'[data-cell="{target}"][data-hour="15"]')

            # Capturas de día/semana/mes en 360/768/1440.
            for width in (360, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 900})
                for view in ('day', 'week', 'month'):
                    if view == 'day':
                        go_target_day()
                    else:
                        set_view(view)
                    page.wait_for_timeout(300)
                    overflow = page.evaluate(
                        'document.documentElement.scrollWidth > window.innerWidth + 2')
                    results.setdefault('overflow', {})[f'{view}-{width}'] = overflow
                    if overflow:
                        failures.append(f'Desbordamiento horizontal de página en {view}-{width}.')
                    file = EVIDENCE / f'{view}-{width}.png'
                    page.screenshot(path=str(file), full_page=False)
                    results['views'].setdefault(view, []).append(str(file.relative_to(ROOT)))
            page.set_viewport_size({'width': 1440, 'height': 900})

            # Filtro por profesional.
            go_target_day()
            page.select_option('[data-filter="professional"]', '2')
            page.wait_for_timeout(400)
            cards = page.locator('.appt').all_inner_texts()
            if not cards or any('Luis Prado' not in text for text in cards):
                failures.append('El filtro por profesional mostró citas de otro profesional.')
            results['flows']['filtro'] = 'ok' if not failures else 'revisar'
            page.select_option('[data-filter="professional"]', '')
            page.wait_for_timeout(300)

            # Alta con hora/profesional preseleccionados desde una celda libre.
            go_target_day()
            page.click(f'[data-cell="{target}"][data-hour="15"][data-professional="1"]')
            page.wait_for_selector('#appointment-form-dialog[open]')
            page.fill('#appointment-form-dialog input[name="title"]', 'Cita evidencia')
            page.select_option('#appointment-form-dialog select[name="professional_id"]', '1')
            page.click('#appointment-form-dialog button[type="submit"]')
            page.wait_for_selector('.appt:has-text("Cita evidencia")', timeout=8000)
            results['flows']['alta'] = 'ok'

            # Conflicto: el formulario conserva los datos y muestra el error.
            page.click('[data-action="new"]')
            page.wait_for_selector('#appointment-form-dialog[open]')
            page.fill('#appointment-form-dialog input[name="title"]', 'Conflicto')
            page.fill('#appointment-form-dialog input[name="start_date"]', target)
            page.fill('#appointment-form-dialog input[name="start_time"]', '15:00')
            page.fill('#appointment-form-dialog input[name="end_date"]', target)
            page.fill('#appointment-form-dialog input[name="end_time"]', '16:00')
            page.select_option('#appointment-form-dialog select[name="professional_id"]', '1')
            page.click('#appointment-form-dialog button[type="submit"]')
            page.wait_for_selector('[data-form-error]:not([hidden])', timeout=8000)
            if page.input_value('#appointment-form-dialog input[name="title"]') != 'Conflicto':
                failures.append('El formulario perdió los datos tras el conflicto.')
            results['flows']['conflicto'] = 'ok'
            page.click('#appointment-form-dialog [data-close]')
            page.wait_for_timeout(200)

            # Detalle, nota e historial.
            page.click('.appt:has-text("Cita evidencia")')
            page.wait_for_selector('#appointment-detail[open]')
            page.fill('#appointment-detail textarea[name="body"]', 'Observación de evidencia')
            page.click('#appointment-detail [data-note-form] button[type="submit"]')
            page.wait_for_selector('#appointment-detail [data-notes]:has-text("Observación de evidencia")',
                                   timeout=8000)
            history_text = page.inner_text('#appointment-detail [data-history]')
            if 'Creación' not in history_text:
                failures.append('El historial no muestra la creación.')
            results['flows']['nota_historial'] = 'ok'

            # Reprogramación (vuelve a Pendiente, conserva identidad).
            page.click('#appointment-detail [data-actions] button:has-text("Reprogramar")')
            page.wait_for_selector('#appointment-form-dialog[open]')
            page.fill('#appointment-form-dialog input[name="start_date"]', target)
            page.fill('#appointment-form-dialog input[name="start_time"]', '16:00')
            page.fill('#appointment-form-dialog input[name="end_date"]', target)
            page.fill('#appointment-form-dialog input[name="end_time"]', '17:00')
            page.fill('#appointment-form-dialog input[name="reason"]', 'Cambio de evidencia')
            page.click('#appointment-form-dialog button[type="submit"]')
            page.wait_for_selector('.appt:has-text("Cita evidencia")', timeout=8000)
            results['flows']['reprogramacion'] = 'ok'

            # Cancelación y vista de canceladas.
            page.click('.appt:has-text("Cita evidencia")')
            page.wait_for_selector('#appointment-detail[open]')
            page.click('#appointment-detail [data-actions] button:has-text("Cancelar")')
            page.wait_for_selector('#appointment-detail [data-field="status"]:has-text("Cancelada")',
                                   timeout=8000)
            page.click('#appointment-detail [data-close]')
            page.check('[data-filter="cancelled"]')
            page.wait_for_timeout(400)
            page.wait_for_selector('.appt:has-text("Cita evidencia")')
            results['flows']['cancelacion'] = 'ok'

            # Recarga: la nota persiste (la fecha vuelve a hoy; se navega al día objetivo).
            page.reload()
            page.wait_for_selector('.agenda-surface')
            go_target_day()
            page.check('[data-filter="cancelled"]')
            page.wait_for_timeout(400)
            page.click('.appt:has-text("Cita evidencia")')
            page.wait_for_selector('#appointment-detail[open]')
            page.wait_for_selector('#appointment-detail [data-notes]:has-text("Observación de evidencia")',
                                   timeout=8000)
            results['flows']['persistencia_recarga'] = 'ok'
            page.click('#appointment-detail [data-close]')

            # Asistencia desde una cita vencida.
            page.click('[data-nav="today"]')
            page.wait_for_timeout(200)
            set_view('day')
            page.click('[data-nav="prev"]')
            page.wait_for_timeout(400)
            page.click('.appt:has-text("Pendiente ayer")')
            page.wait_for_selector('#appointment-detail[open]')
            page.click('#appointment-detail [data-actions] button:has-text("Marcar atendida")')
            page.wait_for_selector('#appointment-detail [data-field="status"]:has-text("Atendida")',
                                   timeout=8000)
            results['flows']['asistencia'] = 'ok'
            page.click('#appointment-detail [data-close]')

            # Mes: "Ver más" abre el día.
            set_view('month')
            more = page.locator('.month-more').first
            if more.count():
                more.click()
                page.wait_for_selector('.day-wrap')
                results['flows']['mes_ver_mas'] = 'ok'
            else:
                failures.append('No se encontró "Ver más" en el mes.')

            # Teclado: Enter abre, Escape cierra y devuelve el foco.
            page.click('[data-action="new"]')
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            page.focus('[data-action="new"]')
            page.keyboard.press('Enter')
            page.wait_for_selector('#appointment-form-dialog[open]')
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            focused = page.evaluate('document.activeElement && document.activeElement.getAttribute("data-action")')
            if focused != 'new':
                failures.append('El foco no volvió al botón de origen tras cerrar el diálogo.')
            results['flows']['teclado'] = 'ok'

            # Zoom 200 % a 1440: sin desbordamiento horizontal de la página.
            page.set_viewport_size({'width': 1440, 'height': 900})
            page.evaluate("document.body.style.zoom='2'")
            page.wait_for_timeout(300)
            overflow = page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 2')
            page.screenshot(path=str(EVIDENCE / 'zoom-200-1440.png'))
            results['zoom_200'] = 'sin desbordamiento' if not overflow else 'desbordamiento detectado'
            if overflow:
                failures.append('Desbordamiento horizontal con zoom 200 %.')
            page.evaluate("document.body.style.zoom='1'")

            browser.close()

        expected_conflict = any(status == 409 and '/api/appointments' in url
                                for status, url in bad_responses)
        real_console = [entry for entry in console
                        if 'favicon' not in entry['text'].lower()
                        and not ('409' in entry['text'] and 'CONFLICT' in entry['text'])]
        bad = [item for item in bad_responses
               if 'favicon' not in item[1].lower()
               and not (item[0] == 409 and '/api/appointments' in item[1])]
        results['expected_conflict'] = expected_conflict
        if real_console:
            failures.append(f'Consola con {len(real_console)} mensajes de error/advertencia.')
        if bad:
            failures.append(f'Recursos con error HTTP: {bad[:5]}')
        results['console'] = real_console
        results['bad_responses'] = bad
        results['failures'] = failures
        (EVIDENCE / 'consola.json').write_text(
            json.dumps({'console': real_console, 'bad_responses': bad,
                        'expected_conflict_409': expected_conflict},
                       ensure_ascii=False, indent=2), encoding='utf-8')
        (EVIDENCE / 'RESUMEN.md').write_text(summary(results), encoding='utf-8')
        print(json.dumps({'failures': failures, 'zoom': results['zoom_200'],
                          'console': len(real_console), 'bad_responses': len(bad)},
                         ensure_ascii=False, indent=2))
        if failures:
            raise SystemExit(1)
    finally:
        server.shutdown()


def summary(results):
    lines = ['# Evidencia P02 — agenda visual (Chromium real)', '',
             f'- Fecha de ejecución: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
             f'- Datos: ficticios, base temporal en `.pytest_cache/p02-evidence/` (no `analitica.db`).',
             f'- Zona del negocio: {TZ}.', f'- URL local: {results["url"]}', '']
    lines.append('## Capturas')
    for view, files in results['views'].items():
        for file in files:
            lines.append(f'- `{file}` ({view})')
    lines += ['', '## Recorrido automatizado', '']
    for name, value in results['flows'].items():
        lines.append(f'- {name}: {value}')
    if results.get('overflow'):
        lines += [''] + [f'- Desbordamiento de página {key}: '
                         f'{"sí" if value else "no"}' for key, value in results['overflow'].items()]
    lines += ['', f'- Zoom 200 %: {results["zoom_200"]}',
              f'- Mensajes de consola/errores no esperados: {len(results["console"])}',
              f'- Recursos HTTP >= 400 no esperados: {len(results["bad_responses"])}',
              f'- Conflicto 409 esperado en la prueba de solape: {results.get("expected_conflict")}']
    if results['failures']:
        lines += ['', '## Fallos detectados', ''] + [f'- {item}' for item in results['failures']]
    else:
        lines += ['', 'Sin fallos detectados en el recorrido automatizado.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    main()
