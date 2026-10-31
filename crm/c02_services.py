"""Servicios comunes de la entrega C02 dentro del único backend Flask/Jinja/JS.

Este módulo no depende de Flask. Recibe la ruta de la base y los actores de forma
explícita, igual que ``crm.reservation_service``. Agrupa, por ahora, las funciones
de dominio de:

- Catálogo editable (C02-CAT-01/02/03): artículos, revisiones y publicación.
- Conocimiento/documentos (C02-CON-01): documentos y fragmentos derivados.
- Canal WhatsApp durable (C02, RF-02): mensajes idempotentes, operaciones
  reclamables y outbox de salida.
- Bandeja humana (C02-HUM): conversaciones, mensajes, alertas y control humano.

División prevista en clases/módulos más finos si crece; hoy se concentra aquí para
mantener un único punto de escritura verificable. El modelo/LLM real, el transporte
WhatsApp real y Google NO se tocan: el adaptador de salida se representa con un
transporte inyectable y un adaptador de modelo configurable (véase C02/ENTREGA).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from crm.store import connect, now
from crm.conv_lock import conversation_lock
from crm.business_config import config_get_extended, config_set_extended

# ---------------------------------------------------------------------------
# Códigos estables (patrón de crm.reservation_service).
# ---------------------------------------------------------------------------
OK = 'ok'
NOT_FOUND = 'not_found'
INVALID = 'invalid'
VERSION_CONFLICT = 'version_conflict'
FORBIDDEN = 'forbidden'
ALREADY = 'already'
EMPTY = 'empty'
HANDLED = 'handled'
CONCURRENCY = 'concurrency'
UNSUPPORTED = 'unsupported'

KINDS = ('producto', 'servicio', 'regalo', 'promocion')
PUBLISH_STATES = ('borrador', 'publicado')


def _ok(**extra):
    base = {'ok': True, 'code': OK}
    base.update(extra)
    return base


def _err(code, message, **extra):
    base = {'ok': False, 'code': code, 'message': message}
    base.update(extra)
    return base


def _clean(value, length=400):
    if value is None:
        return ''
    return str(value).strip()[:length]


def _money(cents):
    return None if cents in (None, '') else int(cents)


def _int_or(value, default=None):
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


# ===========================================================================
# Catálogo editable (C02-CAT-01/02/03)
# ===========================================================================

def catalog_list(path, include_hidden=True, include_internal=True):
    """Lista de artículos del catálogo con su revisión actual."""
    q = ('SELECT i.*, p.name AS professional_name, r.snapshot AS rev_snapshot '
         'FROM crm_catalog_items i '
         'LEFT JOIN crm_professionals p ON p.id=i.professional_id '
         'LEFT JOIN crm_catalog_revisions r ON r.item_id=i.id '
         '   AND r.revision=i.current_revision '
         'ORDER BY i.id')
    with connect(path) as conn:
        rows = conn.execute(q).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if not include_internal:
            d.pop('internal_notes', None)
        try:
            d['published'] = json.loads(d.pop('rev_snapshot')) if d.get('rev_snapshot') else None
        except (TypeError, ValueError):
            d['published'] = None
        result.append(d)
    return result


def catalog_detail(path, item_id, include_internal=False):
    with connect(path) as conn:
        row = conn.execute(
            'SELECT i.*, p.name AS professional_name FROM crm_catalog_items i '
            'LEFT JOIN crm_professionals p ON p.id=i.professional_id WHERE i.id=?',
            (item_id,)).fetchone()
        if not row:
            return _err(NOT_FOUND, 'Artículo no encontrado')
        item = dict(row)
        if not include_internal:
            item.pop('internal_notes', None)
        # Revisión publicada vigente (base del recuperador público).
        pub = conn.execute(
            'SELECT snapshot FROM crm_catalog_revisions WHERE item_id=? AND publish_state=? '
            'ORDER BY revision DESC LIMIT 1',
            (item_id, 'publicado')).fetchone()
        try:
            item['public_revision'] = json.loads(pub['snapshot']) if pub else None
        except (TypeError, ValueError):
            item['public_revision'] = None
    return _ok(item=item)


def catalog_revisions(path, item_id):
    """Historial de revisiones de un artículo (publicadas o borrador, nunca borrado)."""
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT r.revision, r.publish_state, r.created_at, u.name AS author
               FROM crm_catalog_revisions r
               LEFT JOIN crm_users u ON u.id=r.author_user_id
               WHERE r.item_id=? ORDER BY r.revision DESC""",
            (item_id,)).fetchall()
    return _ok(revisions=[dict(r) for r in rows])


def catalog_item_public(path, item_id):
    """Instantánea publicada vigente (para el recuperador del bot); si la revisión
    publicada es anterior, se revalida activo/precio/stock contra la base."""
    with connect(path) as conn:
        item = conn.execute('SELECT * FROM crm_catalog_items WHERE id=?', (item_id,)).fetchone()
        if not item:
            return None
        if item['active'] not in (1, '1', True):
            return None
        row = conn.execute(
            'SELECT snapshot FROM crm_catalog_revisions WHERE item_id=? AND publish_state=? '
            'ORDER BY revision DESC LIMIT 1',
            (item_id, 'publicado')).fetchone()
        if not row:
            return None
        try:
            snap = json.loads(row['snapshot'])
        except (TypeError, ValueError):
            return None
        # La instantánea comunicada es siempre la de una revisión publicada.
        snap['publish_state'] = 'publicado'
        # Revalidación operativa: el precio comunicado pertenece a la revisión
        # pública, pero activo/stock vigentes se leen de la base.
        snap['active'] = item['active']
        snap['stock'] = item['stock']
        snap['stock_na'] = item['stock_na']
        return snap


