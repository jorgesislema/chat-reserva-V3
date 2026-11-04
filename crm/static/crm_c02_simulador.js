/* Simulador de conversaciones: envía el texto al endpoint que corre el motor del
   canal sobre una copia de la base y pinta la conversación como un chat. */
(function () {
  'use strict';
  var app = document.getElementById('sim-app');
  if (!app) { return; }
  var body = document.getElementById('sim-body');
  var form = document.getElementById('sim-form');
  var input = document.getElementById('sim-text');
  var estado = document.getElementById('sim-estado');
  var reset = document.getElementById('sim-reset');
  var csrf = app.getAttribute('data-csrf');

  function pintar(datos) {
    body.innerHTML = '';
    (datos.mensajes || []).forEach(function (m) {
      var d = document.createElement('div');
      d.className = 'sim-msg ' + (m.dir === 'out' ? 'out' : 'in');
      var p = document.createElement('span');
      p.textContent = m.texto || '';
      d.appendChild(p);
      var h = document.createElement('span');
      h.className = 'hora';
      h.textContent = m.hora || '';
      d.appendChild(h);
      body.appendChild(d);
    });
    body.scrollTop = body.scrollHeight;
    if (datos.derivado) {
      estado.textContent = 'Derivado a una persona: el control quedó en la bandeja humana.';
    } else if (datos.mensajes && datos.mensajes.length) {
      estado.textContent = 'Conversación atendida por el bot · estado: ' + datos.estado;
    } else {
      estado.textContent = 'Sin mensajes todavía.';
    }
  }

  function enviar(texto, reiniciar) {
    var cuerpo = reiniciar ? { reiniciar: true } : { texto: texto };
    return fetch('/api/c02/simulador', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify(cuerpo)
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || j.ok === false) {
          throw new Error((j && j.error && j.error.message) || 'No se pudo simular');
        }
        return j;
      });
    });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var t = input.value.trim();
    if (!t) { return; }
    input.value = '';
    enviar(t).then(pintar, function (e) { estado.textContent = 'Error: ' + e.message; });
  });

  reset.addEventListener('click', function () {
    enviar('', true).then(pintar, function (e) { estado.textContent = 'Error: ' + e.message; });
  });
})();
