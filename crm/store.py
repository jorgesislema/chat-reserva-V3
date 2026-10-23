"""Persistencia SQLite. Tablas con prefijo crm_ para preservar datos anteriores."""
from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path):
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path):
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS crm_users (
          id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
          name TEXT NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('admin','user')),
          active INTEGER NOT NULL DEFAULT 1, session_version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS crm_accounts (
          id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
          credential_env TEXT NOT NULL, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_professionals (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL,
          email TEXT NOT NULL, calendar_id TEXT UNIQUE, account_id INTEGER REFERENCES crm_accounts(id),
          active INTEGER NOT NULL DEFAULT 1, last_sync TEXT, sync_error TEXT);
        CREATE TABLE IF NOT EXISTS crm_leads (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE,
          email TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'Manual',
          stage TEXT NOT NULL DEFAULT 'Nuevo' CHECK(stage IN
          ('Nuevo','Contactado','Cita agendada','Ganado','Perdido')),
          notes TEXT NOT NULL DEFAULT '', value REAL NOT NULL DEFAULT 0,
          followup TEXT, owner_id INTEGER REFERENCES crm_users(id),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_appointments (
          id INTEGER PRIMARY KEY, professional_id INTEGER NOT NULL REFERENCES crm_professionals(id),
          lead_id INTEGER REFERENCES crm_leads(id), title TEXT NOT NULL,
          start TEXT NOT NULL, end TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
          event_id TEXT NOT NULL, origin TEXT NOT NULL DEFAULT 'local',
          sync_status TEXT NOT NULL DEFAULT 'pending', sync_error TEXT,
          updated_at TEXT NOT NULL, UNIQUE(professional_id,event_id));
        CREATE INDEX IF NOT EXISTS crm_appointments_range ON crm_appointments(professional_id,start,end);
        CREATE TABLE IF NOT EXISTS crm_audit (
          id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES crm_users(id),
          action TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_login_attempts (
          identity TEXT PRIMARY KEY, count INTEGER NOT NULL, blocked_until REAL NOT NULL);
        PRAGMA user_version=1;
        """)


def audit(db, user_id, action):
    db.execute("INSERT INTO crm_audit(user_id,action,created_at) VALUES (?,?,?)",
               (user_id, action, now()))