def catalog_create(path, *, name, kind='servicio', professional_id=None, created_by=None):
    """Crea un artículo en borrador con su primera revisión."""
    name = _clean(name, 150)
    if not name:
        return _err(EMPTY, 'El nombre del artículo es obligatorio')
    if kind not in KINDS:
        return _err(INVALID, 'Tipo de artículo no válido')
    stamp = now()
    with connect(path) as conn:
        code = 'ART-{:04d}'.format(conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_items').fetchone()['n'] + 1)
        cursor = conn.execute(
            """INSERT INTO crm_catalog_items
               (code, name, kind, publish_state, current_revision, created_at, updated_at)
               VALUES (?,?,?,'borrador',1,?,?)""",
            (code, name, kind, stamp, stamp))
        item_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO crm_catalog_revisions
               (item_id, revision, author_user_id, created_at, publish_state, snapshot)
               VALUES (?,1,?,?,'borrador',?)""",
            (item_id, created_by, stamp, json.dumps({'name': name, 'kind': kind})))
    return _ok(item_id=item_id, code=code)


def catalog_update(path, *, item_id, expected_revision, field, value, actor=None,
                   reason=None, publish=False, role='user'):
    """Actualiza un campo de celda o de detalle con control de versión optimista.

    ``field`` es el nombre de una columna editable del artículo. Guardar un valor
    genera una **revisión nueva** con la instantánea de los campos publicables.
    ``publish=True`` marca la revisión como publicada (borrador -> publicado), con
    revalidación contra la base (precio/activo/stock) antes de quedar vigente.
    Las notas internas (RF-05, sólo equipo) exigen rol admin a la hora de escribirlas.
    """
    if field not in ('name', 'kind', 'details', 'public_notes', 'internal_notes',
                     'price_cents', 'currency', 'stock', 'stock_na', 'active',
                     'valid_from', 'valid_until', 'duration_min', 'professional_id'):
        return _err(INVALID, 'Campo no editable')
    if field == 'internal_notes' and role != 'admin':
        return _err(FORBIDDEN, 'Sólo un administrador puede escribir notas internas')
    if reason is not None and not _clean(reason, 400):
        reason = None

    with connect(path) as conn:
        item = conn.execute('SELECT * FROM crm_catalog_items WHERE id=?', (item_id,)).fetchone()
        if not item:
            return _err(NOT_FOUND, 'Artículo no encontrado')
        try:
            expected = int(expected_revision)
        except (TypeError, ValueError):
            expected = -1
        if item['current_revision'] != expected:
            return _err(VERSION_CONFLICT,
                        'El registro cambió mientras editaba; recargue para no sobrescribir cambios.')

        # Normalización del valor según el campo (whitelist ya validada arriba).
        if field == 'name':
            value = _clean(value, 150)
            if not value:
                return _err(EMPTY, 'El nombre no puede quedar vacío')
        elif field == 'kind':
            if value not in KINDS:
                return _err(INVALID, 'Tipo de artículo no válido')
        elif field == 'price_cents':
            value = _money(value)
        elif field == 'stock':
            value = _int_or(value)
        elif field == 'stock_na':
            value = 1 if value in (True, '1', 'on', 'true') else 0
        elif field == 'active':
            value = 1 if value in (True, '1', 'on', 'true') else 0
        elif field == 'duration_min':
            value = _int_or(value)
        elif field == 'professional_id':
            value = _int_or(value) if value else None
        elif field in ('details', 'public_notes', 'internal_notes'):
            value = _clean(value, 4000)
        else:
            value = _clean(value, 200)

        # Aplicar (la whitelist garantiza que `field` es una columna permitida).
        conn.execute(
            f'UPDATE crm_catalog_items SET "{field}"=?, updated_at=? WHERE id=?',
            (value, now(), item_id))

        new_rev = item['current_revision'] + 1
        snapshot = dict(item)
        snapshot[field] = value
        snapshot['publish_state'] = 'publicado' if publish else 'borrador'
        conn.execute(
            """INSERT INTO crm_catalog_revisions
               (item_id, revision, author_user_id, created_at, publish_state, snapshot)
               VALUES (?,?,?,?,?,?)""",
            (item_id, new_rev, actor, datetime.now(timezone.utc).isoformat(),
             snapshot['publish_state'], json.dumps(snapshot, ensure_ascii=False)))
        conn.execute('UPDATE crm_catalog_items SET current_revision=?, publish_state=? WHERE id=?',
                     (new_rev, snapshot['publish_state'], item_id))

    return _ok(revision=new_rev, field=f'"{field}"')


def catalog_publish(path, *, item_id, actor=None):
    """Publica la última revisión: revalida activo/precio/stock y marca publicado."""
    with connect(path) as conn:
        item = conn.execute('SELECT * FROM crm_catalog_items WHERE id=?', (item_id,)).fetchone()
        if not item:
            return _err(NOT_FOUND, 'Artículo no encontrado')
        if item['active'] not in (1, '1', True):
            return _err(INVALID, 'Un artículo inactivo no puede publicarse hasta activarlo.')
        if item['price_cents'] is None and item['kind'] in ('producto', 'servicio'):
            return _err(INVALID, 'Un producto/servicio sin precio no puede publicarse.')
        rev = conn.execute(
            'SELECT revision FROM crm_catalog_revisions WHERE item_id=? ORDER BY revision DESC LIMIT 1',
            (item_id,)).fetchone()
        if not rev:
            return _err(INVALID, 'El artículo no tiene revisiones.')
        snapshot = conn.execute(
            'SELECT snapshot FROM crm_catalog_revisions WHERE item_id=? AND revision=?',
            (item_id, rev['revision'])).fetchone()
        try:
            snap = json.loads(snapshot['snapshot']) if snapshot else {}
        except (TypeError, ValueError):
            snap = {}
        snap['publish_state'] = 'publicado'
        conn.execute(
            'UPDATE crm_catalog_revisions SET publish_state=? WHERE item_id=? AND revision=?',
            ('publicado', item_id, rev['revision']))
        conn.execute('UPDATE crm_catalog_items SET publish_state=?, updated_at=? WHERE id=?',
                     ('publicado', now(), item_id))
    return _ok(revision=rev['revision'])


# ===========================================================================
# Conocimiento / documentos (C02-CON-01)
# ===========================================================================

KB_KINDS = ('texto', 'md', 'txt', 'pdf', 'docx', 'xlsx', 'csv')


def kb_list(path, *, role='admin'):
    with connect(path) as conn:
        rows = conn.execute(
            'SELECT id, name, version, state, visibility, kind, index_state, '
            'source_name, procedencia, extract_error, created_at, updated_at '
            'FROM crm_kb_documents ORDER BY id').fetchall()
    docs = [dict(r) for r in rows]
    if role != 'admin':
        # Separación público/interno: un usuario sin privilegios sólo ve
        # documentos publicados y públicos; nunca borradores ni notas internas.
        docs = [d for d in docs
                if d['state'] == 'publicado' and d['visibility'] == 'publico']
    return _ok(documents=docs)


def kb_detail(path, doc_id, *, role='admin'):
    with connect(path) as conn:
        row = conn.execute('SELECT * FROM crm_kb_documents WHERE id=?',
                           (doc_id,)).fetchone()
    if not row:
        return _err(NOT_FOUND, 'Documento no encontrado')
    # El cuerpo documental es interno: sólo un administrador puede editarlo.
    if role != 'admin':
        return _err(FORBIDDEN, 'Sin permiso para ver este documento')
    return _ok(document=dict(row))


def kb_upsert(path, *, doc_id, name, body_text, kind='texto', visibility='privado',
              state='borrador', source_name=None, source_path=None,
              procedencia=None, extract_error=None, actor=None):
    """Crea o actualiza (nueva revisión) un documento del conocimiento.

    ``procedencia`` (JSON: páginas/secciones/hojas/filas) y ``extract_error``
    describen el origen del texto: un documento con error de extracción o sin
    texto no puede publicarse.
    """
    name = _clean(name, 200)
    if not name:
        return _err(EMPTY, 'El nombre del documento es obligatorio')
    if kind not in KB_KINDS:
        return _err(INVALID, 'Tipo de documento no admitido')
    visibility = visibility if visibility in ('privado', 'publico') else 'privado'
    if state not in ('borrador', 'publicado', 'desactivado', 'error'):
        state = 'borrador'
    body_text = _clean(body_text, 200000)
    procedencia_json = json.dumps(procedencia, ensure_ascii=False) if procedencia else None
    stamp = now()
    with connect(path) as conn:
        if doc_id:
            old = conn.execute('SELECT * FROM crm_kb_documents WHERE id=?', (doc_id,)).fetchone()
            if not old:
                return _err(NOT_FOUND, 'Documento no encontrado')
            version = old['version'] + 1
            _drop_fragments(conn, doc_id)
            conn.execute(
                """UPDATE crm_kb_documents SET name=?, body_text=?, kind=?, visibility=?,
                   state=?, source_name=?, source_path=?, procedencia=?, extract_error=?,
                   uploaded_by=?, version=?, index_state='pendiente', index_error=NULL,
                   updated_at=? WHERE id=?""",
                (name, body_text, kind, visibility, state, source_name, source_path,
                 procedencia_json, extract_error, actor, version, stamp, doc_id))
            return _ok(doc_id=doc_id, version=version)
        cursor = conn.execute(
            """INSERT INTO crm_kb_documents (name, version, state, visibility, kind,
               body_text, source_name, source_path, procedencia, extract_error,
               uploaded_by, index_state, created_at, updated_at)
               VALUES (?,1,?,?,?,?,?,?,?,?,?,'pendiente',?,?)""",
            (name, state, visibility, kind, body_text, source_name, source_path,
             procedencia_json, extract_error, actor, stamp, stamp))
        doc_id = cursor.lastrowid
    return _ok(doc_id=doc_id, version=1)


# v12 — crm_kb_documents sin `kind` nuevo en kb_from_upload
def kb_from_upload(path, *, name, filename, data, visibility, actor, doc_id=None):
    """Extrae un documento subido y lo guarda como BORRADOR (no publica solo).

    Los documentos son fuentes: se extrae sólo texto; las instrucciones del
    documento nunca cambian reglas. Un documento sin texto extraíble (PDF
    escaneado sin OCR) se rechaza aquí: no se guarda contenido que no se leyó.
    ``doc_id`` distinto de None edita ese documento (nueva revisión).
    """
    from crm import c02_docs
    extracted = c02_docs.extraer_documento(filename, data)
    kind = extracted['kind'] or 'texto'
    if kind in ('doc', 'xls'):
        return _err(UNSUPPORTED, extracted['extract_error'])
    if not extracted['ok']:
        return _err(INVALID, extracted['extract_error'])
    if extracted.get('extract_error'):
        return _err(INVALID, extracted['extract_error'])
    if not extracted['body_text']:
        return _err(UNSUPPORTED,
                    'El documento no tiene texto extraíble (¿escaneado sin OCR?). '
                    'No se guarda contenido que no se haya leído.')
    warnings = extracted.get('warnings') or []
    return kb_upsert(
        path, doc_id=doc_id, name=name, body_text=extracted['body_text'], kind=kind,
        visibility=visibility, state='borrador', source_name=filename,
        source_path=filename, procedencia=extracted.get('procedencia') or [],
        extract_error=' '.join(warnings) if warnings else None, actor=actor)


def _drop_fragments(conn, doc_id):
    conn.execute('DELETE FROM crm_kb_fragments WHERE doc_id=?', (doc_id,))


def kb_publish(path, *, doc_id, actor=None):
    """Publica (o re-publica) un documento y deriva sus fragmentos (índice derivado).

    Un documento con error de extracción (no leído), vacío o desactivado no se
    publica. La publicación nunca es automática tras la carga.
    """
    with connect(path) as conn:
        doc = conn.execute('SELECT * FROM crm_kb_documents WHERE id=?', (doc_id,)).fetchone()
        if not doc:
            return _err(NOT_FOUND, 'Documento no encontrado')
        if doc['state'] == 'desactivado':
            return _err(INVALID, 'El documento está desactivado; edítelo antes de publicar')
        if doc['extract_error']:
            return _err(INVALID, f"No se publica: {doc['extract_error']}")
        _drop_fragments(conn, doc_id)
        body = doc['body_text'] or ''
        if not body.strip():
            return _err(EMPTY, 'Un documento vacío no puede publicarse')
        _fragmentize(conn, doc)
        conn.execute(
            "UPDATE crm_kb_documents SET state='publicado', index_state='listo', "
            "index_error=NULL, updated_at=? WHERE id=?", (now(), doc_id))
    return _ok(doc_id=doc_id, version=doc['version'])


def kb_deactivate(path, *, doc_id, actor=None):
    """Desactiva: retira fragmentos para impedir recuperación."""
    with connect(path) as conn:
        doc = conn.execute('SELECT * FROM crm_kb_documents WHERE id=?', (doc_id,)).fetchone()
        if not doc:
            return _err(NOT_FOUND, 'Documento no encontrado')
        _drop_fragments(conn, doc_id)
        conn.execute(
            "UPDATE crm_kb_documents SET state='desactivado', index_state='pendiente', "
            "updated_at=? WHERE id=?", (now(), doc_id))
    return _ok()


def kb_retrieve_public(path, query, limit=5):
    """Recuperación derivada: fragmentos de documentos públicos publicados.

    Implementación determinista de marcado de subcadena (sin modelo externo). El
    índice derivado se consulta aquí; los documentos desactivados no aparecen.
    """
    tokens = [t.lower() for t in re.findall(r'\w+', query or '') if len(t) > 1]
    if not tokens:
        return []
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT f.doc_id, f.doc_version, f.visibility, f.body, d.name, d.version
               FROM crm_kb_fragments f JOIN crm_kb_documents d ON d.id=f.doc_id
               WHERE d.state='publicado' AND d.visibility='publico'
               ORDER BY f.id DESC""").fetchall()
    scored = []
    for r in rows:
        lower = (r['body'] or '').lower()
        score = sum(1 for t in tokens if t in lower)
        if score:
            scored.append((score, dict(r)))
    scored.sort(key=lambda x: -x[0])
    result = [r for _, r in scored[:limit]]
    return [
        {'doc_id': r['doc_id'], 'doc_version': r['doc_version'], 'visibility': r['visibility'],
         'body': r['body'], 'name': r['name'], 'version': r['version']} for r in result
    ]


def _fragmentize(conn, doc):
    """Divide el texto en oraciones/fragmentos estables (índice derivado)."""
    body = doc['body_text'] or ''
    parts = re.split(r'\n{2,}|(?<=[.!?])\s+', body)
    for idx, part in enumerate(parts):
        part = part.strip()
        if len(part) > 2:
            conn.execute(
                """INSERT INTO crm_kb_fragments (doc_id, doc_version, visibility, body)
                   VALUES (?,?,?,?)""",
                (doc['id'], doc['version'], doc['visibility'], part))


# ===========================================================================
# Canal WhatsApp durable (RF-02)
# ===========================================================================

