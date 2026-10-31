"""Servidor CRM local. No requiere OpenRouter, Qdrant ni Google para arrancar."""
from datetime import date, datetime, time, timedelta, timezone
from functools import wraps
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

# El adaptador IA (chat_adapter) se importa a nivel de módulo y congelaba
# ADAPTADOR_ACTIVO ANTES de cargar las variables: cargar .env en lo alto
# garantiza que la configuración del proveedor (CRM_CHAT_*) exista cuando
# se construye el adaptador por defecto. create_app() conserva su carga
# idempotente.
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')

from crm import agenda_time
from crm import business_profile
from crm import chat_adapter as _chat_adapter
from crm import health as _health
from crm.business_config import zone as _eff_zone
from crm.calendar import queue_for_resend, sync
from crm.reservation_service import (FORBIDDEN, NOT_FOUND, OVERLAP,
                                     STATUS_LABELS, VERSION_CONFLICT, add_note,
                                     admin_correct_status, appointment_detail,
                                     cancel_appointment, confirm_appointment,
                                     list_appointments, mark_attendance,
                                     pending_closure, reprogram_appointment,
                                     save_appointment)
from crm.store import audit, connect, initialize, now

STAGES = ['Nuevo', 'Contactado', 'Cita agendada', 'Ganado', 'Perdido']
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(32))
# Endpoints de disponibilidad: públicos, sin sesión y sin BD en before_request
# (liveness no puede depender de la base que se intenta supervisar).
HEALTH_PATHS = frozenset({'/health', '/ready'})


def _eff_check_window(database, start_utc, end_utc):
    """Regla de horario del negocio efectiva (crm_settings + perfil base).

    Se evalúa por petición para que cambios de horarios, excepciones por fecha
    y zona surtan efecto inmediatamente en el panel, igual que en el canal.
    """
    from crm.business_config import check_window
    return check_window(database, start_utc, end_utc)


def _bloqueo_manual_fecha(database, fecha_iso):
    """Excepción del negocio POR FECHA (cerrado u horario especial). Es un
    bloqueo DISTINTO del horario habitual: se respeta siempre en esta entrega;
    la cita excepcional del operador no se salta fechas cerradas ni horarios
    especiales (requieren una excepción expresamente diseñada y autorizada)."""
    from crm.business_config import effective_settings as _settings
    from crm.business_config import _parse_json as _bcfg_json
    exc = _bcfg_json(_settings(database).get('negocio_excepciones'), {})
    return exc.get(fecha_iso)


def _hhmm_min(hhmm):
    try:
        h, m = str(hhmm).split(':', 1)
        return int(h) * 60 + int(m)
    except (TypeError, ValueError):
        return 0


def _solapa(citas, start_utc, end_utc):
    "¿Alguna cita existente solapa el intervalo UTC?"
    for c in citas:
        try:
            cs = datetime.fromisoformat(str(c['start']).replace('Z', '+00:00'))
            ce = datetime.fromisoformat(str(c['end']).replace('Z', '+00:00'))
            if cs.tzinfo is None:
                cs = cs.replace(tzinfo=timezone.utc)
            if ce.tzinfo is None:
                ce = ce.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if cs < end_utc and ce > start_utc:
            return True
    return False


