/* C02 — Alerta superior de atención humana. Sin scripts inline (CSP estricta).
   Indicador global en la cabecera de TODAS las pantallas autenticadas: campana
   + número de conversaciones pendientes (únicas, sin duplicados) + texto
   accesible ("Sin atenciones pendientes" / "N conversaciones requieren
   atención") + etiqueta de prioridad (texto y color, nunca sólo color).

   - Polling moderado con setTimeout ENCADENADO al final de cada consulta: una
     respuesta lenta nunca solapa a la siguiente (sin solapes).
   - Si la consulta falla se muestra "No se pudo actualizar" conservando el
     último estado conocido: NO se apaga falsamente el indicador.
   - GET puro: abrir la campana NO resuelve (la resolución es un acto explícito
     del operador en la bandeja). Persiste al recargar y refleja los cambios de
     otra pestaña porque siempre se relee el estado de la base.
   - Sin sonido. Sin animaciones si el usuario pide prefers-reduced-motion.
   - El panel NO expone mensajes privados: sólo motivo, prioridad, tiempo de
     espera, cliente y responsable; cada fila abre la conversación en la bandeja. */
(function () {
  'use strict';

  var root = document.getElementById('atencion-bell');
  if (!root) return;

  var ENLACE_BANDEJA = '/?tab=inbox&conversation=';
  var INTERVALO_MS = 20000;

  var RAZONES = {
    'humano_explicito': 'Solicitó hablar con una persona',
    'emergencia': 'Posible emergencia',
    'reclamo': 'Reclamo o queja',
    'peligro_inmediato': 'Posible peligro inmediato',
    'sin_fuente': 'Sin información suficiente',
    'fallo_servicio': 'Fallo del proveedor de IA',
    'por_revision': 'Requiere revisión'
  };

  var estado = {
    ok: false,           // última consulta respondió ok
    nunca: true,         // aún no hubo ni una consulta exitosa
    pendientes: [],      // conversaciones pendientes (agrupadas por el servidor)
    en_atencion: [],     // conversaciones en atención con responsable
    total_pendientes: 0,
    total_en_atencion: 0,
    total_global: 0,
    ultimo_exito: null   // copia del último estado bueno conocido
  };
  var abierto = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    n.textContent = text || '';
    return n;
  }

  function fmtEspera(seg) {
    if (seg == null || seg < 60) return 'menos de 1 min';
    var min = Math.floor(seg / 60);
    if (min < 60) return min + ' min';
    var h = Math.floor(min / 60);
    var m = min % 60;
    return m ? (h + ' h ' + m + ' min') : (h + ' h');
  }

  function razonLabel(r) { return RAZONES[r] || r; }

  function prioridadDe(lista) {
    var alta = lista.some(function (c) { return c.prioridad_max === 'alta'; });
    return alta ? 'alta' : 'normal';
  }

  function rebuild() {
    var total = estado.total_pendientes;
    root.classList.toggle('has-pending', total > 0);
    root.classList.toggle('prio-alta', total > 0 && prioridadDe(estado.pendientes) === 'alta');
    root.classList.toggle('prio-normal', total > 0 && prioridadDe(estado.pendientes) === 'normal');
    root.classList.toggle('stale', !estado.ok);

    var btn = root.querySelector('.bell-button');
    var acc = estado.nunca
      ? 'Cargando atenciones...'
      : (estado.ok
        ? (total > 0 ? (total + (total === 1 ? ' conversación requiere atención' : ' conversaciones requieren atención')) : 'Sin atenciones pendientes')
        : 'No se pudo actualizar');
    btn.setAttribute('aria-label', acc);
    btn.setAttribute('aria-expanded', abierto ? 'true' : 'false');

    var count = root.querySelector('.bell-count');
    count.textContent = String(total);
    count.hidden = total === 0;

    var text = root.querySelector('.bell-text');
    text.textContent = estado.nunca
      ? 'Cargando atenciones...'
      : (estado.ok
        ? (total > 0 ? (total + (total === 1 ? ' conversación requiere atención' : ' conversaciones requieren atención')) : 'Sin atenciones pendientes')
        : 'No se pudo actualizar');

    var prio = root.querySelector('.bell-prio');
    if (total > 0 && estado.ok) {
      prio.hidden = false;
      prio.textContent = prioridadDe(estado.pendientes) === 'alta'
        ? 'Prioridad alta' : 'Prioridad normal';
    } else {
      prio.hidden = true;
    }
    renderPanel();
  }

  function renderPanel() {
    var list = root.querySelector('.bell-list');
    list.innerHTML = '';
    var status = root.querySelector('.bell-status');

    if (!estado.ok && !estado.nunca) {
      status.hidden = false;
      status.textContent = 'No se pudo actualizar';
      status.className = 'bell-status stale';
    } else if (estado.nunca) {
      status.hidden = false;
      status.textContent = 'Cargando atenciones...';
      status.className = 'bell-status loading';
    } else if (estado.total_pendientes === 0 && estado.total_en_atencion === 0) {
      status.hidden = false;
      status.textContent = 'Sin atenciones pendientes ni en curso.';
      status.className = 'bell-status';
    } else {
      status.hidden = true;
    }

    if (estado.pendientes.length) {
      var h2 = el('li', 'bell-section-label', 'Pendientes');
      list.appendChild(h2);
      estado.pendientes.forEach(function (c) { list.appendChild(filaConversacion(c)); });
    }
    if (estado.en_atencion.length) {
      var h3 = el('li', 'bell-section-label', 'En atención');
      list.appendChild(h3);
      estado.en_atencion.forEach(function (c) {
        var li = filaConversacion(c, true);
        var resp = el('small', 'bell-resp', 'Responsable: ' + (c.responsible_name || '—'));
        li.appendChild(resp);
        list.appendChild(li);
      });
    }
    if (!estado.pendientes.length && !estado.en_atencion.length && estado.ok && !estado.nunca) {
      var vacio = el('li', 'bell-empty', 'No hay conversaciones que requieran atención.');
      list.appendChild(vacio);
    }
  }

  function filaConversacion(c, enAtencion) {
    var motivo = (c.alerts || []).map(function (a) { return razonLabel(a.reason); }).join('; ');
    var li = el('li', 'bell-row' + (c.prioridad_max === 'alta' ? ' prio-alta' : ''));
    var link = document.createElement('a');
    link.href = ENLACE_BANDEJA + c.conversation_id;
    link.className = 'bell-row-main';
    if (enAtencion) link.setAttribute('aria-label', 'En atención: ' + (c.client_key || ''));
    link.appendChild(el('strong', 'bell-client', c.client_key || ('Conversación #' + c.conversation_id)));
    link.appendChild(el('span', 'bell-motivo', motivo));
    var meta = el('span', 'bell-meta',
      (c.prioridad_max === 'alta' ? 'Prioridad alta' : 'Prioridad normal') +
      ' · espera ' + fmtEspera(c.tiempo_espera_seg));
    link.appendChild(meta);
    li.appendChild(link);
    return li;
  }

  function aplicar(j) {
    estado.ok = true;
    estado.nunca = false;
    estado.pendientes = (j && j.pendientes) || [];
    estado.en_atencion = (j && j.en_atencion) || [];
    estado.total_pendientes = (j && j.total_pendientes != null) ? j.total_pendientes : estado.pendientes.length;
    estado.total_en_atencion = (j && j.total_en_atencion != null) ? j.total_en_atencion : estado.en_atencion.length;
    estado.total_global = estado.total_pendientes + estado.total_en_atencion;
    estado.ultimo_exito = {
      pendientes: estado.pendientes, en_atencion: estado.en_atencion,
      total_pendientes: estado.total_pendientes, total_en_atencion: estado.total_en_atencion
    };
    rebuild();
  }

  function fallo() {
    // Consulta fallida: NO se apaga falsamente. Se conserva el último estado
    // bueno conocido y se muestra el aviso; el siguiente ciclo reintenta.
    if (estado.ultimo_exito) {
      var u = estado.ultimo_exito;
      estado.pendientes = u.pendientes;
      estado.en_atencion = u.en_atencion;
      estado.total_pendientes = u.total_pendientes;
      estado.total_en_atencion = u.total_en_atencion;
      estado.total_global = u.total_pendientes + u.total_en_atencion;
    }
    estado.ok = false;
    rebuild();
  }

  function consultar() {
    fetch('/api/c02/atencion', {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin'
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(aplicar, fallo);
  }

  function ciclo() {
    // setTimeout encadenado DESPUÉS de terminar la consulta: nunca se solapan.
    consultar();
    setTimeout(ciclo, INTERVALO_MS);
  }

  function construir() {
    root.innerHTML = '';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'bell-button';
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');
    btn.appendChild(el('span', 'bell-icon', '🔔'));
    var count = el('span', 'bell-count', '0');
    count.hidden = true;
    btn.appendChild(count);
    btn.appendChild(el('span', 'bell-text', 'Cargando atenciones...'));
    var prio = el('span', 'bell-prio', '');
    prio.hidden = true;
    btn.appendChild(prio);
    root.appendChild(btn);

    var panel = el('div', 'bell-panel');
    panel.hidden = true;
    panel.setAttribute('role', 'region');
    panel.setAttribute('aria-label', 'Atenciones pendientes');
    panel.appendChild(el('p', 'bell-title', 'Conversaciones que requieren atención'));
    panel.appendChild(el('p', 'bell-status', 'Cargando atenciones...'));
    var list = el('ul', 'bell-list');
    panel.appendChild(list);
    panel.appendChild(el('p', 'bell-nota', 'Abra una conversación para atenderla. Resolver es un acto explícito en la bandeja.'));
    root.appendChild(panel);

    btn.addEventListener('click', function () {
      abierto = !abierto;
      panel.hidden = !abierto;
      btn.setAttribute('aria-expanded', abierto ? 'true' : 'false');
      if (abierto) renderPanel();
    });

    document.addEventListener('click', function (ev) {
      if (abierto && !root.contains(ev.target)) {
        abierto = false;
        panel.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', function (ev) {
      if (abierto && ev.key === 'Escape') {
        abierto = false;
        panel.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  construir();
  rebuild();
  ciclo();
})();