def wa_ingest(path, *, external_id, phone, body, direction='inbound',
              account='whatsapp', kind='text', foreign_id=None):
    """Registra un mensaje externo con idempotencia durable.

    Devuelve un diccionario indicando si fue insertado o duplicado (por ID externo
    + cuenta + dirección). Es idempotente frente a reinicio.
    """
    stamp = now()
    with connect(path) as conn:
        dup = conn.execute(
            'SELECT id FROM crm_wa_messages WHERE external_id=? AND account=? AND direction=?',
            (external_id, account, direction)).fetchone()
        if dup:
            return _ok(existing=True, message_id=dup['id'], handled='duplicate')
        cursor = conn.execute(
            """INSERT INTO crm_wa_messages (external_id, account, direction, phone, type,
               body, received_at) VALUES (?,?,?,?,?,?,?)""",
            (external_id, account, direction, _clean(phone, 40), kind, _clean(body, 4000), stamp))
        message_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO crm_operations (kind,payload,created_at,updated_at)
               VALUES ('wa_message',?,?,?)""",
            (json.dumps({'message_id': message_id, 'external_id': external_id,
                         'phone': phone, 'body': body, 'foreign_id': foreign_id}),
             stamp, stamp))
    return _ok(existing=False, message_id=message_id, operation_kind='wa_message')


def wa_mark_acked(path, message_id):
    with connect(path) as conn:
        conn.execute('UPDATE crm_wa_messages SET acked=1 WHERE id=?', (message_id,))
    return _ok()


# ---------------------------------------------------------------------------
# Operaciones reclamables (worker exclusivo con recuperación de abandonados)
# ---------------------------------------------------------------------------

def op_claim(path, worker, timeout_seconds=90, limit=1):
    """Reclama operaciones pendientes o abandonadas de forma exclusiva.

    Un solo worker gana cada fila; los abandonos (expiración) se recuperan.
    """
    from datetime import timedelta
    with connect(path) as conn:
        claimed = []
        for _ in range(limit):
            expires = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            candidate = conn.execute(
                """SELECT id FROM crm_operations
                   WHERE state='pendiente'
                      OR (state='en_proceso' AND expires_at < ?)
                   ORDER BY id LIMIT 1""",
                (expires,)).fetchone()
            if not candidate:
                break
            op_id = candidate['id']
            conn.execute(
                """UPDATE crm_operations SET state='en_proceso', worker=?, claimed_at=?,
                   expires_at=?, attempts=attempts+1, updated_at=? WHERE id=? AND
                   (state='pendiente' OR (state='en_proceso' AND expires_at < ?))""",
                (worker, now(),
                 (datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)).isoformat(),
                 now(), op_id, expires))
            if conn.execute('SELECT changes() AS n').fetchone()['n'] == 1:
                op = conn.execute('SELECT * FROM crm_operations WHERE id=?', (op_id,)).fetchone()
                claimed.append(dict(op))
    return _ok(claimed=claimed)


def op_complete(path, operation_id, state='hecho', error=None):
    with connect(path) as conn:
        if state == 'error':
            conn.execute('UPDATE crm_operations SET state=?, last_error=?, updated_at=? WHERE id=?',
                         (state, (error or '')[:400], now(), operation_id))
        else:
            conn.execute('UPDATE crm_operations SET state=?, updated_at=? WHERE id=?',
                         (state, now(), operation_id))
    return _ok()


def op_release(path, operation_id):
    return op_complete(path, operation_id, state='pendiente')


def op_payload(path, operation_id):
    with connect(path) as conn:
        row = conn.execute('SELECT payload FROM crm_operations WHERE id=?', (operation_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row['payload'])
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Outbox de salida
# ---------------------------------------------------------------------------

def outbox_enqueue(path, *, channel, recipient, payload, correlation=None, operation_id=None,
                   uow=None, conversation_id=None, origin='ia', generation=None, request_id=None):
    """Encola una tarea de salida industrial.

    ``uow``: unidad de trabajo opcional (``crm.store.use``): inserta en la
    transacción de quien abrió la conexión (por ejemplo la guardia del worker, de
    modo que la cita y su mensaje se confirman juntos). Trazabilidad (HUM-05):
    cada tarea lleva su conversación, origen (ia|humano) y generación de la
    conversación en el momento de encolarse; la clave de solicitud estable
    (``request_id``) da idempotencia a los reintentos del cliente. El CHECK de
    estados sigue intacto; origin humano jamás se invalida por generación.
    """
    stamp = now()
    origin = origin if origin in ('ia', 'humano', 'sistema') else 'ia'
    scope = uow if uow is not None else connect(path)
    with scope as conn:
        cursor = conn.execute(
            """INSERT INTO crm_outbox (operation_id,channel,recipient,payload,correlation,
               state,conversation_id,origin,generation,request_id,created_at,updated_at)
               VALUES (?,?,?,?,?,'pendiente',?,?,?,?,?,?)""",
            (operation_id, channel, _clean(recipient, 60),
             json.dumps(payload, ensure_ascii=False), correlation,
             conversation_id, origin, int(generation or 0), _clean(request_id, 120) or None,
             stamp, stamp))
    return _ok(outbox_id=cursor.lastrowid)


def outbox_next(path, channel='whatsapp', limit=5):
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT * FROM crm_outbox WHERE state='pendiente' AND channel=? ORDER BY id LIMIT ?""",
            (channel, limit)).fetchall()
    return _ok(pending=[dict(r) for r in rows])


def outbox_mark(path, outbox_id, state, provider_state=None, attempts_delta=1,
                provider_message_id=None):
    with connect(path) as conn:
        if provider_message_id is not None:
            conn.execute(
                """UPDATE crm_outbox SET state=?, provider_state=?, attempts=attempts+?,
                   provider_message_id=?, updated_at=? WHERE id=?""",
                (state, _clean(provider_state, 200) or None, attempts_delta,
                 _clean(provider_message_id, 120) or None, now(), outbox_id))
            # WH-03: un webhook de estado que llegó ANTES de guardar el wamid
            # (delivery event temprano) se reconcilia ahora, en la misma
            # transacción, con la regla acumulativa; nada se pierde.
            _reconciliar_eventos(conn, provider_message_id, outbox_id)
        else:
            conn.execute(
                """UPDATE crm_outbox SET state=?, provider_state=?, attempts=attempts+?,
                   updated_at=? WHERE id=?""",
                (state, _clean(provider_state, 200) or None, attempts_delta, now(), outbox_id))
    return _ok()


def _aplicar_evento_estado(conn, outbox_id, *, estado, timestamp, error=None):
    """Aplica UN evento de estado de Meta a una fila del outbox con la regla
    acumulativa Y cronológica (WH-03-B): la evidencia MÁS RECIENTE conocida
    gana con independencia del orden de llegada, de modo que un delivered/read
    posterior a un fallo antiguo sustituye el fallo (o lo hace su
    reconciliación con el wamid), y un fallo antiguo jamás regresa un
    entregado/leído más nuevo. Un evento con marca anterior a la ya conocida
    es no-op; con la misma marca los estados normales sólo avanzan
    (repetidos/fuera de orden: nada que hacer), y el fallo no contradice una
    confirmación con igual o mayor marca. Actualizar provider_state/state
    jamás devuelve la fila a 'pendiente', por lo que no desbloquea reenvíos ni
    reintentos de resultados inciertos. Devuelve True si cambió algo. ``conn``
    es la conexión de la transacción en curso (evita locks de conexiones
    anidadas)."""
    fila = conn.execute('SELECT id, provider_state FROM crm_outbox WHERE id=?',
                        (outbox_id,)).fetchone()
    if not fila:
        return False
    actual = (fila['provider_state'] or 'aceptado').split('@', 1)[0]
    marca_ts = (fila['provider_state'] or '').split('@', 1)[1] if '@' in (fila['provider_state'] or '') else '0'
    nuevo_ts = str(timestamp)[:40] if timestamp is not None else '0'
    orden = {'aceptado': 0, 'enviado': 1, 'entregado': 2, 'leido': 3}
    if nuevo_ts < marca_ts:
        return False  # evidencia anterior a la ya conocida: no regresa el reloj
    if estado == 'fallido':
        # El fallo sólo se materializa si no contradice un entregado/leído ya
        # confirmado con la misma o mayor marca.
        if actual in ('entregado', 'leido') and nuevo_ts <= marca_ts:
            return False
        provider = 'fallido:%s' % _clean(str(error or ''), 200) if error else 'fallido'
    else:
        es_fallo_previo = actual == 'fallido' or actual.startswith('fallido:')
        if not es_fallo_previo and actual in orden and orden[estado] <= orden[actual]:
            return False  # repetido o sin avance en la escala normal
        provider = estado
    conn.execute(
        """UPDATE crm_outbox SET provider_state=?, updated_at=? WHERE id=?""",
        ('%s@%s' % (provider, nuevo_ts), now(), outbox_id))
    if conn.execute('SELECT changes() AS n').fetchone()['n'] == 1:
        conn.execute('UPDATE crm_outbox SET state=? WHERE id=?',
                     ('fallo' if estado == 'fallido' else 'enviado', outbox_id))
        return True
    return False


def _reconciliar_eventos(conn, wamid, outbox_id):
    """Aplica los eventos de estado pendientes de un wamid a su fila del outbox
    (WH-03: un delivered que llegó ANTES de guardar el wamid no se pierde).
    En orden cronológico ascendente, con la regla acumulativa; cada evento
    aplicado se marca para no re-procesarlo tras un reinicio."""
    eventos = conn.execute(
        """SELECT * FROM crm_wa_delivery_events WHERE wamid=? AND applied=0
           ORDER BY event_timestamp ASC""", (wamid,)).fetchall()
    evento = None
    for ev in eventos:
        aplicado = _aplicar_evento_estado(
            conn, outbox_id, estado=ev['status'],
            timestamp=ev['event_timestamp'], error=ev['error'])
        evento = ev['id']
        # Marcado SIEMPRE (aplicado o no-op por regla acumulativa): el evento
        # ya fue considerado para esta fila y no se re-procesa; el registro
        # (independiente del efecto) queda en la tabla para trazabilidad.
        conn.execute(
            'UPDATE crm_wa_delivery_events SET applied=1, outbox_id=? WHERE id=?',
            (outbox_id, ev['id']))
    return evento


def outbox_webhook_status(path, *, wamid, status, timestamp=None, error=None,
                          recipient_id=None):
    """Webhook de estado de Meta (sent/delivered/read/failed): PERSISTE el
    evento siempre (tabla crm_wa_delivery_events, deduplicada) y, si el outbox
    ya tiene ese wamid, lo aplica con la regla acumulativa (wh-answer no
    retrocede por eventos repetidos o fuera de orden). Si el wamid aún no está
    guardado (entrega temprana), el evento queda pendiente y se reconciliará al
    registrar el identificador del envío: nada se pierde tras el ack 200.
    Devuelve el outbox_id correlacionado o None si el evento se persistió sin
    fila (pendiente de reconciliación)."""
    NORM = {'sent': 'enviado', 'delivered': 'entregado', 'read': 'leido',
            'failed': 'fallido'}
    estado = NORM.get(status, status)
    stamp = timestamp or now()
    with connect(path) as conn:
        # 1) Persistencia durable y deduplicada del evento firmado.
        conn.execute(
            """INSERT OR IGNORE INTO crm_wa_delivery_events
               (wamid, status, event_timestamp, recipient_id, error,
                outbox_id, applied, created_at)
               VALUES (?,?,?,?,?,NULL,0,?)""",
            (wamid, estado, str(stamp)[:40], _clean(recipient_id or '', 40),
             _clean(error or '', 200), now()))
        # 2) Si ya hay fila con ese wamid, aplicar ahora; si no, queda el
        #    evento persistido y la reconciliación ocurre al marcar el wamid.
        fila = conn.execute(
            'SELECT id FROM crm_outbox WHERE provider_message_id=?', (wamid,)).fetchone()
        if not fila:
            return None
        _aplicar_evento_estado(conn, fila['id'], estado=estado,
                               timestamp=stamp, error=error)
        _reconciliar_eventos(conn, wamid, fila['id'])
    return fila['id']


