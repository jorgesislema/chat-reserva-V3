/* C02 — frontend único: catálogo editable (cero inline, CSP estricta).
   Contrato de carga operativo (R1): la API devuelve {items:[...]} y esta pantalla
   lo convierte a filas; error inicial con reintento; edición por celda y detalle
   con Guardar/Cancelar/Enter/Escape, protección de doble envío y conflicto 409. */
(function () {
  'use strict';

  var app = document.querySelector('#c02-catalog-app');
  if (!app) {
    try {
      if (/(^|[?&])tab=catalog\b/.test(window.location.search)) {
        document.body.insertAdjacentHTML('afterbegin',
          '<p class="notice">No se encontró el panel de catálogo en esta página. ' +
          'Actualice con Ctrl+F5; si sigue así, cierre sesión y vuelva a entrar.</p>');
      }
    } catch (e) {}
    return;
  }

  var table = document.getElementById('c02-cat-table');
  var empty = document.getElementById('c02-cat-empty');
  var status = app.querySelector('.status-line');
  var retryBtn = document.getElementById('c02-cat-retry');
  var spinnerEl = document.getElementById('c02-cat-spinner');
  var csrf = app.getAttribute('data-csrf');
  var isAdmin = app.getAttribute('data-admin') === '1';
  var dlg = document.getElementById('c02-cat-dialog');
  var project = null;

  function json(url, method, body) {
    var ctrl = null, timer = null;
    try {
      if (typeof AbortController !== 'undefined') {
        ctrl = new AbortController();
        timer = setTimeout(function () { ctrl.abort(); }, 25000);
      }
    } catch (e) { ctrl = null; }
    var opts = {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: body ? JSON.stringify(body) : undefined
    };
    if (ctrl) opts.signal = ctrl.signal;
    return fetch(url, opts).then(function (r) {
      if (timer) clearTimeout(timer);
      if (r.redirected || (r.type === 'opaqueredirect')) {
        var err = new Error('Sesión vencida. Actualice la página e ingrese de nuevo.');
        err.status = 401;
        throw err;
      }
      return r.json().then(function (j) {
        if (!r.ok) {
          var err2 = new Error((j.error && j.error.message) || 'Error de servidor');
          err2.code = (j && j.error && j.error.code) || (j && j.code);
          err2.status = r.status;
          throw err2;
        }
        return j;
      }, function () {
        var err3 = new Error('Respuesta inválida del servidor. Actualice la página.');
        err3.status = r.status;
        throw err3;
      });
    }, function (e) {
      if (timer) clearTimeout(timer);
      if (e && e.name === 'AbortError') {
        var err4 = new Error('Tiempo de espera agotado (25 s). Pulse Reintentar.');
        err4.status = 0;
        throw err4;
      }
      throw e;
    });
  }

  function flash(msg, kind) {
    status.textContent = msg || '';
    status.className = 'status-line ' + (kind || 'info');
    status.style.display = msg ? '' : 'none';
  }
  function bubble(on) {
    if (spinnerEl) spinnerEl.hidden = !on;
  }

  function money(cents, currency) {
    if (cents === null || cents === undefined) return '—';
    var cur = (currency || 'USD');
    return new Intl.NumberFormat('es', { style: 'currency', currency: cur }).format(cents / 100);
  }

  function button(label, onClick, cls) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'button ' + (cls || 'ghost');
    b.textContent = label;
    b.addEventListener('click', function (ev) { ev.stopPropagation(); if (onClick) onClick(b); });
    return b;
  }

  function kindLabel(k) {
    return { servicio: 'Servicio', producto: 'Producto', regalo: 'Regalo', promocion: 'Promoción' }[k] || k;
  }

  // --- Edición de celda: Enter/Guardar confirma, Escape/Cancelar descarta. ---
  function editableTextCell(it, field, validate, isMultiline) {
    var td = document.createElement('td');
    var el = document.createElement(isMultiline ? 'textarea' : 'input');
    el.className = 'cell-edit';
    el.dataset.field = field;
    el.dataset.orig = it[field] === null || it[field] === undefined ? '' : it[field];
    el.value = el.dataset.orig;
    el.title = el.dataset.orig; // nombre completo accesible aunque corte la celda
    var busy = false;
    function commit(tr) {
      if (busy) return Promise.resolve(false);
      if (el.value === el.dataset.orig) return Promise.resolve(false);
      if (validate) {
        var bad = validate(el.value, it);
        if (bad) { flash(bad, 'error'); el.focus(); return Promise.reject(new Error(bad)); }
      }
      busy = true;
      el.disabled = true;
      return saveRaw(it, field, el.value, tr).then(function () {
        el.dataset.orig = el.value; el.title = el.value;
        busy = false; el.disabled = false;
        return true;
      }, function (e) {
        busy = false; el.disabled = false;
        flash('No se guardó por el momento: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
        throw e;
      });
    }
    el.__crmCommit = commit;
    function discard() {
      el.value = el.dataset.orig; el.blur();
    }
    function commitSolo() {
      var tr = el.closest ? el.closest('tr') : null;
      commit(tr).then(function (guardo) {
        if (guardo) {
          el.blur();
          reload().then(function () {
            flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
          });
        } else { el.blur(); }
      }).catch(function () {});
    }
    el.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && !isMultiline) { ev.preventDefault(); commitSolo(); }
      else if (ev.key === 'Escape') { discard(); }
    });
    if (isMultiline) {
      // Ctrl/Cmd+Enter confirma
      el.placeholder = 'Ctrl+Intro para guardar';
      el.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); commitSolo(); }
      });
    }
    el.addEventListener('change', function () { /* no guardar por blur */ });
    td.appendChild(el);
    return td;
  }

  function kindCell(it) {
    var td = document.createElement('td');
    td.className = 'cell-kind';
    var sel = document.createElement('select');
    sel.title = kindLabel(it.kind);
    sel.setAttribute('aria-label', 'Tipo de artículo');
    sel.dataset.field = 'kind';
    sel.dataset.orig = it.kind;
    ['servicio', 'producto', 'regalo', 'promocion'].forEach(function (k) {
      var o = document.createElement('option');
      o.value = k; o.textContent = kindLabel(k);
      if (k === it.kind) o.selected = true;
      sel.appendChild(o);
    });
    var busy = false;
    function commitKind(tr) {
      if (busy) return Promise.resolve(false);
      if (sel.value === sel.dataset.orig) return Promise.resolve(false);
      busy = true; sel.disabled = true;
      sel.title = kindLabel(sel.value);
      return saveRaw(it, 'kind', sel.value, tr).then(function () {
        sel.dataset.orig = sel.value; busy = false; sel.disabled = false;
        return true;
      }, function (e) {
        busy = false; sel.disabled = false;
        flash('No se guardó: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
        throw e;
      });
    }
    sel.__crmCommit = commitKind;
    sel.addEventListener('change', function () {
      var tr = sel.closest ? sel.closest('tr') : null;
      commitKind(tr).then(function (guardo) {
        if (guardo) reload().then(function () {
          flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
        });
      }).catch(function () {});
    });
    td.appendChild(sel);
    return td;
  }

  function priceCell(it, field) {
    field = field || 'price_cents';
    var td = document.createElement('td');
    var input = document.createElement('input');
    input.type = 'number';
    input.step = '0.01';
    input.className = 'c02-precio';
    var shown = it[field] === null || it[field] === undefined ? '' : (it[field] / 100);
    input.value = shown;
    input.dataset.orig = shown;
    input.dataset.field = field;
    input.setAttribute('aria-label', field === 'price_domicilio_cents' ? 'Precio a domicilio' : 'Precio local');
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); commitSoloP(); }
      else if (ev.key === 'Escape') { input.value = input.dataset.orig; input.blur(); }
    });
    function commitP(tr) {
      var v = input.value === '' ? null : Math.round(parseFloat(input.value) * 100);
      if (input.value === input.dataset.orig) return Promise.resolve(false);
      return saveRaw(it, field, v, tr).then(function () {
        input.dataset.orig = input.value;
        return true;
      }, function (e) {
        flash('No se guardó: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
        throw e;
      });
    }
    input.__crmCommit = commitP;
    function commitSoloP() {
      var tr = input.closest ? input.closest('tr') : null;
      commitP(tr).then(function (guardo) {
        if (guardo) reload().then(function () {
          flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
        });
      }).catch(function () {});
    }
    td.appendChild(input);
    var cur = document.createElement('small');
    cur.className = 'muted';
    cur.textContent = ' ' + (it.currency || 'USD');
    td.appendChild(cur);
    return td;
  }

  function vigenciaCell(it) {
    // Apiladas verticalmente a ancho completo: se ven enteras sin depender
    // del desplazamiento lateral.
    function fmt(iso) {
      var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
      return m ? m[1] + '-' + m[2] + '-' + m[3] : '';
    }
    var td = document.createElement('td');
    td.className = 'cell-vigencia';
    function guardar(campo, input, tr) {
      var v = input.value || '';
      if ((v || '') === (fmt(it[campo]) || '')) return Promise.resolve(false);
      return saveRaw(it, campo, v || null, tr).then(function () {
        input.dataset.orig = v;
        return true;
      }, function () {
        input.value = fmt(it[campo]);
        throw new Error('version');
      });
    }
    [['valid_from', 'Vigencia desde'], ['valid_until', 'Vigencia hasta']].forEach(function (par) {
      var lab = document.createElement('label');
      lab.className = 'vig-label';
      lab.textContent = par[1];
      var input = document.createElement('input');
      input.type = 'date';
      input.value = fmt(it[par[0]]);
      input.dataset.orig = input.value;
      input.dataset.field = par[0];
      input.title = par[1];
      input.setAttribute('aria-label', par[1]);
      (function (campo, inp) {
        inp.addEventListener('change', function () {
          var tr = inp.closest ? inp.closest('tr') : null;
          guardar(campo, inp, tr).then(function (guardo) {
            if (guardo) reload().then(function () {
              flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
            });
          }).catch(function () {});
        });
        inp.__crmCommit = function (tr) { return guardar(campo, inp, tr); };
      })(par[0], input);
      lab.appendChild(input);
      td.appendChild(lab);
    });
    return td;
  }


  function stateChip(it) {
    var td = document.createElement('td');
    var chip = document.createElement('span');
    chip.className = 'preview-chip';
    if (it.active === 0) chip.textContent = 'Inactivo';
    else if (it.publish_state === 'publicado') chip.textContent = 'Publicado';
    else chip.textContent = 'Borrador';
    td.appendChild(chip);
    return td;
  }

  function textCell(value, maxlen) {
    var td = document.createElement('td');
    var txt = value === null || value === undefined ? '' : String(value);
    if (!txt.trim()) { td.textContent = '—'; td.classList.add('muted'); return td; }
    var norm = String(txt).replace(/\s+/g, ' ').trim();
    if (maxlen && norm.length > maxlen) {
      norm = norm.slice(0, maxlen - 1).replace(/\s+\S*$/, '') + '…';
    }
    td.textContent = norm;
    if (String(txt).length > norm.length) td.title = String(txt).replace(/\s+/g, ' ').trim();
    return td;
  }

  function stockCell(it) {
    var td = document.createElement('td');
    var noAplica = it.stock_na === 1 || it.stock_na === '1' || it.stock_na === true ||
      ((it.kind === 'servicio' || it.kind === 'promocion') && (it.stock === null || it.stock === undefined));
    if (noAplica) {
      td.textContent = 'No aplica';
      td.classList.add('muted');
      return td;
    }
    var input = document.createElement('input');
    input.type = 'number';
    input.step = '1';
    input.min = '0';
    var shown = it.stock === null || it.stock === undefined ? '' : it.stock;
    input.value = shown;
    input.dataset.orig = shown;
    input.dataset.field = 'stock';
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); commitSoloS(); }
      else if (ev.key === 'Escape') { input.value = input.dataset.orig; input.blur(); }
    });
    function commitS(tr) {
      var v = input.value === '' ? null : parseInt(input.value, 10);
      if (v !== null && (isNaN(v) || v < 0)) {
        flash('Las existencias deben ser un número entero.', 'error');
        input.value = input.dataset.orig;
        return Promise.reject(new Error('stock'));
      }
      if (String(input.value) === String(input.dataset.orig)) return Promise.resolve(false);
      return saveRaw(it, 'stock', v, tr).then(function () {
        input.dataset.orig = input.value;
        return true;
      }, function (e) {
        flash('No se guardó: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
        throw e;
      });
    }
    input.__crmCommit = commitS;
    function commitSoloS() {
      var tr = input.closest ? input.closest('tr') : null;
      commitS(tr).then(function (guardo) {
        if (guardo) reload().then(function () {
          flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
        });
      }).catch(function () {});
    }
    td.appendChild(input);
    return td;
  }

  // Acciones: «Publicar / Nueva revisión» y «Detalle» como botones separados y
  // legibles (los recorta el CSS .cell-col con .cel, nunca pegados).
  function finalCol(it) {
    var td = document.createElement('td');
    td.className = 'cell-col';
    td.appendChild(button('Guardar', function (b) {
      var tr = b.closest ? b.closest('tr') : null;
      if (!tr) return;
      var sucios = [];
      var celdas = tr.querySelectorAll('[data-field]');
      for (var i = 0; i < celdas.length; i++) {
        var el = celdas[i];
        if (el.__crmCommit && el.value !== el.dataset.orig) sucios.push(el);
      }
      if (!sucios.length) { flash('Sin cambios por guardar.', 'ok'); return; }
      b.disabled = true;
      var cadena = Promise.resolve();
      sucios.forEach(function (el) {
        cadena = cadena.then(function () { return el.__crmCommit(tr); });
      });
      cadena.then(function () {
        reload().then(function () {
          flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
        });
      }, function (e) {
        if (e && e.message && e.message !== 'version') flash('No se guardó: ' + e.message + '.', 'error');
        reload();
      }).catch(function () { reload(); });
    }));
    if (it.publish_state !== 'publicado') {
      td.appendChild(button('Publicar', function (b) {
        b.disabled = true;
        json('/api/c02/catalog/' + it.id + '/publish', 'POST', {})
          .then(function () { flash('Publicado: el bot ya lo ve en el chat y el simulador.', 'ok'); reload(); }, function (e) {
            flash('No se publicó: ' + e.message + '.', 'error'); b.disabled = false;
          }).catch(function () {});
      }));
    } else {
      td.appendChild(button('Nueva revisión', function () { openDetail(it.id); }));
    }
    td.appendChild(button('Detalle', function () { openDetail(it.id); }));
    return td;
  }

  function render(raw) {
    var items = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.items) ? raw.items : []);
    table.hidden = items.length === 0;
    empty.hidden = items.length > 0;
    if (!items.length) { flash(''); return; }
    var tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    items.forEach(function (it) {
      var tr = document.createElement('tr');
      tr.dataset.id = it.id;
      tr.dataset.rev = it.current_revision;
      var c = document.createElement('td'); c.textContent = it.code || '—'; tr.appendChild(c);
      tr.appendChild(editableTextCell(it, 'name', function (v) {
        if (!String(v).trim()) return 'El nombre no puede quedar vacío.';
        return null;
      }));
      tr.appendChild(kindCell(it));
      tr.appendChild(editableTextCell(it, 'details', null, true));
      tr.appendChild(editableTextCell(it, 'public_notes'));
      tr.appendChild(priceCell(it, 'price_cents'));
      tr.appendChild(priceCell(it, 'price_domicilio_cents'));
      tr.appendChild(vigenciaCell(it));
      tr.appendChild(stockCell(it));
      tr.appendChild(stateChip(it));
      tr.appendChild(activeCell(it));
      tr.appendChild(finalCol(it));
      tbody.appendChild(tr);
    });
    flash('');
    try { document.dispatchEvent(new CustomEvent('crm:tabla-actualizada')); } catch (e) {}
  }

  // Columna Activo/Inactivo con interruptor directo: al cambiar se guarda
  // (revisión nueva) y el bot deja de verlo de inmediato si se desactiva.
  function activeCell(it) {
    var td = document.createElement('td');
    var label = document.createElement('label');
    label.className = 'check';
    label.title = 'Activo para el bot y la agenda';
    var input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = (it.active == 1 || it.active === true);
    input.setAttribute('aria-label', 'Artículo activo');
    input.addEventListener('change', function () {
      var quiere = input.checked ? 1 : 0;
      save(it, 'active', quiere).then(null, function () {
        input.checked = !input.checked;
      });
    });
    label.appendChild(input);
    var texto = document.createElement('span');
    texto.textContent = input.checked ? 'Activo' : 'Inactivo';
    label.appendChild(texto);
    td.appendChild(label);
    return td;
  }

  function saveRaw(it, field, value, tr) {
    var rev = Number((tr && tr.dataset.rev) || it.current_revision);
    return json('/api/c02/catalog/' + it.id, 'POST',
      { field: field, value: value, revision: rev }).then(function (res) {
        var r = Number(res && res.revision) || (rev + 1);
        it.current_revision = r;
        if (tr) { try { tr.dataset.rev = String(r); } catch (e) {} }
        return r;
      });
  }

  function save(it, field, value, tr) {
    return saveRaw(it, field, value, tr).then(function () {
      reload().then(function () {
        flash('Guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
      });
    });
  }

  var loading = false;
  function reload(auto) {
    if (loading) return Promise.resolve();
    loading = true;
    bubble(true);
    return json('/api/c02/catalog').then(render).catch(function (e) {
      flash('No se pudo cargar el catálogo: ' + e.message + '.', 'error');
      if (auto && e.status !== 401 && e.status !== 404 && retryBtn) retryBtn.hidden = false;
      throw e;
    }).then(function () { loading = false; bubble(false); },
      function (e) { loading = false; bubble(false); throw e; });
  }

  // --- Detalle por artículo (diálogo modal) ---
  function val(id) { var e = document.getElementById(id); return e ? e.value : ''; }

  function openDetail(id) {
    json('/api/c02/catalog/' + id).then(function (j) {
      if (!j.ok) throw new Error(j.message || 'No se pudo abrir el artículo');
      var it = j.item;
      project = it;
      if (dlg) delete dlg.dataset.creating;
      fillDetail(it);
      dlg.showModal();
      var nameF = document.getElementById('c02-f-name');
      if (nameF) nameF.focus();
    }, errFlash).catch(function (e) { if (e && e.message) { /* cuerpo vacío */ } });
  }

  function errFlash(e) { if (e && e.message) flash(e.message, 'error'); }

  function attrsATexto(valor) {
    // {"color":"rojo"} → «color: rojo» (una línea por atributo).
    if (!valor) return '';
    var obj = valor;
    if (typeof obj === 'string') {
      try { obj = JSON.parse(obj); } catch (e) { return valor; }
    }
    if (!obj || typeof obj !== 'object') return '';
    return Object.keys(obj).map(function (k) {
      return k + ': ' + obj[k];
    }).join('\n');
  }

  function textoAAttrs(texto) {
    // «color: rojo» por línea → objeto JSON (o '' si no hay nada).
    var obj = {};
    (texto || '').split(/\r?\n/).forEach(function (linea) {
      var i = linea.indexOf(':');
      if (i <= 0) return;
      var clave = linea.slice(0, i).trim().toLowerCase();
      var valor = linea.slice(i + 1).trim();
      if (clave && valor) obj[clave] = valor;
    });
    return Object.keys(obj).length ? JSON.stringify(obj) : '';
  }

  function aplicarTipo(kind) {
    var prod = document.getElementById('c02-bloque-producto');
    var trat = document.getElementById('c02-bloque-tratamiento');
    var esProducto = kind !== 'servicio';
    if (prod) prod.style.display = esProducto ? '' : 'none';
    if (trat) trat.style.display = esProducto ? 'none' : '';
  }

  function fillDetail(it) {
    var pairs = [
      ['c02-f-code', it.code], ['c02-f-name', it.name], ['c02-f-details', it.details || ''],
      ['c02-f-public-notes', it.public_notes || ''],
      ['c02-f-internal-notes', it.internal_notes || ''],
      ['c02-f-currency', it.currency || 'USD'],
      ['c02-f-stock', it.stock === null || it.stock === undefined ? '' : it.stock],
      ['c02-f-valid-from', it.valid_from || ''],
      ['c02-f-valid-until', it.valid_until || ''],
      ['c02-f-brand', it.brand || ''],
      ['c02-f-presentation', it.presentation || ''],
      ['c02-f-attributes', attrsATexto(it.attributes_json)],
      ['c02-f-allergens', it.allergens || ''],
      ['c02-f-warnings', it.warnings || ''],
      ['c02-f-aliases', it.aliases || ''],
      ['c02-f-sessions', it.sessions === null || it.sessions === undefined ? '' : it.sessions],
      ['c02-f-prep-notes', it.prep_notes || ''],
      ['c02-f-aftercare-notes', it.aftercare_notes || ''],
      ['c02-f-duration', it.duration_min === null || it.duration_min === undefined ? '' : it.duration_min]
    ];
    pairs.forEach(function (p) {
      var el = document.getElementById(p[0]);
      if (el) el.value = p[1];
    });
    var kindSel = document.getElementById('c02-f-kind'); if (kindSel) kindSel.value = it.kind;
    aplicarTipo(it.kind);
    var req = document.getElementById('c02-f-requires-evaluation');
    if (req) req.checked = it.requires_evaluation === 1 || it.requires_evaluation === '1' || it.requires_evaluation === true;
    var act = document.getElementById('c02-f-active'); if (act) act.checked = it.active === 1 || it.active === '1' || it.active === true;
    var sna = document.getElementById('c02-f-stock-na'); if (sna) sna.checked = it.stock_na === 1 || it.stock_na === '1' || it.stock_na === true;
    var priceIn = document.getElementById('c02-f-price'); if (priceIn) priceIn.value = it.price_cents === null || it.price_cents === undefined ? '' : (it.price_cents / 100);
    var priceDom = document.getElementById('c02-f-price-dom'); if (priceDom) priceDom.value = it.price_domicilio_cents === null || it.price_domicilio_cents === undefined ? '' : (it.price_domicilio_cents / 100);
    var prof = document.getElementById('c02-f-professional'); if (prof) prof.value = it.professional_id || '';
  }

  var detailForm = document.getElementById('c02-detail-form');
  if (detailForm && dlg) {
    var kindField = document.getElementById('c02-f-kind');
    if (kindField) {
      kindField.addEventListener('change', function () { aplicarTipo(kindField.value); });
    }
    detailForm.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var submitBtn = detailForm.querySelector('button[type="submit"]');
      if (submitBtn && submitBtn.disabled) return;
      if (submitBtn) submitBtn.disabled = true;
      if (pubBtn) pubBtn.disabled = true;
      var creating = dlg.dataset.creating === '1';

      var updates = [];
      if (!creating) {
        updates.push({ field: 'name', value: val('c02-f-name') });
        updates.push({ field: 'kind', value: val('c02-f-kind') });
      }
      updates.push({ field: 'details', value: val('c02-f-details') });
      updates.push({ field: 'public_notes', value: val('c02-f-public-notes') });
      updates.push({ field: 'internal_notes', value: val('c02-f-internal-notes') });
      updates.push({ field: 'currency', value: val('c02-f-currency') || 'USD' });
      var priceStr = val('c02-f-price');
      updates.push({ field: 'price_cents', value: priceStr === '' ? null : Math.round(parseFloat(priceStr) * 100) });
      var priceDomStr = val('c02-f-price-dom');
      updates.push({ field: 'price_domicilio_cents', value: priceDomStr === '' ? null : Math.round(parseFloat(priceDomStr) * 100) });
      var stockStr = val('c02-f-stock');
      updates.push({ field: 'stock', value: stockStr === '' ? null : parseInt(stockStr, 10) });
      var sna = document.getElementById('c02-f-stock-na');
      updates.push({ field: 'stock_na', value: sna && sna.checked ? 1 : 0 });
      var act = document.getElementById('c02-f-active');
      updates.push({ field: 'active', value: act && act.checked ? 1 : 0 });
      var dur = val('c02-f-duration');
      updates.push({ field: 'duration_min', value: dur === '' ? null : parseInt(dur, 10) });
      updates.push({ field: 'valid_from', value: val('c02-f-valid-from') || null });
      updates.push({ field: 'valid_until', value: val('c02-f-valid-until') || null });
      var profEl = document.getElementById('c02-f-professional');
      updates.push({ field: 'professional_id', value: profEl && profEl.value ? parseInt(profEl.value, 10) : null });
      // Detalle del artículo: cada dato en su campo, editable desde aquí.
      updates.push({ field: 'brand', value: val('c02-f-brand') });
      updates.push({ field: 'presentation', value: val('c02-f-presentation') });
      updates.push({ field: 'attributes_json', value: textoAAttrs(val('c02-f-attributes')) });
      updates.push({ field: 'allergens', value: val('c02-f-allergens') });
      updates.push({ field: 'warnings', value: val('c02-f-warnings') });
      updates.push({ field: 'aliases', value: val('c02-f-aliases') });
      var ses = val('c02-f-sessions');
      updates.push({ field: 'sessions', value: ses === '' ? null : parseInt(ses, 10) });
      updates.push({ field: 'prep_notes', value: val('c02-f-prep-notes') });
      updates.push({ field: 'aftercare_notes', value: val('c02-f-aftercare-notes') });
      var req = document.getElementById('c02-f-requires-evaluation');
      updates.push({ field: 'requires_evaluation', value: req && req.checked ? 1 : 0 });

      var rev = 1;
      var targetId = project ? project.id : null;

      function ensureCreated() {
        if (!creating || targetId) return Promise.resolve();
        // En modo crear: primero damos de alta el artículo (revisión 1) y luego
        // se aplican el resto de campos como ediciones con la versión vigente.
        return json('/api/c02/catalog', 'POST',
                    { name: val('c02-f-name') || 'Sin nombre', kind: val('c02-f-kind') })
          .then(function (j) {
            targetId = j.item_id;
            return json('/api/c02/catalog/' + targetId).then(function (d) {
              rev = Number(d.item.current_revision);
              if (val('c02-f-kind')) {
                // name/kind ya quedaron puestos al alta.
              }
            });
          });
      }

      ensureCreated().then(function () {
        if (!targetId) throw new Error('No se pudo crear el artículo');
        (function next(i) {
          if (i >= updates.length) {
            if (submitBtn) submitBtn.disabled = false;
            if (pubBtn) pubBtn.disabled = false;
            if (dlg.dataset.publicar === '1') {
              dlg.dataset.publicar = '';
              json('/api/c02/catalog/' + targetId + '/publish', 'POST', {})
                .then(function () {
                  dlg.close();
                  flash('Publicado: el bot ya lo ve en el chat y el simulador.', 'ok');
                  reload();
                }, function (e) {
                  dlg.close();
                  flash('Guardado, pero no se pudo publicar: ' + e.message + '.', 'error');
                  reload();
                }).catch(function () { reload(); });
              return;
            }
            dlg.close();
            flash('Artículo guardado como borrador. Pulse «Publicar» en la fila para que el bot lo vea.', 'ok');
            reload();
            return;
          }
          var u = updates[i];
          json('/api/c02/catalog/' + targetId, 'POST', { field: u.field, value: u.value, revision: rev })
            .then(function () {
              return json('/api/c02/catalog/' + targetId).then(function (d) {
                if (d.item.current_revision > rev) rev = d.item.current_revision;
                return d;
              });
            })
            .then(function () { next(i + 1); })
            .catch(function (e) {
              if (submitBtn) submitBtn.disabled = false;
              if (pubBtn) pubBtn.disabled = false;
              flash('No se guardó: ' + e.message + '.', 'error');
              if (e.code === 'version_conflict' || e.status === 409) { reload(); dlg.close(); }
            });
        })(0);
      }).catch(function (e) {
        if (submitBtn) submitBtn.disabled = false;
        if (pubBtn) pubBtn.disabled = false;
        flash('No se guardó: ' + e.message + '.', 'error');
      });
    });
    var pubBtn = document.getElementById('c02-detail-save-publish');
    if (pubBtn && !pubBtn.dataset.enlazado) {
      pubBtn.dataset.enlazado = '1';
      pubBtn.addEventListener('click', function () {
        if (pubBtn.disabled) return;
        dlg.dataset.publicar = '1';
        if (detailForm.requestSubmit) detailForm.requestSubmit();
        else detailForm.dispatchEvent(new Event('submit', { cancelable: true }));
      });
    }
    var cancelBtn = dlg.querySelector('.detail-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', function () { dlg.close(); });
    // Escape por defecto del <dialog> cierra sin guardar.
  }

  var newBtn = document.getElementById('c02-cat-new');
  if (newBtn) newBtn.addEventListener('click', function () { openCreate(); });

  // Aviso antes de recargar con celdas sin guardar: sin esto, un F5 borra
  // lo editado porque la edición solo se confirma con Guardar/Enter.
  window.addEventListener('beforeunload', function (ev) {
    try {
      var pendientes = document.querySelectorAll('#c02-cat-table [data-field]');
      for (var i = 0; i < pendientes.length; i++) {
        var el = pendientes[i];
        if (el && el.value !== el.dataset.orig) {
          ev.preventDefault();
          ev.returnValue = '';
          return;
        }
      }
    } catch (e) { /* nunca bloquear la salida por el aviso */ }
  });

  function openCreate() {
    // Modo crear: abre el diálogo con campos vacíos y guarda un artículo nuevo.
    project = null;
    ['c02-f-code', 'c02-f-name', 'c02-f-details', 'c02-f-public-notes',
     'c02-f-internal-notes', 'c02-f-currency', 'c02-f-stock', 'c02-f-valid-from',
     'c02-f-valid-until', 'c02-f-duration', 'c02-f-price', 'c02-f-brand',
     'c02-f-presentation', 'c02-f-attributes', 'c02-f-allergens',
     'c02-f-warnings', 'c02-f-aliases', 'c02-f-sessions', 'c02-f-prep-notes',
     'c02-f-aftercare-notes', 'c02-f-price-dom'].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.value = '';
    });
    var k = document.getElementById('c02-f-kind');
    var nk = document.getElementById('c02-new-kind');
    if (k) k.value = (nk && nk.value) || 'servicio';
    aplicarTipo(k ? k.value : 'servicio');
    var reqEv = document.getElementById('c02-f-requires-evaluation');
    if (reqEv) reqEv.checked = false;
    var pa = document.getElementById('c02-f-active'); if (pa) pa.checked = true;
    var sn = document.getElementById('c02-f-stock-na'); if (sn) sn.checked = false;
    var pr = document.getElementById('c02-f-professional'); if (pr) pr.value = '';
    dlg.dataset.creating = '1';
    dlg.showModal();
    var nameF = document.getElementById('c02-f-name');
    if (nameF) nameF.focus();
  }

  if (retryBtn) retryBtn.addEventListener('click', function () { retryBtn.hidden = true; reload(true).catch(function () {}); });

  reload(true).catch(function () {});
})();