def _slots_dia(database, professional_id, fecha_iso, duration_min):
    """Espacios libres del profesional en un día local (cita excepcional C02).

    Devuelve huecos DENTRO del horario habitual del día (perfil efectivo +
    excepciones por fecha) que no solapan con citas existentes, más el estado
    de la fecha para la propuesta excepcional del operador. No existe control
    de recursos físicos (consultorios/salas) en esta entrega: se DECLARA esa
    limitación y no se promete comprobarla.
    """
    from crm.business_config import effective_profile
    from crm.business_config import effective_settings as _settings
    from crm.business_config import _parse_json as _bcfg_json
    prof = effective_profile(database)
    zona = prof.zone
    try:
        d = date.fromisoformat(fecha_iso)
    except (TypeError, ValueError):
        return {'ok': False, 'code': 'invalid', 'message': 'Fecha no válida'}
    with connect(database) as conn:
        prof_row = conn.execute('SELECT active FROM crm_professionals WHERE id=?',
                                (professional_id,)).fetchone()
        profesionales = conn.execute(
            'SELECT id,name,active FROM crm_professionals ORDER BY name').fetchall()
    if not prof_row:
        return {'ok': False, 'code': 'not_found', 'message': 'El profesional no existe'}
    if prof_row['active'] in (0, '0', False):
        return {'ok': False, 'code': 'inactivo',
                'message': 'El profesional está inactivo; no puede recibir citas.'}
    exc = _bcfg_json(_settings(database).get('negocio_excepciones'), {})
    exc_day = exc.get(fecha_iso)
    if (exc_day or {}).get('estado') == 'cerrado':
        return {'ok': True, 'cerrado': True, 'bloqueo_manual': True,
                'fuera_horario_permitido': False, 'slots': [], 'motivo': None,
                'profesionales': [dict(p) for p in profesionales],
                'recursos_fisicos': False}
    rango = ((exc_day or {}).get('horario') or None) or prof.hours.get(d.weekday()) or None
    tz = ZoneInfo(zona)
    d0 = datetime(d.year, d.month, d.day, 0, 0, tzinfo=tz)
    citas = list_appointments(database, start_utc=d0.astimezone(timezone.utc).isoformat(),
                              end_utc=(d0 + timedelta(days=1)).astimezone(timezone.utc).isoformat(),
                              professional=str(professional_id), status='',
                              include_cancelled=False)
    slots = []
    if rango:
        o = _hhmm_min(rango[0]) if isinstance(rango[0], str) else int(rango[0])
        c = _hhmm_min(rango[1]) if isinstance(rango[1], str) else int(rango[1])
        tmin = o
        while tmin + duration_min <= c:
            ini_l = datetime(d.year, d.month, d.day, tmin // 60, tmin % 60, tzinfo=tz)
            fin_l = ini_l + timedelta(minutes=duration_min)
            ini_u, fin_u = ini_l.astimezone(timezone.utc), fin_l.astimezone(timezone.utc)
            if _eff_check_window(database, ini_u, fin_u) is None \
                    and not _solapa(citas, ini_u, fin_u):
                slots.append({'inicio': '%02d:%02d' % (tmin // 60, tmin % 60), 'fuera': False})
            tmin += duration_min
    return {'ok': True, 'cerrado': False,
            'bloqueo_manual': bool(exc_day),
            'fuera_horario_permitido': not bool(exc_day),
            'motivo': None if rango else 'El día no tiene horario habitual.',
            'slots': slots,
            'profesionales': [dict(p) for p in profesionales],
            'recursos_fisicos': False}


def required(name, limit=200):
    value = request.form.get(name, '').strip()
    if not value or len(value) > limit:
        raise ValueError(f'El campo {name} es obligatorio (máximo {limit} caracteres)')
    return value


def email(name='email'):
    value = required(name).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('Ingrese un correo válido')
    return value


def password_hash(password):
    if len(password) < 12 or len(password) > 256:
        raise ValueError('La contraseña debe tener entre 12 y 256 caracteres')
    return generate_password_hash(password, method='scrypt')


def create_app(test_config=None):
    load_dotenv(ROOT / '.env')
    app = Flask(__name__)
    accent = (os.getenv('CRM_ACCENT') or '#18765b').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        accent = '#18765b'
    app.config.update(DATABASE=os.getenv('CRM_DATABASE') or str(ROOT / 'analitica.db'),
                      SECRET_KEY=os.getenv('CRM_SECRET_KEY') or secrets.token_hex(32),
                      BUSINESS_NAME=os.getenv('CRM_BUSINESS_NAME', ''),
                      ACCENT=accent,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                      MAX_CONTENT_LENGTH=10 * 1024 * 1024)
    if test_config:
        app.config.update(test_config)
    # G01B R1: el perfil es la ÚNICA autoridad de zona y nombre operativo.
    # CRM_TIMEZONE sólo alimenta el perfil interno cuando no hay perfil
    # externo; un conflicto se rechaza en el arranque (nunca silencioso).
    profile = test_config.get('PROFILE') if test_config else None
    if profile is None:
        # Una sola autoridad: el test TIMEZONE si lo trae; si no, el entorno
        # (CRM_TIMEZONE alimenta el perfil interno; con perfil externo y
        # CRM_TIMEZONE contradictoria hay error de arranque).
        legacy = (test_config.get('TIMEZONE') if test_config
                  else None) or os.getenv('CRM_TIMEZONE')
        profile = business_profile.resolve_profile(legacy)
    elif test_config.get('TIMEZONE') and test_config['TIMEZONE'] != profile.zone:
        raise business_profile.ProfileError(
            f"Conflicto de zona en pruebas: el perfil define {profile.zone} y "
            f"la configuración indica {test_config['TIMEZONE']}")
    app.config['PROFILE'] = profile
    app.config['TIMEZONE'] = profile.zone
    if not app.config.get('BUSINESS_NAME'):
        # Sin CRM_BUSINESS_NAME (ni valor de pruebas), manda el perfil.
        app.config['BUSINESS_NAME'] = os.getenv('CRM_BUSINESS_NAME') or profile.name
    initialize(app.config['DATABASE'])

    def db():
        return connect(app.config['DATABASE'])

    def protected(admin=False):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not g.user:
                    return redirect(url_for('login'))
                if admin and g.user['role'] != 'admin':
                    abort(403)
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def protected_api(admin=False):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not g.user:
                    return jsonify(error={'code': 'session_expired',
                                          'message': 'Sesión vencida. Vuelva a ingresar.'}), 401
                if admin and g.user['role'] != 'admin':
                    return jsonify(error={'code': 'forbidden',
                                          'message': 'Permiso insuficiente.'}), 403
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    @app.before_request
    def security():
        g.user = None
        if request.path in HEALTH_PATHS:
            # Liveness/readiness se sirven sin sesión ni consultas previas:
            # deben responder aunque la BD esté caída (con 200/503 según toque).
            return None
        with db() as conn:
            user = conn.execute('SELECT * FROM crm_users WHERE id=? AND active=1',
                                (session.get('user_id'),)).fetchone()
        if user and user['session_version'] == session.get('version'):
            g.user = user
        if request.method == 'POST' and not request.path.startswith('/webhook'):
            token = request.form.get('csrf') or request.headers.get('X-CSRF-Token', '')
            current = session.get('csrf', '')
            if not current or not secrets.compare_digest(current.encode(), token.encode()):
                if request.path.startswith('/api/'):
                    return jsonify(error={'code': 'csrf',
                                          'message': 'Sesión vencida. Actualice la página.'}), 400
                abort(400, 'Sesión vencida. Actualice la página.')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'")
        return response

    @app.get('/theme.css')
    def theme_css():
        css = ":root{--accent:%s;}" % app.config['ACCENT']
        return Response(css, mimetype='text/css')

    @app.context_processor
    def context():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        demo = False
        try:
            demo = (app.config.get('DEMO_BANNER') or '').lower() in ('1', 'true', 'si')
        except Exception:
            demo = False
        return dict(csrf=session['csrf'], business=app.config['BUSINESS_NAME'], stages=STAGES,
                    user=g.user, zone=app.config['TIMEZONE'], accent=app.config['ACCENT'],
                    demo=demo)

    @app.template_filter('localtime')
    def localtime(value):
        return datetime.fromisoformat(value).astimezone(ZoneInfo(app.config['TIMEZONE'])).strftime('%d/%m/%Y %H:%M') if value else '—'

    @app.errorhandler(ValueError)
    def bad_input(exc):
        if request.path.startswith('/api/'):
            return jsonify(error={'code': 'invalid', 'message': str(exc)}), 400
        flash(str(exc), 'error')
        return redirect(url_for('home', tab=request.args.get('tab', 'overview')))

    @app.errorhandler(sqlite3.IntegrityError)
    def duplicate(_exc):
        if request.path.startswith('/api/'):
            return jsonify(error={'code': 'integrity',
                                  'message': 'Referencia no válida o registro duplicado.'}), 400
        flash('Ya existe un registro con esos datos o la referencia no es válida.', 'error')
        return redirect(url_for('home'))

    @app.errorhandler(sqlite3.OperationalError)
    def db_unavailable(_exc):
        """Indisponibilidad clara cuando la BD no está accesible en plena
        operación (archivo movido/bloqueado/vacío): 503 explícito, sin datos
        internos ni rutas, en lugar de un 500 genérico."""
        if request.path.startswith('/api/'):
            return jsonify(error={'code': 'base_datos_no_disponible',
                                  'message': 'La base de datos no está disponible. '
                                             'Intente de nuevo en unos momentos.'}), 503
        return Response('Base de datos no disponible. El CRM no puede atender la '
                        'solicitud ahora; verifique la instalación o solicite soporte.',
                        status=503, mimetype='text/plain; charset=utf-8')

    @app.get('/health')
    def health():
        """Liveness: el proceso vivo responde. Sin BD, sin proveedores, sin
        efectos secundarios. La salud de la BD se consulta en /ready."""
        return jsonify(status='ok', servicio='crm')

    @app.get('/ready')
    def ready():
        """Readiness: acceso a BD + esquema compatible (sólo lectura, nunca
        ejecuta migraciones ni repara). La IA sin configurar se reporta como
        limitación propia, sin afectar la disponibilidad del CRM ni simular."""
        ok_db, db_detail = _health.probe_database(app.config['DATABASE'])
        ia = _health.chat_ia_estado(_chat_adapter.ADAPTADOR_ACTIVO)
        payload = {'status': 'ok' if ok_db else 'error',
                   'checks': {'database': db_detail, 'chat_ia': ia}}
        return jsonify(payload), 200 if ok_db else 503

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            identity = request.form.get('email', '').strip().lower()[:200]
            # Límite global por IP además del usuario: evita probar correos ilimitados.
            keys = ['ip:' + str(request.remote_addr), 'email:' + identity]
            with db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                attempts = [conn.execute('SELECT * FROM crm_login_attempts WHERE identity=?', (key,)).fetchone() for key in keys]
                if any(a and a['count'] >= 5 and a['blocked_until'] > time.time() for a in attempts):
                    return render_template('login.html', error='Espere 15 minutos antes de reintentar.'), 429
                user = conn.execute('SELECT * FROM crm_users WHERE email=? AND active=1', (identity,)).fetchone()
                valid = check_password_hash(user['password_hash'] if user else DUMMY_PASSWORD_HASH,
                                            request.form.get('password', '')[:257]) and user is not None
                if not valid:
                    for key, attempt in zip(keys, attempts):
                        count = attempt['count'] + 1 if attempt and attempt['blocked_until'] > time.time() else 1
                        conn.execute('INSERT OR REPLACE INTO crm_login_attempts VALUES (?,?,?)',
                                     (key, count, time.time() + 900))
                    return render_template('login.html', error='Correo o contraseña incorrectos.'), 401
                for key in keys:
                    conn.execute('DELETE FROM crm_login_attempts WHERE identity=?', (key,))
                session.clear()
                session.update(user_id=user['id'], version=user['session_version'], permanent=True)
                audit(conn, user['id'], 'Inicio de sesión')
            return redirect(url_for('home'))
        with db() as conn:
            configured = conn.execute('SELECT COUNT(*) FROM crm_users').fetchone()[0]
        return render_template('login.html', configured=configured)

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @protected()
    def home():
        tab = request.args.get('tab', 'overview')
        if tab in ('team', 'users', 'accounts', 'audit', 'sync') and g.user['role'] != 'admin':
            abort(403)
        search = request.args.get('q', '').strip()[:100]
        stage = request.args.get('stage', '')
        doctor_filter = request.args.get('professional', '')
        with db() as conn:
            leads = conn.execute("""SELECT l.*,u.name AS owner FROM crm_leads l
                LEFT JOIN crm_users u ON u.id=l.owner_id WHERE
                (l.name LIKE ? OR l.phone LIKE ? OR l.email LIKE ?)
                AND (?='' OR l.stage=?) ORDER BY l.updated_at DESC""",
                (*(['%' + search + '%'] * 3), stage, stage)).fetchall()
            professionals = conn.execute('SELECT * FROM crm_professionals ORDER BY name').fetchall()
            agenda_leads = (conn.execute(
                'SELECT id,name,phone FROM crm_leads ORDER BY updated_at DESC LIMIT 200').fetchall()
                if tab == 'agenda' else [])
            users = conn.execute('SELECT id,email,name,role,active FROM crm_users ORDER BY name').fetchall()
            accounts = conn.execute('SELECT * FROM crm_accounts ORDER BY name').fetchall() if g.user['role'] == 'admin' else []
            funnel = dict(conn.execute('SELECT stage,COUNT(*) FROM crm_leads GROUP BY stage').fetchall())
            sources = conn.execute("""SELECT source,COUNT(*) AS total,
                SUM(CASE WHEN stage='Ganado' THEN 1 ELSE 0 END) AS won
                FROM crm_leads GROUP BY source ORDER BY total DESC""").fetchall()
            total = sum(funnel.values())
            pipeline = conn.execute("SELECT COALESCE(SUM(value),0) FROM crm_leads WHERE stage NOT IN ('Ganado','Perdido')").fetchone()[0]
            today = datetime.now(ZoneInfo(app.config['TIMEZONE'])).date().isoformat()
            overdue = conn.execute("SELECT COUNT(*) FROM crm_leads WHERE followup<=? AND stage NOT IN ('Ganado','Perdido')", (today,)).fetchone()[0]
            pending = conn.execute("""SELECT COUNT(*) FROM crm_appointments a JOIN crm_professionals p
                ON p.id=a.professional_id WHERE a.sync_status!='synced' AND p.calendar_id IS NOT NULL""").fetchone()[0]
            logs = conn.execute("""SELECT a.*,u.name FROM crm_audit a LEFT JOIN crm_users u ON u.id=a.user_id
                ORDER BY a.id DESC LIMIT 100""").fetchall() if tab == 'audit' else []
            sync_queue = (conn.execute("""SELECT a.id, a.title, a.start, a.end, a.status,
                a.operational_status, a.sync_status, a.sync_error, a.sync_attempts,
                a.sync_next_attempt, a.updated_at, p.name AS professional
                FROM crm_appointments a JOIN crm_professionals p ON p.id=a.professional_id
                WHERE a.sync_status!='synced'
                ORDER BY a.sync_status, a.updated_at DESC LIMIT 200""").fetchall()
                if tab == 'sync' else [])
            sync_professionals = (conn.execute("""SELECT name, specialty, calendar_id, active,
                last_sync, sync_error FROM crm_professionals ORDER BY name""").fetchall()
                if tab == 'sync' else [])
        return render_template('dashboard.html', tab=tab, leads=leads, agenda_leads=agenda_leads,
            professionals=professionals, users=users, accounts=accounts, funnel=funnel,
            sources=sources, total=total, pipeline=pipeline, overdue=overdue, pending=pending,
            sync_queue=sync_queue, sync_professionals=sync_professionals,
            conversion=round(100 * funnel.get('Ganado', 0) / total, 1) if total else 0,
            q=search, stage=stage, professional_filter=doctor_filter, logs=logs, today=today)

    @app.post('/users')
    @protected(admin=True)
    def users_save():
        with db() as conn:
            role = required('role')
            if role not in ('admin', 'user'):
                raise ValueError('Rol no válido')
            conn.execute('INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)',
                         (email(), required('name'), password_hash(request.form.get('password', '')), role))
            audit(conn, g.user['id'], 'Creación de usuario')
        flash('Usuario creado. Ya puede ingresar con su correo y contraseña.', 'success')
        return redirect(url_for('home', tab='users'))

    @app.post('/users/<int:identifier>')
    @protected(admin=True)
    def user_update(identifier):
        with db() as conn:
            target = conn.execute('SELECT * FROM crm_users WHERE id=?', (identifier,)).fetchone()
            if not target:
                abort(404)
            if request.form.get('action') == 'password':
                conn.execute('UPDATE crm_users SET password_hash=?,session_version=session_version+1 WHERE id=?',
                             (password_hash(request.form.get('password', '')), identifier))
            else:
                if identifier == g.user['id']:
                    raise ValueError('No puede desactivar su propia cuenta')
                conn.execute('UPDATE crm_users SET active=1-active,session_version=session_version+1 WHERE id=?', (identifier,))
            audit(conn, g.user['id'], f'Actualización de usuario {identifier}')
        return redirect(url_for('home', tab='users'))

    @app.post('/password')
    @protected()
    def change_password():
        if not check_password_hash(g.user['password_hash'], request.form.get('current_password', '')):
            raise ValueError('La contraseña actual no coincide')
        with db() as conn:
            conn.execute('UPDATE crm_users SET password_hash=?,session_version=session_version+1 WHERE id=?',
                         (password_hash(request.form.get('password', '')), g.user['id']))
            audit(conn, g.user['id'], 'Cambio de contraseña propia')
        session.clear()
        return redirect(url_for('login'))

    @app.post('/accounts')
    @protected(admin=True)
    def account_save():
        credential_env = required('credential_env')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', credential_env):
            raise ValueError('Use el nombre de una variable de entorno, por ejemplo GOOGLE_CREDS_CENTRO')
        with db() as conn:
            conn.execute('INSERT INTO crm_accounts(name,email,credential_env) VALUES (?,?,?)',
                         (required('name'), email(), credential_env))
            audit(conn, g.user['id'], 'Alta de cuenta Google')
        return redirect(url_for('home', tab='accounts'))

    @app.post('/professionals')
    @protected(admin=True)
    def professional_save():
        identifier = request.form.get('id')
        calendar_id = request.form.get('calendar_id', '').strip() or None
        account = request.form.get('account_id') or None
        if bool(calendar_id) != bool(account):
            raise ValueError('Seleccione cuenta y calendario, o deje ambos vacíos para uso local')
        with db() as conn:
            values = (required('name'), required('specialty'), email(), calendar_id, account)
            if identifier:
                previous = conn.execute('SELECT * FROM crm_professionals WHERE id=?', (identifier,)).fetchone()
                if not previous:
                    abort(404)
                if previous['calendar_id'] != calendar_id and conn.execute(
                        'SELECT 1 FROM crm_appointments WHERE professional_id=? LIMIT 1', (identifier,)).fetchone():
                    raise ValueError('Este profesional ya tiene citas: conserve su calendario o cree otro profesional')
                conn.execute('UPDATE crm_professionals SET name=?,specialty=?,email=?,calendar_id=?,account_id=?,active=? WHERE id=?',
                             (*values, int(request.form.get('active') == '1'), identifier))
            else:
                conn.execute('INSERT INTO crm_professionals(name,specialty,email,calendar_id,account_id) VALUES (?,?,?,?,?)', values)
            audit(conn, g.user['id'], 'Actualización de profesionales')
        return redirect(url_for('home', tab='team'))

    @app.post('/leads')
    @protected()
    def lead_save():
        identifier = request.form.get('id')
        stage = required('stage')
        if stage not in STAGES:
            raise ValueError('Etapa no válida')
        phone = re.sub(r'[\s()+.-]', '', required('phone'))
        if not re.fullmatch(r'\d{7,15}', phone):
            raise ValueError('El teléfono debe tener entre 7 y 15 dígitos, incluido el código de país')
        value = float(request.form.get('value') or 0)
        if not 0 <= value <= 1e12:
            raise ValueError('El valor debe ser positivo y finito')
        followup = request.form.get('followup') or None
        if followup:
            datetime.strptime(followup, '%Y-%m-%d')
        with db() as conn:
            values = (required('name'), phone, request.form.get('email', '').strip()[:200],
                      required('source'), stage, request.form.get('notes', '')[:5000], value,
                      followup, request.form.get('owner_id') or None, now())
            if identifier:
                conn.execute('UPDATE crm_leads SET name=?,phone=?,email=?,source=?,stage=?,notes=?,value=?,followup=?,owner_id=?,updated_at=? WHERE id=?', (*values, identifier))
            else:
                conn.execute('INSERT INTO crm_leads(name,phone,email,source,stage,notes,value,followup,owner_id,updated_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (*values, now()))
            audit(conn, g.user['id'], 'Actualización de lead')
        return redirect(url_for('home', tab='leads'))

    @app.post('/appointments')
    @protected()
    def appointment_save():
        identifier = request.form.get('id') or None
        doctor = required('professional_id')
        try:
            professional_id = int(doctor)
            appointment_id = int(identifier) if identifier else None
        except ValueError:
            raise ValueError('Profesional o cita no válidos')
        lead_id = request.form.get('lead_id') or None
        version = request.form.get('version') or None
        if appointment_id is not None and not version:
            raise ValueError('Falta la versión de la cita; recargue la agenda')
        result = save_appointment(
            app.config['DATABASE'],
            professional_id=professional_id,
            start=required('start'),
            end=required('end'),
            title=required('title'),
            zone=_eff_zone(app.config['DATABASE']),
            appointment_id=appointment_id,
            lead_id=lead_id,
            actor=g.user['id'],
            expected_version=version,
            reason=request.form.get('reason') or None,
            role=g.user['role'],
            channel='web',
            window_policy=lambda s, e: _eff_check_window(app.config['DATABASE'], s, e),
        )
        if not result['ok']:
            raise ValueError(result['message'])
        flash('Cita guardada localmente. Sincronice para enviarla a Google.', 'success')
        return redirect(url_for('home', tab='agenda'))

    @app.post('/appointments/<int:identifier>/cancel')
    @protected()
    def appointment_cancel(identifier):
        version = request.form.get('version')
        if not version:
            raise ValueError('Falta la versión de la cita; recargue la agenda')
        result = cancel_appointment(
            app.config['DATABASE'], appointment_id=identifier, actor=g.user['id'],
            expected_version=version,
            reason=request.form.get('reason') or None)
        if not result['ok']:
            raise ValueError(result['message'])
        flash(result['message'], 'success')
        return redirect(url_for('home', tab='agenda'))

    @app.post('/appointments/<int:identifier>/sync-retry')
    @protected(admin=True)
    def appointment_sync_retry(identifier):
        result = queue_for_resend(app.config['DATABASE'], appointment_id=identifier,
                                  actor=g.user['id'])
        if not result['ok'] and result['code'] == 'not_found':
            abort(404)
        flash(result['message'], 'success' if result['ok'] else 'info')
        return redirect(url_for('home', tab='sync'))

    @app.post('/analytics/rebuild')
    @protected(admin=True)
    def analytics_rebuild():
        from crm import analytics
        target = os.getenv('CRM_ANALYTICS_DB') or str(ROOT / 'analitica_bi.db')
        summary = analytics.rebuild(app.config['DATABASE'], target,
                                    app.config['TIMEZONE'])
        flash(f"Base analítica reconstruida: {summary['fact_citas']} citas, "
              f"{summary['dim_cliente']} clientes ({summary['desde']} a "
              f"{summary['hasta']}).", 'success')
        return redirect(url_for('home', tab='sync'))

    @app.post('/sync')
    @protected(admin=True)
    def calendar_sync():
        results = sync(app.config['DATABASE'], app.config['TIMEZONE'])
        for result in results:
            flash(result['name'] + ': ' + (result.get('error') or f"{result.get('events', 0)} eventos sincronizados"),
                  'error' if result.get('error') else 'success')
        if not results:
            flash('Agregue una cuenta Google y un calendario a un profesional para sincronizar.', 'info')
        with db() as conn:
            audit(conn, g.user['id'], 'Sincronización Google Calendar')
        return redirect(url_for('home', tab='agenda'))

    # --- API de agenda (JSON) ------------------------------------------------
    def api_error(code, message, status=400):
        return jsonify(error={'code': code, 'message': message}), status

    def service_status(code):
        if code == NOT_FOUND:
            return 404
        if code in (VERSION_CONFLICT, OVERLAP, 'too_late', 'too_early', 'already_closed'):
            return 409
        if code == FORBIDDEN:
            return 403
        return 400

    def serialize_event(row):
        tz = app.config['TIMEZONE']
        start = agenda_time.local_label(row['start'], tz)
        end = agenda_time.local_label(row['end'], tz)
        has_notes = row['has_notes'] if 'has_notes' in row.keys() else False
        return {
            'id': row['id'], 'professional_id': row['professional_id'],
            'professional_name': row['professional_name'], 'title': row['title'],
            'start_utc': row['start'], 'end_utc': row['end'],
            'start_local': start['date_time'], 'start_date': start['date'],
            'start_time': start['time'], 'end_local': end['date_time'],
            'end_date': end['date'], 'end_time': end['time'],
            'operational_status': row['operational_status'],
            'status_label': STATUS_LABELS.get(row['operational_status'], row['operational_status']),
            'status': row['status'], 'sync_status': row['sync_status'],
            'origin': row['origin'], 'row_version': row['row_version'],
            'pending_closure': pending_closure(row), 'has_notes': bool(has_notes),
        }

    def serialize_detail(result):
        tz = app.config['TIMEZONE']
        appointment = result['appointment']
        appointment.pop('calendar_id', None)
        for key in ('start', 'end'):
            appointment[key + '_local'] = agenda_time.local_label(appointment[key], tz)['date_time']
        appointment['status_label'] = STATUS_LABELS.get(
            appointment['operational_status'], appointment['operational_status'])
        for note in result['notes']:
            note['created_local'] = agenda_time.local_label(note['created_at'], tz)['date_time']
        for entry in result['history']:
            entry['created_local'] = agenda_time.local_label(entry['created_at'], tz)['date_time']
        return {'appointment': appointment,
                'pending_closure': result['pending_closure'],
                'allowed_actions': result['allowed_actions'],
                'notes': result['notes'], 'history': result['history']}

    @app.get('/api/agenda')
    @protected_api()
    def api_agenda():
        tz = app.config['TIMEZONE']
        view = request.args.get('view', 'week')
        date_value = request.args.get('date') or datetime.now(ZoneInfo(tz)).date().isoformat()
        try:
            rng = agenda_time.view_range(view, date_value, tz)
            rows = list_appointments(
                app.config['DATABASE'], start_utc=rng['start_utc'], end_utc=rng['end_utc'],
                professional=request.args.get('professional', ''),
                status=request.args.get('status', ''),
                include_cancelled=request.args.get('cancelled', '0') in ('1', 'true', 'on'))
        except (ValueError, TypeError) as exc:
            return api_error('invalid_range', str(exc))
        with db() as conn:
            professionals = conn.execute(
                'SELECT id,name,active FROM crm_professionals ORDER BY name').fetchall()
        return jsonify(view=view, date=date_value, timezone=tz,
                       label=agenda_time.period_label(rng),
                       range={key: rng[key] for key in
                              ('start_utc', 'end_utc', 'start_date', 'end_date')},
                       days=rng['days'], professionals=[dict(p) for p in professionals],
                       appointments=[serialize_event(row) for row in rows])

    @app.get('/api/appointments/<int:identifier>')
    @protected_api()
    def api_appointment_detail(identifier):
        result = appointment_detail(app.config['DATABASE'], appointment_id=identifier,
                                    role=g.user['role'])
        if not result['ok']:
            return api_error(result['code'], result['message'], service_status(result['code']))
        return jsonify(serialize_detail(result))

    @app.post('/api/appointments')
    @protected_api()
    def api_appointment_create():
        data = request.get_json(silent=True) or {}
        try:
            professional_id = int(data.get('professional_id'))
        except (TypeError, ValueError):
            return api_error('invalid', 'Seleccione un profesional')
        result = save_appointment(
            app.config['DATABASE'], professional_id=professional_id,
            start=data.get('start'), end=data.get('end'),
            title=data.get('title') or '', zone=_eff_zone(app.config['DATABASE']),
            lead_id=data.get('lead_id') or None, actor=g.user['id'],
            role=g.user['role'], channel='web',
            reason=data.get('reason') or None,
            window_policy=lambda s, e: _eff_check_window(app.config['DATABASE'], s, e))
        if not result['ok']:
            return api_error(result['code'], result['message'], service_status(result['code']))
        detail = appointment_detail(app.config['DATABASE'],
                                    appointment_id=result['appointment']['id'],
                                    role=g.user['role'])
        return jsonify(serialize_detail(detail)), 201

    @app.post('/api/appointments/<int:identifier>/transition')
    @protected_api()
    def api_appointment_transition(identifier):
        data = request.get_json(silent=True) or {}
        action = data.get('action')
        version = data.get('version')
        if version in (None, ''):
            return api_error('version_required',
                             'Falta la versión de la cita; recargue la agenda', 409)
        actor = g.user['id']
        role = g.user['role']
        database = app.config['DATABASE']
        if action == 'confirm':
            result = confirm_appointment(database, appointment_id=identifier,
                                         expected_version=version, actor=actor)
        elif action == 'reprogram':
            result = reprogram_appointment(
                database, appointment_id=identifier, start=data.get('start'),
                end=data.get('end'), title=data.get('title'),
                zone=_eff_zone(database), expected_version=version,
                reason=data.get('reason'), actor=actor, role=role,
                window_policy=lambda s, e: _eff_check_window(database, s, e)
            )
        elif action == 'cancel':
            result = cancel_appointment(database, appointment_id=identifier,
                                        expected_version=version, reason=data.get('reason'),
                                        actor=actor)
        elif action in ('attend', 'no_show'):
            result = mark_attendance(
                database, appointment_id=identifier,
                outcome='attended' if action == 'attend' else 'no_show',
                expected_version=version, actor=actor)
        elif action == 'admin_correct':
            result = admin_correct_status(
                database, appointment_id=identifier, target=data.get('target'),
                reason=data.get('reason'), expected_version=version, actor=actor, role=role)
        else:
            return api_error('invalid_action', 'Acción no válida')
        if not result['ok']:
            return api_error(result['code'], result['message'], service_status(result['code']))
        detail = appointment_detail(database, appointment_id=identifier, role=role)
        return jsonify(serialize_detail(detail))

    @app.post('/api/appointments/<int:identifier>/notes')
    @protected_api()
    def api_appointment_notes(identifier):
        data = request.get_json(silent=True) or {}
        result = add_note(app.config['DATABASE'], appointment_id=identifier,
                          body=data.get('body'), author=g.user['id'])
        if not result['ok']:
            return api_error(result['code'], result['message'], service_status(result['code']))
        detail = appointment_detail(app.config['DATABASE'], appointment_id=identifier,
                                    role=g.user['role'])
        return jsonify(serialize_detail(detail)), 201

    @app.cli.command('create-admin')
    @click.option('--email', 'user_email', prompt='Correo del administrador')
    @click.option('--name', prompt='Nombre')
    @click.password_option(confirmation_prompt=True)
    def create_admin(user_email, name, password):
        """Crea un administrador desde la computadora, nunca desde un registro público."""
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', user_email) or not name.strip():
            raise click.ClickException('Nombre o correo no válido')
        try:
            with db() as conn:
                conn.execute('INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)',
                             (user_email.lower().strip(), name.strip(), password_hash(password), 'admin'))
        except (ValueError, sqlite3.IntegrityError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo('Administrador creado.')

    @app.cli.command('sync-calendar')
    def sync_command():
        """Sincroniza todos los profesionales activos; apto para el Programador de tareas."""
        results = sync(app.config['DATABASE'], app.config['TIMEZONE'])
        for result in results:
            click.echo(str(result))
        if any(result.get('error') for result in results):
            raise click.ClickException('Hay calendarios o cambios con errores pendientes')

    # C02: webhook de WhatsApp dentro del mismo arranque (ruta /webhook).
    try:
        from crm.whatsapp_webhook import wa_webhooks
        app.register_blueprint(wa_webhooks)
    except Exception as exc:  # nunca debe impedir arrancar el panel
        app.logger.warning('No se pudo registrar el webhook de WhatsApp: %s', exc)

    # C02: rutas API del catálogo editable y bandeja humana (mismo panel).
    import crm.c02_services as c02

    @app.get('/api/c02/catalog')
    @protected()
    def c02_catalog_list():
        items = c02.catalog_list(app.config['DATABASE'], include_internal=g.user['role'] == 'admin')
        return jsonify(items=items)

    @app.post('/api/c02/catalog')
    @protected()
    def c02_catalog_create():
        body = request.get_json(silent=True) or {}
        res = c02.catalog_create(app.config['DATABASE'], name=body.get('name'),
                                 kind=body.get('kind', 'servicio'),
                                 professional_id=body.get('professional_id'),
                                 created_by=g.user['id'])
        if not res['ok']:
            return jsonify(error={'code': res['code'], 'message': res['message']}), 400
        return jsonify(res), 201

    @app.get('/api/c02/catalog/<int:identifier>')
    @protected()
    def c02_catalog_detail(identifier):
        res = c02.catalog_detail(app.config['DATABASE'], identifier,
                                 include_internal=g.user['role'] == 'admin')
        return jsonify(res), (200 if res['ok'] else 404)

    @app.get('/api/c02/catalog/<int:identifier>/revisions')
    @protected()
    def c02_catalog_revisions(identifier):
        return jsonify(c02.catalog_revisions(app.config['DATABASE'], identifier))

    @app.post('/api/c02/catalog/<int:identifier>')
    @protected()
    def c02_catalog_update(identifier):
        body = request.get_json(silent=True) or {}
        res = c02.catalog_update(
            app.config['DATABASE'], item_id=identifier,
            expected_revision=body.get('revision'), field=body.get('field'),
            value=body.get('value'), actor=g.user['id'],
            reason=body.get('reason'), publish=body.get('publish'),
            role=g.user['role'])
        return jsonify(res), (200 if res['ok'] else 409 if res['code'] == 'version_conflict' else 400)

    @app.post('/api/c02/catalog/<int:identifier>/publish')
    @protected()
    def c02_catalog_publish(identifier):
        res = c02.catalog_publish(app.config['DATABASE'], item_id=identifier,
                                  actor=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 400)

    @app.get('/api/c02/knowledge')
    @protected()
    def c02_kb_list():
        return jsonify(c02.kb_list(app.config['DATABASE'], role=g.user['role']))

    @app.post('/api/c02/knowledge/upload')
    @protected(admin=True)
    def c02_kb_upload():
        """Extrae un documento subido y devuelve una vista previa SIN guardar.

        No se publica automáticamente: el archivo queda en borrador tras la
        confirmación del usuario en /api/c02/knowledge. Los documentos son
        fuentes de datos; sus instrucciones nunca modifican reglas del sistema.
        """
        from crm import c02_docs
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify(ok=False, error={'code': 'empty',
                                            'message': 'Seleccione un archivo'}), 400
        data = file.read(c02_docs.MAX_UPLOAD_BYTES + 1)
        if len(data) > c02_docs.MAX_UPLOAD_BYTES:
            return jsonify(ok=False, error={'code': 'too_large',
                                            'message': 'El archivo excede el límite de 10 MB'}), 400
        extracted = c02_docs.extraer_documento(file.filename, data)
        preview = {
            'filename': file.filename,
            'kind': extracted['kind'],
            'body_text': (extracted.get('body_text') or '')[:40000],
            'procedencia': extracted.get('procedencia') or [],
            'warnings': extracted.get('warnings') or [],
            'extract_error': extracted.get('extract_error'),
            'ok': extracted.get('ok', False),
            'n_pages': extracted.get('n_pages'),
            'sheets': len(extracted.get('sheets') or []),
            'rows': sum(len(s.get('filas') or []) for s in (extracted.get('sheets') or [])),
        }
        if not extracted.get('ok'):
            return jsonify(ok=False, preview=preview,
                           error={'code': 'invalid',
                                  'message': extracted.get('extract_error') or 'Formato no admitido'}), 400
        return jsonify(ok=True, preview=preview)

    @app.post('/api/c02/knowledge')
    @protected(admin=True)
    def c02_kb_save():
        body = request.get_json(silent=True) or {}
        res = c02.kb_upsert(app.config['DATABASE'], doc_id=body.get('doc_id'),
                            name=body.get('name'), body_text=body.get('body_text', ''),
                            kind=body.get('kind') or 'texto',
                            visibility=body.get('visibility') or 'privado',
                            source_name=body.get('source_name'),
                            source_path=body.get('source_path'),
                            procedencia=body.get('procedencia'),
                            extract_error=body.get('extract_error'),
                            actor=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 400)

    @app.post('/api/c02/knowledge/<int:identifier>/publish')
    @protected(admin=True)
    def c02_kb_publish(identifier):
        res = c02.kb_publish(app.config['DATABASE'], doc_id=identifier, actor=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 400)

    @app.post('/api/c02/knowledge/<int:identifier>/deactivate')
    @protected(admin=True)
    def c02_kb_deactivate(identifier):
        res = c02.kb_deactivate(app.config['DATABASE'], doc_id=identifier, actor=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 400)

    @app.get('/api/c02/knowledge/<int:identifier>')
    @protected()
    def c02_kb_detail(identifier):
        # El cuerpo del documento es interno: sólo un administrador puede editarlo.
        res = c02.kb_detail(app.config['DATABASE'], identifier, role=g.user['role'])
        return jsonify(res), (200 if res['ok'] else 403 if res['code'] == 'forbidden' else 404)

    # --- Importación de inventario (punto 3 C02, paso B) ---
    # Flujo separado y controlado: subir → hoja → mapeo → vista previa →
    # confirmación explícita → aplicar. El mismo archivo se reenvía en cada
    # paso (sin estado temporal en el servidor); nada se aplica sin confirmación.
    @app.post('/api/c02/inventory/upload')
    @protected(admin=True)
    def c02_inventory_upload():
        from crm import c02_inventory
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify(ok=False, error={'code': 'empty',
                                            'message': 'Seleccione un archivo'}), 400
        from crm import c02_docs as _docs
        data = file.read(_docs.MAX_UPLOAD_BYTES + 1)
        if len(data) > _docs.MAX_UPLOAD_BYTES:
            return jsonify(ok=False, error={'code': 'too_large',
                                            'message': 'El archivo excede el límite de 10 MB'}), 400
        res = c02_inventory.inventory_upload_info(file.filename, data)
        return jsonify(res), (200 if res['ok'] else 400)

    @app.post('/api/c02/inventory/preview')
    @protected(admin=True)
    def c02_inventory_preview():
        from crm import c02_inventory
        from crm import c02_docs as _docs
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify(ok=False, error={'code': 'empty',
                                            'message': 'Seleccione un archivo'}), 400
        data = file.read(_docs.MAX_UPLOAD_BYTES + 1)
        sheet = request.form.get('sheet', '')
        mapping_raw = request.form.get('mapping', '{}')
        try:
            mapping = json.loads(mapping_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error={'code': 'invalid',
                                            'message': 'Mapeo de columnas no válido'}), 400
        res = c02_inventory.inventory_preview(app.config['DATABASE'], file.filename,
                                              data, sheet, mapping)
        return jsonify(res), (200 if res['ok'] else 400)

    @app.post('/api/c02/inventory/apply')
    @protected(admin=True)
    def c02_inventory_apply():
        from crm import c02_inventory
        from crm import c02_docs as _docs
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify(ok=False, error={'code': 'empty',
                                            'message': 'Seleccione un archivo'}), 400
        data = file.read(_docs.MAX_UPLOAD_BYTES + 1)
        sheet = request.form.get('sheet', '')
        confirm = request.form.get('confirm', '') == 'true'
        mapping_raw = request.form.get('mapping', '{}')
        try:
            mapping = json.loads(mapping_raw)
        except (TypeError, ValueError):
            return jsonify(ok=False, error={'code': 'invalid',
                                            'message': 'Mapeo de columnas no válido'}), 400
        res = c02_inventory.inventory_apply(app.config['DATABASE'], file.filename,
                                            data, sheet, mapping, confirm,
                                            actor=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 400)

    @app.post('/api/c02/chat')
    @protected()
    def c02_chat_internal():
        body = (request.get_json(silent=True) or {}).get('question', '')
        res = c02.responder_chat_internal(app.config['DATABASE'], body, role=g.user['role'])
        return jsonify(answer=res.get('answer', ''), ok=res.get('ok', True),
                       fuente=res.get('fuente'), documento=res.get('documento'),
                       version=res.get('version'), procedencia=res.get('procedencia'),
                       fuentes=res.get('fuentes', []), abstencion=res.get('abstencion', False),
                       adaptador=res.get('adaptador'), modo=res.get('modo'),
                       fallo_proveedor=res.get('fallo_proveedor', False),
                       telemetria=res.get('telemetria'),
                       resumen=res.get('resumen'))

    @app.get('/api/c02/config')
    @protected()
    def c02_config_get():
        res = c02.config_get_all(app.config['DATABASE'])
        # El saludo es interno (equipo); sólo un admin lo ve por completo.
        if g.user['role'] != 'admin':
            res['settings'] = {}
        return jsonify(res)

    @app.post('/api/c02/config')
    @protected()
    def c02_config_set():
        if g.user['role'] != 'admin':
            return jsonify(ok=False, error={'message': 'Sólo un administrador edita la configuración'}), 403
        body = request.get_json(silent=True) or {}
        res = c02.config_set(app.config['DATABASE'], key=body.get('key'),
                             value=body.get('value'), actor=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 400)

    @app.get('/api/c02/inbox')
    @protected()
    def c02_inbox_list():
        from crm import c02_services as _c
        alerts = _c.conv_alerts(app.config['DATABASE'])
        convs = _c.conversations_list(app.config['DATABASE'],
                                      role=g.user['role'], user_id=g.user['id'])
        return jsonify(alerts=alerts, conversations=convs, active=None)

    @app.get('/api/c02/inbox/<int:conversation_id>/messages')
    @protected()
    def c02_inbox_messages(conversation_id):
        from crm import c02_services as _c
        msgs = _c.conv_messages(app.config['DATABASE'], conversation_id)
        return jsonify(messages=msgs)

    @app.post('/api/c02/inbox/<int:conversation_id>/reply')
    @protected()
    def c02_inbox_reply(conversation_id):
        from crm import c02_services as _c
        data = request.get_json(silent=True) or {}
        res = _c.conv_reply_humano(
            app.config['DATABASE'], conversation_id=conversation_id,
            user_id=g.user['id'], role=g.user['role'],
            body=data.get('body', ''), request_id=data.get('request_id'))
        status = {'forbidden': 403, 'not_found': 404, 'version_conflict': 409,
                  'invalid': 400, 'empty': 400}.get(res.get('code'), 500 if not res['ok'] else 200)
        return jsonify(res), status

    @app.post('/api/c02/inbox/<int:conversation_id>/take')
    @protected()
    def c02_inbox_take(conversation_id):
        res = c02.conv_take(app.config['DATABASE'], conversation_id=conversation_id,
                            user_id=g.user['id'], role=g.user['role'])
        return jsonify(res), (200 if res['ok'] else 403 if res['code'] == 'forbidden' else 409)

    @app.post('/api/c02/inbox/<int:conversation_id>/return')
    @protected()
    def c02_inbox_return(conversation_id):
        res = c02.conv_return(app.config['DATABASE'], conversation_id=conversation_id,
                              user_id=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 403 if res['code'] == 'forbidden' else 409)

    @app.post('/api/c02/inbox/<int:conversation_id>/close')
    @protected()
    def c02_inbox_close(conversation_id):
        res = c02.conv_close(app.config['DATABASE'], conversation_id=conversation_id,
                             user_id=g.user['id'])
        return jsonify(res), (200 if res['ok'] else 403 if res['code'] == 'forbidden' else 409)

    @app.post('/api/c02/inbox/alert/<int:alert_id>/mark')
    @protected()
    def c02_inbox_alert_mark(alert_id):
        state = (request.get_json(silent=True) or {}).get('state', 'leida')
        c02.conv_mark_alert(app.config['DATABASE'], alert_id, state)
        return jsonify(ok=True)

    # --- Alerta superior de atención humana (campana global) ---
    # GET no muta estado: abrir la campana NO resuelve (la resolución es un
    # acto explícito del operador). No expone mensajes privados completos,
    # sólo motivo, prioridad, antigüedad, cliente y responsable.
    @app.get('/api/c02/atencion')
    @protected()
    def c02_atencion_panel():
        res = c02.atencion_panel(app.config['DATABASE'],
                                 role=g.user['role'], user_id=g.user['id'])
        return jsonify(res)

    # --- Cita excepcional coordinada por el operador (C02) --------------------
    # El BOT jamás crea citas fuera de horario ni salta reglas: sólo el operador
    # autorizado (rol admin) puede PROPUESTA de excepción con motivo obligatorio
    # y confirmación explícita de que cae fuera del horario habitual. Crear la
    # cita NO resuelve reclamos ni devuelve el chat a la IA (actos separados).
    @app.get('/api/c02/excepcion/slots')
    @protected()
    def c02_excepcion_slots():
        database = app.config['DATABASE']
        try:
            professional_id = int(request.args.get('professional_id') or 0)
            fecha = request.args.get('date') or ''
            duration_min = int(request.args.get('duration_min') or 30)
        except (TypeError, ValueError):
            return api_error('invalid', 'Parámetros no válidos')
        if duration_min < 5 or duration_min > 480:
            return api_error('invalid', 'Duración no válida')
        if professional_id <= 0:
            # Sin profesional: devolver sólo el catálogo para la primera carga.
            with connect(database) as conn:
                profesionales = conn.execute(
                    'SELECT id,name,active FROM crm_professionals ORDER BY name').fetchall()
            return jsonify(ok=True, cerrado=False, fuera_horario_permitido=False,
                           slots=[], motivo=None,
                           profesionales=[dict(p) for p in profesionales],
                           recursos_fisicos=False)
        res = _slots_dia(database, professional_id, fecha, duration_min)
        if not res['ok']:
            return api_error(res['code'], res['message'])
        return jsonify(res)

    @app.post('/api/c02/excepcion')
    @protected()
    def c02_excepcion_create():
        from crm import c02_services as _c
        data = request.get_json(silent=True) or {}
        database = app.config['DATABASE']
        try:
            professional_id = int(data.get('professional_id'))
            duration_min = int(data.get('duration_min') or 30)
        except (TypeError, ValueError):
            return api_error('invalid', 'Datos de la cita no válidos')
        fecha = str(data.get('fecha') or '')
        inicio = str(data.get('inicio') or '')
        excepcional = bool(data.get('excepcional'))
        confirmada = data.get('confirmada_fuera_horario') is True
        motivo = (data.get('motivo') or '').strip()
        try:
            d = date.fromisoformat(fecha)
            hhmm = datetime.strptime(inicio, '%H:%M').time()
        except (TypeError, ValueError):
            return api_error('invalid', 'Fecha u hora no válidas')
        if duration_min < 5 or duration_min > 480:
            return api_error('invalid', 'Duración no válida')
        if excepcional and g.user['role'] != 'admin':
            return api_error('forbidden',
                             'Solo el administrador puede autorizar una cita excepcional', 403)
        if excepcional and (len(motivo) < 8 or not confirmada):
            return api_error('invalid',
                             'Una cita excepcional exige un motivo (mínimo 8 caracteres) y '
                             'la confirmación de que está fuera del horario habitual')
        titulo = ((data.get('title') or '').strip() or 'Cita excepcional')[:200]
        zona = _eff_zone(database)
        tz = ZoneInfo(zona)
        ini_l = datetime(d.year, d.month, d.day, hhmm.hour, hhmm.minute, tzinfo=tz)
        fin_l = ini_l + timedelta(minutes=duration_min)
        start_utc, end_utc = ini_l.astimezone(timezone.utc), fin_l.astimezone(timezone.utc)
        wmotivo = _eff_check_window(database, start_utc, end_utc)
        if excepcional:
            if wmotivo is None:
                return api_error('no_requiere_excepcion',
                                 'Ese horario está dentro del horario habitual; '
                                 'cree la cita sin excepción.')
            if _bloqueo_manual_fecha(database, fecha):
                return api_error('fecha_bloqueada',
                                 'El negocio tiene un bloqueo ese día; la excepción no '
                                 'puede saltarlo. Elija otra fecha u horario.')
        elif wmotivo is not None:
            return api_error('outside_window',
                             'Ese horario está fuera del horario habitual; use el flujo '
                             'de cita excepcional (con motivo y autorización).')
        result = save_appointment(
            database, professional_id=professional_id,
            start=start_utc.isoformat(), end=end_utc.isoformat(),
            title=titulo, zone=zona,
            lead_id=data.get('lead_id') or None, actor=g.user['id'],
            role='admin' if excepcional else g.user['role'], channel='web',
            reason=motivo or None,
            window_policy=lambda s, e: _eff_check_window(database, s, e))
        if not result['ok']:
            return api_error(result['code'], result['message'],
                             service_status(result['code']))
        cita_id = result['appointment']['id']
        conv_id = data.get('conversation_id')
        if conv_id:
            _c.conv_add_message(database, int(conv_id), direction='internal',
                                body=('Cita #%d creada por el operador%s. Motivo: %s.'
                                      % (cita_id,
                                         ' (fuera del horario habitual)' if excepcional else '',
                                         motivo or '—')),
                                author_type='sistema')
        return jsonify(ok=True, excepcional=excepcional,
                       appointment={'id': cita_id,
                                    'professional_id': professional_id,
                                    'start': result['appointment']['start'],
                                    'end': result['appointment']['end'],
                                    'title': titulo}), 201

    # --- Biblioteca de recursos privados (punto 5, 2026-10-29) ---
    @app.get('/api/c02/library')
    @protected()
    def c02_library_list():
        from crm import library as _lib
        return jsonify(items=_lib.library_list(app.config['DATABASE']))

    @app.get('/api/c02/library/<int:resource_id>')
    @protected(admin=True)
    def c02_library_detail(resource_id):
        from crm import library as _lib
        res = _lib.library_detail(app.config['DATABASE'], resource_id)
        return jsonify(res), (200 if res else 404)

    @app.post('/api/c02/library/upload')
    @protected(admin=True)
    def c02_library_upload():
        """Sube un recurso privado (PDF/catálogo/lista de precios) o una nueva
        versión. No se publica en RAG sin allow_rag; los archivos no se sirven
        como estáticos. La aprobación de plantillas Meta no se toca aquí."""
        from crm import library as _lib
        file = request.files.get('file')
        if not file or not file.filename:
            return jsonify(ok=False, error={'code': 'empty',
                                            'message': 'Seleccione un archivo'}), 400
        data = file.read(_lib.MAX_RESOURCE_BYTES + 1)
        if len(data) > _lib.MAX_RESOURCE_BYTES:
            return jsonify(ok=False, error={'code': 'too_large',
                                            'message': 'El archivo excede el límite de 10 MB'}), 400
        res = _lib.library_upload(
            app.config['DATABASE'], name=request.form.get('name', ''),
            filename=file.filename, data=data,
            categoria=request.form.get('categoria') or 'documento',
            descripcion=request.form.get('descripcion'),
            allow_send=request.form.get('allow_send') in ('1', 'true', 'on'),
            allow_rag=request.form.get('allow_rag', '1') in ('1', 'true', 'on'),
            actor=g.user['id'],
            resource_id=request.form.get('resource_id') or None)
        return jsonify(res), 201 if res.get('ok') else 400

    @app.post('/api/c02/library/<int:resource_id>')
    @protected(admin=True)
    def c02_library_update(resource_id):
        from crm import library as _lib
        b = request.get_json(silent=True) or {}
        res = _lib.library_update(app.config['DATABASE'], resource_id,
                                  actor=g.user['id'],
                                  name=b.get('name'), descripcion=b.get('descripcion'),
                                  categoria=b.get('categoria'),
                                  allow_send=b.get('allow_send'),
                                  allow_rag=b.get('allow_rag'))
        return jsonify(res), 200 if res.get('ok') else 400

    @app.post('/api/c02/library/<int:resource_id>/retirar')
    @protected(admin=True)
    def c02_library_retirar(resource_id):
        from crm import library as _lib
        res = _lib.library_retirar(app.config['DATABASE'], resource_id,
                                   actor=g.user['id'])
        return jsonify(res), 200 if res.get('ok') else 404 if res['code'] == 'not_found' else 400

    @app.get('/api/c02/library/<int:resource_id>/archivo')
    @protected(admin=True)
    def c02_library_archivo(resource_id):
        """Descarga autorizada de un recurso privado (sólo administradores)."""
        from flask import send_file
        from crm import library as _lib
        ruta, nombre = _lib.library_descargar(app.config['DATABASE'], resource_id)
        if not ruta:
            abort(404)
        return send_file(ruta, as_attachment=True, download_name=nombre)

    # --- Plantillas WhatsApp (declaración local; aprobación = Meta) ---
    @app.get('/api/c02/plantillas')
    @protected()
    def c02_plantillas_list():
        from crm import library as _lib
        return jsonify(items=_lib.plantillas_list(app.config['DATABASE']))

    @app.post('/api/c02/plantillas')
    @protected(admin=True)
    def c02_plantillas_upsert():
        from crm import library as _lib
        b = request.get_json(silent=True) or {}
        res = _lib.plantilla_upsert(
            app.config['DATABASE'], template_id=b.get('template_id'),
            name=b.get('name', ''), language=b.get('language', 'es'),
            category=b.get('category', 'UTILITY'), body=b.get('body', ''),
            parameters=b.get('parameters'), actor=g.user['id'],
            estado=b.get('estado'))
        return jsonify(res), 201 if res.get('ok') else 400

    @app.post('/api/c02/plantillas/<int:template_id>/retirar')
    @protected(admin=True)
    def c02_plantillas_retirar(template_id):
        from crm import library as _lib
        res = _lib.plantilla_retirar(app.config['DATABASE'], template_id,
                                     actor=g.user['id'])
        return jsonify(res), 200 if res.get('ok') else 404 if res['code'] == 'not_found' else 400

    @app.post('/api/c02/plantillas/<int:template_id>/preparar-envio')
    @protected(admin=True)
    def c02_plantilla_preparar_envio(template_id):
        """Selecciona una plantilla (SÓLO aprobada por verificación externa)
        con parámetros y la encola en el outbox existente por el canal WhatsApp.
        Respeta: control humano (la bandeja sigue vigente), ventana de 24 h
        (WH-04 difiere el texto libre; la plantilla explícita sí viaja) y
        protección contra duplicados (request_id estable idempotente). NO
        envía por sí mismo: encola para el egress/worker."""
        from crm import library as _lib
        b = request.get_json(silent=True) or {}
        aprobadas = {t['id']: t for t in _lib.plantillas_seleccionables(
            app.config['DATABASE'])}
        t = aprobadas.get(template_id)
        if not t:
            return jsonify(ok=False, code='not_aproved',
                           error={'code': 'not_aproved',
                                  'message': ('Sólo una plantilla con aprobación'
                                              ' verificada del proveedor puede'
                                              ' prepararse para envío; el estado'
                                              ' actual no lo permite.')}), 400
        recipient = re.sub(r'[^0-9]', '', str(b.get('phone') or ''))
        if not (7 <= len(recipient) <= 15):
            return jsonify(ok=False, error={'code': 'invalid',
                                            'message': 'Destinatario inválido'
                                                        ' (número de 7 a 15 dígitos).'}), 400
        params = b.get('parametros')
        if not isinstance(params, list) or not all(isinstance(x, str) for x in params):
            return jsonify(ok=False, error={'code': 'invalid',
                                            'message': 'Parámetros: lista de cadenas.'}), 400
        request_id = c02._clean(b.get('request_id'), 120)
        if not request_id:
            return jsonify(ok=False, error={'code': 'invalid',
                                            'message': 'Se requiere request_id'
                                                        ' estable (idempotencia).'}), 400
        try:
            res = c02.outbox_enqueue(
                app.config['DATABASE'], channel='whatsapp', recipient=recipient,
                payload={'plantilla': {'nombre': t['name'], 'idioma': t['language'],
                                       'parametros': params[:10]}},
                correlation=c02._clean(b.get('correlation'), 120) or None,
                request_id=request_id, origin='humano')
        except sqlite3.IntegrityError:
            with connect(app.config['DATABASE']) as conn:
                row = conn.execute('SELECT id FROM crm_outbox WHERE request_id=?',
                                   (request_id,)).fetchone()
            return jsonify(ok=True, code='existing', outbox_id=row['id'] if row else None,
                           duplicated=True), 200
        return jsonify(res), 201 if res.get('ok') else 400

    @app.get('/api/c02/outbox')
    @protected()
    def c02_outbox_list():
        """Biblioteca de envíos (sólo lectura): historial reciente del outbox
        con estado del proveedor y eventos de entrega. No reenvía ni muta."""
        items = c02.outbox_history(app.config['DATABASE'], limit=200)
        return jsonify(items=items)

    return app


def _alerts_to_conversations(database, alerts):
    """Resumen de conversaciones con alerta activa para la bandeja."""
    from crm.store import connect
    try:
        with connect(database) as conn:
            rows = conn.execute(
                "SELECT c.*, u.name AS responsible_name FROM crm_conversations c "
                "LEFT JOIN crm_users u ON u.id=c.responsible_user_id "
                "WHERE c.id IN (SELECT DISTINCT conversation_id FROM crm_human_alerts "
                "                WHERE state='activa') ORDER BY c.updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