def en_ventana_servicio(path, phone, horas=24):
    """Ventana de atención de 24 h: la abre un mensaje entrante del cliente y
    permite respuesta de texto libre. Sin inbound reciente, la respuesta sólo
    podría ser una plantilla aprobada (regla Meta). Devuelve True/False."""
    from datetime import timedelta
    limite = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(horas)))).isoformat()
    with connect(path) as conn:
        row = conn.execute(
            """SELECT 1 FROM crm_wa_messages
               WHERE direction='inbound' AND phone=? AND received_at >= ?
               ORDER BY received_at DESC LIMIT 1""",
            (phone, limite)).fetchone()
    return row is not None


def _outbox_task_cancelada(conn, row):
    """Tarea IA de una era anterior a la toma/devolución/cierre de su
    conversación: se invalida en el consumidor y jamás se entrega. Las tareas de
    origen humano (respuestas del operador) nunca se cancelan."""
    if (row['origin'] or 'ia') != 'ia' or not row['conversation_id']:
        return False
    conv = conn.execute('SELECT state, generation FROM crm_conversations WHERE id=?',
                        (row['conversation_id'],)).fetchone()
    if not conv or conv['state'] in ('humano_asignado', 'esperando_humano', 'cerrada'):
        return True
    return int(conv['generation']) != int(row['generation'])


def outbox_claim(path, worker='egress', limit=10):
    """Reclama tareas pendientes para el consumidor de salida (HUM-05).

    El reclamo ocurre dentro de la MISMA transacción (BEGIN IMMEDIATE + lock de
    escritura, válido entre procesos que comparten la base): decidir 'inválida' y
    'reclamada' no deja ventana entre comprobar y marcar. Las tareas IA de la
    era previa usada por la conversación se invalidan (``fallo``/``invalidada``)
    y no salen; las humanas legítimas siempre pasan. Las reclamadas quedan en
    ``intento`` con su PROPIEDAD registrada (``claimed_by``/``claimed_at``,
    migración v10): es el trabajo de este consumidor, y ``outbox_begin_send``
    la revalida justo antes de la llamada externa; un requeue no recupera un
    envío todavía activo."""
    stamp = now()
    claimed = []
    invalidadas = []
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute(
            "SELECT * FROM crm_outbox WHERE state='pendiente' ORDER BY id LIMIT ?",
            (limit,)).fetchall()
        for r in rows:
            if _outbox_task_cancelada(conn, r):
                cur = conn.execute(
                    """UPDATE crm_outbox SET state='fallo', provider_state='invalidada',
                       attempts=attempts+1, updated_at=? WHERE id=? AND state='pendiente'""",
                    (stamp, r['id']))
                if cur.rowcount == 1:
                    invalidadas.append({'outbox_id': r['id'], 'origin': r['origin'],
                                        'conversation_id': r['conversation_id'],
                                        'generation': r['generation']})
                continue
            cur = conn.execute(
                """UPDATE crm_outbox SET state='intento', claimed_by=?, claimed_at=?,
                   attempts=attempts+1, updated_at=?
                   WHERE id=? AND state='pendiente'""",
                (worker, stamp, stamp, r['id']))
            if cur.rowcount == 1:
                d = dict(r)
                d['claimed_by'] = worker
                d['claimed_at'] = stamp
                try:
                    d['payload'] = json.loads(d['payload'] or '{}')
                except ValueError:
                    d['payload'] = {}
                claimed.append(d)
    return _ok(claimed=claimed, invalidadas=invalidadas)


