/* C02 — Biblioteca de recursos privados y plantillas WhatsApp (2026-10-29).
   Subida de recursos, permisos separados de envío/RAG, retirada con
   trazabilidad y plantillas con estado real (nunca auto-aprobadas).
   CSP estricta: sin inline. */
(function () {
  'use strict';

  var app = document.querySelector('#c02-library-app');
  if (!app) return;
  var csrf = app.getAttribute('data-csrf');
  var admin = app.getAttribute('data-admin') === '1';

  var status = document.getElementById('c02-lib-status');
  var table = document.getElementById('c02-lib-table');
  var empty = document.getElementById('c02-lib-empty');
  var form = document.getElementById('c02-lib-form');
  var tplApp = document.querySelector('#c02-plantillas-app');
  var tplTable = document.getElementById('c02_tpl_table');
  var tplEmpty = document.getElementById('c02_tpl_empty');
  var tplForm = document.getElementById('c02_tpl_form');

  var loading = false;
  var busy = {};

  function flash(msg, kind) {
    if (!status) return;
    if (!msg) { status.textContent = ''; return; }
    status.textContent = msg;
    status.className = 'status-line ' + (kind === 'error' ? 'error'
      : kind === 'ok' ? 'success' : 'info');
  }

  function json(url, method, body) {
    var m = (method || 'GET').toUpperCase();
    return fetch(url, {
      method: m,
      headers: m === 'GET' ? { 'X-CSRF-Token': csrf }
        : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: m === 'GET' ? undefined : JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          throw new Error((j.error && j.error.message) || j.message ||
                          'Error ' + r.status);
        }
        return j;
      });
    });
  }

  function cell(text) {
    var td = document.createElement('td');
    td.textContent = text === null || text === undefined ? '—' : text;
    return td;
  }

  function chip(label, cls) {
    var sp = document.createElement('span');
    sp.className = 'preview-chip' + (cls ? ' ' + cls : '');
    sp.textContent = label;
    return sp;
  }

  function fmtBytes(n) {
    if (!n && n !== 0) return '—';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  function render(items) {
    var tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    var activos = items.filter(function (i) { return i.estado === 'activo'; });
    var retirados = items.filter(function (i) { return i.estado !== 'activo'; });
    var orden = activos.concat(retirados);
    table.hidden = orden.length === 0;
    if (empty) empty.hidden = orden.length > 0;
    orden.forEach(function (it) {
      var tr = document.createElement('tr');
      tr.appendChild(cell(it.name));
      tr.appendChild(cell(({ catalogo: 'Catálogo', lista_precios: 'Lista de precios' }[it.categoria]) || it.categoria));
      tr.appendChild(cell('v' + it.version));
      var tdE = document.createElement('td');
      tdE.appendChild(it.estado === 'activo' ? chip('Activo', 'ok') : chip('Retirado'));
      if (it.retirado_en) tdE.appendChild(document.createTextNode(' ' + String(it.retirado_en).slice(0, 10)));
      tr.appendChild(tdE);
      tr.appendChild(cell(it.allow_send ? 'Permitido' : 'No', it.allow_send ? 'ok' : ''));
      tr.appendChild(cell(it.allow_rag ? 'Permitido' : 'No', it.allow_rag ? 'ok' : ''));
      tr.appendChild(cell(it.fragmentos > 0 ? String(it.fragmentos) : '—'));
      tr.appendChild(cell(fmtBytes(it.tamano)));
      if (admin) {
        var td = document.createElement('td');
        td.className = 'cell-col';
        var btnSend = document.createElement('button');
        btnSend.type = 'button';
        btnSend.className = 'cel';
        btnSend.textContent = it.allow_send ? 'Quitar envío' : 'Permitir envío';
        btnSend.disabled = !!busy[it.id];
        btnSend.addEventListener('click', function () {
          toggle(it.id, 'allow_send', !it.allow_send);
        });
        var btnRag = document.createElement('button');
        btnRag.type = 'button';
        btnRag.className = 'cel';
        btnRag.textContent = it.allow_rag ? 'Quitar RAG' : 'Permitir RAG';
        btnRag.disabled = !!busy[it.id];
        btnRag.addEventListener('click', function () {
          toggle(it.id, 'allow_rag', !it.allow_rag);
        });
        td.appendChild(btnSend);
        if (it.estado === 'activo') {
          var btnRet = document.createElement('button');
          btnRet.type = 'button';
          btnRet.className = 'cel';
          btnRet.textContent = 'Retirar';
          btnRet.disabled = !!busy[it.id];
          btnRet.addEventListener('click', function () { retirar(it.id); });
          td.appendChild(btnRet);
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    });
  }

  function toggle(id, campo, valor) {
    if (busy[id]) return;
    busy[id] = true;
    json('/api/c02/library/' + id, 'POST', (function () { var o = {}; o[campo] = valor; return o; })())
      .then(function () { flash('Permiso actualizado (envío y RAG son independientes).', 'ok'); recargar(); },
            function (e) { flash(e.message, 'error'); delete busy[id]; recargar(); });
  }

  function retirar(id) {
    if (busy[id]) return;
    if (!window.confirm('Retirar el recurso: queda fuera del asistente y del envío, '
                        + 'pero se conservan archivo, versiones y trazabilidad. ¿Continuar?')) return;
    busy[id] = true;
    json('/api/c02/library/' + id + '/retirar', 'POST', {})
      .then(function () { flash('Recurso retirado con trazabilidad.', 'ok'); recargar(); },
            function (e) { flash(e.message, 'error'); delete busy[id]; });
  }

  var itemsCache = [];
  function recargar() {
    if (loading) return Promise.resolve();
    loading = true;
    busy = {};
    return json('/api/c02/library').then(function (res) {
      itemsCache = res.items || [];
      render(itemsCache);
      loading = false;
    }, function (e) {
      flash('No se pudo cargar la biblioteca: ' + e.message, 'error');
      loading = false;
    });
  }

  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var sb = form.querySelector('button[type="submit"]');
      if (sb.disabled) return;
      var file = document.getElementById('c02-lib-file').files[0];
      var name = document.getElementById('c02-lib-name').value.trim();
      if (!file) { flash('Seleccione un archivo (PDF, xlsx, csv, txt o md).', 'error'); return; }
      if (!name) { flash('El nombre del recurso es obligatorio.', 'error'); return; }
      sb.disabled = true;
      var fd = new FormData();
      fd.append('file', file);
      fd.append('name', name);
      fd.append('categoria', document.getElementById('c02-lib-cat').value);
      fd.append('descripcion', document.getElementById('c02-lib-desc').value);
      fd.append('allow_send', document.getElementById('c02-lib-send').checked ? '1' : '0');
      fd.append('allow_rag', document.getElementById('c02-lib-rag').checked ? '1' : '0');
      fetch('/api/c02/library/upload', { method: 'POST', headers: { 'X-CSRF-Token': csrf }, body: fd })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (out) {
          sb.disabled = false;
          if (!out.ok) { flash((out.j.error && out.j.error.message) || 'No se pudo subir.', 'error'); return; }
          if (out.j.extract_error) {
            flash('Subido y archivado; sin texto extraído: ' + out.j.extract_error + ' (no entra al asistente).', 'error');
          } else {
            flash('Recurso archivado (v' + out.j.version + ') con los permisos elegidos.', 'ok');
          }
          form.reset();
          document.getElementById('c02-lib-rag').checked = true;
          recargar();
        })
        .catch(function () { sb.disabled = false; flash('Error de red al subir.', 'error'); });
    });
  }

  recargar();

  /* ---------------- Plantillas WhatsApp ---------------- */
  var ESTADOS = {
    borrador_local: ['Sin verificar (borrador local)', ''],
    pendiente_verificar: ['Pendiente de conexión', ''],
    aprobada: ['Aprobada por Meta', 'ok'],
    rechazada: ['Rechazada por Meta', '']
  };

  function renderTpl(items) {
    var tbody = tplTable.querySelector('tbody');
    tbody.innerHTML = '';
    tplTable.hidden = items.length === 0;
    if (tplEmpty) tplEmpty.hidden = items.length > 0;
    items.forEach(function (t) {
      var tr = document.createElement('tr');
      tr.appendChild(cell(t.name));
      tr.appendChild(cell(t.language));
      tr.appendChild(cell(({ UTILITY: 'Utilidad', MARKETING: 'Marketing', AUTHENTICATION: 'Autenticación' }[t.category]) || t.category));
      var pars = [];
      try { pars = JSON.parse(t.parameters || '[]'); } catch (e) {}
      tr.appendChild(cell(pars.length ? pars.map(function (p, i) {
        return (p && (p.etiqueta || p.name || p)) + ' ({{' + (i + 1) + '}})';
      }).join(', ') : 'Sin parámetros'));
      var tdE = document.createElement('td');
      var est = ESTADOS[t.estado] || [t.estado, ''];
      tdE.appendChild(chip(est[0], est[1]));
      tr.appendChild(tdE);
      tr.appendChild(cell(t.verificado_en ? String(t.verificado_en).slice(0, 16) : '—'));
      if (admin) {
        var td = document.createElement('td');
        td.className = 'cell-col';
        if (t.estado !== 'rechazada') {
          var b = document.createElement('button');
          b.type = 'button'; b.className = 'cel'; b.textContent = 'Retirar borrador';
          b.addEventListener('click', function () {
            if (!window.confirm('Retirar solo es válido mientras NO esté aprobada por Meta. ¿Continuar?')) return;
            fetch('/api/c02/plantillas/' + t.id + '/retirar', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: '{}' })
              .then(function (r) { return r.json(); })
              .then(function (j) { if (!j.ok) throw new Error((j.error && j.error.message) || j.message);
                       flash('Borrador retirado localmente.', 'ok'); cargarTpl(); });
          });
          td.appendChild(b);
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    });
  }

  function cargarTpl() {
    if (!tplTable) return Promise.resolve();
    return json('/api/c02/plantillas').then(function (res) { renderTpl(res.items || []); },
      function () { });
  }

  if (tplForm) {
    tplForm.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var sb = tplForm.querySelector('button[type="submit"]');
      if (sb.disabled) return;
      var params = document.getElementById('c02_tpl_params').value.split('\n')
        .map(function (x) { return x.trim(); }).filter(Boolean)
        .map(function (x) { return { etiqueta: x }; });
      sb.disabled = true;
      json('/api/c02/plantillas', 'POST', {
        name: document.getElementById('c02_tpl_name').value.trim(),
        language: document.getElementById('c02_tpl_lang').value,
        category: document.getElementById('c02_tpl_cat').value,
        body: document.getElementById('c02_tpl_body').value,
        parameters: params
      }).then(function (j) {
        sb.disabled = false;
        flash('Borrador local guardado: ' + j.estado +
              '. Aprobación sólo vía Meta (verificación externa).', 'ok');
        tplForm.reset();
        cargarTpl();
      }, function (e) { sb.disabled = false; flash(e.message, 'error'); });
    });
  }
  cargarTpl();
})();
