/* C02 — frontend único: catálogo editable (cero inline, CSP estricta).
   Contrato de carga operativo (R1): la API devuelve {items:[...]} y esta pantalla
   lo convierte a filas; error inicial con reintento; edición por celda y detalle
   con Guardar/Cancelar/Enter/Escape, protección de doble envío y conflicto 409. */
(function () {
  'use strict';

  var app = document.querySelector('#c02-catalog-app');
  if (!app) return;

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
    return fetch(url, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          var err = new Error((j.error && j.error.message) || 'Error de servidor');
          err.code = (j && j.error && j.error.code) || (j && j.code);
          err.status = r.status;
          throw err;
        }
        return j;
      });
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
    function commit() {
      if (busy) return;
      if (el.value === el.dataset.orig) { el.blur(); return; }
      if (validate) {
        var bad = validate(el.value, it);
        if (bad) { flash(bad, 'error'); el.focus(); return; }
      }
      busy = true;
      el.disabled = true;
      save(it, field, el.value).then(function () {
        el.dataset.orig = el.value; busy = false; el.disabled = false;
      }, function (e) {
        busy = false; el.disabled = false;
        flash('No se guardó por el momento: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
      }).catch(function () {});
    }
    function discard() {
      el.value = el.dataset.orig; el.blur();
    }
    el.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && !isMultiline) { ev.preventDefault(); commit(); }
      else if (ev.key === 'Escape') { discard(); }
    });
    if (isMultiline) {
      // Ctrl/Cmd+Enter confirma
      el.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); commit(); }
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
    ['servicio', 'producto', 'regalo', 'promocion'].forEach(function (k) {
      var o = document.createElement('option');
      o.value = k; o.textContent = kindLabel(k);
      if (k === it.kind) o.selected = true;
      sel.appendChild(o);
    });
    var busy = false;
    sel.addEventListener('change', function () {
      sel.title = kindLabel(sel.value);
      if (busy) return;
      busy = true; sel.disabled = true;
      save(it, 'kind', sel.value).then(function () { busy = false; sel.disabled = false; }, function (e) {
        busy = false; sel.disabled = false;
        flash('No se guardó: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
      }).catch(function () {});
    });
    td.appendChild(sel);
    return td;
  }

  function priceCell(it) {
    var td = document.createElement('td');
    var input = document.createElement('input');
    input.type = 'number';
    input.step = '0.01';
    var shown = it.price_cents === null || it.price_cents === undefined ? '' : (it.price_cents / 100);
    input.value = shown;
    input.dataset.orig = shown;
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); commitP(); }
      else if (ev.key === 'Escape') { input.value = input.dataset.orig; input.blur(); }
    });
    function commitP() {
      var v = input.value === '' ? null : Math.round(parseFloat(input.value) * 100);
      if (v === it.price_cents) return;
      save(it, 'price_cents', v).then(null, function (e) {
        flash('No se guardó: ' + e.message + '.', 'error');
        if (e.code === 'version_conflict' || e.status === 409) reload();
      });
    }
    td.appendChild(input);
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
    if (it.stock === null || it.stock === undefined) { td.textContent = '—'; return td; }
    td.textContent = String(it.stock);
    return td;
  }

  // Acciones: «Publicar / Nueva revisión» y «Detalle» como botones separados y
  // legibles (los recorta el CSS .cell-col con .cel, nunca pegados).
  function finalCol(it) {
    var td = document.createElement('td');
    td.className = 'cell-col';
    if (it.publish_state !== 'publicado') {
      td.appendChild(button('Publicar', function (b) {
        b.disabled = true;
        json('/api/c02/catalog/' + it.id + '/publish', 'POST', {})
          .then(function () { flash('Publicado.', 'ok'); reload(); }, function (e) {
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
      tr.appendChild(textCell(it.details, 80));
      tr.appendChild(textCell(it.public_notes, 70));
      tr.appendChild(priceCell(it));
      tr.appendChild(stockCell(it));
      tr.appendChild(stateChip(it));
      tr.appendChild(finalCol(it));
      tbody.appendChild(tr);
    });
    flash('');
  }

  function save(it, field, value) {
    var rev = Number(it.current_revision);
    return json('/api/c02/catalog/' + it.id, 'POST',
      { field: field, value: value, revision: rev }).then(reload);
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

  function fillDetail(it) {
    var pairs = [
      ['c02-f-code', it.code], ['c02-f-name', it.name], ['c02-f-details', it.details || ''],
      ['c02-f-public-notes', it.public_notes || ''],
      ['c02-f-internal-notes', it.internal_notes || ''],
      ['c02-f-currency', it.currency || 'USD'],
      ['c02-f-stock', it.stock === null || it.stock === undefined ? '' : it.stock],
      ['c02-f-valid-from', it.valid_from || ''],
      ['c02-f-valid-until', it.valid_until || ''],
      ['c02-f-duration', it.duration_min === null || it.duration_min === undefined ? '' : it.duration_min]
    ];
    pairs.forEach(function (p) {
      var el = document.getElementById(p[0]);
      if (el) el.value = p[1];
    });
    var kindSel = document.getElementById('c02-f-kind'); if (kindSel) kindSel.value = it.kind;
    var act = document.getElementById('c02-f-active'); if (act) act.checked = it.active === 1 || it.active === '1' || it.active === true;
    var sna = document.getElementById('c02-f-stock-na'); if (sna) sna.checked = it.stock_na === 1 || it.stock_na === '1' || it.stock_na === true;
    var priceIn = document.getElementById('c02-f-price'); if (priceIn) priceIn.value = it.price_cents === null || it.price_cents === undefined ? '' : (it.price_cents / 100);
    var prof = document.getElementById('c02-f-professional'); if (prof) prof.value = it.professional_id || '';
  }

  var detailForm = document.getElementById('c02-detail-form');
  if (detailForm && dlg) {
    detailForm.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var submitBtn = detailForm.querySelector('button[type="submit"]');
      if (submitBtn && submitBtn.disabled) return;
      if (submitBtn) submitBtn.disabled = true;
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
            dlg.close();
            flash('Artículo guardado.', 'ok');
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
              flash('No se guardó: ' + e.message + '.', 'error');
              if (e.code === 'version_conflict' || e.status === 409) { reload(); dlg.close(); }
            });
        })(0);
      }).catch(function (e) {
        if (submitBtn) submitBtn.disabled = false;
        flash('No se guardó: ' + e.message + '.', 'error');
      });
    });
    var cancelBtn = dlg.querySelector('.detail-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', function () { dlg.close(); });
    // Escape por defecto del <dialog> cierra sin guardar.
  }

  var newBtn = document.getElementById('c02-cat-new');
  if (newBtn) newBtn.addEventListener('click', function () { openCreate(); });

  function openCreate() {
    // Modo crear: abre el diálogo con campos vacíos y guarda un artículo nuevo.
    project = null;
    ['c02-f-code', 'c02-f-name', 'c02-f-details', 'c02-f-public-notes',
     'c02-f-internal-notes', 'c02-f-currency', 'c02-f-stock', 'c02-f-valid-from',
     'c02-f-valid-until', 'c02-f-duration', 'c02-f-price'].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.value = '';
    });
    var k = document.getElementById('c02-f-kind'); if (k) k.value = 'servicio';
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