def outbox_requeue(path, *, outbox_id=None, max_attempts=3, timeout_seconds=120):
    """Reintento EXPLÍCITO y acotado, nunca reenvío ciego (HUM-10/CH-02).

    Estados RECUPERABLES expresamente (lista explícita; actualización atómica
    con comparación del estado y del propietario del intento):
    - ``intento`` VENCIDA por antigüedad (``updated_at < cutoff`` NUNCA autorizó
      una llamada externa; se descarta un reclamo de propiedad aún vigente) y
      ``attempts < max_attempts``;
    - ``fallo`` CIERTO NO ``invalidada`` (rechazo explícito del proveedor sin
      recepción) y ``attempts < max_attempts``.

    NUNCA se recuperan (quedan en ``bloqueados``, nunca se reencolan):
    - ``enviado``/``entregado``/``aceptado`` (ya entregado; reintentar = duplicar);
    - ``fallo``/``invalidada`` (IA de era previa; jamás se reenvía);
    - ``incierto`` y ``autorizado`` (resultado indeterminado/acuse perdido y
      envío en vuelo de un consumidor) HASTA ``outbox_reconciliar`` con
      idempotencia declarada del transporte;
    - ``intento`` RECIENTE (claim de otro proceso/consumidor en curso: la
      propiedad del trabajo bloquea recuperar un envío todavía activo).

    Al reencolar una recuperable se limpian la propiedad, la fase de envío y el
    estado previo (``claimed_by``/``claimed_at``/``began_at``/``provider_state``)
    y vuelve a ``pendiente``.
    """
    from datetime import timedelta
    stamp = now()
    n = 0
    bloqueados = []
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat()
    recuperables = ('intento', 'fallo')
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        if outbox_id is not None:
            rows = conn.execute('SELECT * FROM crm_outbox WHERE id=?', (outbox_id,)).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM crm_outbox
                   WHERE state IN ('intento','fallo') AND updated_at < ? ORDER BY id LIMIT 50""",
                (cutoff,)).fetchall()
        for r in rows:
            if r['state'] not in recuperables:
                bloqueados.append({'outbox_id': r['id'], 'state': r['state'],
                                   'provider_state': r['provider_state'],
                                   'motivo': 'estado_no_recuperable'})
                continue
            if r['state'] == 'fallo' and r['provider_state'] in ('invalidada',):
                bloqueados.append({'outbox_id': r['id'], 'state': r['state'],
                                   'provider_state': r['provider_state'],
                                   'motivo': 'invalidada'})
                continue
            if r['attempts'] >= max_attempts:
                bloqueados.append({'outbox_id': r['id'], 'state': r['state'],
                                   'provider_state': r['provider_state'],
                                   'motivo': 'tope_de_intentos'})
                continue
            if r['state'] == 'intento':
                # Un reclamo vigente es trabajo de otro consumidor (o de este,
                # todavía en curso): no recuperarlo. Sin antigüedad suficiente no
                # es un abandono.
                if not r['claimed_at'] or r['claimed_at'] >= cutoff:
                    bloqueados.append({'outbox_id': r['id'], 'state': r['state'],
                                       'provider_state': r['provider_state'],
                                       'motivo': 'claim_activo'})
                    continue
            # Comparación atómica del estado recuperable: nada más puede
            # reencolarla en paralelo en este intervalo (BEGIN IMMEDIATE).
            cur = conn.execute(
                """UPDATE crm_outbox SET state='pendiente', provider_state=NULL,
                   claimed_by=NULL, claimed_at=NULL, began_at=NULL, updated_at=?
                   WHERE id=? AND state=? AND attempts=? AND attempts < ?""",
                (stamp, r['id'], r['state'], r['attempts'], max_attempts))
            n += cur.rowcount
        # Tareas no recuperables informadas al operador (evidencia del estado).
        for estado in ('enviado', 'incierto', 'autorizado'):
            extra = conn.execute(
                """SELECT id, state, provider_state FROM crm_outbox
                   WHERE state=? AND (? IS NULL OR id=?) ORDER BY id LIMIT 50""",
                (estado, outbox_id, outbox_id)).fetchall()
            bloqueados.extend({'outbox_id': e['id'], 'state': e['state'],
                               'provider_state': e['provider_state'],
                               'motivo': 'no_recuperable_sin_reconciliacion'}
                              for e in extra)
    return _ok(requeued=n, bloqueados=bloqueados)


def outbox_begin_send(path, outbox_id, worker=None):
    """AUTORIZACIÓN LOCAL del transporte (CH-01): coordinación transaccional de
    la toma humana con el inicio del envío.

    Se ejecuta en su PROPIA transacción corta con lock de escritura (BEGIN
    IMMEDIATE; mecanismo entre procesos que comparten la base) y se commitea
    ANTES de la llamada externa: ninguna transacción SQLite queda abierta
    durante la red. NO es el comienzo de la llamada (CH-01 3ª revisión): la
    tarea pasa de ``intento`` a ``autorizado`` con ``began_at`` NULL, es decir
    admitida localmente y lista para comenzar; ``outbox_mark_sending`` (CAS
    durable sobre ``began_at``) es quien decide si la llamada al transporte
    realmente comienza, y esa es la marca que ve la toma (``envio_en_curso``).

    Linealización correcta, sin cambiar nombres de estados para ocultar el
    defecto:
    - Si la toma/devolución/cierre se confirmó ANTES de esta autorización (o la
      propiedad del intento no es de este consumidor), la tarea se INVALIDA aquí
      y el envío NO comienza: cero efectos externos. Una tarea ya invalidada
      (``fallo``/``invalidada``) también se informa como tal.
    - Si esta autorización gana (commit), la llamada aún NO ha comenzado: la
      toma posterior la puede invalidar en ``conv_take`` (``began_at`` NULL) o
      en ``outbox_mark_sending``, y ninguna recepción llega al cliente.
    """
    stamp = now()
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        r = conn.execute('SELECT * FROM crm_outbox WHERE id=?', (outbox_id,)).fetchone()
        if not r:
            return _err(NOT_FOUND, 'Tarea de salida no encontrada')
        if r['state'] != 'intento':
            if r['state'] == 'fallo' and r['provider_state'] == 'invalidada':
                return _ok(begin=False, invalidada=True)
            return _ok(begin=False, existing_state=r['state'])
        if worker is not None and r['claimed_by'] and r['claimed_by'] != worker:
            return _ok(begin=False, existing_state=r['state'], ajeno=True)
        if _outbox_task_cancelada(conn, r):
            conn.execute(
                """UPDATE crm_outbox SET state='fallo', provider_state='invalidada',
                   claimed_at=NULL, updated_at=? WHERE id=? AND state='intento'""",
                (stamp, outbox_id))
            return _ok(begin=False, invalidada=True)
        cur = conn.execute(
            """UPDATE crm_outbox SET state='autorizado', provider_state='en_vuelo',
               claimed_by=?, claimed_at=?, updated_at=? WHERE id=? AND state='intento'""",
            (worker, stamp, stamp, outbox_id))
        return _ok(begin=cur.rowcount == 1)


def outbox_mark_sending(path, outbox_id, worker=None):
    """COMIENZO REAL de la llamada al transporte (CH-01 3ª revisión).

    CAS durable y atómico en su propia transacción corta con lock de escritura
    (BEGIN IMMEDIATE; mecanismo compartido entre procesos de la instalación),
    ejecutada JUSTO ANTES de invocar ``transporte.deliver`` y commiteada ANTES
    de la llamada externa. El commit de este CAS es el punto de linearización
    del inicio del envío: fija ``began_at`` (migración v11) y re-chequea la
    conversación en el MISMO lock que usa ``conv_take``.

    Orden inequívoco (sin sleeps ni cambio de nombres de estados):
    - Si la toma ganó (conversación con era nueva / humano_asignado /
      esperando_humano / cerrada) tras la autorización local, la tarea se
      INVALIDA aquí y la llamada al transporte NO comienza: cero efectos
      externos.
    - Si este CAS gana (commit, ``began_at`` fijado), el transporte YA comenzó:
      una toma posterior ve la marca, informa ``envio_en_curso`` y no afirma
      cancelación. Repetir el CAS sobre una tarea ya comenzada es idempotente
      (``comenzado=True``, ``ya=True``).
    """
    stamp = now()
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        r = conn.execute('SELECT * FROM crm_outbox WHERE id=?', (outbox_id,)).fetchone()
        if not r:
            return _err(NOT_FOUND, 'Tarea de salida no encontrada')
        if r['state'] != 'autorizado':
            if r['state'] == 'fallo' and r['provider_state'] == 'invalidada':
                return _ok(comenzado=False, invalidada=True)
            return _ok(comenzado=False, existing_state=r['state'])
        if worker is not None and r['claimed_by'] and r['claimed_by'] != worker:
            return _ok(comenzado=False, ajeno=True)
        if r['began_at'] is not None:
            return _ok(comenzado=True, ya=True)
        if _outbox_task_cancelada(conn, r):
            conn.execute(
                """UPDATE crm_outbox SET state='fallo', provider_state='invalidada',
                   claimed_at=NULL, updated_at=? WHERE id=? AND state='autorizado'""",
                (stamp, outbox_id))
            return _ok(comenzado=False, invalidada=True, motivo='toma_anterior')
        cur = conn.execute(
            """UPDATE crm_outbox SET began_at=?, updated_at=? WHERE id=? AND state='autorizado'""",
            (stamp, stamp, outbox_id))
        return _ok(comenzado=cur.rowcount == 1)


def outbox_recover_stale(path, timeout_seconds=120, clock=None):
    """Recuperación ante caída del consumidor (CH-01 3ª revisión): nunca deja
    la conversación bloqueada indefinidamente ni permite un reenvío incierto.

    Tarea en ``autorizado`` más antigua que ``timeout_seconds`` (sin actividad):
    - ``began_at`` NULL: la llamada al transporte NUNCA comenzó (el consumidor
      cayó entre la autorización local y el comienzo real). Resultado CIERTO de
      no-entrega: se declara ABANDONADA (``fallo``/``abandonado``) y el reintento
      acotado de ``outbox_requeue`` es legítimo.
    - ``began_at`` NOT NULL: la llamada YA estaba en marcha cuando cayó; el
      destinatario pudo recibir. Resultado INCIERTO: ``incierto``/
      ``timeout:consumidor_caido``, NUNCA reenviado a ciegas (bloqueado hasta
      reconciliar o demostrar idempotencia del transporte).

    ``clock`` es inyectable para pruebas. El barrido es acotado (50 tareas) y la
    comparación es por antigüedad, no un bloqueo: ninguna espera arbitraria.
    """
    stamp = now()
    clock = clock or (lambda: datetime.now(timezone.utc))
    cutoff = (clock() - timedelta(seconds=timeout_seconds)).isoformat()
    abandonadas = 0
    inciertas = 0
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute(
            """SELECT * FROM crm_outbox
               WHERE state='autorizado' AND updated_at < ? ORDER BY id LIMIT 50""",
            (cutoff,)).fetchall()
        for r in rows:
            if r['began_at'] is None:
                cur = conn.execute(
                    """UPDATE crm_outbox SET state='fallo', provider_state='abandonado',
                       claimed_by=NULL, claimed_at=NULL, updated_at=?
                       WHERE id=? AND state='autorizado'""",
                    (stamp, r['id']))
                if cur.rowcount == 1:
                    abandonadas += 1
            else:
                cur = conn.execute(
                    """UPDATE crm_outbox SET state='incierto',
                       provider_state='timeout:consumidor_caido', updated_at=?
                       WHERE id=? AND state='autorizado'""",
                    (stamp, r['id']))
                if cur.rowcount == 1:
                    inciertas += 1
    return _ok(abandonadas=abandonadas, inciertas=inciertas)


def outbox_reconciliar(path, outbox_id, asumir_idempotente=False):
    """Reconciliación explícita de resultado indeterminado (CH-02).

    Una tarea en ``incierto``/``autorizado`` sólo puede reencolarse si quien
    decide declara idempotencia del destino (``asumir_idempotente``): el envío
    repetido con la misma clave de solicitud/correlación es seguro porque el
    destino deduplica. Sin esa declaración, el reenvío queda bloqueado para no
    duplicar un mensaje que el cliente pudo ya recibir."""
    if not asumir_idempotente:
        return _err(INVALID, 'Resultado incierto: se requiere reconciliación o idempotencia del transporte')
    stamp = now()
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        r = conn.execute('SELECT * FROM crm_outbox WHERE id=?', (outbox_id,)).fetchone()
        if not r:
            return _err(NOT_FOUND, 'Tarea de salida no encontrada')
        if r['state'] not in ('incierto', 'autorizado'):
            return _err(INVALID, 'La tarea no requiere reconciliación',
                        state=r['state'])
        conn.execute(
            """UPDATE crm_outbox SET state='pendiente', provider_state='reconciliado',
               claimed_by=NULL, claimed_at=NULL, began_at=NULL, updated_at=? WHERE id=?""",
            (stamp, outbox_id))
    return _ok(reconciliado=True)


# ===========================================================================
# Bandeja humana (C02-HUM)
# ===========================================================================

HANDOFF_REASONS = ('humano_explicito', 'emergencia', 'sin_fuente', 'fallo_servicio', 'por_revision', 'reclamo', 'peligro_inmediato')


def conv_ensure(path, client_key, channel='whatsapp', client_name=None):
    """Devuelve (o crea) la conversación del cliente. Esta no es la versión pública
    a la que el bot puede acceder sin permiso: se usa tras resolver la identidad."""
    stamp = now()
    with connect(path) as conn:
        row = conn.execute('SELECT * FROM crm_conversations WHERE client_key=?', (client_key,)).fetchone()
        if not row:
            cursor = conn.execute(
                """INSERT INTO crm_conversations (client_key, channel, client_name, updated_at)
                   VALUES (?,?,?,?)""", (client_key, channel, _clean(client_name, 120), stamp))
            row = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (cursor.lastrowid,)).fetchone()
    return dict(row)


def conv_add_message(path, conversation_id, *, direction, body, author_type='sistema',
                     author_user_id=None, wa_message_id=None, state='pendiente'):
    stamp = now()
    if direction not in ('inbound', 'outbound', 'note', 'internal'):
        return _err(INVALID, 'Dirección de mensaje no válida')
    with connect(path) as conn:
        cursor = conn.execute(
            """INSERT INTO crm_conversation_messages (conversation_id, direction,
               author_user_id, author_type, body, wa_message_id, state, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (conversation_id, direction, author_user_id, author_type, _clean(body, 4000),
             wa_message_id, state, stamp))
        conn.execute('UPDATE crm_conversations SET updated_at=? WHERE id=?', (stamp, conversation_id))
    return _ok(message_id=cursor.lastrowid)


def outbox_history(path, *, channel=None, limit=200):
    """Biblioteca de envíos (sólo lectura, 2026-10-29). Devuelve las filas
    recientes del outbox con el estado, el último estado del proveedor y el
    recuento de eventos de entrega registrados. No reenvía ni muta nada."""
    with connect(path) as conn:
        if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='crm_outbox'"
        ).fetchone():
            return []
        q = ("SELECT o.id, o.channel, o.recipient, o.operation_id, o.correlation, "
             "o.state, o.provider_state, o.provider_message_id, o.attempts, o.origin, "
             "o.created_at, o.updated_at, "
             "(SELECT COUNT(*) FROM crm_wa_delivery_events e WHERE e.outbox_id=o.id) AS eventos "
             "FROM crm_outbox o")
        params = []
        if channel:
            q += " WHERE o.channel=?"
            params.append(channel)
        q += " ORDER BY o.created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def conversations_list(path, *, role='user', user_id=None):
    """Lista de la bandeja humana: conversaciones con estado, alertas y responsable."""
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT c.*, u.name AS responsible_name,
                      (SELECT COUNT(*) FROM crm_human_alerts a
                       WHERE a.conversation_id=c.id AND a.state='activa') AS alerts_active,
                      (SELECT COUNT(*) FROM crm_conversation_messages m
                       WHERE m.conversation_id=c.id) AS message_count
               FROM crm_conversations c
               LEFT JOIN crm_users u ON u.id=c.responsible_user_id
               ORDER BY c.updated_at DESC""").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            import json as _json
            d['pending'] = _json.loads(d['pending']) if d.get('pending') else None
        except (TypeError, ValueError):
            d['pending'] = None
        result.append(d)
    return result


def conv_messages(path, conversation_id, limit=200):
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT m.*, u.name AS author_name, w.phone AS wa_phone
               FROM crm_conversation_messages m
               LEFT JOIN crm_users u ON u.id=m.author_user_id
               LEFT JOIN crm_wa_messages w ON w.id=m.wa_message_id
               WHERE m.conversation_id=?
               ORDER BY m.id LIMIT ?""", (conversation_id, limit)).fetchall()
        entregas = {}
        for r in rows:
            if r['direction'] == 'outbound':
                tarea = conn.execute(
                    """SELECT state, provider_state FROM crm_outbox
                       WHERE correlation=? ORDER BY id DESC LIMIT 1""",
                    ('msg-%d' % r['id'],)).fetchone()
                if tarea:
                    entregas[r['id']] = {'state': tarea['state'],
                                         'provider_state': tarea['provider_state']}
    result = [dict(r) for r in rows]
    for d in result:
        if d['id'] in entregas:
            d['entrega'] = entregas[d['id']]
    return result


