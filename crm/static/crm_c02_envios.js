/* C02 — Biblioteca de envíos (2026-10-29; cancelación admin 2026-10-31).
   Lista el historial del outbox (GET /api/c02/outbox) sin reenvío. Un
   administrador puede cancelar una tarea PENDIENTE que aún no comenzó a
   enviarse (POST /api/c02/outbox/:id/cancel) con confirmación y motivo
   obligatorio; el servidor valida estado/atomicidad y lo audita. CSP
   estricta: sin inline. */
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

  function esElegibleCancelar(it) {
    return it.state === 'pendiente' && it.attempts === 0 &&
           !it.provider_message_id && !it.began_at;
  }

  function cancelarItem(id) {
    var ok = window.confirm('¿Cancelar la tarea de salida ' + id +
      ' (pendiente, sin enviar)? Esta acción no se puede deshacer.');
    if (!ok) return;
    var motivo = window.prompt('Motivo de la cancelación (obligatorio):', '');
    if (motivo === null) return;
    motivo = String(motivo || '').trim();
    if (motivo.length < 3) {
      window.alert('El motivo es obligatorio (mínimo 3 caracteres).');
      return;
    }
    fetch('/api/c02/outbox/' + id + '/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({ motivo: motivo })
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error((j.message) || 'Error de servidor');
        status.textContent = 'Tarea ' + id + ' cancelada.';
        status.className = 'status-line info';
        status.style.display = '';
        cargar();
      });
    }).catch(function (e) {
      status.textContent = 'No se pudo cancelar: ' + e.message;
      status.className = 'status-line error';
      status.style.display = '';
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
      if (String(it.state || '') === 'cancelado') { return false; }
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
      var tipo = (String(it.correlation || '').indexOf('recordatorio') === 0)
        ? 'Recordatorio'
        : (String(it.correlation || '') === 'aviso-especialista'
           ? 'Aviso urgente' : 'Mensaje');
      tr.appendChild(td(tipo));
      tr.appendChild(td(it.channel || '—'));
      tr.appendChild(td(it.recipient || '—'));
      var st = document.createElement('td'); st.appendChild(stateChip(it.state || '')); tr.appendChild(st);
      tr.appendChild(td(proveedorLabel(it.provider_state)));
      tr.appendChild(td(it.attempts));
      tr.appendChild(td(it.eventos));
      tr.appendChild(td(it.provider_message_id || '—'));
      var acc = document.createElement('td');
      if (esElegibleCancelar(it)) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'button danger';
        btn.textContent = 'Cancelar tarea';
        btn.addEventListener('click', (function (id) {
          return function () { cancelarItem(id); };
        })(it.id));
        acc.appendChild(btn);
      } else {
        acc.textContent = '—';
      }
      tr.appendChild(acc);
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
