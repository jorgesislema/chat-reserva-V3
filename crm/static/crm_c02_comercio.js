/* C02 — Importación de configuración por plantilla Excel fija.
   Flujo: descargar plantilla → llenar → subir → vista previa (errores por
   hoja y fila) → CONFIRMACIÓN explícita → aplicar. Sin mapeo de columnas y
   sin estado temporal en servidor: el archivo se reenvía en cada paso.
   Sin scripts inline (CSP estricta). */
(function () {
  'use strict';

  var app = document.querySelector('#c02-catalog-app');
  if (!app) return;

  var csrf = app.getAttribute('data-csrf');
  var isAdmin = app.getAttribute('data-admin') === '1';
  if (!isAdmin) return;

  var zone = document.getElementById('c02-config-zone');
  if (!zone) return;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function post(url, fd) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrf },
      body: fd
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          var err = new Error((j.error && j.error.message) || j.message || 'Error de servidor');
          err.detalle = j;
          throw err;
        }
        return j;
      });
    });
  }

  var estado = { file: null, filename: null, token: null };

  function limpiar() {
    while (zone.firstChild) zone.removeChild(zone.firstChild);
  }

  function mostrarErrores(errores) {
    var wrap = el('div', 'table-wrap');
    var tabla = el('table');
    var thead = el('thead');
    var tr = el('tr');
    ['Hoja', 'Fila', 'Problema'].forEach(function (h) { tr.appendChild(el('th', null, h)); });
    thead.appendChild(tr);
    tabla.appendChild(thead);
    var tb = el('tbody');
    (errores || []).slice(0, 50).forEach(function (e) {
      var fila = el('tr');
      fila.appendChild(el('td', null, e.hoja || ''));
      fila.appendChild(el('td', null, e.fila === null || e.fila === undefined ? '' : String(e.fila)));
      fila.appendChild(el('td', null, e.mensaje || ''));
      tb.appendChild(fila);
    });
    tabla.appendChild(tb);
    wrap.appendChild(tabla);
    zone.appendChild(wrap);
    if ((errores || []).length > 50) {
      zone.appendChild(el('p', 'muted', 'Mostrando los primeros 50 errores.'));
    }
  }

  function vistaPrevia() {
    limpiar();
    if (!estado.file) return;
    var btn = el('button', 'button', 'Analizando archivo...');
    btn.disabled = true;
    zone.appendChild(btn);
    var fd = new FormData();
    fd.append('file', estado.file);
    post('/api/comercio/importar/vista-previa', fd).then(function (j) {
      btn.remove();
      estado.token = j.token;
      var resumen = Object.keys(j.resumen || {}).map(function (k) {
        return k + ': ' + j.resumen[k];
      }).join(' · ');
      zone.appendChild(el('p', 'status-line', 'Vista previa: ' + (resumen || 'sin cambios') + '.'));
      (j.advertencias || []).forEach(function (a) {
        zone.appendChild(el('p', 'muted', 'Aviso: ' + a));
      });
      var ok = el('button', 'button primary', 'Confirmar y aplicar');
      ok.onclick = aplicar;
      zone.appendChild(ok);
    }, function (e) {
      btn.remove();
      zone.appendChild(el('div', 'status-line error', String(e.message || e)));
      if (e.detalle && e.detalle.errores) mostrarErrores(e.detalle.errores);
    }).catch(function () {});
  }

  function aplicar() {
    limpiar();
    var btn = el('button', 'button', 'Aplicando...');
    btn.disabled = true;
    zone.appendChild(btn);
    var fd = new FormData();
    fd.append('file', estado.file);
    fd.append('confirm', 'true');
    fd.append('token', estado.token || '');
    post('/api/comercio/importar/aplicar', fd).then(function (j) {
      btn.remove();
      zone.appendChild(el('p', 'status-line', 'Aplicado: ' + j.aplicados + ' cambios. Recarga el catálogo para verlos.'));
      (j.advertencias || []).forEach(function (a) {
        zone.appendChild(el('p', 'muted', 'Aviso: ' + a));
      });
    }, function (e) {
      btn.remove();
      zone.appendChild(el('div', 'status-line error', String(e.message || e)));
      if (e.detalle && e.detalle.errores) mostrarErrores(e.detalle.errores);
    }).catch(function () {});
  }

  var subir = el('button', 'button', 'Subir plantilla llena');
  subir.onclick = function () {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = '.xlsx';
    input.onchange = function () {
      var f = input.files && input.files[0];
      if (!f) return;
      estado.file = f;
      estado.filename = f.name;
      estado.token = null;
      vistaPrevia();
    };
    input.click();
  };
  zone.appendChild(subir);
})();
