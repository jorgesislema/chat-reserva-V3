/* Agenda P02 — módulo local, sin dependencias ni código inline.
   Lee la zona del negocio del servidor; el navegador nunca decide la zona. */
(function () {
  'use strict';

  var app = document.getElementById('agenda-app');
  if (!app) { return; }

  var tz = app.getAttribute('data-timezone');
  var role = app.getAttribute('data-role');
  var today = app.getAttribute('data-today');
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrf = csrfMeta ? csrfMeta.getAttribute('content') : '';
  var DEFAULT_MIN_HOUR = 7;
  var DEFAULT_MAX_HOUR = 20;
  var SLOT_PX = 56;
  var grid = {
    minHour: DEFAULT_MIN_HOUR,
    maxHour: DEFAULT_MAX_HOUR,
    height: (DEFAULT_MAX_HOUR - DEFAULT_MIN_HOUR) * SLOT_PX
  };
  var loadToken = 0;
  var VIEW_KEY = 'crm.agenda.view';

  var surface = app.querySelector('[data-surface]');
  var statusEl = app.querySelector('[data-status]');
  var periodEl = app.querySelector('[data-period]');
  var periodLongEl = app.querySelector('[data-period-long]');

  var state = {
    view: null,
    date: today,
    professional: '',
    status: '',
    cancelled: false,
    data: null,
    returnFocus: null,
    formMode: 'create',
    formId: null,
    formVersion: null,
    formStatus: null,
    detail: null
  };

  var proIndex = {};
  var DOW = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'];
  var DOW_LONG = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
  var MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
    'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var SYNC_LABELS = {
    pending: 'Pendiente de sincronizar',
    synced: 'Sincronizada con Google',
    error: 'Error de sincronización reintentable',
    review: 'Revisión pendiente: conflicto con Google'
  };
  var STATUS_LABELS = {
    pending: 'Pendiente', confirmed: 'Confirmada', attended: 'Atendida',
    no_show: 'No asistió', cancelled: 'Cancelada',
    active: 'Activa'
  };
  var ACTION_LABELS = {
    confirm: 'Confirmar', reprogram: 'Reprogramar', cancel: 'Cancelar',
    attend: 'Marcar atendida', no_show: 'No asistió'
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function defaultView() {
    return window.matchMedia && window.matchMedia('(max-width: 700px)').matches ? 'day' : 'week';
  }

  function storedView() {
    try {
      var value = window.sessionStorage.getItem(VIEW_KEY);
      return (value === 'day' || value === 'week' || value === 'month') ? value : null;
    } catch (e) { return null; }
  }

  function saveView(view) {
    try { window.sessionStorage.setItem(VIEW_KEY, view); } catch (e) { /* almacenamiento no disponible */ }
  }

  function parseDate(value) {
    var parts = String(value).split('-').map(Number);
    return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  }

  function isoDate(date) {
    return date.getUTCFullYear() + '-' + pad(date.getUTCMonth() + 1) + '-' + pad(date.getUTCDate());
  }

  function shiftDays(value, delta) {
    var d = parseDate(value);
    d.setUTCDate(d.getUTCDate() + delta);
    return isoDate(d);
  }

  function shiftMonths(value, delta) {
    var p = value.split('-').map(Number);
    var d = new Date(Date.UTC(p[0], p[1] - 1 + delta, 1));
    var last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
    d.setUTCDate(Math.min(p[2], last));
    return isoDate(d);
  }

  function partsInZone(iso) {
    var formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short'
    });
    var out = {};
    formatter.formatToParts(new Date(iso)).forEach(function (part) {
      if (part.type !== 'literal') { out[part.type] = part.value; }
    });
    var hour = parseInt(out.hour, 10);
    if (hour === 24) { hour = 0; }
    return {
      date: out.year + '-' + out.month + '-' + out.day,
      hour: hour,
      minute: parseInt(out.minute, 10),
      weekday: out.weekday
    };
  }

  function minutesOfDay(iso) {
    var p = partsInZone(iso);
    return p.hour * 60 + p.minute;
  }

  function hhmm(minutes) {
    var m = Math.max(0, Math.min(1440, minutes));
    return pad(Math.floor(m / 60)) + ':' + pad(m % 60);
  }

  function dateLabel(dateStr) {
    var d = parseDate(dateStr);
    return DOW_LONG[(d.getUTCDay() + 6) % 7] + ' ' + d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()];
  }

  function setStatus(message, isError) {
    if (!statusEl) { return; }
    statusEl.textContent = message || '';
    statusEl.className = 'agenda-status' + (isError ? ' error' : '');
  }

  function jsonFetch(url, options) {
    options = options || {};
    options.credentials = 'same-origin';
    options.headers = options.headers || {};
    if (options.method && options.method !== 'GET') {
      options.headers['X-CSRF-Token'] = csrf;
      options.headers['Content-Type'] = 'application/json';
    }
    return fetch(url, options).then(function (response) {
      return response.text().then(function (body) {
        var payload = null;
        try { payload = body ? JSON.parse(body) : null; } catch (e) { payload = null; }
        if (!response.ok) {
          var error = payload && payload.error ? payload.error : { code: 'http_' + response.status, message: 'Error inesperado (' + response.status + ')' };
          if (response.status === 401) {
            error.message = 'Sesión vencida. Recargue la página e ingrese de nuevo.';
          }
          var failure = new Error(error.message);
          failure.code = error.code;
          failure.status = response.status;
          throw failure;
        }
        return payload;
      });
    });
  }

  function professionalOf(id) { return proIndex[id] || { index: 0, name: '', active: true }; }

  function proClass(id) { return 'pro-' + (professionalOf(id).index % 6); }

  function buildQuery() {
    var params = new URLSearchParams();
    params.set('view', state.view);
    params.set('date', state.date);
    if (state.professional) { params.set('professional', state.professional); }
    if (state.status) { params.set('status', state.status); }
    if (state.cancelled) { params.set('cancelled', '1'); }
    return '/api/agenda?' + params.toString();
  }

  function load() {
    var ticket = ++loadToken;
    setStatus('Cargando agenda…');
    surface.replaceChildren(el('div', 'agenda-loading', 'Cargando agenda…'));
    return jsonFetch(buildQuery()).then(function (data) {
      if (ticket !== loadToken) { return; }  // respuesta antigua: no dibujar
      state.data = data;
      proIndex = {};
      (data.professionals || []).forEach(function (pro, index) {
        proIndex[pro.id] = { index: index, name: pro.name, active: !!pro.active };
      });
      if (periodEl) { periodEl.textContent = data.label; }
      if (periodLongEl) { periodLongEl.textContent = data.label; }
      render();
      setStatus('');
    }).catch(function (error) {
      if (ticket !== loadToken) { return; }
      surface.replaceChildren();
      var box = el('div', 'agenda-error');
      box.appendChild(el('p', null, error.message));
      var retry = el('button', 'secondary', 'Reintentar');
      retry.type = 'button';
      retry.addEventListener('click', load);
      box.appendChild(retry);
      surface.appendChild(box);
      setStatus(error.message, true);
    });
  }

  function render() {
    surface.replaceChildren();
    var data = state.data;
    if (!data) { return; }
    if (!data.appointments.length) {
      surface.appendChild(el('p', 'agenda-empty', 'No hay citas en este período. Haga clic en un hueco para crear una.'));
    }
    if (state.view === 'day') { renderDay(); }
    else if (state.view === 'week') { renderWeek(); }
    else { renderMonth(); }
  }

  function laneProfessionals() {
    var data = state.data;
    var professionals = data.professionals || [];
    if (state.professional) {
      var found = professionals.filter(function (p) { return String(p.id) === String(state.professional); });
      if (found.length) { return found; }
      return [{ id: Number(state.professional), name: 'Profesional', active: false }];
    }
    var withAppts = {};
    data.appointments.forEach(function (a) { withAppts[a.professional_id] = true; });
    // Todos: activos + cualquier inactivo que tenga citas visibles (no ocultar reservas).
    var lanes = professionals.filter(function (p) { return p.active || withAppts[p.id]; });
    return lanes.length ? lanes : [{ id: null, name: 'Agenda', active: false }];
  }

  function segmentForDay(appt, day) {
    var start = new Date(appt.start_utc).getTime();
    var end = new Date(appt.end_utc).getTime();
    var dStart = new Date(day.start_utc).getTime();
    var dEnd = new Date(day.end_utc).getTime();
    var s = Math.max(start, dStart);
    var e = Math.min(end, dEnd);
    if (e <= s) { return null; }
    var startMin = s === dStart ? 0 : minutesOfDay(new Date(s).toISOString());
    var endMin = e === dEnd ? 1440 : minutesOfDay(new Date(e).toISOString());
    if (endMin <= startMin) { endMin = startMin + 30; }
    return {
      start: startMin,
      end: Math.min(1440, endMin),
      startsBefore: start < dStart,
      endsAfter: end > dEnd
    };
  }

  function computeGrid(segments) {
    var minMinute = DEFAULT_MIN_HOUR * 60;
    var maxMinute = DEFAULT_MAX_HOUR * 60;
    segments.forEach(function (segment) {
      minMinute = Math.min(minMinute, segment.start);
      maxMinute = Math.max(maxMinute, segment.end);
    });
    minMinute = Math.max(0, Math.min(23 * 60, minMinute));
    maxMinute = Math.max(minMinute + 60, Math.min(24 * 60, maxMinute));
    grid.minHour = Math.floor(minMinute / 60);
    grid.maxHour = Math.ceil(maxMinute / 60);
    grid.height = (grid.maxHour - grid.minHour) * SLOT_PX;
  }

  function layout(items) {
    var lanes = [];
    items.sort(function (a, b) { return a.start - b.start; }).forEach(function (item) {
      var lane = 0;
      while (lane < lanes.length && lanes[lane] > item.start) { lane += 1; }
      lanes[lane] = item.end;
      item.lane = lane;
    });
    return Math.max(1, lanes.length);
  }

  function appointmentButton(appt, segment, laneCount) {
    var pro = professionalOf(appt.professional_id);
    var button = el('button', 'appt ' + proClass(appt.professional_id) + ' ' + appt.operational_status);
    button.type = 'button';
    button.setAttribute('data-open', appt.id);
    var continuation = (segment.startsBefore ? ' · continúa desde antes' : '') +
      (segment.endsAfter ? ' · continúa después' : '');
    button.setAttribute('aria-label', appt.title + ', ' + appt.start_time + '–' + appt.end_time + ', ' +
      pro.name + ', ' + appt.status_label + continuation +
      (appt.has_notes ? ', con observaciones' : ''));
    if (laneCount > 1) { button.classList.add('lane-compact'); }
    if (laneCount > 2) { button.classList.add('lane-tight'); }
    button.title = appt.title + ' · ' + appt.start_time + '–' + appt.end_time +
      ' · ' + pro.name + ' · ' + appt.status_label + continuation;
    var top = ((segment.start - grid.minHour * 60) / 60) * SLOT_PX;
    var height = Math.max(26, ((segment.end - segment.start) / 60) * SLOT_PX);
    if (top < 0) { height += top; top = 0; }
    if (top + height > grid.height) { height = Math.max(26, grid.height - top); }
    button.style.top = top + 'px';
    button.style.height = height + 'px';
    if (laneCount > 1) {
      button.style.left = 'calc(' + (segment.lane / laneCount) * 100 + '% + 2px)';
      button.style.width = 'calc(' + (100 / laneCount) + '% - 4px)';
    }
    button.appendChild(el('strong', null, appt.title));
    // Con carriles estrechos el nombre del profesional abreviado mantiene la
    // cita legible; el detalle completo está en el título y al abrir la ficha.
    var nombrePro = String(pro.name || '').split(' ')[0] || '';
    if (laneCount > 2) {
      button.appendChild(el('small', null,
        (segment.startsBefore ? '↪ ' : '') + appt.start_time + '–' + appt.end_time +
        (segment.endsAfter ? ' ↦' : '')));
      button.appendChild(el('small', 'pro-short', nombrePro));
    } else {
      button.appendChild(el('small', null,
        (segment.startsBefore ? '↪ ' : '') + appt.start_time + '–' + appt.end_time +
        (segment.endsAfter ? ' ↦' : '') + ' · ' + nombrePro));
    }
    var meta = el('span', 'appt-meta');
    meta.appendChild(el('span', 'status-badge ' + appt.operational_status, appt.status_label));
    if (appt.pending_closure) { meta.appendChild(el('span', 'badge warn', 'Pendiente de cierre')); }
    if (appt.sync_status === 'error') { meta.appendChild(el('span', 'badge warn', 'Google: error')); }
    if (appt.sync_status === 'review') { meta.appendChild(el('span', 'badge warn', 'Google: revisión')); }
    if (appt.has_notes) { meta.appendChild(el('span', 'badge', 'Observaciones')); }
    button.appendChild(meta);
    return button;
  }

  function hourCells(container, dateStr, professionalId, onPick, enabled) {
    for (var hour = grid.minHour; hour < grid.maxHour; hour += 1) {
      var slot = el('div', 'hour-slot');
      slot.style.top = ((hour - grid.minHour) * SLOT_PX) + 'px';
      slot.style.height = SLOT_PX + 'px';
      if (enabled === false) {
        slot.setAttribute('aria-hidden', 'true');
        container.appendChild(slot);
        continue;
      }
      var button = el('button');
      button.type = 'button';
      button.setAttribute('data-cell', dateStr);
      button.setAttribute('data-hour', hour);
      if (professionalId !== null && professionalId !== undefined) {
        button.setAttribute('data-professional', professionalId);
      }
      button.setAttribute('aria-label', 'Nueva cita el ' + dateLabel(dateStr) + ' a las ' + pad(hour) + ':00');
      button.addEventListener('click', function (event) {
        onPick(event.currentTarget);
      });
      slot.appendChild(button);
      container.appendChild(slot);
    }
  }

  function timeAxis() {
    var axis = el('div', 'axis');
    axis.style.height = grid.height + 'px';
    for (var hour = grid.minHour; hour <= grid.maxHour; hour += 1) {
      var tick = el('span', 'tick', pad(hour) + ':00');
      tick.style.top = ((hour - grid.minHour) * SLOT_PX) + 'px';
      axis.appendChild(tick);
    }
    return axis;
  }

  function renderDay() {
    var day = state.data.days[0];
    var lanes = laneProfessionals();
    var byLane = lanes.map(function (pro) {
      return state.data.appointments
        .filter(function (a) { return !pro.id || a.professional_id === pro.id; })
        .map(function (a) {
          var seg = segmentForDay(a, day);
          return seg ? { appt: a, start: seg.start, end: seg.end,
                         startsBefore: seg.startsBefore, endsAfter: seg.endsAfter } : null;
        })
        .filter(Boolean);
    });
    computeGrid([].concat.apply([], byLane));

    var wrap = el('div', 'day-wrap');
    wrap.style.setProperty('--lanes', lanes.length);

    wrap.appendChild(el('div', 'day-head time-head', 'Hora'));
    lanes.forEach(function (pro) {
      var head = el('div', 'day-head');
      head.appendChild(el('span', 'pro-dot ' + (pro.id ? proClass(pro.id) : '')));
      head.appendChild(document.createTextNode(pro.name + (!pro.active ? ' · inactivo' : '')));
      wrap.appendChild(head);
    });
    wrap.appendChild(timeAxis());

    lanes.forEach(function (pro, index) {
      var lane = el('div', 'day-lane');
      lane.style.height = grid.height + 'px';
      var enabled = pro.id !== null && pro.id !== undefined && !!pro.active;
      hourCells(lane, day.date, pro.id, openCreateFromCell, enabled);
      var segments = byLane[index];
      var laneCount = layout(segments);
      segments.forEach(function (seg) {
        lane.appendChild(appointmentButton(seg.appt, seg, laneCount));
      });
      wrap.appendChild(lane);
    });
    surface.appendChild(wrap);
  }

  function renderWeek() {
    var data = state.data;
    var allSegments = [];
    var byDay = data.days.map(function (day) {
      var segments = data.appointments.map(function (appt) {
        var seg = segmentForDay(appt, day);
        return seg ? { appt: appt, start: seg.start, end: seg.end,
                       startsBefore: seg.startsBefore, endsAfter: seg.endsAfter } : null;
      }).filter(Boolean);
      allSegments = allSegments.concat(segments);
      return segments;
    });
    computeGrid(allSegments);
    var canCreate = true;
    if (state.professional) {
      canCreate = professionalOf(state.professional).active !== false;
    }

    var wrap = el('div', 'week-wrap');
    wrap.appendChild(el('div', 'day-head time-head', 'Hora'));
    data.days.forEach(function (day) {
      var head = el('div', 'week-head' + (day.date === today ? ' today' : ''));
      var d = parseDate(day.date);
      head.appendChild(el('strong', null, DOW[(d.getUTCDay() + 6) % 7]));
      head.appendChild(el('span', null, d.getUTCDate() + ' ' + MONTHS[d.getUTCMonth()].slice(0, 3)));
      wrap.appendChild(head);
    });
    wrap.appendChild(timeAxis());
    data.days.forEach(function (day, dayIndex) {
      var column = el('div', 'week-day' + (day.date === today ? ' today' : ''));
      var body = el('div', 'week-body');
      body.style.height = grid.height + 'px';
      hourCells(body, day.date, state.professional || null, openCreateFromCell, canCreate);
      var segments = byDay[dayIndex];
      var laneCount = layout(segments);
      segments.forEach(function (seg) {
        body.appendChild(appointmentButton(seg.appt, seg, laneCount));
      });
      column.appendChild(body);
      wrap.appendChild(column);
    });
    surface.appendChild(wrap);
  }

  function renderMonth() {
    var data = state.data;
    var selectedMonth = state.date.slice(0, 7);
    var wrap = el('div', 'month-wrap');
    DOW.forEach(function (day) { wrap.appendChild(el('div', 'month-dow', day)); });
    data.days.forEach(function (day) {
      var cell = el('div', 'month-cell');
      if (day.date.slice(0, 7) !== selectedMonth) { cell.classList.add('other'); }
      if (day.date === today) { cell.classList.add('today'); }
      var d = parseDate(day.date);
      var dayButton = el('button', 'day-number', d.getUTCDate());
      dayButton.type = 'button';
      dayButton.setAttribute('data-day', day.date);
      dayButton.setAttribute('aria-label', 'Nueva cita el ' + dateLabel(day.date));
      dayButton.addEventListener('click', function () { openCreateForDay(day.date); });
      cell.appendChild(dayButton);
      var entries = data.appointments.map(function (appt) {
        var seg = segmentForDay(appt, day);
        return seg ? { appt: appt, seg: seg } : null;
      }).filter(Boolean).sort(function (a, b) { return a.seg.start - b.seg.start; });
      entries.slice(0, 2).forEach(function (entry) {
        var appt = entry.appt;
        var seg = entry.seg;
        var chip = el('button', 'month-chip ' + proClass(appt.professional_id) + ' ' +
          appt.operational_status + (seg.startsBefore ? ' continuation-start' : '') +
          (seg.endsAfter ? ' continuation-end' : ''));
        chip.type = 'button';
        chip.setAttribute('data-open', appt.id);
        var proName = professionalOf(appt.professional_id).name || '';
        var firstName = proName.split(' ')[0];
        var continuation = (seg.startsBefore ? 'continúa desde antes; ' : '') +
          (seg.endsAfter ? 'continúa al día siguiente; ' : '');
        chip.setAttribute('aria-label', continuation + appt.start_time + ' ' + appt.title + ', ' +
          proName + ', ' + appt.status_label);
        var prefix = seg.startsBefore ? '↪ ' : '';
        var suffix = seg.endsAfter ? ' ↦' : '';
        chip.appendChild(el('span', 'pro-dot ' + proClass(appt.professional_id)));
        chip.appendChild(el('span', 'chip-text', prefix + appt.start_time + ' ' + firstName + ' · ' + appt.title + suffix));
        chip.appendChild(el('span', 'chip-status', appt.status_label));
        cell.appendChild(chip);
      });
      if (entries.length > 2) {
        var more = el('button', 'month-more', 'Ver más (' + (entries.length - 2) + ')');
        more.type = 'button';
        more.addEventListener('click', function () {
          state.view = 'day';
          state.date = day.date;
          saveView('day');
          syncViewButtons();
          load();
        });
        cell.appendChild(more);
      }
      wrap.appendChild(cell);
    });
    surface.appendChild(wrap);
  }

  function syncViewButtons() {
    app.querySelectorAll('[data-view]').forEach(function (button) {
      button.setAttribute('aria-pressed', button.getAttribute('data-view') === state.view ? 'true' : 'false');
    });
  }

  function openCreateFromCell(button) {
    var dateStr = button.getAttribute('data-cell');
    var hour = parseInt(button.getAttribute('data-hour'), 10);
    var professionalId = button.getAttribute('data-professional') || '';
    var endDate = dateStr;
    var endTime = pad(hour + 1) + ':00';
    if (hour === 23) {
      endDate = shiftDays(dateStr, 1);
      endTime = '00:00';
    }
    openCreateForm({
      start_date: dateStr,
      start_time: pad(hour) + ':00',
      end_date: endDate,
      end_time: endTime,
      professional: professionalId
    });
  }

  function openCreateForDay(dateStr) {
    openCreateForm({ start_date: dateStr, end_date: dateStr,
                     start_time: '', end_time: '',
                     professional: state.professional || '' });
  }

  function openCreateForm(prefill) {
    prefill = prefill || {};
    var form = app.querySelector('[data-appointment-form]');
    form.reset();
    state.formMode = 'create';
    state.formId = null;
    state.formVersion = null;
    state.formStatus = null;
    app.querySelector('[data-form-title]').textContent = 'Nueva cita';
    app.querySelector('[data-form-hint]').textContent = 'La cita se guarda localmente; Google se actualiza al sincronizar.';
    var idInput = form.elements.id; var versionInput = form.elements.version;
    idInput.value = ''; versionInput.value = '';
    form.elements.professional_id.disabled = false;
    form.elements.lead_id.disabled = false;
    var reasonField = form.querySelector('[data-reason-field]');
    reasonField.hidden = true;
    form.elements.reason.required = false;
    var active = (state.data ? state.data.professionals : []).filter(function (p) { return p.active; });
    if (prefill.professional && active.some(function (p) {
      return String(p.id) === String(prefill.professional);
    })) {
      form.elements.professional_id.value = prefill.professional;
    } else if (active.length === 1) {
      form.elements.professional_id.value = active[0].id;
    }
    // La fecha pulsada se conserva; las horas quedan visibles y editables.
    var startDate = prefill.start_date || prefill.date || state.date;
    form.elements.start_date.value = startDate;
    form.elements.start_time.value = prefill.start_time || '';
    form.elements.end_date.value = prefill.end_date || startDate;
    form.elements.end_time.value = prefill.end_time || '';
    form.elements.title.value = '';
    form.elements.lead_id.value = '';
    clearFormError(form);
    var dialog = app.querySelector('#appointment-form-dialog');
    state.returnFocus = document.activeElement;
    dialog.showModal();
    if (!form.elements.start_time.value) { form.elements.start_time.focus(); }
    else { form.elements.title.focus(); }
  }

  function openReprogramForm(detail) {
    var appt = detail.appointment;
    var form = app.querySelector('[data-appointment-form]');
    form.reset();
    state.formMode = 'reprogram';
    state.formId = appt.id;
    state.formVersion = appt.row_version;
    state.formStatus = appt.operational_status;
    app.querySelector('[data-form-title]').textContent = 'Reprogramar cita';
    app.querySelector('[data-form-hint]').textContent = 'La cita volverá a Pendiente y se registrará el motivo y el horario anterior.';
    form.elements.id.value = appt.id;
    form.elements.version.value = appt.row_version;
    form.elements.professional_id.value = appt.professional_id;
    form.elements.professional_id.disabled = true;
    form.elements.lead_id.value = appt.lead_id || '';
    form.elements.lead_id.disabled = true;
    form.elements.title.value = appt.title;
    var startParts = appt.start_local.split('T');
    var endParts = appt.end_local.split('T');
    form.elements.start_date.value = startParts[0];
    form.elements.start_time.value = startParts[1] || '';
    form.elements.end_date.value = endParts[0];
    form.elements.end_time.value = endParts[1] || '';
    var reasonField = form.querySelector('[data-reason-field]');
    reasonField.hidden = false;
    form.elements.reason.value = '';
    form.elements.reason.required = appt.operational_status === 'confirmed';
    clearFormError(form);
    var dialog = app.querySelector('#appointment-form-dialog');
    var detailDialog = app.querySelector('#appointment-detail');
    if (detailDialog.open) { detailDialog.close(); }
    dialog.showModal();
    form.elements.start_time.focus();
  }

  function clearFormError(form) {
    var error = form.querySelector('[data-form-error]');
    error.hidden = true; error.textContent = '';
  }

  function showFormError(form, message) {
    var error = form.querySelector('[data-form-error]');
    error.textContent = message; error.hidden = false;
  }

  function submitAppointmentForm(event) {
    event.preventDefault();
    var form = event.currentTarget;
    clearFormError(form);
    var startDate = form.elements.start_date.value;
    var startTime = form.elements.start_time.value;
    var endDate = form.elements.end_date.value;
    var endTime = form.elements.end_time.value;
    if (!startDate || !startTime || !endDate || !endTime) {
      showFormError(form, 'Indique la fecha y hora de inicio y de fin');
      return;
    }
    var startLocal = startDate + 'T' + startTime;
    var endLocal = endDate + 'T' + endTime;
    // Comparación de hora de pared del negocio; el servidor valida DST.
    if (endLocal <= startLocal) {
      showFormError(form, 'El fin debe ser posterior al inicio');
      return;
    }
    var payload = {
      professional_id: form.elements.professional_id.value,
      lead_id: form.elements.lead_id.value || null,
      title: form.elements.title.value.trim(),
      start: startLocal,
      end: endLocal,
      reason: form.elements.reason.value.trim()
    };
    if (!payload.professional_id) { showFormError(form, 'Seleccione un profesional'); return; }
    if (!payload.title) { showFormError(form, 'Indique el detalle de la cita'); return; }
    var request;
    if (state.formMode === 'reprogram') {
      payload.action = 'reprogram';
      payload.version = state.formVersion;
      request = jsonFetch('/api/appointments/' + state.formId + '/transition', {
        method: 'POST', body: JSON.stringify(payload)
      });
    } else {
      request = jsonFetch('/api/appointments', { method: 'POST', body: JSON.stringify(payload) });
    }
    request.then(function () {
      var dialog = app.querySelector('#appointment-form-dialog');
      dialog.close();
      setStatus(state.formMode === 'reprogram' ? 'Cita reprogramada.' : 'Cita creada.');
      load();
    }).catch(function (error) {
      showFormError(form, error.message);
    });
  }

  function localShort(iso) {
    if (!iso) { return '—'; }
    try {
      var p = partsInZone(iso);
      return p.date.slice(8, 10) + '/' + p.date.slice(5, 7) + ' ' + pad(p.hour) + ':' + pad(p.minute);
    } catch (e) { return String(iso); }
  }

  function describeChanges(before, after) {
    before = before || {};
    after = after || {};
    var parts = [];
    ['title', 'start', 'end', 'operational_status', 'status', 'sync_status'].forEach(function (key) {
      var hasBefore = Object.prototype.hasOwnProperty.call(before, key);
      var hasAfter = Object.prototype.hasOwnProperty.call(after, key);
      if (!hasBefore && !hasAfter) { return; }
      var oldValue = hasBefore ? before[key] : undefined;
      var newValue = hasAfter ? after[key] : undefined;
      if (oldValue === newValue) { return; }
      if (key === 'title') {
        parts.push('Detalle: ' + (oldValue || '—') + ' → ' + (newValue || '—'));
      } else if (key === 'start' || key === 'end') {
        parts.push((key === 'start' ? 'Inicio' : 'Fin') + ': ' +
          localShort(oldValue) + ' → ' + localShort(newValue));
      } else if (key === 'operational_status') {
        parts.push('Estado: ' + (STATUS_LABELS[oldValue] || oldValue || '—') + ' → ' +
          (STATUS_LABELS[newValue] || newValue || '—'));
      } else if (key === 'status') {
        parts.push('Situación: ' + (STATUS_LABELS[oldValue] || oldValue || '—') + ' → ' +
          (STATUS_LABELS[newValue] || newValue || '—'));
      } else if (key === 'sync_status') {
        parts.push('Sincronización: ' + (SYNC_LABELS[oldValue] || oldValue || '—') + ' → ' +
          (SYNC_LABELS[newValue] || newValue || '—'));
      }
    });
    if (!parts.length && !Object.keys(before).length && Object.keys(after).length) {
      if (after.start) { parts.push('Inicio: ' + localShort(after.start)); }
      if (after.end) { parts.push('Fin: ' + localShort(after.end)); }
      if (after.operational_status) {
        parts.push('Estado: ' + (STATUS_LABELS[after.operational_status] || after.operational_status));
      }
      if (after.title) { parts.push('Detalle: ' + after.title); }
    }
    return parts.join(' · ');
  }

  function fillDetail(detail) {
    state.detail = detail;
    var appt = detail.appointment;
    var dialog = app.querySelector('#appointment-detail');
    var text = function (name, value, selector) {
      var node = dialog.querySelector('[data-field="' + (selector || name) + '"]');
      if (node) { node.textContent = value; }
    };
    text('professional', appt.professional_name + (appt.professional_specialty ? ' · ' + appt.professional_specialty : ''));
    text('title', appt.title);
    text('client', appt.lead_name ? appt.lead_name + (appt.lead_phone ? ' · ' + appt.lead_phone : '') : 'Sin cliente vinculado');
    text('start', appt.start_local.replace('T', ' '));
    text('end', appt.end_local.replace('T', ' '));
    text('sync', SYNC_LABELS[appt.sync_status] || appt.sync_status);
    text('version', 'v' + appt.row_version);
    var statusNode = dialog.querySelector('[data-field="status"]');
    statusNode.className = 'status-badge ' + appt.operational_status;
    statusNode.textContent = appt.status_label;
    var closure = dialog.querySelector('[data-field="closure"]');
    closure.hidden = !detail.pending_closure;
    var syncError = dialog.querySelector('[data-field="sync-error"]');
    if (appt.sync_error) { syncError.textContent = appt.sync_error; syncError.hidden = false; }
    else { syncError.hidden = true; syncError.textContent = ''; }

    var actions = dialog.querySelector('[data-actions]');
    actions.replaceChildren();
    (detail.allowed_actions || []).forEach(function (action) {
      if (action === 'admin_correct') { return; }
      var button = el('button', action === 'cancel' ? 'danger' : 'secondary', ACTION_LABELS[action] || action);
      button.type = 'button';
      button.addEventListener('click', function () {
        if (action === 'reprogram') { openReprogramForm(detail); return; }
        runTransition(action, { version: appt.row_version });
      });
      actions.appendChild(button);
    });
    if (!actions.children.length) { actions.appendChild(el('p', 'muted', 'Sin acciones disponibles en este momento.')); }

    var admin = dialog.querySelector('[data-admin-only]');
    if (admin) { admin.open = false; }
    var correctError = dialog.querySelector('[data-correct-error]');
    if (correctError) { correctError.hidden = true; }

    var notes = dialog.querySelector('[data-notes]');
    notes.replaceChildren();
    if (!detail.notes.length) { notes.appendChild(el('li', 'muted', 'Sin observaciones internas.')); }
    detail.notes.forEach(function (note) {
      var item = el('li');
      item.appendChild(document.createTextNode(note.body));
      item.appendChild(el('span', 'meta', note.author + ' · ' + note.created_local.replace('T', ' ')));
      notes.appendChild(item);
    });

    var history = dialog.querySelector('[data-history]');
    history.replaceChildren();
    detail.history.forEach(function (entry) {
      var item = el('li');
      item.appendChild(el('strong', null, entry.action_label));
      var pieces = [entry.actor, entry.created_local.replace('T', ' ')];
      if (entry.reason) { pieces.push('Motivo: ' + entry.reason); }
      var changes = describeChanges(entry.before, entry.after);
      if (changes) { pieces.push(changes); }
      item.appendChild(el('span', 'meta', pieces.join(' · ')));
      history.appendChild(item);
    });
    dialog.querySelector('[data-note-form]').elements.body.value = '';
  }

  function openDetail(id) {
    state.returnFocus = document.activeElement;
    jsonFetch('/api/appointments/' + id).then(function (detail) {
      fillDetail(detail);
      app.querySelector('#appointment-detail').showModal();
    }).catch(function (error) { setStatus(error.message, true); });
  }

  function refreshDetail() {
    if (!state.detail) { return Promise.resolve(); }
    var id = state.detail.appointment.id;
    return jsonFetch('/api/appointments/' + id).then(function (detail) {
      fillDetail(detail); load();
    }).catch(function (error) { setStatus(error.message, true); });
  }

  function runTransition(action, extra) {
    if (!state.detail) { return; }
    var appt = state.detail.appointment;
    var payload = { action: action, version: appt.row_version };
    if (extra) { Object.keys(extra).forEach(function (key) { payload[key] = extra[key]; }); }
    jsonFetch('/api/appointments/' + appt.id + '/transition', {
      method: 'POST', body: JSON.stringify(payload)
    }).then(function () {
      setStatus('Cita actualizada.');
      refreshDetail();
    }).catch(function (error) { setStatus(error.message, true); });
  }

  function submitNote(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var errorNode = form.querySelector('[data-note-error]');
    errorNode.hidden = true;
    var body = form.elements.body.value.trim();
    if (!body) { errorNode.textContent = 'Escriba la observación'; errorNode.hidden = false; return; }
    jsonFetch('/api/appointments/' + state.detail.appointment.id + '/notes', {
      method: 'POST', body: JSON.stringify({ body: body })
    }).then(function () {
      form.elements.body.value = '';
      setStatus('Observación guardada.');
      refreshDetail();
    }).catch(function (error) {
      errorNode.textContent = error.message; errorNode.hidden = false;
    });
  }

  function submitCorrection(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var errorNode = form.querySelector('[data-correct-error]');
    errorNode.hidden = true;
    var reason = form.elements.reason.value.trim();
    if (!reason) { errorNode.textContent = 'El motivo es obligatorio'; errorNode.hidden = false; return; }
    jsonFetch('/api/appointments/' + state.detail.appointment.id + '/transition', {
      method: 'POST',
      body: JSON.stringify({
        action: 'admin_correct', version: state.detail.appointment.row_version,
        target: form.elements.target.value, reason: reason
      })
    }).then(function () {
      form.reset();
      setStatus('Corrección registrada con historial.');
      refreshDetail();
    }).catch(function (error) {
      errorNode.textContent = error.message; errorNode.hidden = false;
    });
  }

  function closeDialog(dialog) {
    if (dialog && dialog.open) { dialog.close(); }
  }

  function bindDialog(dialog) {
    if (!dialog) { return; }
    dialog.querySelectorAll('[data-close]').forEach(function (button) {
      button.addEventListener('click', function () { dialog.close(); });
    });
    dialog.addEventListener('cancel', function (event) {
      event.preventDefault();
      dialog.close();
    });
    dialog.addEventListener('close', function () {
      if (state.returnFocus && document.contains(state.returnFocus)) {
        state.returnFocus.focus();
      }
    });
  }

  function setup() {
    state.view = storedView() || defaultView();
    syncViewButtons();

    app.querySelectorAll('[data-view]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.view = button.getAttribute('data-view');
        saveView(state.view);
        syncViewButtons();
        load();
      });
    });
    app.querySelector('[data-action="new"]').addEventListener('click', function () {
      openCreateForm({ start_date: state.date, end_date: state.date,
                       start_time: '', end_time: '',
                       professional: state.professional || '' });
    });
    app.querySelector('[data-action="refresh"]').addEventListener('click', load);
    app.querySelector('[data-nav="today"]').addEventListener('click', function () {
      state.date = today; load();
    });
    app.querySelector('[data-nav="prev"]').addEventListener('click', function () { navigate(-1); });
    app.querySelector('[data-nav="next"]').addEventListener('click', function () { navigate(1); });
    app.querySelector('[data-filter="professional"]').addEventListener('change', function (event) {
      state.professional = event.currentTarget.value; load();
    });
    app.querySelector('[data-filter="status"]').addEventListener('change', function (event) {
      state.status = event.currentTarget.value; load();
    });
    app.querySelector('[data-filter="cancelled"]').addEventListener('change', function (event) {
      state.cancelled = event.currentTarget.checked; load();
    });

    surface.addEventListener('click', function (event) {
      var opener = event.target.closest('[data-open]');
      if (opener) { openDetail(opener.getAttribute('data-open')); }
    });

    var form = app.querySelector('[data-appointment-form]');
    form.addEventListener('submit', submitAppointmentForm);
    app.querySelector('[data-note-form]').addEventListener('submit', submitNote);
    var correctForm = app.querySelector('[data-correct-form]');
    if (correctForm) { correctForm.addEventListener('submit', submitCorrection); }

    bindDialog(app.querySelector('#appointment-detail'));
    bindDialog(app.querySelector('#appointment-form-dialog'));

    // La vista no cambia al redimensionar; sólo la disposición CSS es adaptable.
    load();
  }

  function navigate(direction) {
    if (state.view === 'day') { state.date = shiftDays(state.date, direction); }
    else if (state.view === 'week') { state.date = shiftDays(state.date, direction * 7); }
    else { state.date = shiftMonths(state.date, direction); }
    load();
  }

  setup();
})();
