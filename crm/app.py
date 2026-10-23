"""Servidor CRM local. No requiere OpenRouter, Qdrant ni Google para arrancar."""
from datetime import datetime, timedelta
from functools import wraps
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from crm.calendar import sync, utc
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
    app.config.update(DATABASE=os.getenv('CRM_DATABASE') or str(ROOT / 'analitica.db'),
                      SECRET_KEY=os.getenv('CRM_SECRET_KEY') or secrets.token_hex(32),
                      BUSINESS_NAME=os.getenv('CRM_BUSINESS_NAME', 'Clínica · CRM'),
                      TIMEZONE=os.getenv('CRM_TIMEZONE', 'America/Guayaquil'),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=65536)
    if test_config:
        app.config.update(test_config)
    ZoneInfo(app.config['TIMEZONE'])
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

    @app.before_request
    def security():
        g.user = None
        with db() as conn:
            user = conn.execute('SELECT * FROM crm_users WHERE id=? AND active=1',
                                (session.get('user_id'),)).fetchone()
        if user and user['session_version'] == session.get('version'):
            g.user = user
        if request.method == 'POST' and not secrets.compare_digest(
                session.get('csrf', '').encode(), request.form.get('csrf', '').encode()):
            abort(400, 'Sesión vencida. Actualice la página.')
        if request.method == 'POST' and not session.get('csrf'):
            abort(400)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        return response

    @app.context_processor
    def context():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        return dict(csrf=session['csrf'], business=app.config['BUSINESS_NAME'], stages=STAGES,
                    user=g.user, zone=app.config['TIMEZONE'])

    @app.template_filter('localtime')
    def localtime(value):
        return datetime.fromisoformat(value).astimezone(ZoneInfo(app.config['TIMEZONE'])).strftime('%d/%m/%Y %H:%M') if value else '—'

    @app.errorhandler(ValueError)
    def bad_input(exc):
        flash(str(exc), 'error')
        return redirect(url_for('home', tab=request.args.get('tab', 'overview')))

    @app.errorhandler(sqlite3.IntegrityError)
    def duplicate(_exc):
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
        if tab in ('team', 'users', 'accounts', 'audit') and g.user['role'] != 'admin':
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
            appointments = conn.execute("""SELECT a.*,p.name AS professional,p.calendar_id FROM crm_appointments a
                JOIN crm_professionals p ON p.id=a.professional_id WHERE (?='' OR p.id=?)
                ORDER BY a.start DESC LIMIT 300""", (doctor_filter, doctor_filter)).fetchall()
            professionals = conn.execute('SELECT * FROM crm_professionals ORDER BY name').fetchall()
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
        return render_template('dashboard.html', tab=tab, leads=leads, appointments=appointments,
            professionals=professionals, users=users, accounts=accounts, funnel=funnel,
            sources=sources, total=total, pipeline=pipeline, overdue=overdue, pending=pending,
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
        start = utc(required('start'), app.config['TIMEZONE'])
        end = utc(required('end'), app.config['TIMEZONE'])
        if end <= start:
            raise ValueError('El fin debe ser posterior al inicio')
        if datetime.fromisoformat(start) < datetime.now(ZoneInfo('UTC')):
            raise ValueError('Seleccione una fecha futura')
        doctor = required('professional_id')
        identifier = request.form.get('id') or None
        with db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if not conn.execute('SELECT id FROM crm_professionals WHERE id=? AND active=1', (doctor,)).fetchone():
                raise ValueError('Seleccione un profesional activo')
            old = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (identifier,)).fetchone() if identifier else None
            if identifier and not old:
                abort(404)
            if old and str(old['professional_id']) != doctor:
                raise ValueError('Para cambiar de profesional, cancele la cita y cree una nueva')
            if conn.execute("""SELECT id FROM crm_appointments WHERE professional_id=? AND status='active'
                    AND start<? AND end>? AND (? IS NULL OR id!=?)""", (doctor, end, start, identifier, identifier)).fetchone():
                raise ValueError('Existe una cita que se superpone con ese horario')
            values = (required('title'), start, end, request.form.get('lead_id') or None, now())
            if old:
                if old['status'] == 'cancelled':
                    raise ValueError('Cree una cita nueva para reemplazar una cancelada')
                conn.execute("UPDATE crm_appointments SET title=?,start=?,end=?,lead_id=?,updated_at=?,sync_status='pending',sync_error=NULL WHERE id=?", (*values, identifier))
            else:
                conn.execute('INSERT INTO crm_appointments(title,start,end,lead_id,updated_at,professional_id,event_id) VALUES (?,?,?,?,?,?,?)', (*values, doctor, uuid.uuid4().hex))
            if values[3]:
                conn.execute("UPDATE crm_leads SET stage='Cita agendada',updated_at=? WHERE id=? AND stage NOT IN ('Ganado','Perdido')", (now(), values[3]))
            audit(conn, g.user['id'], 'Creación o reprogramación de cita')
        flash('Cita guardada localmente. Sincronice para enviarla a Google.', 'success')
        return redirect(url_for('home', tab='agenda'))

    @app.post('/appointments/<int:identifier>/cancel')
    @protected()
    def appointment_cancel(identifier):
        with db() as conn:
            conn.execute("UPDATE crm_appointments SET status='cancelled',sync_status='pending',updated_at=? WHERE id=?", (now(), identifier))
            audit(conn, g.user['id'], f'Cancelación de cita {identifier}')
        return redirect(url_for('home', tab='agenda'))

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