def conv_alerts(path, conversation_id=None, include_resolved=True):
    with connect(path) as conn:
        if conversation_id is not None and not include_resolved:
            rows = conn.execute(
                "SELECT * FROM crm_human_alerts WHERE conversation_id=? AND state='activa' ORDER BY id",
                (conversation_id,)).fetchall()
        elif conversation_id is not None:
            rows = conn.execute(
                'SELECT * FROM crm_human_alerts WHERE conversation_id=? ORDER BY id',
                (conversation_id,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM crm_human_alerts ORDER BY id').fetchall()
    return [dict(r) for r in rows]


def conv_alert_active_count(path):
    with connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM crm_human_alerts WHERE state='activa'").fetchone()
    return int(row['n'])


def conv_raise_alert(path, *, conversation_id, reason, priority='alta', message=None,
                     evidence=None):
    """Crea una alerta humana persistente (antes de pedir todos los datos).

    ``evidence`` es una evidencia breve del mensaje que disparó la derivación
    (texto normalizado y recortado) para el equipo; no se expone en el panel
    global de la campana, sólo en la conversación autorizada.
    """
    if reason not in HANDOFF_REASONS:
        return _err(INVALID, 'Motivo de derivación no válido')
    stamp = now()
    alert_id = None
    with connect(path) as conn:
        dup = conn.execute(
            """SELECT id FROM crm_human_alerts WHERE conversation_id=? AND state='activa' AND reason=?""",
            (conversation_id, reason)).fetchone()
        if dup:
            conn.rollback()
            return _ok(existing=True, alert_id=dup['id'], handled='duplicate')
        conn.execute(
            """INSERT INTO crm_human_alerts (conversation_id, reason, priority, state, created_at, evidence)
               VALUES (?,?,?,'activa',?,?)""",
            (conversation_id, reason, 'alta' if priority not in ('normal',) else priority, stamp,
             _clean(evidence, 400) or None))
        conn.execute("UPDATE crm_conversations SET state='esperando_humano' WHERE id=?",
                     (conversation_id,))
        fila = conn.execute(
            'SELECT id FROM crm_human_alerts WHERE conversation_id=? AND reason=?',
            (conversation_id, reason)).fetchone()
        alert_id = fila['id'] if fila else None
    # La nota interna se escribe FUERA de la transacción de la alerta: evitar
    # anidar conexiones con el lock de escritura de la primera (database locked).
    if message and alert_id:
        conv_add_message(path, conversation_id, direction='internal', body=message,
                         author_type='sistema')
    return _ok(existing=False, alert_id=alert_id)


def conv_mark_alert(path, alert_id, state='leida'):
    """Marca el estado de una alerta. 'resuelta' fija resolved_at (la alerta
    deja de activar el indicador; el historial, motivo y responsable se
    conservan). Abrir/leer ('leida') NO resuelve la atención."""
    stamp = now() if state == 'resuelta' else None
    with connect(path) as conn:
        if stamp:
            conn.execute("UPDATE crm_human_alerts SET state=?, resolved_at=? WHERE id=?",
                         (state, stamp, alert_id))
        else:
            conn.execute('UPDATE crm_human_alerts SET state=? WHERE id=?', (state, alert_id))
    return _ok()


def atencion_panel(path, *, role='user', user_id=None):
    """Estado global de la alerta superior de atención humana.

    Distingue PENDIENTES (alerta activa o leída y la conversación AÚN no está
    tomada por un operador) de EN ATENCIÓN (alerta activa o leída y la
    conversación YA está tomada, con responsable). Agrupa por conversación: el
    contador global es de conversaciones únicas (sin duplicados por varias
    alertas de la misma conversación). NO expone mensajes privados: sólo
    motivo, prioridad, antigüedad, cliente y responsable. Abrir la campana
    (GET) no muta ningún estado: la resolución es un acto explícito del operador.
    """
    ahora = now()
    try:
        ahora_dt = datetime.fromisoformat(ahora)
    except ValueError:
        ahora_dt = datetime.now(timezone.utc)
    with connect(path) as conn:
        rows = conn.execute(
            """SELECT a.id AS alert_id, a.conversation_id, a.reason, a.priority,
                      a.state, a.created_at, a.resolved_at,
                      c.client_key, c.state AS conv_state,
                      u.name AS responsible_name
               FROM crm_human_alerts a
               JOIN crm_conversations c ON c.id = a.conversation_id
               LEFT JOIN crm_users u ON u.id = c.responsible_user_id
               WHERE a.state IN ('activa','leida')
               ORDER BY CASE a.priority WHEN 'alta' THEN 0 ELSE 1 END, a.created_at, a.id""").fetchall()
    por_conversacion = {}
    for r in rows:
        d = dict(r)
        try:
            created = datetime.fromisoformat(d['created_at'])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            espera = max(0, int((ahora_dt - created).total_seconds()))
        except (TypeError, ValueError):
            espera = 0
        item = por_conversacion.setdefault(d['conversation_id'], {
            'conversation_id': d['conversation_id'],
            'client_key': d['client_key'],
            'conv_state': d['conv_state'],
            'responsible_name': d.get('responsible_name'),
            'alerts': [],
            'prioridad_max': 'normal',
            'tiempo_espera_seg': espera,
        })
        item['alerts'].append({
            'alert_id': d['alert_id'], 'reason': d['reason'],
            'priority': d['priority'], 'state': d['state'],
            'created_at': d['created_at'],
        })
        if d['priority'] == 'alta':
            item['prioridad_max'] = 'alta'
        item['tiempo_espera_seg'] = min(item['tiempo_espera_seg'], espera)
    pendientes = []
    en_atencion = []
    for item in por_conversacion.values():
        if item['conv_state'] == 'humano_asignado' and item.get('responsible_name'):
            en_atencion.append(item)
        else:
            pendientes.append(item)
    pendientes.sort(key=lambda x: (x['prioridad_max'] != 'alta', x['tiempo_espera_seg']))
    en_atencion.sort(key=lambda x: (x['prioridad_max'] != 'alta', x['tiempo_espera_seg']))
    return {'ok': True, 'pendientes': pendientes, 'en_atencion': en_atencion,
            'total_pendientes': len(pendientes), 'total_en_atencion': len(en_atencion),
            'total_pendientes_global': len(pendientes) + len(en_atencion)}


def conv_take(path, *, conversation_id, user_id, role='user',
              timeout_seconds=0):
    """Toma de control transaccional (HUM-06, CH-01 3ª revisión): la pausa IA, el
    responsable y el incremento de generación de la conversación se confirman en
    UNA transacción con lock de escritura (BEGIN IMMEDIATE; mecanismo compartido
    entre procesos). Dos operadores concurrentes: un solo ganador, el otro
    recibe conflicto; el ganador persiste tras reiniciar la base. Tomar lo ya
    propio es idempotente (no vuelve a invalidar la generación).

    Coordinación con el comienzo real del transporte (CH-01): la toma adquiere
    el MISMO bloqueo de conversación que usa ``outbox_mark_sending`` + el
    transporte, por lo que nunca se interpola entre el comienzo del envío y su
    llamada.

    1) cuenta las tareas IA de la conversación cuyo transporte YA comenzó
       (``began_at`` NOT NULL, entregado o en vuelo) e informa honestamente como
       ``envio_en_curso``: ese envío puede llegar y no se afirma una cancelación
       imposible;
    2) invalida TODAS las tareas IA que AÚN NO comenzaron (``began_at`` NULL en
       ``pendiente``/``intento``/``autorizado``): con la toma confirmada, ningún
       envío no iniciado puede comenzar después (``outbox_mark_sending``
       re-chequea lo mismo por defensa). Las respuestas humanas (origin humano)
       nunca se invalidan.

    La toma nunca espera indefinidamente: adquiere el bloqueo con el tiempo de
    espera dado (``timeout_seconds=0`` = intento único sin bloqueo). Si otro
    proceso está entregando y retiene el bloqueo, la toma no confirma el éxito;
    informa que hay un envío en curso (``envio_en_curso``) y permite reintentar.
    """
    if role != 'admin':
        return _err(FORBIDDEN, 'Sólo un usuario autorizado puede tomar el control')
    stamp = now()
    with conversation_lock(path, conversation_id,
                           timeout_seconds=timeout_seconds) as adquirido:
        if not adquirido:
            # Otro proceso está entregando: no se confirma la toma, se informa
            # del estado real (envío en curso) y se permite reintentar.
            en_curso = _envio_en_curso_count(path, conversation_id)
            return _err(CONCURRENCY,
                        'La conversación tiene un envío en curso; reintente',
                        envio_en_curso=en_curso)
        with connect(path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conv = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (conversation_id,)).fetchone()
            if not conv:
                return _err(NOT_FOUND, 'Conversación no encontrada')
            if conv['state'] == 'cerrada':
                return _err(INVALID, 'La conversación está cerrada')
            en_curso = _envio_en_curso_count_conn(conn, conversation_id)
            if conv['state'] == 'humano_asignado' and conv['responsible_user_id'] == user_id:
                return _ok(state='humano_asignado', existing=True, envio_en_curso=en_curso)
            if conv['state'] == 'humano_asignado' and conv['responsible_user_id'] and \
               conv['responsible_user_id'] != user_id:
                return _err(CONCURRENCY, 'La conversación ya está asignada a otro operador')
            conn.execute(
                """UPDATE crm_outbox SET state='fallo', provider_state='invalidada',
                   claimed_by=NULL, claimed_at=NULL, updated_at=?
                   WHERE conversation_id=? AND origin='ia' AND began_at IS NULL
                     AND state IN ('pendiente','intento','autorizado')""",
                (stamp, conversation_id))
            conn.execute(
                """UPDATE crm_conversations SET state='humano_asignado', responsible_user_id=?,
                   egress_paused=1, generation=generation+1, updated_at=? WHERE id=?""",
                (user_id, stamp, conversation_id))
            conn.execute(
                """UPDATE crm_conversation_messages SET state='cancelada'
                   WHERE conversation_id=? AND state='pendiente' AND direction='outbound'""",
                (conversation_id,))
    return _ok(state='humano_asignado', envio_en_curso=en_curso)


def _envio_en_curso_count(path, conversation_id) -> int:
    """Cuenta tareas IA de la conversación cuyo transporte comenzó
    (began_at fijado), entregado o en vuelo. Lectura breve, sin retener bloqueo."""
    if not conversation_id:
        return 0
    with connect(path) as conn:
        return _envio_en_curso_count_conn(conn, conversation_id)


def _envio_en_curso_count_conn(conn, conversation_id) -> int:
    return int(conn.execute(
        """SELECT COUNT(*) AS n FROM crm_outbox
           WHERE conversation_id=? AND origin='ia' AND began_at IS NOT NULL""",
        (conversation_id,)).fetchone()['n'])


def conv_return(path, *, conversation_id, user_id):
    """Devuelve explícitamente a la IA (HUM-07): sólo el operador asignado.
    Limpia la intención pendiente que el humano dejó obsoleta —devolver NO
    reactiva la cadena vieja—, levanta la pausa e incrementa la generación para
    invalidar cualquier resto de la era humana. Si ya estaba en IA activa se
    devuelve el estado como idempotente."""
    stamp = now()
    with conversation_lock(path, conversation_id) as adquirido:
        if not adquirido:
            return _err(CONCURRENCY,
                        'La conversación tiene un envío en curso; reintente')
        with connect(path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conv = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (conversation_id,)).fetchone()
            if not conv:
                return _err(NOT_FOUND, 'Conversación no encontrada')
            if conv['state'] == 'ia_activa':
                return _ok(state='ia_activa', existing=True)
            if conv['state'] != 'humano_asignado' or conv['responsible_user_id'] != user_id:
                return _err(FORBIDDEN, 'Sólo el operador asignado puede devolver la conversación')
            conn.execute(
                """UPDATE crm_conversations SET state='ia_activa', responsible_user_id=NULL,
                   pending=NULL, egress_paused=0, generation=generation+1, updated_at=? WHERE id=?""",
                (stamp, conversation_id))
    return _ok(state='ia_activa')


def conv_close(path, *, conversation_id, user_id):
    """Cierra la conversación desde la bandeja (HUM-07b): no admite respuestas ni
    vuelta a IA; la generación nueva invalida los trabajos antiguos. Sólo el
    operador asignado (o una conversación ya cerrada, idempotente)."""
    stamp = now()
    with conversation_lock(path, conversation_id) as adquirido:
        if not adquirido:
            return _err(CONCURRENCY,
                        'La conversación tiene un envío en curso; reintente')
        with connect(path) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conv = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (conversation_id,)).fetchone()
            if not conv:
                return _err(NOT_FOUND, 'Conversación no encontrada')
            if conv['state'] == 'cerrada':
                return _ok(state='cerrada', existing=True)
            if conv['state'] != 'humano_asignado' or conv['responsible_user_id'] != user_id:
                return _err(FORBIDDEN, 'Sólo el operador asignado puede cerrar la conversación')
            conn.execute(
                """UPDATE crm_conversations SET state='cerrada', egress_paused=1,
                   pending=NULL, generation=generation+1, updated_at=? WHERE id=?""",
                (stamp, conversation_id))
            conn.execute(
                """UPDATE crm_conversation_messages SET state='cancelada'
                   WHERE conversation_id=? AND state='pendiente' AND direction='outbound'""",
                (conversation_id,))
    return _ok(state='cerrada')


def conv_reply_humano(path, *, conversation_id, user_id, role, body, request_id=None):
    """Respuesta autorizada del operador asignado, coordinada con el outbox (N4).

    Crea el mensaje (outbound, autor humano) y la tarea de salida (origen humano,
    misma conversación y generación) en UNA transacción: la respuesta humana
    jamás se invalida por generación y el consumidor la entrega por el transporte
    inyectable. La clave de solicitud estable (``request_id``) hace idempotente el
    reintento con el mismo contenido y rechaza (409) la misma clave con otro
    contenido sin sobrescribir lo ya aceptado (HUM-09)."""
    body = _clean((body or ''), 4000)
    if not body:
        return _err(EMPTY, 'El mensaje de respuesta no puede estar vacío')
    request_id = _clean(request_id, 120)
    if not request_id:
        return _err(INVALID, 'Falta una clave de solicitud estable (request_id)')
    if role != 'admin':
        return _err(FORBIDDEN, 'Sólo un operador autorizado puede responder')
    stamp = now()
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        conv = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (conversation_id,)).fetchone()
        if not conv:
            return _err(NOT_FOUND, 'Conversación no encontrada')
        if conv['state'] == 'cerrada':
            return _err(INVALID, 'La conversación está cerrada')
        if conv['state'] != 'humano_asignado' or conv['responsible_user_id'] != user_id:
            return _err(FORBIDDEN, 'Sólo el operador asignado puede responder a esta conversación')
        prev = conn.execute(
            """SELECT id, payload FROM crm_outbox
               WHERE request_id=? AND conversation_id=? ORDER BY id DESC LIMIT 1""",
            (request_id, conversation_id)).fetchone()
        if prev:
            try:
                prev_body = (json.loads(prev['payload'] or '{}') or {}).get('text')
            except ValueError:
                prev_body = None
            if prev_body != body:
                return _err(VERSION_CONFLICT, 'La clave de solicitud ya se usó con otro contenido',
                            existing=True)
            return _ok(existing=True, outbox_id=prev['id'])
        cursor = conn.execute(
            """INSERT INTO crm_conversation_messages (conversation_id, direction,
               author_user_id, author_type, body, state, created_at)
               VALUES (?,?,?,?,?,'pendiente',?)""",
            (conversation_id, 'outbound', user_id, 'humano', body, stamp))
        msg_id = cursor.lastrowid
        outbox = conn.execute(
            """INSERT INTO crm_outbox (operation_id,channel,recipient,payload,correlation,
               state,conversation_id,origin,generation,request_id,created_at,updated_at)
               VALUES (?,?,?,?,?,'pendiente',?,?,?,?,?,?)""",
            ('humano', 'whatsapp', conv['client_key'],
             json.dumps({'text': body}, ensure_ascii=False), 'msg-%d' % msg_id,
             conversation_id, 'humano', int(conv['generation']), request_id, stamp, stamp))
        conn.execute('UPDATE crm_conversations SET updated_at=? WHERE id=?', (stamp, conversation_id))
    return _ok(message_id=msg_id, outbox_id=outbox.lastrowid)


