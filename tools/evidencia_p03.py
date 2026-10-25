"""Evidencia real P03: outbox sin bloqueo, retirada, conflicto y cola admin.

Uso:
    python tools/evidencia_p03.py

Datos ficticios, base temporal en .pytest_cache. Guarda capturas y resumen en
docs/producto/evidencias/p03/ sin tocar analitica.db, .venv-crm ni servicios reales.
Google se simula; la prueba con calendario real queda pendiente de autorización.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json
import shutil
import sqlite3
import sys
import threading

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

from crm import reservation_service as rs
from crm.app import create_app
from crm.calendar import _acquire_lease, queue_for_resend, sync
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
EVIDENCE = ROOT / 'docs' / 'producto' / 'evidencias' / 'p03'
WORK = ROOT / '.pytest_cache' / 'p03-evidence'
PASSWORD = 'evidencia-password-123'


class Failure500(Exception):
    resp = SimpleNamespace(status=500)


class Fake:
    def __init__(self, items=None, patch_errors=None):
        self.items = items or []
        self.patch_errors = list(patch_errors or [])
        self.patched = 0
        self.deleted = 0

    class _Events:
        def __init__(self, service):
            self.service = service

        def list(self, **kwargs):
            return self

        def patch(self, **kwargs):
            self.service.patched += 1
            if self.service.patch_errors:
                error = self.service.patch_errors.pop(0)
                if error is not None:
                    raise error
            return self

        def insert(self, **kwargs):
            return self

        def delete(self, **kwargs):
            self.service.deleted += 1
            return self

        def execute(self, **kwargs):
            return {'items': self.service.items}

    def events(self):
        return self._Events(self)


class Probe(Fake):
    """Durante patch intenta escribir con otra conexión: detecta bloqueos."""

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.locked = False
        self.error = None

    class _Events(Fake._Events):
        def patch(self, **kwargs):
            try:
                probe = sqlite3.connect(self.service.path, timeout=0.3)
                probe.execute('BEGIN IMMEDIATE')
                probe.execute("UPDATE crm_professionals SET specialty='Sonda' WHERE id=1")
                probe.execute('COMMIT')
                probe.close()
            except sqlite3.OperationalError as exc:
                self.service.locked = True
                self.service.error = str(exc)
            return super().patch(**kwargs)


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def book(path, offset_hours, title):
    start = now() + timedelta(days=3) + timedelta(hours=offset_hours)
    result = rs.save_appointment(path, professional_id=1, start=start.isoformat(),
                                 end=(start + timedelta(hours=1)).isoformat(),
                                 title=title, zone=TZ, actor=1, clock=now())
    assert result['ok'], result
    return result['appointment']


def row(path, appointment_id):
    with connect(path) as db:
        return db.execute('SELECT * FROM crm_appointments WHERE id=?',
                          (appointment_id,)).fetchone()


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    path = str(WORK / 'agenda.db')
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,?,?,?,?)",
                   ('admin@example.invalid', 'Operador Demo',
                    generate_password_hash(PASSWORD), 'admin'))
        db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                   "VALUES (1,'svc@example.invalid','GOOGLE','Cuenta')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) "
                   "VALUES (1,'Ana Torres','General','ana@example.invalid','ana-cal',1)")
    failures = []
    results = {'flows': {}, 'screenshots': []}

    # 1) La red corre sin transacción de escritura abierta.
    outbox_appt = book(path, 0, 'Cita outbox')
    probe = Probe(path)
    outcome = sync(path, service_factory=lambda _d: probe, clock=now())
    if probe.locked or outcome[0].get('error'):
        failures.append(f'outbox: bloqueo={probe.locked} error={outcome[0].get("error")} '
                        f'detalle={probe.error}')
    if row(path, outbox_appt['id'])['sync_status'] != 'synced':
        failures.append('outbox: la cita no quedó synced')
    results['flows']['outbox_sin_bloqueo'] = 'ok' if not failures else 'fallo'

    # 2) Retirada: fallo, fallo, vencimiento y recuperación.
    backoff_appt = book(path, 4, 'Cita con retirada')
    base = now()
    failing = Fake(patch_errors=[Failure500(), Failure500()])
    sync(path, service_factory=lambda _d: failing, clock=base)
    first = row(path, backoff_appt['id'])
    sync(path, service_factory=lambda _d: failing, clock=base + timedelta(seconds=5))
    second = row(path, backoff_appt['id'])
    not_due = Fake()
    sync(path, service_factory=lambda _d: not_due, clock=base + timedelta(seconds=30))
    skipped = row(path, backoff_appt['id'])
    healed = Fake()
    sync(path, service_factory=lambda _d: healed, clock=base + timedelta(minutes=30))
    final = row(path, backoff_appt['id'])
    if not (first['sync_attempts'] == 1 and first['sync_next_attempt'] is None
            and second['sync_attempts'] == 2 and second['sync_next_attempt'] is not None
            and skipped['sync_attempts'] == 2 and not not_due.patched
            and final['sync_status'] == 'synced' and healed.patched == 1):
        failures.append('retirada: progresión inesperada '
                        f'{first["sync_attempts"]}/{second["sync_attempts"]}/'
                        f'{skipped["sync_attempts"]}/{final["sync_status"]}')
    else:
        results['flows']['retirada_y_recuperacion'] = 'ok'

    # 3) Conflicto lógico -> revisión, y reenvío manual desde administración.
    conflict_appt = book(path, 8, 'Cita en conflicto')
    overlapping = {'id': 'otro', 'summary': 'Ocupado',
                   'start': {'dateTime': conflict_appt['start']},
                   'end': {'dateTime': conflict_appt['end']}}
    conflicting = Fake(items=[overlapping])
    sync(path, service_factory=lambda _d: conflicting, clock=now())
    reviewed = row(path, conflict_appt['id'])
    again = Fake()
    sync(path, service_factory=lambda _d: again, clock=now())
    if not (reviewed['sync_status'] == 'review' and 'Conflicto' in reviewed['sync_error']
            and again.patched == 0):
        failures.append(f'conflicto: estado={reviewed["sync_status"]}')
    else:
        results['flows']['conflicto_a_revision'] = 'ok'

    # 4) Arriendo: bloquea un segundo proceso y expira solo.
    lease_appt = book(path, 12, 'Cita con arriendo')
    holder = now()
    assert _acquire_lease(path, 'sync:1', 'otro-proceso', holder,
                          holder + timedelta(minutes=5))
    blocked = Fake()
    outcome = sync(path, service_factory=lambda _d: blocked, clock=holder)
    if blocked.patched or 'en curso' not in (outcome[0].get('error') or ''):
        failures.append(f'arriendo: no bloqueó ({outcome[0]})')
    else:
        results['flows']['arriendo_bloquea'] = 'ok'
    worker = Fake()
    outcome = sync(path, service_factory=lambda _d: worker,
                   clock=holder + timedelta(minutes=6))
    if worker.patched != 1 or row(path, lease_appt['id'])['sync_status'] != 'synced':
        failures.append('arriendo: no se recuperó tras expirar')
    else:
        results['flows']['arriendo_expira'] = 'ok'

    # 5) Navegador: cola de administración y «Enviar ahora».
    retry_appt = book(path, 16, 'Cita para reenviar')
    down = Fake(patch_errors=[Failure500()])
    sync(path, service_factory=lambda _d: down, clock=now())  # deja error en cola
    app = create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'evidence',
                      'TIMEZONE': TZ})
    server = make_server('127.0.0.1', 0, app)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f'http://127.0.0.1:{port}'
    console = []
    bad = []
    try:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            failures.append(f'Playwright no disponible: {exc}')
            raise SystemExit(1) from exc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('console', lambda msg: console.append(msg.text)
                    if msg.type in ('error', 'warning') else None)
            page.on('response', lambda response: bad.append((response.status, response.url))
                    if response.status >= 400 else None)
            page.goto(base_url + '/login')
            page.fill('input[name="email"]', 'admin@example.invalid')
            page.fill('input[name="password"]', PASSWORD)
            page.click('form button')
            page.wait_for_url(base_url + '/')
            page.goto(base_url + '/?tab=sync')
            page.wait_for_selector('table')
            body = page.inner_text('main')
            for needle in ('Cita para reenviar', 'Error de transporte',
                           'Revisión: conflicto', 'Enviar ahora'):
                if needle not in body:
                    failures.append(f'cola admin: falta «{needle}»')
            page.screenshot(path=str(EVIDENCE / 'queue-1440.png'))
            results['screenshots'].append('queue-1440.png')
            page.set_viewport_size({'width': 360, 'height': 900})
            page.screenshot(path=str(EVIDENCE / 'queue-360.png'), full_page=True)
            results['screenshots'].append('queue-360.png')
            page.click(f'tr:has-text("Cita para reenviar") button:has-text("Enviar ahora")')
            page.wait_for_selector('.notice')
            page.screenshot(path=str(EVIDENCE / 'retry-360.png'), full_page=True)
            results['screenshots'].append('retry-360.png')
            if row(path, retry_appt['id'])['sync_status'] != 'pending':
                failures.append('reenvío manual: la cita no volvió a la cola')
            else:
                results['flows']['reenvio_manual'] = 'ok'
            browser.close()
        real_console = [text for text in console if 'favicon' not in text.lower()]
        real_bad = [item for item in bad if 'favicon' not in item[1].lower()]
        if real_console or real_bad:
            failures.append(f'navegador: consola={real_console[:3]} recursos={real_bad[:3]}')
        results['console'] = real_console
        results['bad_responses'] = real_bad
    finally:
        server.shutdown()

    results['failures'] = failures
    (EVIDENCE / 'consola.json').write_text(json.dumps(
        {'console': results.get('console', []), 'bad_responses': results.get('bad_responses', [])},
        ensure_ascii=False, indent=2), encoding='utf-8')
    (EVIDENCE / 'RESUMEN.md').write_text(summary(results), encoding='utf-8')
    print(json.dumps({'failures': failures,
                      'flows': results['flows'],
                      'console': len(results.get('console', [])),
                      'bad_responses': len(results.get('bad_responses', []))},
                     ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


def summary(results):
    lines = ['# Evidencia P03 — outbox, retirada, conflictos y cola administrable', '',
             f'- Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
             '- Datos ficticios; base temporal en `.pytest_cache/p03-evidence/`.',
             '- Google simulado; sin servicios ni cuentas reales.', '',
             '## Escenarios', '']
    for name, value in results['flows'].items():
        lines.append(f'- {name}: {value}')
    lines += ['', '## Capturas', '']
    for name in results['screenshots']:
        lines.append(f'- `{name}`')
    lines += ['', f'- Mensajes de consola no esperados: {len(results.get("console", []))}',
              f'- Recursos HTTP >=400 no esperados: {len(results.get("bad_responses", []))}']
    if results['failures']:
        lines += ['', '## Fallos', ''] + [f'- {item}' for item in results['failures']]
    else:
        lines += ['', 'Sin fallos detectados en el recorrido automatizado.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    main()
