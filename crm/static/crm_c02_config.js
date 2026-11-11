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
  var rubroEtiqueta = el('c02-cfg-rubro-etiqueta');
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

  function buildWeek(horarios, almuerzos) {
    if (!weekBody) return;
    weekBody.innerHTML = '';
    for (var d = 0; d < 7; d++) {
      var win = horarios && horarios[String(d)];
      var alm = almuerzos && almuerzos[String(d)];
      var tr = document.createElement('tr');
      var td1 = document.createElement('td'); td1.textContent = DIAS[d];
      var td2 = document.createElement('td');
      var chk = document.createElement('input');
      chk.type = 'checkbox'; chk.className = 'c02-dia-lab';
      chk.dataset.dia = d; chk.checked = !!(win && (win[0] || win[1]));
      td2.appendChild(chk);
      var td3 = document.createElement('td');
      var inpA = document.createElement('input');
      inpA.type = 'time'; inpA.step = '60'; inpA.dataset.dia = d; inpA.dataset.lado = 'a';
      var td4 = document.createElement('td');
      var inpC = document.createElement('input');
      inpC.type = 'time'; inpC.step = '60'; inpC.dataset.dia = d; inpC.dataset.lado = 'c';
      if (win && win[0]) inpA.value = win[0];
      if (win && win[1]) inpC.value = win[1];
      td3.appendChild(inpA); td4.appendChild(inpC);
      var td5 = document.createElement('td');
      var inpA2 = document.createElement('input');
      inpA2.type = 'time'; inpA2.step = '60'; inpA2.dataset.dia = d; inpA2.dataset.lado = 'a2';
      var td6 = document.createElement('td');
      var inpC2 = document.createElement('input');
      inpC2.type = 'time'; inpC2.step = '60'; inpC2.dataset.dia = d; inpC2.dataset.lado = 'c2';
      if (alm && alm[0]) inpA2.value = alm[0];
      if (alm && alm[1]) inpC2.value = alm[1];
      td5.appendChild(inpA2); td6.appendChild(inpC2);
      tr.appendChild(td1); tr.appendChild(td2);
      tr.appendChild(td3); tr.appendChild(td4);
      tr.appendChild(td5); tr.appendChild(td6);
      weekBody.appendChild(tr);
    }
  }

  function horariosFromDom() {
    var out = {};
    var almuerzos = {};
    if (!weekBody) return { horarios: out, almuerzos: almuerzos };
    var checks = weekBody.querySelectorAll('input.c02-dia-lab');
    var labels = {};
    for (var i = 0; i < checks.length; i++) labels[checks[i].dataset.dia] = checks[i].checked;
    // Sólo entradas de hora (con data-lado): el checkbox tiene data-dia pero
    // su value ("on") no es una hora y antes contaminaba la lectura.
    var inputs = weekBody.querySelectorAll('input[data-dia][data-lado]');
    for (var j = 0; j < inputs.length; j++) {
      var inp = inputs[j];
      var d = inp.dataset.dia;
      if (labels[d] === false) continue;
      if (inp.validity && inp.validity.badInput) {
        throw new Error('El día ' + DIAS[Number(d)] + ' tiene una hora no válida');
      }
      var lado = inp.dataset.lado;
      var destino = (lado === 'a2' || lado === 'c2') ? almuerzos : out;
      if (!destino[d]) destino[d] = [];
      var idx = (lado === 'a' || lado === 'a2') ? 0 : 1;
      var val = inp.value || null;
      // 00:00 = casilla sin usar (el reloj queda en 00:00 al limpiar).
      if (val === '00:00' && (lado === 'a2' || lado === 'c2')) val = null;
      destino[d][idx] = val;
    }
    Object.keys(out).forEach(function (d) {
      var w = out[d];
      if (!w[0] && !w[1]) { delete out[d]; return; }
      if (!w[0] || !w[1]) throw new Error('El día ' + DIAS[Number(d)] + ' debe tener apertura y cierre');
      if (w[0] >= w[1]) throw new Error('En ' + DIAS[Number(d)] + ' la apertura debe ser anterior al cierre');
    });
    Object.keys(almuerzos).forEach(function (d) {
      var w = almuerzos[d];
      if (!w[0] && !w[1]) { delete almuerzos[d]; return; }
      if (!w[0] || !w[1]) throw new Error('El almuerzo del ' + DIAS[Number(d)] + ' debe tener inicio y fin');
      if (w[0] >= w[1]) throw new Error('En el almuerzo del ' + DIAS[Number(d)] + ' el inicio debe ser anterior al fin');
    });
    return { horarios: out, almuerzos: almuerzos };
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
      var alm = document.createElement('span');
      alm.className = 'muted tiny';
      alm.textContent = ' Almuerzo: ';
      var inpA = document.createElement('input');
      inpA.type = 'time'; inpA.step = '60'; inpA.value = esp.almuerzo_inicio || '';
      inpA.setAttribute('aria-label', 'Almuerzo desde de ' + esp.nombre);
      inpA.addEventListener('change', function () {
        // 00:00 = casilla sin usar.
        esp.almuerzo_inicio = (inpA.value === '00:00') ? null : (inpA.value || null);
        ok('Cambios pendientes de guardar.');
      });
      var inpC = document.createElement('input');
      inpC.type = 'time'; inpC.step = '60'; inpC.value = esp.almuerzo_fin || '';
      inpC.setAttribute('aria-label', 'Almuerzo hasta de ' + esp.nombre);
      inpC.addEventListener('change', function () {
        esp.almuerzo_fin = (inpC.value === '00:00') ? null : (inpC.value || null);
        ok('Cambios pendientes de guardar.');
      });
      alm.appendChild(inpA); alm.appendChild(document.createTextNode('–')); alm.appendChild(inpC);
      lab.appendChild(txt); lab.appendChild(chk); lab.appendChild(alm);
      espBox.appendChild(lab);
      // Horario semanal por doctor, visible debajo de su nombre:
      // palomita por día (sin marcar = no trabaja ese día),
      // horas vacías = sigue el horario del negocio.
      if (!esp.horario || typeof esp.horario !== 'object') esp.horario = {};
      var grid = document.createElement('div');
      grid.className = 'c02-esp-horario';
      for (var d = 0; d < 7; d++) (function (dd) {
        var fila = document.createElement('div');
        var on = document.createElement('input');
        on.type = 'checkbox';
        var cur = esp.horario[String(dd)];
        on.checked = !!cur || cur instanceof Array;
        var nom = document.createElement('span');
        nom.className = 'muted tiny';
        nom.textContent = ' ' + DIAS[dd] + ' ';
        var ia = document.createElement('input');
        ia.type = 'time'; ia.step = '60';
        var ic = document.createElement('input');
        ic.type = 'time'; ic.step = '60';
        if (cur instanceof Array && cur[0]) ia.value = cur[0];
        if (cur instanceof Array && cur[1]) ic.value = cur[1];
        var leer = function () {
          if (!on.checked) { delete esp.horario[String(dd)]; return; }
          var a = (ia.value === '00:00') ? '' : ia.value;
          var c = (ic.value === '00:00') ? '' : ic.value;
          if (!a && !c) { esp.horario[String(dd)] = []; return; }
          esp.horario[String(dd)] = [a || null, c || null];
        };
        var cambio = function () {
          leer();
          ok('Cambios pendientes de guardar.');
        };
        on.addEventListener('change', cambio);
        ia.addEventListener('change', cambio);
        ic.addEventListener('change', cambio);
        fila.appendChild(on); fila.appendChild(nom);
        fila.appendChild(ia); fila.appendChild(document.createTextNode('–')); fila.appendChild(ic);
        grid.appendChild(fila);
      })(d);
      espBox.appendChild(grid);
    });
  }

  function guardar() {
    if (!saveBtn) return;
    saveBtn.disabled = true;
    if (msgEl) msgEl.textContent = 'Guardando…';
    var horarios;
    var almuerzos;
    try {
      var semana = horariosFromDom();
      horarios = semana.horarios;
      almuerzos = semana.almuerzos;
      // Horario propio por doctor: día marcado con horas exige inicio < fin.
      especialistas.forEach(function (esp) {
        var h = esp.horario || {};
        Object.keys(h).forEach(function (d) {
          var w = h[d];
          if (w instanceof Array && w.length === 0) return;
          if (!w || w.length !== 2 || !w[0] || !w[1]) {
            throw new Error('Horario de ' + esp.nombre + ' el ' + DIAS[Number(d)] + ': apertura y cierre (HH:MM) o casilla vacía');
          }
          if (w[0] >= w[1]) {
            throw new Error('Horario de ' + esp.nombre + ' el ' + DIAS[Number(d)] + ': la apertura debe ser anterior al cierre');
          }
        });
      });
    }
    catch (e) { saveBtn.disabled = false; fail(e); return; }

    var claves = [
      ['negocio_nombre', nombre && nombre.value.trim()],
      ['negocio_rubro', rubro && rubro.value.trim()],
      ['negocio_rubro_etiqueta', rubroEtiqueta && rubroEtiqueta.value.trim()],
      ['negocio_zona', zona && zona.value.trim()],
      ['negocio_moneda', moneda && moneda.value.trim().toUpperCase()],
      ['saludo', saludo && saludo.value],
      ['mensaje_fuera', fuera && fuera.value],
      ['negocio_horarios', JSON.stringify(horarios)],
      ['negocio_almuerzos', JSON.stringify(almuerzos)],
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
    if (rubro) rubro.value = s.negocio_rubro || p.rubro || '';
    if (rubroEtiqueta) rubroEtiqueta.value = s.negocio_rubro_etiqueta || p.rubro_etiqueta || '';
    if (zona) zona.value = s.negocio_zona || p.zona || '';
    if (moneda) moneda.value = s.negocio_moneda || p.moneda || '';
    if (saludo) saludo.value = s.saludo || '';
    if (fuera) fuera.value = s.mensaje_fuera || '';
    var horarios = p.horarios || {};
    if (typeof s.negocio_horarios === 'string' && s.negocio_horarios) {
      try { var parsed = JSON.parse(s.negocio_horarios); if (parsed && typeof parsed === 'object') horarios = parsed; } catch (e) {}
    }
    var almuerzos = {};
    if (typeof s.negocio_almuerzos === 'string' && s.negocio_almuerzos) {
      try { var parsedA = JSON.parse(s.negocio_almuerzos); if (parsedA && typeof parsedA === 'object') almuerzos = parsedA; } catch (e) {}
    }
    buildWeek(horarios, almuerzos);
    excs = (s.negocio_excepciones && typeof s.negocio_excepciones === 'object')
      ? s.negocio_excepciones : {};
    renderExcs();
    especialistas = (s.negocio_especialistas || []).map(function (e) { return { id: e.id, nombre: e.nombre, especialidad: e.especialidad || '', activo: !!e.activo, almuerzo_inicio: e.almuerzo_inicio || null, almuerzo_fin: e.almuerzo_fin || null, horario: (e.horario && typeof e.horario === 'object') ? e.horario : {} }; });
    renderEspecialistas();
    if (msgEl) msgEl.textContent = '';
  }).catch(function (e) {
    if (msgEl) msgEl.textContent = 'Error al cargar: ' + e.message;
  });
})();