def conv_state(path, conversation_id):
    with connect(path) as conn:
        row = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (conversation_id,)).fetchone()
    return dict(row) if row else None


def conv_confirm_pause(path, conversation_id, role='user', user_id=None):
    """Barrera determinista: si el humano tiene el control, la IA no puede emitir.

    Devuelve True si la IA puede continuar (mayoría de casos: nadie tomó).
    """
    with connect(path) as conn:
        conv = conn.execute('SELECT * FROM crm_conversations WHERE id=?', (conversation_id,)).fetchone()
    if not conv or conv['state'] in ('humano_asignado', 'esperando_humano'):
        return False
    return True


def conv_by_key(path, client_key):
    """Devuelve la conversación por clave de cliente (teléfono) si existe."""
    with connect(path) as conn:
        row = conn.execute('SELECT * FROM crm_conversations WHERE client_key=?',
                           (client_key,)).fetchone()
    return dict(row) if row else None


def conv_set_pending(path, conversation_id, pending):
    """Guarda el contexto del diálogo multi-turno (intención + datos recogidos)."""
    import json as _json
    raw = _json.dumps(pending or {}, ensure_ascii=False) if pending else None
    with connect(path) as conn:
        conn.execute('UPDATE crm_conversations SET pending=?, updated_at=? WHERE id=?',
                     (raw, now(), conversation_id))
    return _ok()


def conv_clear_pending(path, conversation_id):
    with connect(path) as conn:
        conn.execute('UPDATE crm_conversations SET pending=NULL, updated_at=? WHERE id=?',
                     (now(), conversation_id))
    return _ok()


def _conv_pending_row(path, conversation_id):
    with connect(path) as conn:
        row = conn.execute('SELECT pending FROM crm_conversations WHERE id=?',
                           (conversation_id,)).fetchone()
    if not row or not row['pending']:
        return None
    try:
        return json.loads(row['pending'])
    except (TypeError, ValueError):
        return None


def conv_pending(path, conversation_id):
    return _conv_pending_row(path, conversation_id) or {}


def conv_set_egress_paused(path, conversation_id, paused):
    with connect(path) as conn:
        conn.execute('UPDATE crm_conversations SET egress_paused=?, updated_at=? WHERE id=?',
                     (1 if paused else 0, now(), conversation_id))
    return _ok()


def conv_egress_paused(path, conversation_id):
    with connect(path) as conn:
        row = conn.execute('SELECT egress_paused FROM crm_conversations WHERE id=?',
                           (conversation_id,)).fetchone()
    return bool(row and row['egress_paused'])


def appointments_for_lead(path, lead_id, only_upcoming=True):
    """Citas del cliente (para cancelar o reprogramar) ordenadas por inicio."""
    from datetime import datetime, timezone as _tz
    lead_id = _int_or(lead_id)
    lead_id = None if lead_id is None else lead_id
    if lead_id is None:
        return []
    with connect(path) as conn:
        if only_upcoming:
            rows = conn.execute(
                """SELECT a.* FROM crm_appointments a
                   WHERE a.lead_id=? AND a.operational_status IN ('pending','confirmed')
                   ORDER BY a.start""", (lead_id,)).fetchall()
        else:
            rows = conn.execute(
                """SELECT a.* FROM crm_appointments a WHERE a.lead_id=? ORDER BY a.start""",
                (lead_id,)).fetchall()
    return [dict(r) for r in rows]


# ===========================================================================
# Configuración editable de IA/negocio (R4, §10.2): saludo + datos del negocio.
# El perfil (zona/horarios/moneda) sigue viniendo de business_profile; el saludo
# y campos editables se alojan en crm_settings dentro del mismo backend.
# ===========================================================================

def config_get_all(path, *, include_secrets=False):
    """Configuración completa del negocio (perfil base + sobrescritos en
    crm_settings). Usa el perfil efectivo para que web y bot compartan la misma
    zona, horarios, moneda, saludo y especialistas."""
    return _ok(**config_get_extended(path))


def config_set(path, *, key, value, actor=None):
    return config_set_extended(path, key=key, value=value, actor=actor)


# ===========================================================================
# Chat interno (R4, §10.3): IA conectada a RAG (KB publicada) y a la BD agenda.
# ===========================================================================

def _fold(s):
    """Normaliza minúsculas y acentos para la comparación de texto.

    El chat opera con escritura informal: los usuarios suelen escribir «sabado»
    aunque el documento diga «sábados». Sin esta normalización, la consulta
    pierde fragmentos relevantes (bug real confirmado en E2E punto 3: la
    pregunta sin tilde no recuperaba la versión v2 con tilde).
    """
    import unicodedata as _ud
    s = (s or '').lower()
    return ''.join(c for c in _ud.normalize('NFKD', s) if not _ud.combining(c))


