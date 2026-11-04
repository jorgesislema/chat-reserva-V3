"""Backup/restauracion consistente de una base C02 con contenido (2026-10-28).

Reproduce el recorrido recomendado en README (seccion "Copias de seguridad y
restauracion") con la API backup() de SQLite, sobre una base TEMPORAL con datos
sinteticos C02: documento publicado, producto con stock, registro de importacion
y reserva.

Comando documentado en README (respaldo consistente en un unico archivo):

    import sqlite3
    s = sqlite3.connect('analitica.db')
    d = sqlite3.connect('backups/respaldo-consistente.db')
    s.backup(d); d.close(); s.close()

- Respaldo: un solo archivo autocontenido (sin depender de -wal/-shm).
- Restauracion: en OTRA ruta temporal (procesos detenidos, sin -wal/-shm).
- Verificacion: integridad, relaciones (foreign_key_check), conservacion exacta
  de los datos sembrados y lectura real por la aplicacion (create_app) contra la
  copia restaurada.
Sin datos de clientes, sin redes, sin secretos. La base de trabajo es temporal.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import c02_inventory as inv
from crm import reservation_service as rs
from crm.app import create_app
from werkzeug.security import generate_password_hash


def _sembrar(path: str) -> dict:
    """Crea la base con contenido sintético C02 y devuelve las referencias."""
    initialize(path)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(email,name,password_hash,role) "
                     "VALUES (?,?,?,?)",
                     ('admin@backup.local', 'Admin Backup',
                      generate_password_hash('backup-pass-123'), 'admin'))
        conn.execute("INSERT INTO crm_professionals(name,specialty,email,active) "
                     "VALUES (?,?,?,1)",
                     ('Dra. Backup', 'General', 'dra@backup.local'))
    with connect(path) as conn:
        prof = conn.execute("SELECT id FROM crm_professionals WHERE email=?",
                            ('dra@backup.local',)).fetchone()
    prof_id = prof['id']

    # 1) Documento publicado (conocimiento, fuente del chat interno).
    doc = svc.kb_upsert(path, doc_id=None, name='Protocolo Backup',
                        body_text='La clínica de prueba atiende de 8:00 a 18:00.',
                        visibility='publico', actor=1)
    pub = svc.kb_publish(path, doc_id=doc['doc_id'], actor=1)
    assert pub['ok'], pub

    # 2) Producto con stock + 3) registro de importación (crm_inventory_imports;
    #    inventory_apply registra el archivo/hoja/sha256/mapeo/resumen).
    csv_b = b'code,name,kind,stock,active\nBK-1,Gasas backup,producto,25,1\n'
    ap = inv.inventory_apply(path, 'backup.csv', csv_b, 'CSV',
                             {'code': 'A', 'name': 'B', 'kind': 'C',
                              'stock': 'D', 'active': 'E'}, True, 1)
    assert ap['ok'] and ap['creadas'] == 1, ap

    # 4) Reserva (crm_appointments) asociada al profesional.
    zone = 'America/Guayaquil'
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=2)
    cita = rs.save_appointment(path, professional_id=prof_id,
                               start=start.isoformat(),
                               end=(start + timedelta(minutes=30)).isoformat(),
                               title='Cita de respaldo', zone=zone, actor=1)
    assert cita['ok'], cita

    return {'prof_id': prof_id, 'doc_id': doc['doc_id'], 'cita_id': cita['appointment']['id'],
            'start': start.isoformat(), 'csv_sha': ap.get('sha256')}


def test_backup_restaura_base_c02_con_contenido_y_app_la_lee(tmp_path):
    live = str(tmp_path / 'live.db')
    backup = tmp_path / 'backup.db'
    restored = tmp_path / 'restored.db'

    refs = _sembrar(live)
    with connect(live) as conn:
        doc_estado = conn.execute('SELECT state, version FROM crm_kb_documents WHERE id=?',
                                  (refs['doc_id'],)).fetchone()
        item = conn.execute("SELECT code, stock FROM crm_catalog_items WHERE code='BK-1'").fetchone()
        import_count = conn.execute('SELECT COUNT(*) FROM crm_inventory_imports').fetchone()[0]
        cita = conn.execute('SELECT id, title FROM crm_appointments WHERE id=?',
                            (refs['cita_id'],)).fetchone()
    assert doc_estado['state'] == 'publicado' and doc_estado['version'] == 1
    assert item['code'] == 'BK-1' and item['stock'] == 25
    assert import_count == 1
    assert cita['title'] == 'Cita de respaldo'

    # --- Respaldo consistente (API backup de SQLite, un solo archivo) ---
    source = sqlite3.connect(live)
    destination = sqlite3.connect(str(backup))
    with destination:
        source.backup(destination)
    destination.close()
    source.close()
    assert backup.exists() and backup.stat().st_size > 0

    # La base viva muta DESPUÉS del respaldo: la copia debe quedar intacta.
    with connect(live) as conn:
        conn.execute("UPDATE crm_kb_documents SET state='desactivado', body_text='MUTADO' "
                     "WHERE id=?", (refs['doc_id'],))
        conn.execute("UPDATE crm_catalog_items SET stock=999 WHERE code='BK-1'")
        conn.execute('UPDATE crm_appointments SET title=? WHERE id=?',
                     ('Cita mutada', refs['cita_id']))

    # --- Restauración en OTRA ruta temporal (procesos detenidos) ---
    shutil.copyfile(backup, restored)
    assert not restored.with_name(restored.name + '-wal').exists()
    assert not restored.with_name(restored.name + '-shm').exists()

    # --- 5a. Integridad y relaciones de la copia restaurada ---
    con = sqlite3.connect(str(restored))
    con.row_factory = sqlite3.Row
    assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    fks = con.execute('PRAGMA foreign_key_check').fetchall()
    assert fks == [], f'violaciones FK: {fks}'
    doc = con.execute('SELECT name, state, version FROM crm_kb_documents WHERE id=?',
                      (refs['doc_id'],)).fetchone()
    assert doc['name'] == 'Protocolo Backup' and doc['state'] == 'publicado' \
        and doc['version'] == 1
    item_r = con.execute("SELECT code, stock FROM crm_catalog_items WHERE code='BK-1'").fetchone()
    assert item_r['code'] == 'BK-1' and item_r['stock'] == 25
    assert con.execute('SELECT COUNT(*) FROM crm_inventory_imports').fetchone()[0] == 1
    cita_r = con.execute('SELECT title, professional_id FROM crm_appointments WHERE id=?',
                         (refs['cita_id'],)).fetchone()
    assert cita_r['title'] == 'Cita de respaldo' and cita_r['professional_id'] == refs['prof_id']
    # Relación importación -> artículo: existe el registro con el hash del archivo.
    if refs['csv_sha']:
        imp = con.execute('SELECT sha256 FROM crm_inventory_imports ORDER BY id DESC').fetchone()
        assert imp['sha256'] == refs['csv_sha']
    con.close()

    # --- 5b. La aplicación lee los datos de la copia restaurada ---
    app = create_app({'TESTING': True, 'DATABASE': str(restored)})
    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    assert client.post('/login', data={'csrf': csrf,
                                       'email': 'admin@backup.local',
                                       'password': 'backup-pass-123'},
                       follow_redirects=True).status_code == 200
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    headers = {'X-CSRF-Token': csrf}
    kb = client.get('/api/c02/knowledge', headers=headers).get_json()
    assert any(d['name'] == 'Protocolo Backup' and d['state'] == 'publicado'
               for d in kb['documents'])
    cat = client.get('/api/c02/catalog', headers=headers).get_json()
    bk = next(i for i in cat['items'] if i['code'] == 'BK-1')
    assert bk['stock'] == 25
    cit = client.get(f"/api/appointments/{refs['cita_id']}", headers=headers).get_json()
    assert cit['appointment']['title'] == 'Cita de respaldo'
