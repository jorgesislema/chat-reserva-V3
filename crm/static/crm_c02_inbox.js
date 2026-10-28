/* C02 — Bandeja humana operativa. Sin scripts inline (CSP estricta).
   Lista conversaciones, toma de control, responder como operador (N4), estado de
   entrega de la respuesta (en cola/enviando/entregado/simulado/invalidada),
   devolver a IA y cerrar. La respuesta del operador lleva una clave de
   solicitud estable (request_id): los reintentos de red del mismo contenido no
   duplican y un borrador editado obtiene clave nueva (HUM-09). */
(function () {
  'use strict';

  var app = document.getElementById('c02-inbox-app');
  if (!app) return;

  var csrf = app.getAttribute('data-csrf');
  var userId = app.getAttribute('data-user');
  var listEl = document.getElementById('c02-inbox-list');
  var countEl = document.getElementById('c02-inbox-count');
  var emptyEl = document.getElementById('c02-inbox-empty');
  var statusEl = document.getElementById('c02-inbox-status');
  var threadEl = document.getElementById('c02-inbox-thread');
  var msgbox = document.getElementById('c02-inbox-messages');
  var nameEl = document.getElementById('c02-inbox-thread-name');
  var metaEl = document.getElementById('c02-inbox-thread-meta');
  var actionsEl = document.getElementById('c02-inbox-thread-actions');
  var replyForm = document.getElementById('c02-inbox-reply-form');
  var replyText = document.getElementById('c02-inbox-reply-text');
  var sendBtn = document.getElementById('c02-inbox-send');
  var conversations = [];
  var activeId = null;
  var replyKeyByThread = {};
  var lastBadgeSig = '';

  function makeRequestId() {
    if (window.crypto && window.crypto.randomUUID) return 'rq-' + window.crypto.randomUUID();
    return 'rq-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
  }

  function json(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { throw new Error((j.error && j.error.message) || 'Error de servidor'); }
        return j;
      });
    });
  }

  function flash(msg, kind) {
    statusEl.textContent = msg || '';
    statusEl.className = 'status-line ' + (kind || 'info');
    statusEl.style.display = msg ? '' : 'none';
  }

  function stateLabel(state) {
    return { 'ia_activa': 'IA activa', 'esperando_humano': 'Requiere persona',
             'humano_asignado': 'Humano asignado', 'cerrada': 'Cerrada' }[state] || state;
  }

  function entregaInfo(m) {
    if (!m.entrega) return null;
    var s = m.entrega.state;
    if (s === 'pendiente') return { text: 'en cola', cls: 'pending' };
    if (s === 'intento') return { text: 'enviando', cls: 'pending' };
    if (s === 'autorizado') return { text: 'admitido, en vuelo', cls: 'pending' };
    if (s === 'enviado') {
      var t = m.entrega.provider_state === 'entregado' ? 'entregado'
        : m.entrega.provider_state === 'simulado' ? 'simulado'
        : m.entrega.provider_state === 'aceptado' ? 'aceptado'
        : (m.entrega.provider_state || 'enviado');
      return { text: t, cls: 'ok' };
    }
    if (s === 'incierto') {
      // Resultado indeterminado (acuse perdido): se muestra, no se oculta.
      return { text: 'pendiente de confirmación', cls: 'err' };
    }
    if (s === 'fallo') {
      return { text: m.entrega.provider_state === 'invalidada' ? 'invalidada'
               : (m.entrega.provider_state || 'fallo'), cls: 'err' };
    }
    return null;
  }

  function badgeSignature(j) {
    // Huella de los estados de entrega visibles: al cambiar el estado REAL del
    // mensaje (cola -> admitido -> entregado/incierto) la firma cambia y
    // repinta la banda.
    var parts = [];
    (j.messages || []).forEach(function (m) {
      if (m.entrega) parts.push(m.id + ':' + m.entrega.state + ':' + (m.entrega.provider_state || ''));
    });
    return parts.join('|');
  }

  function renderList() {
    listEl.hidden = conversations.length === 0;
    emptyEl.hidden = conversations.length > 0;
    countEl.textContent = String(conversations.length);
    listEl.innerHTML = '';
    conversations.forEach(function (c) {
      var li = document.createElement('li');
      li.className = 'inbox-row';
      li.dataset.id = c.id;
      li.tabIndex = 0;
      li.addEventListener('click', function () { openThread(c.id); });

      var chip = document.createElement('span');
      chip.className = 'preview-chip inbox-row-state';
      chip.textContent = stateLabel(c.state);
      if (c.alerts_active > 0) chip.textContent += ' · alerta';
      li.appendChild(chip);

      var key = document.createElement('strong');
      key.className = 'inbox-row-key';
      key.textContent = c.client_key;
      var name = document.createElement('small');
      name.className = 'inbox-row-name';
      name.textContent = c.client_name || '';
      var last = document.createElement('small');
      last.className = 'inbox-row-last';
      last.textContent = c.message_count + ' msgs';
      li.appendChild(key); li.appendChild(name); li.appendChild(last);
      listEl.appendChild(li);
    });
  }

  function openThread(id) {
    activeId = id;
    json('/api/c02/inbox/' + id + '/messages').then(function (j) {
      lastBadgeSig = badgeSignature(j);
      var conv = null;
      conversations.forEach(function (c) { if (String(c.id) === String(id)) conv = c; });
      if (conv) {
        nameEl.textContent = conv.client_name || conv.client_key || 'Conversación';
        metaEl.textContent = (conv.client_key || '') + ' · ' + stateLabel(conv.state) +
          ' · Resp: ' + (conv.responsible_name || 'nadie');
        renderActions(conv);
      }
      msgbox.innerHTML = '';
      (j.messages || []).forEach(function (m) {
        var d = document.createElement('div');
        d.className = 'inbox-message ' +
          (m.direction === 'inbound' ? 'in' : m.direction === 'outbound' ? 'out' : 'note');
        var who = m.author_name || (m.direction === 'inbound' ? 'Cliente' : 'Operador');
        var t = document.createElement('div');
        t.className = 'mbody'; t.textContent = m.body;
        var mt = document.createElement('small');
        mt.textContent = who + ' · ' + (m.created_at || '');
        d.appendChild(t); d.appendChild(mt);
        var ent = entregaInfo(m);
        if (ent) {
          var badge = document.createElement('em');
          badge.className = 'entrega ' + ent.cls;
          badge.textContent = ent.text;
          d.appendChild(badge);
        }
        msgbox.appendChild(d);
      });
      threadEl.hidden = false;
      msgbox.scrollTop = msgbox.scrollHeight;
    }, flash_err);
  }

  function renderActions(conv) {
    actionsEl.innerHTML = '';
    var takenByMe = conv.responsible_user_id && String(conv.responsible_user_id) === String(userId);
    if (takenByMe) {
      var back = document.createElement('button');
      back.type = 'button'; back.className = 'button ghost';
      back.textContent = 'Devolver a IA';
      back.addEventListener('click', function () { returnToIa(conv.id); });
      actionsEl.appendChild(backSecondary(conv));
      actionsEl.appendChild(back);
      enableReply();
    } else {
      var take = document.createElement('button');
      take.type = 'button'; take.className = 'button';
      take.textContent = 'Tomar el chat';
      take.addEventListener('click', function () { takeConv(conv.id); });
      actionsEl.appendChild(take);
      disableReply();
    }
  }

  function backSecondary(conv) {
    var close = document.createElement('button');
    close.type = 'button'; close.className = 'button ghost';
    close.textContent = 'Cerrar';
    close.addEventListener('click', function () {
      if (window.confirm('¿Cerrar esta conversación? Ya no responderá la IA ni se admiten respuestas.')) {
        closeConv(conv.id);
      }
    });
    return close;
  }

  function enableReply() { sendBtn.disabled = false; replyText.disabled = false; }
  function disableReply() { sendBtn.disabled = true; replyText.disabled = true; }

  function takeConv(id) {
    json('/api/c02/inbox/' + id + '/take', 'POST', {}).then(reload, flash_err);
  }
  function returnToIa(id) {
    json('/api/c02/inbox/' + id + '/return', 'POST', {}).then(reload, flash_err);
  }
  function closeConv(id) {
    json('/api/c02/inbox/' + id + '/close', 'POST', {}).then(function () {
      activeId = null;
      reload();
    }, flash_err);
  }
  function flash_err(e) { if (e && e.message) flash(e.message, 'error'); }

  if (replyForm) {
    replyForm.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var body = replyText.value;
      if (!body.trim() || activeId === null) return;
      // Clave de solicitud estable para reintentos del MISMO contenido; el
      // borrador editado obtiene una clave nueva (no sobrescribe en servidor).
      var info = replyKeyByThread[activeId];
      if (!info || info.body !== body) {
        info = { key: makeRequestId(), body: body };
        replyKeyByThread[activeId] = info;
      }
      sendBtn.disabled = true;
      json('/api/c02/inbox/' + activeId + '/reply', 'POST',
           { body: body, request_id: info.key }).then(function () {
        delete replyKeyByThread[activeId];
        replyText.value = '';
        sendBtn.disabled = false;
        openThread(activeId);
      }, function (e) {
        // El borrador se conserva para reintentar o corregir (HUM-12).
        sendBtn.disabled = false;
        flash_err(e);
      });
    });
  }

  function reload() {
    json('/api/c02/inbox').then(function (j) {
      conversations = j.conversations || [];
      renderList();
      var conv = null;
      conversations.forEach(function (c) { if (c.id === activeId) conv = c; });
      if (conv) renderActions(conv);
      flash('');
    }, flash_err);
  }

  function pollAire() {
    // Actualiza la banda cuando cambie el estado REAL del mensaje (de 'en cola'
    // a 'entregado'/'incierto'/etc.), no sólo cuando hay mensajes en vuelo.
    if (activeId === null) return;
    json('/api/c02/inbox/' + activeId + '/messages').then(function (j) {
      var sig = badgeSignature(j);
      if (sig !== lastBadgeSig) { lastBadgeSig = sig; openThread(activeId); }
    }, function () {});
  }

  flash('Cargando bandeja...');
  reload();
  setInterval(function () { reload(); }, 20000);
  setInterval(pollAire, 5000);
})();
