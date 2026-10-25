"""Servidor CRM local. No requiere OpenRouter, Qdrant ni Google para arrancar."""
from datetime import datetime, timedelta
from functools import wraps
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

from crm import agenda_time
from crm import business_profile
from crm.calendar import queue_for_resend, sync
from crm.reservation_service import (FORBIDDEN, NOT_FOUND, OVERLAP,
                                     STATUS_LABELS, VERSION_CONFLICT, add_note,
                                     admin_correct_status, appointment_detail,
                                     cancel_appointment, confirm_appointment,
                                     list_appointments, mark_attendance,
                                     pending_closure, reprogram_appointment,
                                     save_appointment)
from crm.store import audit, connect, initialize, now

ROOT = Path(__file__).resolve().parent.parent
STAGES = ['Nuevo', 'Contactado', 'Cita agendada', 'Ganado', 'Perdido']
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(32))


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
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=65536)
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
        with db() as conn:
            user = conn.execute('SELECT * FROM crm_users WHERE id=? AND active=1',
                                (session.get('user_id'),)).fetchone()
        if user and user['session_version'] == session.get('version'):
            g.user = user
        if request.method == 'POST':
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
        return dict(csrf=session['csrf'], business=app.config['BUSINESS_NAME'], stages=STAGES,
                    user=g.user, zone=app.config['TIMEZONE'], accent=app.config['ACCENT'])

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
            zone=app.config['TIMEZONE'],
            appointment_id=appointment_id,
            lead_id=lead_id,
            actor=g.user['id'],
            expected_version=version,
            reason=request.form.get('reason') or None,
            role=g.user['role'],
            channel='web',
            window_policy=app.config['PROFILE'].check_window,
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
            title=data.get('title') or '', zone=app.config['TIMEZONE'],
            lead_id=data.get('lead_id') or None, actor=g.user['id'],
            role=g.user['role'], channel='web',
            reason=data.get('reason') or None,
            window_policy=app.config['PROFILE'].check_window)
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
                zone=app.config['TIMEZONE'], expected_version=version,
                reason=data.get('reason'), actor=actor, role=role,
                window_policy=app.config['PROFILE'].check_window)
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

    return app
