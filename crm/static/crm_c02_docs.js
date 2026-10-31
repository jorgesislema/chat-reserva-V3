/* C02 — Conocimiento editable y (más abajo) importación de inventario (punto 3).
   Cero inline, CSP estricta: estado en data-* y peticiones con X-CSRF-Token.
   Carga de .docx/.pdf/.xlsx/.csv con vista previa: la validación y la
   extracción de texto ocurren en el backend; aquí se muestra el resultado y
   sólo se guarda lo que el usuario confirma (nunca se publica al cargar). */
(function () {
  'use strict';

  var app = document.querySelector('#c02-docs-app');
  if (!app) return;

  var csrf = app.getAttribute('data-csrf');
  var isAdmin = app.getAttribute('data-admin') === '1';

  function json(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          var err = new Error((j.error && j.error.message) || 'Error de servidor');
          err.code = (j && j.error && j.error.code) || '';
          throw err;
        }
        return j;
      });
    });
  }

  function uploadJson(data) {
    return fetch('/api/c02/knowledge/upload', {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrf },
      body: data
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          var err = new Error((j.error && j.error.message) || 'Error de servidor');
          err.code = (j && j.error && j.error.code) || '';
          throw err;
        }
        return j;
      });
    });
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function flashIn(box, kind, text) {
    box.innerHTML = '';
    box.appendChild(el('div', 'status-line ' + kind, text));
  }

  // --- Tabla y editor de documentos de conocimiento ---
  var kbTable = document.getElementById('c02-kb-table');
  var kbBtn = document.getElementById('c02-kb-new');
  var kbDialog = document.getElementById('c02-kb-dialog');
  var kbForm = document.getElementById('c02-kb-form');
  var kbFile = document.getElementById('c02-kb-file');
  var kbPreviewBtn = document.getElementById('c02-kb-preview');
  var kbPreviewBox = document.getElementById('c02-kb-preview-box');
  var kbSavePublic = document.getElementById('c02-kb-save-public');
  var kbDocs = [];
  var uploadState = null;

  function stateLabel(s) {
    return { publicado: 'Publicado', borrador: 'Borrador', desactivado: 'Inactivo',
             inactivo: 'Inactivo', error: 'Error' }[s] || s || '—';
  }

  function kindLabel(k) {
    return { texto: 'Texto', md: 'Markdown', txt: 'Texto', docx: 'Word',
             pdf: 'PDF', xlsx: 'Excel', csv: 'CSV' }[k] || k || '—';
  }

  function origenLabel(d) {
    if (d.source_name) return d.source_name;
    return 'texto manual';
  }

  function origenTitle(d) {
    if (!d.procedencia) return '';
    try {
      var items = typeof d.procedencia === 'string' ? JSON.parse(d.procedencia) : d.procedencia;
      if (!items || !items.length) return '';
      return items.slice(0, 5).map(function (p) {
        return (p.tipo || '') + ': ' + (p.ubicacion || '');
      }).join(' · ');
    } catch (e) { return ''; }
  }

  function renderKb() {
    if (!kbTable) return;
    var tbody = kbTable.querySelector('tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    var emptyEl = document.getElementById('c02-kb-empty');
    if (emptyEl) emptyEl.hidden = kbDocs.length > 0;
    kbDocs.forEach(function (d) {
      var tr = document.createElement('tr');
      var n = el('td', '', d.name); tr.appendChild(n);
      tr.appendChild(el('td', '', stateLabel(d.state)));
      tr.appendChild(el('td', '', d.visibility || 'privado'));
      tr.appendChild(el('td', '', String(d.version || 1)));
      var or = el('td', '');
      or.appendChild(el('span', '', origenLabel(d)));
      var t = origenTitle(d);
      if (t) or.appendChild(el('small', 'kb-origen-detail', t));
      tr.appendChild(or);
      var ix = el('td', '', d.index_state || '—');
      if (d.extract_error) ix.textContent += ' · ' + d.extract_error;
      tr.appendChild(ix);
      var ac = el('td', '');
      if (isAdmin && d.state !== 'desactivado' && d.state !== 'inactivo') {
        var editBtn = el('button', 'button ghost', 'Editar');
        editBtn.type = 'button';
        editBtn.addEventListener('click', function () { openKb(d); });
        ac.appendChild(editBtn);
        if (d.state !== 'publicado') {
          var pubBtn = el('button', 'button ghost', 'Publicar');
          pubBtn.type = 'button';
          pubBtn.addEventListener('click', function () {
            pubBtn.disabled = true;
            json('/api/c02/knowledge/' + d.id + '/publish', 'POST', {})
              .then(function () { flashStatus('Documento publicado.', 'ok'); kbReload(); },
                    function (e) { pubBtn.disabled = false; flashStatus(e.message, 'error'); })
              .catch(function () {});
          });
          ac.appendChild(pubBtn);
        }
        var deactBtn = el('button', 'button ghost', 'Desactivar');
        deactBtn.type = 'button';
        deactBtn.addEventListener('click', function () {
          deactBtn.disabled = true;
          json('/api/c02/knowledge/' + d.id + '/deactivate', 'POST', {})
            .then(function () { flashStatus('Documento retirado.', 'ok'); kbReload(); },
                  function (e) { deactBtn.disabled = false; flashStatus(e.message, 'error'); })
            .catch(function () {});
        });
        ac.appendChild(deactBtn);
      }
      tr.appendChild(ac);
      tbody.appendChild(tr);
    });
  }

  function flashStatus(msg, kind) {
    var status = document.querySelector('#c02-docs-app .status-line');
    if (!status) return;
    status.textContent = msg || '';
    status.className = 'status-line ' + (kind || 'info');
    status.style.display = msg ? '' : 'none';
  }

  function showPreview(res) {
    if (!kbPreviewBox) return;
    kbPreviewBox.innerHTML = '';
    kbPreviewBox.hidden = false;
    var p = res.preview || {};
    var box = kbPreviewBox;
    if (!res.ok) {
      flashIn(box, 'error', 'No se pudo leer el archivo: ' + p.extract_error);
      uploadState = null;
      return;
    }
    var head = el('div', 'kb-preview-head',
      'Archivo: ' + p.filename + ' · Tipo: ' + kindLabel(p.kind) +
      (p.n_pages ? ' · Páginas: ' + p.n_pages : '') +
      (p.sheets ? ' · Hojas: ' + p.sheets : '') +
      (p.rows ? ' · Filas: ' + p.rows : ''));
    box.appendChild(head);
    (p.warnings || []).forEach(function (w) {
      box.appendChild(el('div', 'status-line error', w));
    });
    if (!p.body_text.trim()) {
      box.appendChild(el('div', 'status-line error',
        'Sin texto extraíble. No se puede guardar contenido que no se haya leído.'));
      uploadState = null;
      return;
    }
    (p.procedencia || []).slice(0, 10).forEach(function (pr) {
      box.appendChild(el('div', 'kb-proc-item',
        (pr.tipo || '') + ' — ' + (pr.ubicacion || '') + (pr.texto ? ': ' + pr.texto : '')));
    });
    if ((p.procedencia || []).length > 10) {
      box.appendChild(el('div', 'kb-proc-item', '+ ' + (p.procedencia.length - 10) + ' entradas más'));
    }
    var bodyArea = el('div', 'kb-preview-body', p.body_text);
    box.appendChild(bodyArea);
    uploadState = p;
    var nameInput = document.getElementById('c02-kb-name');
    if (nameInput && !nameInput.value) {
      nameInput.value = p.filename.replace(/\.[^.]+$/, '');
    }
    var kindInput = document.getElementById('c02-kb-kind');
    if (kindInput && kindInput.value === 'texto' && p.kind && ['docx', 'pdf', 'xlsx', 'csv'].indexOf(p.kind) >= 0) {
      kindInput.value = p.kind;
    }
  }

  function openKb(d) {
    uploadState = null;
    document.getElementById('c02-kb-id').value = d ? String(d.id) : '';
    document.getElementById('c02-kb-name').value = '';
    document.getElementById('c02-kb-visibility').value = 'publico';
    document.getElementById('c02-kb-kind').value = 'texto';
    document.getElementById('c02-kb-body').value = '';
    if (kbFile) kbFile.value = '';
    if (kbPreviewBox) { kbPreviewBox.hidden = true; kbPreviewBox.innerHTML = ''; }
    if (d && isAdmin) {
      json('/api/c02/knowledge/' + d.id).then(function (j) {
        var doc = j.document || {};
        if (!document.getElementById('c02-kb-dialog').open) return;
        document.getElementById('c02-kb-name').value = doc.name || '';
        document.getElementById('c02-kb-visibility').value = doc.visibility || 'publico';
        document.getElementById('c02-kb-kind').value = doc.kind || 'texto';
        document.getElementById('c02-kb-body').value = doc.body_text || '';
      }, function (e) { flashStatus(e.message, 'error'); });
    }
    kbDialog.showModal();
  }

  if (kbPreviewBtn) {
    kbPreviewBtn.addEventListener('click', function () {
      if (!kbFile || !kbFile.files || !kbFile.files[0]) {
        flashIn(kbPreviewBox, 'error', 'Seleccione un archivo primero.');
        kbPreviewBox.hidden = false;
        return;
      }
      kbPreviewBtn.disabled = true;
      var fd = new FormData();
      fd.append('file', kbFile.files[0]);
      uploadJson(fd).then(function (j) {
        kbPreviewBtn.disabled = false;
        showPreview(j);
      }, function (e) {
        kbPreviewBtn.disabled = false;
        flashIn(kbPreviewBox, 'error', e.message);
        kbPreviewBox.hidden = false;
        uploadState = null;
      }).catch(function () {});
    });
  }

  if (kbForm) {
    function guardarKb(publicar) {
      var sb = kbForm.querySelector('button[type="submit"]');
      if (sb.disabled) return;
      var name = document.getElementById('c02-kb-name').value.trim();
      if (!name) { flashStatus('El nombre es obligatorio.', 'error'); return; }
      sb.disabled = true; if (kbSavePublic) kbSavePublic.disabled = true;
      var bodyText = document.getElementById('c02-kb-body').value;
      if (uploadState && !bodyText.trim()) {
        bodyText = uploadState.body_text || '';
      }
      var body = {
        doc_id: document.getElementById('c02-kb-id').value.length ? Number(document.getElementById('c02-kb-id').value) : null,
        name: name,
        body_text: bodyText,
        kind: document.getElementById('c02-kb-kind').value,
        visibility: document.getElementById('c02-kb-visibility').value
      };
      if (uploadState) {
        body.source_name = uploadState.filename;
        body.source_path = uploadState.filename;
        body.procedencia = uploadState.procedencia || [];
        body.extract_error = uploadState.extract_error || null;
      }
      if (!body.body_text.trim()) {
        sb.disabled = false; if (kbSavePublic) kbSavePublic.disabled = false;
        flashStatus('El contenido está vacío; no se puede guardar un documento sin texto.', 'error');
        return;
      }
      json('/api/c02/knowledge', 'POST', body).then(function (res) {
        if (publicar && res && res.doc_id) {
          return json('/api/c02/knowledge/' + res.doc_id + '/publish', 'POST', {});
        }
        return null;
      }).then(function () {
        sb.disabled = false; if (kbSavePublic) kbSavePublic.disabled = false;
        if (kbDialog) kbDialog.close();
        flashStatus(publicar ? 'Documento publicado y activo para la IA.' : 'Documento guardado como borrador (no publicado).', 'ok');
        kbReload();
      }, function (e) {
        sb.disabled = false; if (kbSavePublic) kbSavePublic.disabled = false;
        flashStatus(e.message, 'error');
      }).catch(function () {});
    }
    kbForm.addEventListener('submit', function (ev) { ev.preventDefault(); guardarKb(false); });
    var kbClose = kbForm.querySelector('[data-kb-close]');
    if (kbClose) kbClose.addEventListener('click', function () { if (kbDialog) kbDialog.close(); });
    var kbCancel = document.getElementById('c02-kb-cancel');
    if (kbCancel) kbCancel.addEventListener('click', function () { if (kbDialog) kbDialog.close(); });
  }

  if (kbBtn) {
    kbBtn.addEventListener('click', function () { openKb(null); });
    if (kbSavePublic) kbSavePublic.addEventListener('click', function () { guardarKb(true); });
  }

  function kbReload() {
    if (!isAdmin) return;
    json('/api/c02/knowledge').then(function (j) {
      kbDocs = (j && j.documents) || [];
      renderKb();
    }, function (e) { flashStatus(e.message, 'error'); }).catch(function () {});
  }

  if (kbTable) {
    if (kbBtn && !isAdmin) kbBtn.hidden = true;
    kbReload();
  }
})();
