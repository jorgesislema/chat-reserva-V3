/* C02 — Configuración de IA y negocio (R4, §10.2). Sin scripts inline (CSP
   estricta). Edita el perfil del negocio (nombre, zona, moneda), el saludo y
   mensajes del bot, el horario semanal OPERATIVO (día -> apertura/cierre), las
   fechas cerradas/excepciones y la disponibilidad de especialistas. Todo se
   persiste en crm_settings vía POST /api/c02/config y lo aplican el panel y el
   canal con la MISMA regla (business_config.effective_profile/check_window).
   Los días usan la convención de Python weekday: 0=lunes ... 6=domingo. */
(function () {
  'use strict';

  var app = document.getElementById('c02-config-app');
  if (!app) return;
  var csrf = app.getAttribute('data-csrf');
  var DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
  var estado = { guardado: false };

  var el = function (id) { return document.getElementById(id); };
  var nombre = el('c02-cfg-nombre');
  var rubro = el('c02-cfg-rubro');
  var zona = el('c02-cfg-zona');
  var moneda = el('c02-cfg-moneda');
  var saludo = el('c02-cfg-saludo');
  var fuera = el('c02-cfg-fuera');
  var weekBody = document.querySelector('#c02-cfg-week tbody');
  var excFecha = el('c02-cfg-exc-fecha');
  var excEstado = el('c02-cfg-exc-estado');
  var excA = el('c02-cfg-exc-a');
  var excC = el('c02-cfg-exc-c');
  var excAdd = el('c02-cfg-exc-add');
  var excList = el('c02-cfg-exc-list');
  var excBody = document.querySelector('#c02-cfg-exc-list tbody');
  var excEmpty = el('c02-cfg-exc-empty');
  var espBox = el('c02-cfg-especialistas');
  var espEmpty = el('c02-cfg-esp-empty');
  var saveBtn = el('c02-cfg-save');
  var msgEl = el('c02-cfg-msg');
  var excs = {};          // fecha -> {estado, horario?}
  var especialistas = []; // [{id, nombre, activo}]

  function json(url, method, body) {
    return fetch(url, {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) {
          throw new Error((j && (j.error && j.error.message || j.message)) || 'Error de servidor');
        }
        return j;
      });
    });
  }

  function ok(msg) {
    estado.guardado = true;
    if (msgEl) { msgEl.textContent = msg; msgEl.className = 'muted tiny ok'; }
    if (saveBtn) saveBtn.disabled = false;
  }
  function fail(e) {
    estado.guardado = false;
    if (msgEl) { msgEl.textContent = 'Error: ' + (e && e.message || e); msgEl.className = 'muted tiny err'; }
    if (saveBtn) saveBtn.disabled = false;
  }

  function buildWeek(horarios) {
    if (!weekBody) return;
    weekBody.innerHTML = '';
    for (var d = 0; d < 7; d++) {
      var win = horarios && horarios[String(d)];
      var tr = document.createElement('tr');
      var td1 = document.createElement('td'); td1.textContent = DIAS[d];
      var td2 = document.createElement('td');
      var inpA = document.createElement('input');
      inpA.type = 'time'; inpA.step = '1800'; inpA.dataset.dia = d; inpA.dataset.lado = 'a';
      var inpC = document.createElement('input');
      inpC.type = 'time'; inpC.step = '1800'; inpC.dataset.dia = d; inpC.dataset.lado = 'c';
      if (win && win[0]) inpA.value = win[0];
      if (win && win[1]) inpC.value = win[1];
      var td3 = document.createElement('td');
      td2.appendChild(inpA); td3.appendChild(inpC);
      tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3);
      weekBody.appendChild(tr);
    }
  }

  function horariosFromDom() {
    var out = {};
    if (!weekBody) return out;
    var inputs = weekBody.querySelectorAll('input[data-dia]');
    for (var i = 0; i < inputs.length; i++) {
      var inp = inputs[i];
      var d = inp.dataset.dia;
      if (!out[d]) out[d] = [];
      out[d][inp.dataset.lado === 'a' ? 0 : 1] = inp.value || null;
    }
    Object.keys(out).forEach(function (d) {
      var w = out[d];
      if (!w[0] && !w[1]) { delete out[d]; return; }
      if (!w[0] || !w[1]) throw new Error('El día ' + DIAS[Number(d)] + ' debe tener apertura y cierre');
      if (w[0] >= w[1]) throw new Error('En ' + DIAS[Number(d)] + ' la apertura debe ser anterior al cierre');
    });
    return out;
  }

  function renderExcs() {
    if (!excBody) return;
    excBody.innerHTML = '';
    var fechas = Object.keys(excs).sort();
    excEmpty.hidden = fechas.length > 0;
    excList.hidden = fechas.length === 0;
    fechas.forEach(function (f) {
      var e = excs[f];
      var tr = document.createElement('tr');
      var tdF = document.createElement('td'); tdF.textContent = f;
      var tdE = document.createElement('td');
      tdE.textContent = e.estado === 'cerrado' ? 'Cerrado todo el día' : 'Horario especial';
      var tdH = document.createElement('td');
      tdH.textContent = (e.horario && e.horario[0] && e.horario[1])
        ? e.horario[0] + ' a ' + e.horario[1] : '—';
      var tdX = document.createElement('td');
      var btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'button secondary tiny';
      btn.textContent = 'Quitar';
      btn.addEventListener('click', function () {
        delete excs[f];
        renderExcs();
        ok('Cambios pendientes de guardar.');
      });
      tdX.appendChild(btn);
      tr.appendChild(tdF); tr.appendChild(tdE); tr.appendChild(tdH); tr.appendChild(tdX);
      excBody.appendChild(tr);
    });
  }

  function renderEspecialistas() {
    if (!espBox) return;
    espBox.innerHTML = '';
    espEmpty.hidden = especialistas.length > 0;
    especialistas.forEach(function (esp) {
      var lab = document.createElement('label');
      lab.className = 'c02-esp-item';
      var chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = !!esp.activo;
      chk.dataset.id = esp.id;
      chk.addEventListener('change', function () {
        esp.activo = chk.checked;
        ok('Cambios pendientes de guardar.');
      });
      var txt = document.createElement('span');
      txt.textContent = esp.nombre + (esp.especialidad ? ' (' + esp.especialidad + ')' : '');
      lab.appendChild(chk); lab.appendChild(txt);
      espBox.appendChild(lab);
    });
  }

  function guardar() {
    if (!saveBtn) return;
    saveBtn.disabled = true;
    if (msgEl) msgEl.textContent = 'Guardando…';
    var horarios;
    try { horarios = horariosFromDom(); }
    catch (e) { saveBtn.disabled = false; fail(e); return; }

    var claves = [
      ['negocio_nombre', nombre && nombre.value.trim()],
      ['negocio_zona', zona && zona.value.trim()],
      ['negocio_moneda', moneda && moneda.value.trim().toUpperCase()],
      ['saludo', saludo && saludo.value],
      ['mensaje_fuera', fuera && fuera.value],
      ['negocio_horarios', JSON.stringify(horarios)],
      ['negocio_excepciones', JSON.stringify(excs)],
      ['negocio_especialistas', JSON.stringify(especialistas)]
    ];
    claves = claves.filter(function (kv) { return kv[1] !== null && kv[1] !== undefined; });
    claves.reduce(function (p, kv) {
      return p.then(function () {
        return json('/api/c02/config', 'POST', { key: kv[0], value: kv[1] });
      });
    }, Promise.resolve()).then(function () {
      ok('Guardado.');
    }, fail);
  }

  if (saveBtn) saveBtn.addEventListener('click', guardar);
  if (excAdd) excAdd.addEventListener('click', function () {
    var f = excFecha && excFecha.value;
    if (!f) { fail(new Error('Indique una fecha para la excepción')); return; }
    if (excs[f]) { fail(new Error('Esa fecha ya tiene una excepción; quítela para cambiarla')); return; }
    var est = excEstado && excEstado.value;
    var item = { estado: est === 'horario' ? 'horario' : 'cerrado' };
    if (item.estado === 'horario') {
      if (!excA.value || !excC.value || excA.value >= excC.value) {
        fail(new Error('Para horario especial indique apertura y cierre válidos'));
        return;
      }
      item.horario = [excA.value, excC.value];
    }
    excs[f] = item;
    if (excFecha) excFecha.value = '';
    renderExcs();
    ok('Cambios pendientes de guardar.');
  });

  json('/api/c02/config').then(function (j) {
    var p = j.perfil || {};
    var s = j.settings || {};
    if (nombre) nombre.value = s.negocio_nombre || p.nombre || '';
    if (rubro) rubro.value = p.rubro_etiqueta || p.rubro || '';
    if (zona) zona.value = s.negocio_zona || p.zona || '';
    if (moneda) moneda.value = s.negocio_moneda || p.moneda || '';
    if (saludo) saludo.value = s.saludo || '';
    if (fuera) fuera.value = s.mensaje_fuera || '';
    var horarios = p.horarios || {};
    if (typeof s.negocio_horarios === 'string' && s.negocio_horarios) {
      try { var parsed = JSON.parse(s.negocio_horarios); if (parsed && typeof parsed === 'object') horarios = parsed; } catch (e) {}
    }
    buildWeek(horarios);
    excs = (s.negocio_excepciones && typeof s.negocio_excepciones === 'object')
      ? s.negocio_excepciones : {};
    renderExcs();
    especialistas = (s.negocio_especialistas || []).map(function (e) { return { id: e.id, nombre: e.nombre, especialidad: e.especialidad || '', activo: !!e.activo }; });
    renderEspecialistas();
    if (msgEl) msgEl.textContent = '';
  }).catch(function (e) {
    if (msgEl) msgEl.textContent = 'Error al cargar: ' + e.message;
  });
})();
