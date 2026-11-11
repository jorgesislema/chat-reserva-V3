"""Índice vectorial local (Qdrant + FastEmbed) para el CRM vigente.

- Qdrant en modo local con persistencia en disco junto a cada base:
  ``<base>.qdrant/`` (una por negocio; la demo nunca mezcla con la operativa).
- Modelo: ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
  (multilingüe, ~50 idiomas incluido español; 384 dimensiones).
- Colección única ``crm_contenido``. Cada punto apunta a su fuente:
  kind (``catalogo``|``kb``), ref_id, revision (current_revision del
  artículo o published_version del documento), nombre y visibilidad.
- Solo contenido vigente y público: artículos publicados+activos y
  documentos publicados con visibilidad pública. Borradores, privados y
  datos de pacientes JAMÁS se indexan.
- Si el índice no existe o falla, se lanza ``IndiceNoDisponible``: quien
  llama conserva la búsqueda por texto y deja constancia del fallo.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

MODELO = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
DIM = 384
COLECCION = 'crm_contenido'
UMBRAL_DEBIL = 0.30


def _dir_cache() -> str:
    """Carpeta del modelo, fuera de temporales: los tests redirigen
    ``tempfile`` a carpetas efímeras y el modelo no debe descargarse
    en cada prueba (además la red está bloqueada en pruebas)."""
    import os
    base = os.environ.get('FASTEMBED_CACHE_DIR') or os.path.join(
        os.path.expanduser('~'), '.cache', 'fastembed')
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    return base


def _obtener_modelo():
    global _MODELO
    if _MODELO is None:
        try:
            from fastembed import TextEmbedding
            _MODELO = TextEmbedding(model_name=MODELO, cache_dir=_dir_cache())
        except Exception as exc:
            raise IndiceNoDisponible('no se pudo cargar el modelo: %s' % exc)
    return _MODELO


class IndiceNoDisponible(Exception):
    """El índice vectorial no está listo (sin construir, corrupto o el
    modelo no cargó). Quien llama debe seguir con búsqueda por texto."""


_clientes: Dict[str, Any] = {}
_MODELO = None


def ruta_indice(db_path: str) -> str:
    return str(db_path) + '.qdrant'


def _cliente(db_path: str):
    from qdrant_client import QdrantClient
    clave = str(db_path)
    cli = _clientes.get(clave)
    if cli is None:
        try:
            cli = QdrantClient(path=ruta_indice(db_path))
        except Exception as exc:
            raise IndiceNoDisponible('no se pudo abrir el índice: %s' % exc)
        _clientes[clave] = cli
    return cli


def cerrar(db_path: str) -> None:
    """Cierra el cliente en caché de una base (libera sus archivos).

    Necesario antes de copiar o borrar su carpeta ``.qdrant`` en Windows,
    donde los archivos abiertos no se pueden copiar ni eliminar.
    """
    cli = _clientes.pop(str(db_path), None)
    if cli is not None:
        try:
            cli.close()
        except Exception:
            pass


def _asegurar_coleccion(cli) -> None:
    from qdrant_client.models import Distance, VectorParams
    try:
        names = [c.name for c in cli.get_collections().collections]
    except Exception as exc:
        raise IndiceNoDisponible('índice ilegible: %s' % exc)
    if COLECCION not in names:
        cli.create_collection(
            collection_name=COLECCION,
            vectors_config=VectorParams(size=DIM, distance=Distance.COSINE))


def texto_catalogo(item: Dict[str, Any]) -> str:
    partes = [str(item.get('name') or ''), str(item.get('kind') or '')]
    if item.get('code'):
        partes.append('código %s' % item.get('code'))
    for campo in ('details', 'public_notes'):
        if str(item.get(campo) or '').strip():
            partes.append(str(item.get(campo)).strip())
    return '. '.join(p for p in partes if p)


def texto_documento(nombre: str, cuerpo: str) -> str:
    return '%s. %s' % (str(nombre or '').strip(), str(cuerpo or '').strip())


def _pid(kind: str, ref_id) -> str:
    import uuid as _uu
    return str(_uu.uuid5(_uu.NAMESPACE_URL, 'crm/%s:%s' % (kind, ref_id)))


def _punto(pid: str, vector, payload: Dict[str, Any]):
    from qdrant_client.models import PointStruct
    return PointStruct(id=_pid(payload.get('kind', ''), payload.get('ref_id')),
                       vector=list(vector), payload=dict(payload, pid=pid))


def _vectores(textos: List[str]):
    modelo = _obtener_modelo()
    return list(modelo.embed(textos))


def reconstruir(db_path: str) -> Dict[str, Any]:
    """Reconstruye el índice desde cero con el contenido vigente y público."""
    from crm.store import connect
    cli = _cliente(db_path)
    try:
        cli.delete_collection(collection_name=COLECCION)
    except Exception:
        pass
    _asegurar_coleccion(cli)
    puntos, textos = [], []
    with connect(db_path) as conn:
        filas = conn.execute(
            "SELECT id, name, kind, code, details, public_notes, "
            "current_revision FROM crm_catalog_items "
            "WHERE publish_state='publicado' AND active=1").fetchall()
        for r in filas:
            pid = 'catalogo:%s' % r['id']
            puntos.append((pid, {
                'kind': 'catalogo', 'ref_id': int(r['id']),
                'revision': int(r['current_revision'] or 0),
                'nombre': r['name'] or '', 'code': r['code'] or '',
                'visibilidad': 'publico'}))
            textos.append(texto_catalogo(dict(r)))
        docs = conn.execute(
            "SELECT d.id, d.name, v.body_text, d.published_version "
            "FROM crm_kb_documents d JOIN crm_kb_versions v "
            "ON v.doc_id=d.id AND v.version=d.published_version "
            "WHERE d.published_version IS NOT NULL AND d.visibility='publico'"
        ).fetchall()
        for d in docs:
            pid = 'kb:%s' % d['id']
            puntos.append((pid, {
                'kind': 'kb', 'ref_id': int(d['id']),
                'revision': int(d['published_version'] or 0),
                'nombre': d['name'] or '', 'code': '',
                'visibilidad': 'publico'}))
            textos.append(texto_documento(d['name'], d['body_text'] or ''))
    if not puntos:
        return {'ok': True, 'puntos': 0}
    vecs = _vectores(textos)
    cli.upsert(collection_name=COLECCION,
               points=[_punto(pid, v, pay)
                       for (pid, pay), v in zip(puntos, vecs)],
               wait=True)
    return {'ok': True, 'puntos': len(puntos)}


def sincronizar_catalogo(db_path: str, item_id: int) -> Dict[str, Any]:
    """Da de alta, actualiza o retira UN artículo según su estado vigente."""
    from crm.store import connect
    cli = _cliente(db_path)
    _asegurar_coleccion(cli)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, name, kind, code, details, public_notes, "
            "current_revision, publish_state, active FROM crm_catalog_items "
            "WHERE id=?", (item_id,)).fetchone()
    if row is None or row['publish_state'] != 'publicado' or row['active'] not in (1, '1', True):
        cli.delete(collection_name=COLECCION,
                   points_selector=[_pid('catalogo', item_id)], wait=True)
        return {'ok': True, 'accion': 'retirado'}
    vec = _vectores([texto_catalogo(dict(row))])[0]
    cli.upsert(collection_name=COLECCION,
               points=[_punto('catalogo:%s' % item_id, vec, {
                   'kind': 'catalogo', 'ref_id': int(row['id']),
                   'revision': int(row['current_revision'] or 0),
                   'nombre': row['name'] or '', 'code': row['code'] or '',
                   'visibilidad': 'publico'})],
               wait=True)
    return {'ok': True, 'accion': 'indexado'}


def sincronizar_documento(db_path: str, doc_id: int) -> Dict[str, Any]:
    """Da de alta, actualiza o retira UN documento según su publicación."""
    from crm.store import connect
    cli = _cliente(db_path)
    _asegurar_coleccion(cli)
    with connect(db_path) as conn:
        fila = conn.execute(
            "SELECT d.id, d.name, d.visibility, d.published_version, v.body_text "
            "FROM crm_kb_documents d LEFT JOIN crm_kb_versions v "
            "ON v.doc_id=d.id AND v.version=d.published_version "
            "WHERE d.id=?", (doc_id,)).fetchone()
    if fila is None or not fila['published_version'] or fila['visibility'] != 'publico':
        cli.delete(collection_name=COLECCION,
                   points_selector=[_pid('kb', doc_id)], wait=True)
        return {'ok': True, 'accion': 'retirado'}
    vec = _vectores([texto_documento(fila['name'], fila['body_text'] or '')])[0]
    cli.upsert(collection_name=COLECCION,
               points=[_punto('kb:%s' % doc_id, vec, {
                   'kind': 'kb', 'ref_id': int(fila['id']),
                   'revision': int(fila['published_version'] or 0),
                   'nombre': fila['name'] or '', 'code': '',
                   'visibilidad': 'publico'})],
               wait=True)
    return {'ok': True, 'accion': 'indexado'}


def buscar(db_path: str, texto: str, limite: int = 4) -> List[Dict[str, Any]]:
    """Búsqueda semántica. Cada hit apunta a su fuente y trae la revisión
    indexada para que el llamador la revalide contra la ficha actual."""
    if not (texto or '').strip():
        return []
    cli = _cliente(db_path)
    try:
        nombres = [c.name for c in cli.get_collections().collections]
    except Exception as exc:
        raise IndiceNoDisponible('índice ilegible: %s' % exc)
    if COLECCION not in nombres:
        raise IndiceNoDisponible('índice sin construir')
    vec = _vectores([texto])[0]
    try:
        res = cli.query_points(collection_name=COLECCION, query=list(vec),
                               limit=max(1, int(limite or 4)),
                               with_payload=True)
        puntos = res.points if hasattr(res, 'points') else res
    except Exception as exc:
        raise IndiceNoDisponible('búsqueda fallida: %s' % exc)
    hits = []
    for p in puntos or []:
        pay = p.payload or {}
        hits.append({'kind': pay.get('kind'), 'ref_id': pay.get('ref_id'),
                     'revision': pay.get('revision'), 'nombre': pay.get('nombre') or '',
                     'score': float(p.score or 0.0)})
    # Lo muy débil (< 0.30) ni siquiera se ofrece como opción: equivale a
    # no haber encontrado nada y deja pedir aclaración o abstenerse.
    return [h for h in hits
            if h['kind'] and h['ref_id'] is not None and h['score'] >= UMBRAL_DEBIL]


def verificar(db_path: str, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Revalida cada hit contra la fuente actual: si la ficha cambió, se
    retiró o se despublicó, el hit se descarta (nunca se responde con una
    versión vieja)."""
    from crm.store import connect
    vivos = []
    with connect(db_path) as conn:
        for h in hits or []:
            if h.get('kind') == 'catalogo':
                r = conn.execute(
                    "SELECT id, publish_state, active, current_revision "
                    "FROM crm_catalog_items WHERE id=?", (h.get('ref_id'),)).fetchone()
                if r is None or r['publish_state'] != 'publicado' \
                        or r['active'] not in (1, '1', True):
                    continue
                h = dict(h, vigente=True)
                vivos.append(h)
            elif h.get('kind') == 'kb':
                r = conn.execute(
                    "SELECT id, visibility, published_version "
                    "FROM crm_kb_documents WHERE id=?", (h.get('ref_id'),)).fetchone()
                if r is None or not r['published_version'] or r['visibility'] != 'publico':
                    continue
                h = dict(h, vigente=True)
                vivos.append(h)
    return vivos