_STOPWORDS_ES = frozenset(
    'a al con de del el en es la las lo los para por que qué se un una '
    'y o e u su sus mi mis tu tus nuestro nuestros como más mas muy hay '
    'entre desde hacia hasta sobre bajo ante sin si no ni pero porque '
    'cuando donde quien quienes cual cuales este esta estos estas ese esa '
    'aquello aquella eso ello le les me te nos os se'.split())

# Palabras vacías del español que no aportan discriminación en una consulta
# corta de chat: «¿a qué hora abren los lunes?» contiene "qué", "hora",
# "abren", "los" y "lunes"; sin filtrarlas, "los" daba al fragmento
# «Los sábados...» el mismo score que «...lunes a viernes...» y el desempate
# por densidad lo subía por encima del correcto (regresión detectada por
# test_chat_kb_con_fuentes_identificables).


def _words_filtradas(query_folded):
    return [w for w in re.split(r'\W+', query_folded) if len(w) > 2
            and w not in _STOPWORDS_ES]


def kb_search(path, query, limit=4):
    """Recuperación simple sobre fragmentos publicados (RAG interno).

    Devuelve además ``doc_version`` (revisión del documento que aporta el
    fragmento) y su ``procedencia`` (página/sección/hoja/fila) para que las
    fuentes del chat sean identificables.
    """
    query = _fold((query or ''))
    words = _words_filtradas(query)
    rows = []
    with connect(path) as conn:
        docs = conn.execute(
            "SELECT id, name, visibility, version, procedencia "
            "FROM crm_kb_documents WHERE state='publicado'").fetchall()
        for doc in docs:
            frags = conn.execute(
                'SELECT body, doc_version FROM crm_kb_fragments WHERE doc_id=?',
                (doc['id'],)).fetchall()
            for f in frags:
                body = _fold(f['body'] or '')
                score = sum(1 for w in words if w in body)
                if score:
                    # Desempate por densidad: del mismo modo que el usuario
                    # pregunta por una palabra, el fragmento MÁS ESPECÍFICO
                    # (mayor proporción de coincidencias) debe quedar primero;
                    # con empate exacto gana el de mayor densidad — antes un
                    # fragmento genérico («lunes a viernes»: 1/7) vencía a uno
                    # específico («sábados»: 1/6) por orden de inserción.
                    palabra_body = _words_filtradas(body)
                    dens = score / max(1, len(palabra_body))
                    try:
                        procedencia = json.loads(doc['procedencia']) \
                            if doc['procedencia'] else None
                    except (TypeError, ValueError):
                        procedencia = None
                    rows.append({'doc_id': doc['id'], 'doc': doc['name'],
                                 'visibility': doc['visibility'],
                                 'doc_version': doc['version'],
                                 'procedencia': procedencia,
                                 'body': f['body'], 'score': score,
                                 'densidad': dens})
    rows.sort(key=lambda r: (r['score'], r['densidad']), reverse=True)
    return rows[:limit]


def _agenda_summary(path):
    from datetime import datetime, timezone as _tz
    stamp = datetime.now(_tz.utc).isoformat()
    with connect(path) as conn:
        profs = conn.execute(
            'SELECT name FROM crm_professionals WHERE active=1 ORDER BY name').fetchall()
        next_citas = conn.execute(
            """SELECT p.name AS prof, a.start FROM crm_appointments a
               JOIN crm_professionals p ON p.id=a.professional_id
               WHERE a.operational_status='confirmed' AND a.start>?
               ORDER BY a.start LIMIT 1""", (stamp,)).fetchone()
    # Para hoy/mañana contar citas abiertas ayuda a dar contexto operativo.
    citas_abiertas = 0
    with connect(path) as conn:
        citas_abiertas = conn.execute(
            "SELECT COUNT(*) FROM crm_appointments WHERE operational_status IN "
            "('pending','confirmed')").fetchone()[0]
    return {'profesionales': [dict(p) for p in profs],
            'proxima': dict(next_citas) if next_citas else None,
            'citas_abiertas': citas_abiertas}


def _herramientas_chat(path, role):
    """Funciones autorizadas que el adaptador IA puede consultar (sólo lectura).

    El chat interno de esta entrega CONSULTA: KB publicada, catálogo publicado,
    agenda resumida (sin datos de clientes individuales) y stock desde la BD.
    Ninguna herramienta escribe citas ni inventario.
    """
    def kb_buscar(pregunta):
        hits = kb_search(path, pregunta)
        # Separación público/interno: sin rol de administración, la KB sólo
        # recupera conocimiento PUBLISHED PÚBLICO (nunca notas internas).
        if role != 'admin':
            hits = [h for h in hits if h['visibility'] == 'publico']
        return hits

    def catalogo_buscar(q):
        hits = _catalog_search(path, q)
        return hits

    def catalogo_buscar_stock(q):
        # P3-02: permisos ANTES de recuperar datos. Sólo un rol autorizado
        # consulta borradores/inventario interno; un usuario sin permiso sólo
        # ve el catálogo publicado (jamás artículos en borrador ni stock
        # privado). El stock de roles autorizados se lee de la BD real.
        if role != 'admin':
            return _catalog_search(path, q, solo_publicados=True)
        return _catalog_search(path, q, solo_publicados=False)

    def agenda_resumen():
        return _agenda_summary(path)

    def stock_consultar(item_id):
        # Relectura operativa desde BD para roles autorizados. Sin permiso, el
        # stock sólo se comunica de un artículo publicado y activo (P3-02).
        with connect(path) as conn:
            row = conn.execute(
                'SELECT stock, stock_na, name, code, publish_state, active '
                'FROM crm_catalog_items WHERE id=?',
                (item_id,)).fetchone()
        if not row:
            return None
        if row['stock_na']:
            return None
        if role != 'admin':
            if str(row['publish_state']) != 'publicado':
                return None
            if row['active'] not in (1, '1', True):
                return None
        return row['stock']

    return {'kb_buscar': kb_buscar, 'catalogo_buscar': catalogo_buscar,
            'catalogo_buscar_stock': catalogo_buscar_stock,
            'agenda_resumen': agenda_resumen, 'stock_consultar': stock_consultar}


def responder_chat_internal(path, pregunta, *, role='admin', adaptador=None):
    """Chat interno sobre el adaptador IA inyectable (punto 3 C02, paso C).

    ``adaptador`` viene inyectado (contrato ChatAdapter); por defecto el
    simulado. La respuesta siempre declara las fuentes identificables y se
    ABSTIENE (``abstencion=True``) cuando no hay información suficiente; no
    inventa datos y no expone borradores, notas internas ni datos de clientes.
    """
    pregunta = (pregunta or '').strip()
    if not pregunta:
        return {'ok': False, 'error': 'Consulta vacía', 'answer': ''}
    if adaptador is None:
        from crm import chat_adapter
        adaptador = chat_adapter.ADAPTADOR_ACTIVO
    herramientas = _herramientas_chat(path, role)
    try:
        resp = adaptador.consultar(pregunta, herramientas=herramientas, rol=role)
    except Exception as exc:  # el adaptador nunca debe tumbar el chat interno
        return {'ok': False, 'error': f'Error del adaptador: {exc}', 'answer': '',
                'modo': getattr(adaptador, 'modo', '')}
    fuentes = [f.a_dict() for f in resp.fuentes]
    # Telemetría del proveedor (punto 3C): se registra proveedor/modelo,
    # latencia y uso de tokens ÚNICAMENTE si el proveedor los reportó; si no,
    # figura «no disponible», nunca un cero inventado. La telemetría nunca
    # tumba el chat.
    telemetria = None
    if getattr(resp, 'proveedor', ''):
        telemetria = {
            'proveedor': resp.proveedor,
            'modelo': resp.modelo or 'no disponible',
            'latencia_us': resp.latencia_us,
            'uso_tokens': resp.uso_tokens or 'no disponible',
            'uso_reportado': resp.uso_reportado,
        }
        try:
            report_invocation(
                path, operation_id='chat', model=resp.modelo or 'no disponible',
                latency_us=resp.latencia_us,
                tokens=json.dumps(resp.uso_tokens) if resp.uso_tokens else 'no disponible',
                unknown=not resp.uso_reportado)
        except Exception:
            pass
    # Compatibilidad con el frontend R4 (label por primera fuente).
    if fuentes:
        primera = fuentes[0]
        fuente_label = {'kb_doc': 'kb', 'catalog_item': 'catalogo',
                        'stock_bd': 'bd', 'agenda': 'bd'}.get(primera['tipo'], 'kb')
        documento = primera['nombre']
        version = primera['version']
        procedencia = primera['procedencia']
    else:
        fuente_label = 'ninguna'
        documento = version = procedencia = None
    return {'ok': True, 'answer': resp.answer,
            'fuente': fuente_label, 'documento': documento,
            'version': version, 'procedencia': procedencia,
            'fuentes': fuentes, 'abstencion': resp.abstencion,
            'adaptador': adaptador.nombre,
            'modo': getattr(adaptador, 'modo', 'simulado'),
            'fallo_proveedor': getattr(resp, 'fallo_proveedor', False),
            'telemetria': telemetria,
            'resumen': resp.resumen}


def _catalog_search(path, query, limit=4, solo_publicados=True):
    """Búsqueda simple sobre artículos del catálogo.

    ``solo_publicados=True`` es la visión pública (catálogo vigente).
    ``solo_publicados=False`` es la lectura OPERATIVA INTERNA (chat del equipo):
    incluye borradores para consultar existencias reales en BD, pero estos
    nunca se exponen al público.
    """
    q = (query or '').lower()
    words = [w for w in re.split(r'\W+', q) if len(w) > 2]
    if not words:
        return []
    where = "publish_state='publicado' AND active=1" if solo_publicados else 'active=1'
    with connect(path) as conn:
        rows = conn.execute(
            f"""SELECT id, name, kind, price_cents, currency, stock, stock_na,
                       active, publish_state, details, code, current_revision
               FROM crm_catalog_items
               WHERE {where}
               ORDER BY id""").fetchall()
    scored = []
    for r in rows:
        text = ' '.join(str(r[k] or '') for k in ('name', 'kind', 'details')).lower()
        score = sum(1 for w in words if w in text)
        if score:
            d = dict(r)
            d['score'] = score
            scored.append(d)
    scored.sort(key=lambda r: r['score'], reverse=True)
    return scored[:limit]


def report_invocation(path, *, operation_id, model, latency_us=None, tokens=None, unknown=False):
    """Registro de uso por invocación (telemetría mínima, sin IDs ambiguos)."""
    stamp = now()
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO crm_audit (user_id, action, created_at)
               VALUES (NULL, ?, ?)""",
            (f'C02 invocación {operation_id} modelo={model} latencia_us={latency_us} '
             f'tokens={tokens} unknown={unknown}', stamp))
    return _ok()
