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
      var cita = document.createElement('button');
      cita.type = 'button'; cita.className = 'button ghost';
      cita.textContent = 'Proponer cita';
      cita.addEventListener('click', function () { abrirCitaDialog(conv); });
      actionsEl.appendChild(cita);
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

  // ---------- Cita excepcional coordinada por el operador ----------
  // El operador autorizado propone una cita desde la conversación: elige un
  // espacio DENTRO del horario habitual o una cita EXCEPCIONAL fuera de
  // horario con motivo obligatorio y confirmación explícita. El bot jamás abre
  // horarios; crear la cita no resuelve la atención ni devuelve el chat a la
  // IA (resolución y devolución son actos separados en la bandeja).
  var convIdCita = null;
  var modalExc = null;
  var modalProf = null;
  var modalFecha = null;
  var modalDur = null;
  var modalMotivo = null;
  var modalConfirm = null;

  function fechaLocalMañana() {
    var d = new Date(); d.setDate(d.getDate() + 1);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
      '-' + String(d.getDate()).padStart(2, '0');
  }

  function abrirCitaDialog(conv) {
    convIdCita = conv.id;
    var overlay = document.createElement('div');
    overlay.className = 'cita-overlay';
    overlay.id = 'cita-overlay';
    var mp = document.createElement('div');
    mp.className = 'cita-modal';
    mp.setAttribute('role', 'dialog');
    mp.setAttribute('aria-label', 'Proponer cita');

    var h = document.createElement('h3');
    h.className = 'cita-title';
    h.textContent = 'Proponer cita para ' + (conv.client_name || conv.client_key || 'el cliente');
    mp.appendChild(h);

    var nota = document.createElement('p');
    nota.className = 'cita-note';
    nota.textContent = 'Solo el administrador puede crear una cita excepcional fuera del horario habitual, con motivo obligatorio. Esta cita no resuelve la alerta ni devuelve el chat a la IA.';
    mp.appendChild(nota);

    var f = document.createElement('div');
    f.className = 'cita-field';
    f.appendChild(labelFor('cita-prof', 'Profesional'));
    modalProf = document.createElement('select');
    modalProf.id = 'cita-prof';
    modalProf.disabled = true;
    f.appendChild(modalProf);
    mp.appendChild(f);

    var f2 = document.createElement('div');
    f2.className = 'cita-field';
    f2.appendChild(labelFor('cita-fecha', 'Fecha'));
    modalFecha = document.createElement('input');
    modalFecha.id = 'cita-fecha'; modalFecha.type = 'date'; modalFecha.value = fechaLocalMañana();
    f2.appendChild(modalFecha);
    mp.appendChild(f2);

    var f3 = document.createElement('div');
    f3.className = 'cita-field';
    f3.appendChild(labelFor('cita-dur', 'Duración'));
    modalDur = document.createElement('select');
    modalDur.id = 'cita-dur';
    [15, 30, 45, 60, 90].forEach(function (d) {
      var o = document.createElement('option');
      o.value = String(d); o.textContent = d + ' min';
      if (d === 30) o.selected = true;
      modalDur.appendChild(o);
    });
    f3.appendChild(modalDur);
    mp.appendChild(f3);

    var status = document.createElement('p');
    status.className = 'status-line';
    status.style.display = 'none';
    mp.appendChild(status);

    var slotsWrap = document.createElement('div');
    slotsWrap.id = 'cita-slots';
    mp.appendChild(slotsWrap);

    var buscar = document.createElement('button');
    buscar.type = 'button'; buscar.className = 'button';
    buscar.textContent = 'Buscar espacios';
    buscar.addEventListener('click', function () {
      cargarSlots(status, slotsWrap);
    });
    mp.appendChild(buscar);

    var pie = document.createElement('div');
    pie.className = 'cita-pie';
    var cancel = document.createElement('button');
    cancel.type = 'button'; cancel.className = 'button ghost';
    cancel.textContent = 'Cancelar';
    cancel.addEventListener('click', function () { cerrarCitaDialog(); });
    pie.appendChild(cancel);
    mp.appendChild(pie);

    overlay.appendChild(mp);
    document.body.appendChild(overlay);
    json('/api/c02/excepcion/slots?professional_id=0').then(function (j) {
      modalProf.disabled = true;
      (j.profesionales || []).forEach(function (p) {
        var o = document.createElement('option');
        o.value = String(p.id);
        o.textContent = p.name + (String(p.active) === '1' ? '' : ' (inactivo)');
        modalProf.appendChild(o);
      });
      modalProf.disabled = false;
    }, function (e) { flashCita(status, e.message, 'error'); });
  }

  function labelFor(id, texto) {
    var l = document.createElement('label');
    l.setAttribute('for', id);
    l.textContent = texto;
    return l;
  }

  function cargarSlots(status, wrap) {
    if (!modalProf.value || !modalFecha.value) {
      flashCita(status, 'Seleccione profesional y fecha.', 'error');
      return;
    }
    wrap.innerHTML = '';
    json('/api/c02/excepcion/slots?professional_id=' + encodeURIComponent(modalProf.value) +
         '&date=' + encodeURIComponent(modalFecha.value) +
         '&duration_min=' + encodeURIComponent(modalDur.value)).then(function (j) {
      flashCita(status, '', '');
      var profName = '';
      (j.profesionales || []).forEach(function (p) { if (String(p.id) === modalProf.value) profName = p.name; });
      if (j.cerrado) {
        flashCita(status, 'El negocio está cerrado ese día. Elija otra fecha.', 'error');
        modalExc = null;
        return;
      }
      if ((j.slots || []).length) {
        var t = document.createElement('p');
        t.className = 'cita-note';
        t.textContent = 'Espacios disponibles dentro del horario habitual:';
        wrap.appendChild(t);
        var cj = document.createElement('div');
        cj.className = 'cita-slots';
        (j.slots || []).forEach(function (s) {
          var b = document.createElement('button');
          b.type = 'button'; b.className = 'cita-slot-btn';
          b.textContent = s.inicio;
          b.addEventListener('click', function () {
            if (window.confirm('¿Crear la cita con ' + profName + ' a las ' + s.inicio +
                               ' el ' + modalFecha.value + ' (' + modalDur.value + ' min)?')) {
              crearCita(false, s.inicio, '', status, wrap);
            }
          });
          cj.appendChild(b);
        });
        wrap.appendChild(cj);
      } else {
        var v = document.createElement('p');
        v.className = 'cita-note';
        v.textContent = 'Sin espacios libres dentro del horario habitual de ese día.';
        wrap.appendChild(v);
      }
      // Apartado de atención EXCEPCIONAL (fuera del horario habitual).
      var ex = document.createElement('div');
      ex.className = 'cita-exc';
      var eh = document.createElement('p');
      eh.className = 'cita-exc-title';
      eh.textContent = 'Cita excepcional (fuera del horario habitual)';
      ex.appendChild(eh);
      if (!j.fuera_horario_permitido) {
        var bloqueo = document.createElement('p');
        bloqueo.className = 'cita-exc-note';
        bloqueo.textContent = 'Este día tiene un bloqueo del negocio; la excepción no puede saltarlo.';
        ex.appendChild(bloqueo);
        modalExc = null;
      } else {
        var fila = document.createElement('div');
        fila.className = 'cita-field';
        fila.appendChild(labelFor('cita-exc-hora', 'Hora de inicio'));
        modalExc = document.createElement('input');
        modalExc.id = 'cita-exc-hora'; modalExc.type = 'time';
        modalExc.step = '600';
        fila.appendChild(modalExc);
        ex.appendChild(fila);
        var fm = document.createElement('div');
        fm.className = 'cita-field';
        fm.appendChild(labelFor('cita-exc-motivo', 'Motivo obligatorio'));
        modalMotivo = document.createElement('input');
        modalMotivo.id = 'cita-exc-motivo'; modalMotivo.type = 'text';
        modalMotivo.placeholder = '¿Por qué se atiende fuera del horario habitual?';
        fm.appendChild(modalMotivo);
        ex.appendChild(fm);
        var fc = document.createElement('label');
        fc.className = 'cita-exc-confirm';
        modalConfirm = document.createElement('input');
        modalConfirm.type = 'checkbox';
        fc.appendChild(modalConfirm);
        fc.appendChild(document.createTextNode(
          ' Confirmo que esta cita es excepcional, está fuera del horario habitual y no abre el horario general del negocio.'));
        ex.appendChild(fc);
        var btn = document.createElement('button');
        btn.type = 'button'; btn.className = 'button';
        btn.textContent = 'Crear cita excepcional';
        btn.addEventListener('click', function () {
          if (!modalExc.value) { flashCita(status, 'Indique la hora de inicio.', 'error'); return; }
          crearCita(true, modalExc.value, (modalMotivo.value || '').trim(), status, wrap);
        });
        ex.appendChild(btn);
      }
      wrap.appendChild(ex);
    }, function (e) { flashCita(status, e.message, 'error'); });
  }

  function crearCita(excepcional, inicio, motivo, status, wrap) {
    var payload = {
      professional_id: parseInt(modalProf.value, 10),
      fecha: modalFecha.value,
      inicio: inicio,
      duration_min: parseInt(modalDur.value, 10),
      title: 'Cita coordinada por operador',
      conversation_id: convIdCita,
      excepcional: excepcional
    };
    if (excepcional) {
      if (motivo.length < 8) { flashCita(status, 'El motivo debe tener al menos 8 caracteres.', 'error'); return; }
      if (!modalConfirm || !modalConfirm.checked) {
        flashCita(status, 'Confirme que la cita está fuera del horario habitual.', 'error');
        return;
      }
      payload.motivo = motivo;
      payload.confirmada_fuera_horario = true;
    }
    json('/api/c02/excepcion', 'POST', payload).then(function () {
      flash('Cita creada en la agenda', 'ok');
      cerrarCitaDialog();
      reload();
    }, function (e) {
      // Muestra el conflicto (solapamiento, bloqueo, fuera de horario sin
      // excepción...) y deja elegir otra opción: el diálogo permanece abierto.
      flashCita(status, e.message, 'error');
    });
  }

  function flashCita(el, msg, kind) {
    el.textContent = msg || '';
    el.className = 'status-line ' + (kind || 'info');
    el.style.display = msg ? '' : 'none';
  }

  function cerrarCitaDialog() {
    var overlay = document.getElementById('cita-overlay');
    if (overlay) overlay.remove();
    convIdCita = null; modalExc = null; modalMotivo = null; modalConfirm = null;
  }

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
  var qs = new URLSearchParams(window.location.search);
  var deep = qs.get('conversation');
  if (deep) {
    // Deep-link de la campana de atención: abre la conversación directamente.
    // El primer reload() ya cargó la lista; se usa el ID para abrir el hilo.
    var target = parseInt(deep, 10);
    if (target > 0) {
      var abrir = function () {
        var existe = conversations.some(function (c) { return String(c.id) === String(target); });
        if (existe) { openThread(target); window.history.replaceState({}, '', '/?tab=inbox'); }
        else { setTimeout(abrir, 400); }
      };
      setTimeout(abrir, 300);
    }
  }
  setInterval(function () { reload(); }, 20000);
  setInterval(pollAire, 5000);
})();
