/* C02 — Biblioteca de envíos (sólo lectura, 2026-10-29).
   Lista el historial del outbox (GET /api/c02/outbox) sin ninguna acción de
   reenvío ni mutación. CSP estricta: sin inline. */
(function () {
  'use strict';

  var app = document.querySelector('#c02-outbox-app');
  if (!app) return;
  var csrf = app.getAttribute('data-csrf');

  var table = document.getElementById('c02-outbox-table');
  var empty = document.getElementById('c02-outbox-empty');
  var status = app.querySelector('.status-line');
  var refresh = document.getElementById('c02-outbox-refresh');
  var filtro = document.getElementById('c02-outbox-filter');
  var itemsCache = [];

  function json(url) {
    return fetch(url, { headers: { 'X-CSRF-Token': csrf } }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error((j.error && j.error.message) || 'Error de servidor');
        return j;
      });
    });
  }

  function estLabel(s) {
    return { pendiente: 'Pendiente', enviado: 'Enviado', fallo: 'Fallo',
             incierto: 'Incierto', bloqueado: 'Bloqueado', ajeno: 'Ajeno',
             diferida: 'Diferida' }[s] || s || '—';
  }

  function proveedorLabel(ps) {
    if (!ps) return '—';
    var base = String(ps).split('@')[0];
    var partes = base.split(':');
    var label = { aceptado: 'Aceptado', enviado: 'Enviado', entregado: 'Entregado',
                  leido: 'Leído', fallido: 'Fallo del proveedor' }[partes[0]] || partes[0];
    if (partes[1]) label += ': ' + partes[1];
    return label;
  }

  function stateChip(state) {
    var chip = document.createElement('span');
    chip.className = 'preview-chip';
    var cls = '';
    if (state === 'enviado') cls = '';
    else if (state === 'fallo' || state === 'bloqueado') { chip.style.background = '#fdecea'; chip.style.color = '#b3261e'; }
    else if (state === 'incierto') { chip.style.background = '#fff7e0'; chip.style.color = '#7a5a12'; }
    chip.textContent = estLabel(state);
    return chip;
  }

  function render(raw) {
    itemsCache = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.items) ? raw.items : []);
    pintar();
  }

  function pintar() {
    var items = itemsCache.filter(function (it) {
      return !filtro || filtro.value === 'todos' || it.channel === filtro.value;
    });
    table.hidden = items.length === 0;
    if (empty) empty.hidden = items.length > 0;
    if (!items.length) { status.textContent = ''; status.style.display = 'none'; return; }
    var tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    items.forEach(function (it) {
      var tr = document.createElement('tr');
      var td = function (txt) { var c = document.createElement('td'); c.textContent = txt === null || txt === undefined ? '—' : txt; return c; };
      tr.appendChild(td(it.created_at));
      tr.appendChild(td(it.channel || '—'));
      tr.appendChild(td(it.recipient || '—'));
      var st = document.createElement('td'); st.appendChild(stateChip(it.state || '')); tr.appendChild(st);
      tr.appendChild(td(proveedorLabel(it.provider_state)));
      tr.appendChild(td(it.attempts));
      tr.appendChild(td(it.eventos));
      tr.appendChild(td(it.provider_message_id || '—'));
      tbody.appendChild(tr);
    });
    status.textContent = items.length + ' envíos registrados.';
    status.className = 'status-line info';
    status.style.display = '';
  }

  var loading = false;
  function cargar() {
    if (loading) return;
    loading = true;
    status.textContent = 'Actualizando...';
    status.style.display = '';
    return json('/api/c02/outbox').then(render, function (e) {
      status.textContent = 'No se pudo cargar el historial: ' + e.message;
      status.className = 'status-line error';
      status.style.display = '';
    }).catch(function () {}).then(function () { loading = false; });
  }

  if (refresh) refresh.addEventListener('click', cargar);
  if (filtro) filtro.addEventListener('change', pintar);
  cargar();
})();
