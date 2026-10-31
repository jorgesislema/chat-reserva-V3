"""C02 — Biblioteca de recursos privados (punto 5, 2026-10-29).

Catálogo PRIVADO de PDFs, catálogos y listas de precios: no es el historial de
envíos (outbox), que vive en la pantalla «Historial de envíos». Reglas:

- Los archivos se guardan en el directorio `library/` junto a la base, por
  SHA-256 (sin paths del usuario: `library/<sha8>___<nombre-sanitizado>`). No
  se sirven como archivo estático: sólo administradores con sesión válida.
- PERMISOS SEPARADOS: `allow_send` (adjuntar/seleccionar para envío a
  pacientes) es independiente de `allow_rag` (usar el texto extraído en la
  recuperación del asistente). Un recurso puede estar en la biblioteca sin
  entrar al RAG, o al revés.
- Versiones inmutables: cada subida crea una versión; retirar NO borra, deja
  `estado='retirado'` con actor y fecha (trazabilidad histórica).
- Los documentos son FUENTES DE DATOS: el texto extraído nunca modifica reglas
  ni stock (misma política que el conocimiento R4; reutiliza c02_docs).
- Plantillas WhatsApp: `crm/library.py` gestiona borradores locales con idioma,
  categoría y parámetros. La APROBACIÓN sólo la fija el proveedor (Meta): sin
  una verificación externa el estado queda `borrador_local`/`pendiente_verificar`
  y la API RECHAZA marcarla aprobada a demanda (no se falsifica).

Las constantes y validadores aquí no hablan con Meta ni con clientes: todo es
local hasta que exista la integración de plantillas (pendiente, documentada en
RELEVO).
"""
from __future__ import annotations

import sqlite3
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from crm import c02_docs
from crm.c02_services import _clean, _err, _ok
from crm.store import connect, now

_IntegrityError = sqlite3.IntegrityError

CATEGORIAS = ('catalogo', 'lista_precios', 'documento')
ESTADOS_RECURSO = ('activo', 'retirado')
# Estados de plantilla según Meta: `aprobante` sólo lo fija una verificación
# EXTERNA (approve_reason del proveedor); localmente sólo se declaran borrador
# (`borrador_local`) o el envío a revisión (`pendiente_verificar`).
ESTADOS_PLANTILLA = ('borrador_local', 'pendiente_verificar', 'aprobada',
                     'rechazada')
IDIOMAS = ('es', 'en')  # ampliación posterior con datos reales del negocio
MAX_RESOURCE_BYTES = c02_docs.MAX_UPLOAD_BYTES


def _recurso_dict(r) -> Dict[str, Any]:
    d = dict(r)
    d['allow_send'] = bool(d.get('allow_send'))
    d['allow_rag'] = bool(d.get('allow_rag'))
    return d


def _slug(filename: str) -> str:
    nombre = os.path.basename(filename or 'archivo')
    nombre = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode()
    nombre = re.sub(r'[^A-Za-z0-9._-]+', '_', nombre)[:80]
    return nombre or 'archivo'


def _ruta_biblioteca(db_path: str) -> str:
    return str(Path(db_path).parent / 'library')


def _guardar_archivo(db_path: str, sha: str, filename: str, data: bytes) -> str:
    carpeta = _ruta_biblioteca(db_path)
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, '%s___%s' % (sha[:8], _slug(filename)))
    with open(destino, 'wb') as f:
        f.write(data)
    return destino


