/* C02 — Importación de inventario por Excel/CSV (punto 3, paso B).
   Wizard separado y controlado: subir → elegir hoja → mapear columnas →
   vista previa (nuevas/actualizaciones/duplicados/errores) → CONFIRMACIÓN
   explícita → aplicar. Sin estado temporal en servidor: el archivo se reenvía
   en cada paso. Sin scripts inline (CSP estricta). */
(function () {
  'use strict';

  var app = document.querySelector('#c02-catalog-app');
  if (!app) return;

  var csrf = app.getAttribute('data-csrf');
  var isAdmin = app.getAttribute('data-admin') === '1';
  if (!isAdmin) return;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function json(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          var err = new Error((j.error && j.error.message) || j.message || 'Error de servidor');
          var fc = (j.error && j.error.filas_afectadas) || j.filas_afectadas || [];
          if (fc.length) err.filas = fc;
          err.code = (j && j.error && j.error.code) || (j && j.code) || '';
          throw err;
        }
        return j;
      });
    });
  }

  function uploadJson(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrf },
      body: data
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          var err = new Error((j.error && j.error.message) || j.message || 'Error de servidor');
          var fc = (j.error && j.error.filas_afectadas) || j.filas_afectadas || [];
          if (fc.length) err.filas = fc;
          err.code = (j && j.error && j.error.code) || (j && j.code) || '';
          throw err;
        }
        return j;
      });
    });
  }

  var zone = document.getElementById('c02-inventory-zone');
  if (!zone) return;

  var CAMPOS = [
    { id: 'code', label: 'ID / código (*)' },
    { id: 'name', label: 'Nombre' },
    { id: 'kind', label: 'Tipo' },
    { id: 'details', label: 'Detalles' },
    { id: 'public_notes', label: 'Notas públicas' },
    { id: 'internal_notes', label: 'Observaciones internas' },
    { id: 'stock', label: 'Stock (conteo)' },
    { id: 'active', label: 'Activo' }
  ];

  var estado = { filename: null, data: null, sheets: [], sheet: null,
                 mapping: {}, rows: [], summary: null };

  function opcion(col) {
    return '<option value="' + col + '">' + col + '</option>';
  }

  function readFile(next) {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = '.xlsx,.csv';
    input.onchange = function () {
      var f = input.files && input.files[0];
      if (!f) return;
      estado.filename = f.name;
      var fd = new FormData();
      fd.append('file', f);
      var btn = el('button', 'button', 'Analizando hoja...');
      btn.disabled = true;
      zone.appendChild(btn);
      uploadJson('/api/c02/inventory/upload', fd).then(function (j) {
        btn.remove();
        estado.data = f;   // se reenvía el archivo original en cada paso
        next(j.sheets);
      }, function (e) {
        btn.remove();
        zone.appendChild(el('div', 'status-line error', e.message));
      }).catch(function () {});
    };
    input.click();
  }

  function columnasDeHoja() {
    var cols = [];
    (estado.sheets || []).forEach(function (s) {
      if (s.nombre === estado.sheet && Array.isArray(s.columnas)) {
        cols = s.columnas;
      }
    });
    return cols;
  }

  // Sugerencia de mapeo por posición típica, limitada a las columnas que
  // REALMENTE existen en la hoja seleccionada (MODO-01): el backend rechaza
  // un mapeo a una columna inexistente; los campos opcionales ausentes quedan
  // «(sin usar)» en lugar de inventar una columna F.
  function mapeoSugerido() {
    var cols = columnasDeHoja();
    var porPosicion = { code: 'A', name: 'B', kind: 'C', stock: 'D', active: 'E',
                        details: 'F', public_notes: 'G', internal_notes: 'H' };
    var sugerido = {};
    CAMPOS.forEach(function (campo) {
      var letra = porPosicion[campo.id];
      if (letra && cols.indexOf(letra) !== -1) sugerido[campo.id] = letra;
    });
    return sugerido;
  }

  function paso1(sheets) {
    estado.sheets = sheets;
    zone.innerHTML = '';
    var box = el('div', 'inv-step');
    box.appendChild(el('h3', '', '1. Seleccione la hoja'));
    var sel = document.createElement('select');
    sel.id = 'inv-sheet';
    sheets.forEach(function (s, i) {
      var o = document.createElement('option');
      o.value = s.nombre;
      o.textContent = s.nombre + ' (' + s.n_filas + ' filas)';
      sel.appendChild(o);
    });
    box.appendChild(sel);
    var nextBtn = el('button', 'button', 'Siguiente: asociar columnas');
    nextBtn.type = 'button';
    nextBtn.addEventListener('click', function () {
      estado.sheet = sel.value;
      paso2();
    });
    box.appendChild(nextBtn);
    zone.appendChild(box);
  }

  function paso2() {
    zone.innerHTML = '';
    var box = el('div', 'inv-step');
    box.appendChild(el('h3', '', '2. Asocie las columnas de la hoja con los campos del catálogo'));

    // Selector de hoja: al cambiar, recalcular las columnas disponibles y
    // descartar asociaciones que apunten a columnas inexistentes en la nueva.
    if ((estado.sheets || []).length > 1) {
      var selHoja = document.createElement('select');
      selHoja.id = 'inv-sheet2';
      estado.sheets.forEach(function (s) {
        var o = document.createElement('option');
        o.value = s.nombre;
        o.textContent = s.nombre + ' (' + s.n_filas + ' filas)';
        if (s.nombre === estado.sheet) o.selected = true;
        selHoja.appendChild(o);
      });
      selHoja.addEventListener('change', function () {
        estado.sheet = selHoja.value;
        // Eliminar asociaciones previas que ya no existan en la nueva hoja.
        var cols = columnasDeHoja();
        Object.keys(estado.mapping).forEach(function (campoId) {
          if (estado.mapping[campoId] && cols.indexOf(estado.mapping[campoId]) === -1) {
            delete estado.mapping[campoId];
          }
        });
        paso2();
      });
      box.appendChild(el('label', '', 'Hoja'));
      box.appendChild(selHoja);
    }

    var grid = el('div', 'inv-select-grid');
    var columnas = columnasDeHoja();
    var sugerido = mapeoSugerido();
    CAMPOS.forEach(function (campo) {
      var lab = el('label', '', campo.label);
      var sel = document.createElement('select');
      var o = document.createElement('option');
      o.value = '';
      o.textContent = '(sin usar)';
      sel.appendChild(o);
      // Preselección: la asociación ya confirmada por el usuario, o la
      // sugerencia por posición — siempre dentro de las columnas reales.
      var preseleccion = (estado.mapping[campo.id] || sugerido[campo.id] || '');
      columnas.forEach(function (col) {
        var oo = document.createElement('option');
        oo.value = col;
        oo.textContent = 'Columna ' + col;
        if (col === preseleccion) oo.selected = true;
        sel.appendChild(oo);
      });
      sel.dataset.campo = campo.id;
      lab.appendChild(sel);
      grid.appendChild(lab);
    });
    box.appendChild(grid);
    var prevBtn = el('button', 'button', 'Previsualizar cambios');
    prevBtn.type = 'button';
    prevBtn.addEventListener('click', function () {
      estado.mapping = {};
      grid.querySelectorAll('select').forEach(function (s) {
        if (s.value) estado.mapping[s.dataset.campo] = s.value;
      });
      paso3();
    });
    box.appendChild(prevBtn);
    zone.appendChild(box);
  }

  function badgeEstado(r) {
    var map = { nueva: ['nueva', 'Nueva'], actualizacion: ['actualizacion', 'Actualización'],
                duplicado: ['duplicado', 'Duplicado'], error: ['error', 'Error'] };
    var b = map[r.estado] || ['', r.estado];
    return '<span class="inv-badge ' + b[0] + '">' + b[1] + '</span>';
  }

  function paso3() {
    zone.innerHTML = '';
    var box = el('div', 'inv-step');
    box.appendChild(el('h3', '', '3. Vista previa (no se aplica nada aún)'));
    var fd = new FormData();
    fd.append('file', estado.data);
    fd.append('sheet', estado.sheet);
    fd.append('mapping', JSON.stringify(estado.mapping));
    uploadJson('/api/c02/inventory/preview', fd).then(function (j) {
      box.appendChild(el('div', 'status-line ok',
        'Nuevas: ' + j.summary.nuevas + ' · Actualizaciones: ' + j.summary.actualizaciones +
        ' · Duplicados: ' + j.summary.duplicados + ' · Errores: ' + j.summary.errores +
        ' · Stock ignorado (servicios): ' + j.summary.stock_ignorado));
      var table = el('table', 'inv-map-table');
      var thead = el('thead', '');
      var trh = el('tr', '');
      ['Fila','ID/código','Campos','Estado','Errores/avisos'].forEach(function (h) {
        trh.appendChild(el('th', '', h));
      });
      thead.appendChild(trh);
      table.appendChild(thead);
      var tbody = el('tbody', '');
      j.rows.forEach(function (r) {
        var tr = el('tr', r.estado === 'error' ? 'inv-row-err' : '', '');
        tr.appendChild(el('td', '', String(r.fila)));
        tr.appendChild(el('td', '', r.code || '—'));
        var campos = Object.keys(r.campos).map(function (k) {
          return k + '=' + (r.campos[k] || '');
        }).join(', ');
        tr.appendChild(el('td', '', campos));
        tr.appendChild(el('td', '', badgeEstado(r)));
        tr.appendChild(el('td', '', (r.errores || []).join('; ') +
                                (r.avisos && r.avisos.length ? ' [' + r.avisos.join('; ') + ']' : '')));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      box.appendChild(table);
      estado.rows = j.rows;
      estado.summary = j.summary;

      var backBtn = el('button', 'button ghost', '← Atrás');
      backBtn.type = 'button';
      backBtn.addEventListener('click', paso2);
      box.appendChild(backBtn);

      var applyBtn = el('button', 'button', 'Aplicar importación');
      applyBtn.type = 'button';
      applyBtn.addEventListener('click', function () {
        if (!window.confirm('¿Aplicar estos cambios al inventario? Esta acción se registrará.')) return;
        applyBtn.disabled = true;
        var fd2 = new FormData();
        fd2.append('file', estado.data);
        fd2.append('sheet', estado.sheet);
        fd2.append('mapping', JSON.stringify(estado.mapping));
        fd2.append('confirm', 'true');
        uploadJson('/api/c02/inventory/apply', fd2).then(function (res) {
          var msg = (res.ya_aplicada ? 'Ya aplicada antes (sin cambios). ' : '') +
            'Aplicadas: ' + res.aplicadas + ' (nuevas ' + res.creadas +
            ', actualizaciones ' + res.actualizadas + '). Duplicados ignorados: ' +
            res.duplicados + '. Errores: ' + res.errores + '.';
          box.appendChild(el('div', 'status-line ok', msg));
          paso4();
        }, function (e) {
          applyBtn.disabled = false;
          box.appendChild(el('div', 'status-line error', e.message));
        }).catch(function () {});
      });
      box.appendChild(applyBtn);
    }, function (e) {
      box.appendChild(el('div', 'status-line error', e.message));
    }).catch(function () {});
    zone.appendChild(box);
  }

  function paso4() {
    zone.innerHTML = '';
    var box = el('div', 'inv-step');
    box.appendChild(el('h3', '', '4. Listo'));
    box.appendChild(el('div', 'status-line ok',
      'La importación quedó registrada (archivo, usuario, fecha y resultado). ' +
      'La IA consulta las existencias desde la base de datos.'));

    var moreBtn = el('button', 'button', 'Otra importación');
    moreBtn.type = 'button';
    moreBtn.addEventListener('click', function () {
      estado = { filename: null, data: null, mapping: {}, sheet: null, rows: [], summary: null };
      readFile(paso1);
    });
    box.appendChild(moreBtn);
    zone.appendChild(box);
  }

  var startBtn = el('button', 'button', 'Importar inventario…');
  startBtn.type = 'button';
  startBtn.addEventListener('click', function () { readFile(paso1); });
  zone.appendChild(startBtn);
})();
