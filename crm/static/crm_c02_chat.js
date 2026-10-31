/* C02 — Chat de IA interno (punto 3): adaptador IA inyectable con fuentes.
   Muestra documento/ID/versión/procedencia y registros consultados, distingue
   abstención honesta y modo del adaptador (simulado/remoto_no_validado).
   Sin scripts inline (CSP estricta); el historial vive en el DOM. */
(function () {
  'use strict';

  var block = document.querySelector('.c02-chat-block');
  if (!block) return;

  var csrf = block.getAttribute('data-csrf');
  var form = document.getElementById('c02-chat-form');
  var input = document.getElementById('c02-chat-input');
  var sendBtn = document.getElementById('c02-chat-send');
  var log = document.getElementById('c02-chat-log');
  var fuenteBadge = document.getElementById('c02-chat-fuente');

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

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function addMsg(text, cls) {
    var d = el('div', 'inbox-message ' + cls, text);
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  function tipoLabel(t) {
    return { kb_doc: 'Conocimiento', catalog_item: 'Catálogo',
             stock_bd: 'Stock (BD)', agenda: 'Agenda', '': 'BD agenda',
             kb: 'Conocimiento', ninguna: 'sin fuente' }[t] || t || '';
  }

  function modoLabel(m) {
    return { simulado: 'adaptador simulado (solo pruebas/desarrollo)',
             remoto: 'proveedor de IA conectado',
             no_configurado: 'IA no configurada' }[m] || m || '';
  }

  function renderFuentes(j) {
    if (!fuenteBadge) return;
    var label = tipoLabel(j.fuente);
    var extra = j.adaptador ? ' · ' + modoLabel(j.modo) : '';
    fuenteBadge.textContent = 'fuente: ' + label + extra;
    var list = j.fuentes || [];
    list.forEach(function (f) {
      var parts = [tipoLabel(f.tipo) + ': ' + f.nombre];
      if (f.id) parts.push('ID ' + f.id);
      if (f.version) parts.push('v' + f.version);
      if (f.procedencia) parts.push(f.procedencia);
      addMsg(parts.join(' · '), 'note');
    });
  }

  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var q = input.value;
      if (!q.trim() || sendBtn.disabled) return;
      addMsg(q, 'out');
      input.value = '';
      sendBtn.disabled = true;
      json('/api/c02/chat', 'POST', { question: q })
        .then(function (j) {
          sendBtn.disabled = false;
          if (j.abstencion) {
            addMsg(j.answer || 'No tengo información suficiente.', 'note');
          } else {
            addMsg(j.answer || 'Sin respuesta.', 'in');
          }
          if (j.documento) {
            var dbg = j.version ? ' · versión ' + j.version : '';
            var dbp = j.procedencia ? ' · ' + j.procedencia : '';
            addMsg('Documento/registro: ' + j.documento + dbg + dbp, 'note');
          }
          renderFuentes(j);
        })
        .catch(function (e) {
          sendBtn.disabled = false;
          addMsg('Error: ' + (e && e.message), 'note');
        });
    });
  }
})();