def library_upload(path_db: str, *, name: str, filename: str, data: bytes,
                   categoria: str = 'documento', descripcion: str = None,
                   allow_send: bool = False, allow_rag: bool = True,
                   actor: int = None, resource_id: int = None):
    """Sube (o nueva versión de) un recurso privado. Valida tamaño, extensión y
    magic con c02_docs; el archivo se guarda por SHA-256 junto a la base. El
    texto extraído alimenta el RAG SOLO si allow_rag=1."""
    name = _clean(name, 200)
    if not name:
        return _err('empty', 'El nombre es obligatorio.')
    if categoria not in CATEGORIAS:
        return _err('invalid', 'Categoría no válida: use catálogo, lista de precios o documento.')
    if not data:
        return _err('empty', 'El archivo está vacío.')
    if len(data) > MAX_RESOURCE_BYTES:
        return _err('too_large', 'El archivo excede el límite de %d MB.' %
                    (MAX_RESOURCE_BYTES // (1024 * 1024)))
    # El formato debe estar admitido ANTES de archivar nada (`.exe`, sin
    # extensión, etc. se rechazan sin escribir el archivo ni la fila).
    if c02_docs._detect_extension(filename) is None:
        return _err('invalid', 'Formato no admitido. Use .pdf, .xlsx, .csv, .txt o .md.')
    magic_error = c02_docs._detect_magic(c02_docs._detect_extension(filename), data)
    if magic_error:
        return _err('invalid', magic_error)
    extracted = c02_docs.extraer_documento(filename, data)
    sha = hashlib.sha256(data).hexdigest()

    with connect(path_db) as conn:
        if resource_id is not None:
            fila = conn.execute('SELECT * FROM crm_library_resources WHERE id=?',
                                (resource_id,)).fetchone()
            if not fila:
                return _err('not_found', 'El recurso no existe.')
            nueva_version = fila['version'] + 1
            destino = _guardar_archivo(path_db, sha, filename, data)
            conn.execute(
                """UPDATE crm_library_resources SET name=?, description=?, categoria=?,
                          version=?, estado='activo', allow_send=?, allow_rag=?,
                          sha256=?, filename=?, kind=?, path=?, tamano=?,
                          extract_error=?, retirado_en=NULL, retirado_por=NULL,
                          updated_at=? WHERE id=?""",
                (name, _clean(descripcion or '', 1000) or None, categoria, nueva_version,
                 1 if allow_send else 0, 1 if allow_rag else 0, sha,
                 _clean(filename, 250), extracted.get('kind') or 'binario', destino,
                 len(data), extracted.get('extract_error'), now(), resource_id))
            conn.execute(
                """INSERT INTO crm_library_versions (resource_id, version, sha256, filename,
                     kind, path, tamano, extract_error, created_by, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (resource_id, nueva_version, sha, _clean(filename, 250),
                 extracted.get('kind') or 'binario', destino, len(data),
                 extracted.get('extract_error'), actor, now()))
            rid = resource_id
            version = nueva_version
        else:
            destino = _guardar_archivo(path_db, sha, filename, data)
            stamp = now()
            cur = conn.execute(
                """INSERT INTO crm_library_resources (name, description, categoria, version,
                     estado, allow_send, allow_rag, sha256, filename, kind, path, tamano,
                     extract_error, created_by, created_at, updated_at)
                   VALUES (?,?,?,1,'activo',?,?,?,?,?,?,?,?,?,?,?)""",
                (name, _clean(descripcion or '', 1000) or None, categoria,
                 1 if allow_send else 0, 1 if allow_rag else 0, sha,
                 _clean(filename, 250), extracted.get('kind') or 'binario', destino,
                 len(data), extracted.get('extract_error'), actor, stamp, stamp))
            rid = cur.lastrowid
            version = 1
            conn.execute(
                """INSERT INTO crm_library_versions (resource_id, version, sha256, filename,
                     kind, path, tamano, extract_error, created_by, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (rid, version, sha, _clean(filename, 250),
                 extracted.get('kind') or 'binario', destino, len(data),
                 extracted.get('extract_error'), actor, now()))

        # Fragmentos RAG: el índice refleja SIEMPRE el allow_rag actual. Si el
        # recurso no debe usarse en RAG se limpia su índice; si debe, se
        # reindexa el texto extraído.
        conn.execute('DELETE FROM crm_library_fragments WHERE resource_id=?', (rid,))
        if allow_rag and extracted.get('ok'):
            cuerpo = (extracted.get('body_text') or '')[:20000]
            frag_size = 900
            for i in range(0, len(cuerpo), frag_size):
                trozo = cuerpo[i:i + frag_size]
                if trozo.strip():
                    conn.execute(
                        'INSERT INTO crm_library_fragments (resource_id, body, procedencia,'
                        ' created_at) VALUES (?,?,?,?)',
                        (rid, trozo, json.dumps(extracted.get('procedencia') or [])[:2000],
                         now()))
        conn.execute(
            'INSERT INTO crm_audit (user_id, action, created_at) VALUES (?,?,?)',
            (actor, 'Biblioteca %s v%d "%s" (envio=%s rag=%s)' %
             ('nueva versión' if resource_id else 'alta', version, name[:80],
              int(bool(allow_send)), int(bool(allow_rag))), now()))

    return _ok(resource_id=rid, version=version,
               extract_error=extracted.get('extract_error'),
               ok_extract=bool(extracted.get('ok')))


def library_list(path_db: str, *, estado: str = None):
    with connect(path_db) as conn:
        q = ("SELECT r.*, (SELECT COUNT(*) FROM crm_library_fragments f"
             "              WHERE f.resource_id=r.id) AS fragmentos,"
             "       u.name AS autor FROM crm_library_resources r"
             "  LEFT JOIN crm_users u ON u.id=r.created_by")
        params = []
        if estado:
            q += ' WHERE r.estado=?'
            params.append(estado)
        q += ' ORDER BY r.updated_at DESC'
        return [_recurso_dict(r) for r in conn.execute(q, params).fetchall()]


def library_detail(path_db: str, resource_id: int):
    with connect(path_db) as conn:
        r = conn.execute(
            'SELECT r.*, u.name AS autor FROM crm_library_resources r'
            ' LEFT JOIN crm_users u ON u.id=r.created_by WHERE r.id=?',
            (resource_id,)).fetchone()
        if not r:
            return None
        versiones = conn.execute(
            'SELECT v.*, u.name AS autor FROM crm_library_versions v'
            ' LEFT JOIN crm_users u ON u.id=v.created_by'
            ' WHERE v.resource_id=? ORDER BY v.version DESC', (resource_id,)).fetchall()
        return dict(_recurso_dict(r), versiones=[dict(v) for v in versiones])


def library_update(path_db: str, resource_id: int, *, actor=None, name=None,
                   descripcion=None, categoria=None, allow_send=None,
                   allow_rag=None):
    """Edita metadatos y permisos SIN tocar el archivo (los cambios de permiso
    reindexan el RAG). `allow_rag` controla el índice: desactivarlo retira los
    fragmentos del asistente sin borrar el recurso."""
    with connect(path_db) as conn:
        fila = conn.execute('SELECT * FROM crm_library_resources WHERE id=?',
                            (resource_id,)).fetchone()
        if not fila:
            return _err('not_found', 'El recurso no existe.')
        categoria_final = categoria if categoria is not None else fila['categoria']
        if categoria_final not in CATEGORIAS:
            return _err('invalid', 'Categoría no válida.')
        allow_send_final = (1 if allow_send else 0) if allow_send is not None \
            else fila['allow_send']
        allow_rag_final = (1 if allow_rag else 0) if allow_rag is not None \
            else fila['allow_rag']
        conn.execute(
            """UPDATE crm_library_resources SET name=COALESCE(?,name),
                      description=COALESCE(?,description), categoria=?,
                      allow_send=?, allow_rag=?, updated_at=? WHERE id=?""",
            (_clean(name, 200) or None if name is not None else None,
             _clean(descripcion, 1000) if descripcion is not None else None,
             categoria_final, allow_send_final, allow_rag_final, now(), resource_id))
        if not allow_rag_final:
            conn.execute('DELETE FROM crm_library_fragments WHERE resource_id=?',
                         (resource_id,))
        elif fila['allow_rag'] != allow_rag_final:
            # Volver a activar RAG exige volver a extraer: se reindexa desde el archivo.
            try:
                with open(fila['path'], 'rb') as f:
                    data = f.read()
                extracted = c02_docs.extraer_documento(fila['filename'], data)
                conn.execute('DELETE FROM crm_library_fragments WHERE resource_id=?',
                             (resource_id,))
                if extracted.get('ok'):
                    cuerpo = (extracted.get('body_text') or '')[:20000]
                    for i in range(0, len(cuerpo), 900):
                        trozo = cuerpo[i:i + 900]
                        if trozo.strip():
                            conn.execute(
                                'INSERT INTO crm_library_fragments (resource_id, body,'
                                ' procedencia, created_at) VALUES (?,?,?,?)',
                                (resource_id, trozo,
                                 json.dumps(extracted.get('procedencia') or [])[:2000],
                                 now()))
            except OSError:
                pass
        conn.execute('INSERT INTO crm_audit (user_id, action, created_at) VALUES (?,?,?)',
                     (actor, 'Biblioteca permisos #%d (envio=%s rag=%s)' %
                      (resource_id, int(allow_send_final), int(allow_rag_final)), now()))
    return _ok(resource_id=resource_id, allow_send=bool(allow_send_final),
               allow_rag=bool(allow_rag_final))


def library_retirar(path_db: str, resource_id: int, *, actor=None):
    """Retirada con trazabilidad: estado='retirado' + fecha/autor, fuera del
    RAG, el archivo y las versiones se CONSERVAN. Un recurso retirado no puede
    seleccionarse para envío."""
    with connect(path_db) as conn:
        fila = conn.execute('SELECT * FROM crm_library_resources WHERE id=?',
                            (resource_id,)).fetchone()
        if not fila:
            return _err('not_found', 'El recurso no existe.')
        stamp = now()
        conn.execute(
            "UPDATE crm_library_resources SET estado='retirado', retirado_en=?,"
            " retirado_por=?, updated_at=? WHERE id=?",
            (stamp, actor, stamp, resource_id))
        conn.execute('DELETE FROM crm_library_fragments WHERE resource_id=?',
                     (resource_id,))
        conn.execute('INSERT INTO crm_audit (user_id, action, created_at) VALUES (?,?,?)',
                     (actor, 'Biblioteca retirada #%d "%s"' % (resource_id, fila['name'][:80]),
                      stamp))
    return _ok(resource_id=resource_id, estado='retirado')


def library_descargar(path_db: str, resource_id: int):
    """Devuelve (ruta, filename) para descarga autorizada, o (None, None)."""
    with connect(path_db) as conn:
        r = conn.execute('SELECT path, filename, estado FROM crm_library_resources'
                         ' WHERE id=?', (resource_id,)).fetchone()
    if not r:
        return None, None
    return r['path'], r['filename']


def library_rag_search(path_db: str, query: str, limit: int = 4):
    """Recuperación sobre fragmentos de recursos permitidos para RAG (equivalente
    a kb_search pero sobre la biblioteca privada; sólo recursos activos con
    allow_rag=1)."""
    from crm.c02_services import _fold, _words_filtradas
    query = _fold(query or '')
    words = _words_filtradas(query)
    rows = []
    with connect(path_db) as conn:
        docs = conn.execute(
            "SELECT id, name, categoria, version FROM crm_library_resources"
            " WHERE estado='activo' AND allow_rag=1").fetchall()
        for doc in docs:
            frags = conn.execute(
                'SELECT body, procedencia FROM crm_library_fragments WHERE resource_id=?',
                (doc['id'],)).fetchall()
            for f in frags:
                body = _fold(f['body'] or '')
                score = sum(1 for w in words if w in body)
                if score:
                    palabra_body = _words_filtradas(body)
                    dens = score / max(1, len(palabra_body))
                    try:
                        procedencia = json.loads(f['procedencia']) if f['procedencia'] else None
                    except (TypeError, ValueError):
                        procedencia = None
                    rows.append({'resource_id': doc['id'], 'doc': doc['name'],
                                 'categoria': doc['categoria'],
                                 'doc_version': doc['version'],
                                 'procedencia': procedencia, 'body': f['body'],
                                 'score': score, 'densidad': dens,
                                 'origen': 'biblioteca'})
    rows.sort(key=lambda r: (r['score'], r['densidad']), reverse=True)
    return rows[:limit]


# ---------------------------------------------------------------- plantillas


def plantillas_list(path_db: str):
    with connect(path_db) as conn:
        return [dict(t) for t in conn.execute(
            'SELECT * FROM crm_wa_templates ORDER BY name COLLATE NOCASE').fetchall()]


def plantilla_upsert(path_db: str, *, template_id=None, name: str, language: str = 'es',
                     category: str = 'UTILITY', body: str = '', parameters=None,
                     actor=None, estado: str = None, motivo_estado: str = None):
    """Crea/actualiza el borrador local de una plantilla WhatsApp (idioma,
    categoría, cuerpo y parámetros). Estado de APROBACIÓN: sólo se aceptan
    `borrador_local` y `pendiente_verificar` sin verificación externa;
    `aprobada`/`rechazada` exigen una verificación del proveedor y el helper
    `plantilla_registrar_verificacion` (nunca la API con datos del usuario)."""
    name = _clean(name, 100)
    if not name:
        return _err('empty', 'El nombre de la plantilla es obligatorio.')
    if language not in IDIOMAS:
        return _err('invalid', 'Idioma no admitido en este despliegue: es o en.')
    if category not in ('UTILITY', 'MARKETING', 'AUTHENTICATION'):
        return _err('invalid', 'Categoría Meta no válida (UTILITY/MARKETING/AUTHENTICATION).')
    body = _clean(body, 4000)
    if not body:
        return _err('empty', 'El cuerpo de la plantilla es obligatorio.')
    if estado in ('aprobada', 'rechazada'):
        return _err('invalid', 'El estado de aprobación sólo lo fija la verificación'
                    ' externa del proveedor (Meta). Un borrador local NO es'
                    ' aprobado: quede en borrador_local o pendiente_verificar.')
    try:
        params = json.loads(parameters) if isinstance(parameters, str) else (parameters or [])
        if not isinstance(params, list):
            raise ValueError
    except (TypeError, ValueError):
        return _err('invalid', 'Los parámetros deben ser una lista JSON.')
    estado_final = estado if estado in ESTADOS_PLANTILLA else 'borrador_local'
    stamp = now()
    try:
        with connect(path_db) as conn:
            if template_id is not None:
                existente = conn.execute('SELECT * FROM crm_wa_templates WHERE id=?',
                                         (template_id,)).fetchone()
                if not existente:
                    return _err('not_found', 'La plantilla no existe.')
            else:
                existente = conn.execute(
                    'SELECT * FROM crm_wa_templates WHERE name=? AND language=?',
                    (name, language)).fetchone()
            if existente:
                conn.execute(
                    """UPDATE crm_wa_templates SET name=?, language=?, category=?, body=?,
                              parameters=?, estado=?, motivo_estado=?, verificado_en=?, updated_at=?
                       WHERE id=?""",
                    (name, language, category, body, json.dumps(params)[:4000],
                     estado_final, _clean(motivo_estado or '', 200) or None,
                     existente['verificado_en'], stamp, existente['id']))
                tid = existente['id']
            else:
                cur = conn.execute(
                    """INSERT INTO crm_wa_templates (name, language, category, body, parameters,
                         estado, motivo_estado, created_by, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?, ?,?,?)""",
                    (name, language, category, body, json.dumps(params)[:4000], estado_final,
                     _clean(motivo_estado or '', 200) or None, actor, stamp, stamp))
                tid = cur.lastrowid
            conn.execute('INSERT INTO crm_audit (user_id, action, created_at) VALUES (?,?,?)',
                         (actor, 'Plantilla "%s (%s)" estado=%s' % (name[:80], language, estado_final),
                          stamp))
    except _IntegrityError:
        return _err('duplicate', 'Ya existe una plantilla con ese nombre e idioma.')
    return _ok(template_id=tid, estado=estado_final,
               nota='Aprobación únicamente vía verificación externa (Meta).'
               if estado_final in ('borrador_local', 'pendiente_verificar') else None)


def plantilla_retirar(path_db: str, template_id: int, *, actor=None):
    with connect(path_db) as conn:
        t = conn.execute('SELECT * FROM crm_wa_templates WHERE id=?',
                         (template_id,)).fetchone()
        if not t:
            return _err('not_found', 'La plantilla no existe.')
        if t['estado'] == 'aprobada':
            return _err('invalid',
                        'No se retira localmente una plantilla aprobada por el proveedor;'
                        ' retirela en Meta Business Manager y registre la verificación.')
        conn.execute("UPDATE crm_wa_templates SET estado='rechazada', motivo_estado=?,"
                     ' updated_at=? WHERE id=?',
                     ('Retirada local (borrador no verificado)', now(), template_id))
        conn.execute('INSERT INTO crm_audit (user_id, action, created_at) VALUES (?,?,?)',
                     (actor, 'Plantilla #%d retirada localmente' % template_id, now()))
    return _ok(template_id=template_id, estado='rechazada', local=True)


def plantilla_registrar_verificacion(path_db: str, template_id: int, *,
                                     estado: str, motivo: str = None, actor=None):
    """REGISTRA una verificación EXTERNA hecha fuera del CRM (la respuesta real
    de Meta). Sólo este helper fija `aprobada`/`rechazada`, y con constancia de
    auditoría. La UI NO lo expone como pulsador editable."""
    if estado not in ('aprobada', 'rechazada', 'pendiente_verificar'):
        return _err('invalid', 'Estado de verificación no válido.')
    with connect(path_db) as conn:
        if not conn.execute('SELECT id FROM crm_wa_templates WHERE id=?',
                            (template_id,)).fetchone():
            return _err('not_found', 'La plantilla no existe.')
        stamp = now()
        conn.execute('UPDATE crm_wa_templates SET estado=?, motivo_estado=?, verificado_en=?,'
                     ' updated_at=? WHERE id=?',
                     (estado, _clean(motivo or '', 200) or None,
                      stamp if estado in ('aprobada', 'rechazada') else None,
                      stamp, template_id))
        conn.execute('INSERT INTO crm_audit (user_id, action, created_at) VALUES (?,?,?)',
                     (actor, 'Plantilla #%d verificación externa: %s (%s)' %
                      (template_id, estado, (motivo or '')[:80]), stamp))
    return _ok(template_id=template_id, estado=estado, verificado_en=stamp)


def plantillas_seleccionables(path_db: str):
    """Sólo plantillas con aprobación EXTERNA verificada sirven para enviar."""
    with connect(path_db) as conn:
        return [dict(t) for t in conn.execute(
            "SELECT * FROM crm_wa_templates WHERE estado='aprobada'"
            ' ORDER BY name COLLATE NOCASE').fetchall()]
