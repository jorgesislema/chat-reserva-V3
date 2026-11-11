/* Tema claro/oscuro persistente (CSP estricta: sin inline).
   Aplica data-theme en <html> antes de pintar; guarda la elección en
   localStorage('crm-theme') y respeta prefers-color-scheme por defecto.
   El botón conmutador vive en la barra lateral (#theme-toggle). */
(function () {
  'use strict';
  var KEY = 'crm-theme';
  var root = document.documentElement;

  function actual() {
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) {}
    if (stored === 'dark' || stored === 'light') return stored;
    return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
      ? 'dark' : 'light';
  }

  function aplicar(theme, sync) {
    root.setAttribute('data-theme', theme);
    if (sync !== false) {
      try { localStorage.setItem(KEY, theme); } catch (e) {}
    }
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      var dark = theme === 'dark';
      btn.textContent = dark ? 'Modo claro' : 'Modo oscuro';
      btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
    }
  }

  function vincularBoton() {
    var btn = document.getElementById('theme-toggle');
    if (!btn || btn.dataset['temaEnlazado']) return;
    btn.dataset['temaEnlazado'] = '1';
    btn.addEventListener('click', function () {
      aplicar(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true);
    });
  }

  aplicar(actual(), false);
  // Barra horizontal superior sincronizada para tablas anchas
  // (Catálogo, inventario): evita bajar hasta el final para desplazarse.
  window.CRMTopScroll = function (wrap) {
    if (!wrap) return;
    function anchoExistente() {
      try {
        var b = wrap.previousElementSibling;
        if (b && b.classList && b.classList.contains('table-scroll-top')) {
          var sp = b.firstChild;
          if (sp) sp.style.width = Math.max(wrap.scrollWidth, wrap.clientWidth) + 'px';
          b.scrollLeft = wrap.scrollLeft;
        }
      } catch (e) {}
    }
    if (wrap.dataset.topscroll) { anchoExistente(); return; }
    try { wrap.dataset.topscroll = '1'; } catch (e) { return; }
    var bar = document.createElement('div');
    bar.className = 'table-scroll-top';
    bar.setAttribute('aria-hidden', 'true');
    bar.title = 'Arrastre para moverse a la derecha/izquierda sin bajar';
    var spacer = document.createElement('div');
    spacer.className = 'table-scroll-spacer';
    spacer.innerHTML = '&nbsp;';
    bar.appendChild(spacer);
    wrap.parentNode.insertBefore(bar, wrap);
    var syncing = false;
    function ancho() {
      spacer.style.width = Math.max(wrap.scrollWidth, wrap.clientWidth) + 'px';
      bar.scrollLeft = wrap.scrollLeft;
    }
    try { wrap.__crmAncho = ancho; } catch (e) {}
    bar.addEventListener('scroll', function () {
      if (syncing) return; syncing = true;
      wrap.scrollLeft = bar.scrollLeft; syncing = false;
    });
    wrap.addEventListener('scroll', function () {
      if (syncing) return; syncing = true;
      bar.scrollLeft = wrap.scrollLeft; syncing = false;
    });
    // Rueda con Mayús (o rueda horizontal) mueve la tabla a los lados
    // sin usar la barra: útil cuando la tabla es muy ancha.
    wrap.addEventListener('wheel', function (ev) {
      if (ev.shiftKey && !ev.ctrlKey && !ev.metaKey) {
        if (wrap.scrollWidth > wrap.clientWidth) {
          wrap.scrollLeft += (ev.deltaY || 0);
          try { bar.scrollLeft = wrap.scrollLeft; } catch (e2) {}
          ev.preventDefault();
        }
      }
    }, { passive: false });
    ancho();
    if (window.ResizeObserver) {
      try {
        new ResizeObserver(ancho).observe(wrap);
        var tabla = wrap.querySelector('table');
        if (tabla) new ResizeObserver(ancho).observe(tabla);
        var cuerpo = wrap.querySelector('tbody');
        if (cuerpo) new ResizeObserver(ancho).observe(cuerpo);
      } catch (e) {}
    }
    window.addEventListener('resize', ancho);
  };
  function aplicarBarras() {
    var zonas = document.querySelectorAll('.table-wrap');
    for (var i = 0; i < zonas.length; i++) window.CRMTopScroll(zonas[i]);
  }
  window.CRMTopScrollRefresh = aplicarBarras;
  aplicarBarras();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', aplicarBarras);
  }
  window.addEventListener('load', aplicarBarras);
  document.addEventListener('crm:tabla-actualizada', aplicarBarras);
  if (window.MutationObserver) {
    try {
      var raiz = document.documentElement || document;
      var antiRuido = false;
      new MutationObserver(function (muts) {
        if (antiRuido) return;
        var hay = false;
        for (var i = 0; i < muts.length && !hay; i++) {
          var nodos = muts[i].addedNodes || [];
          for (var j = 0; j < nodos.length; j++) {
            var n = nodos[j];
            if (n.nodeType === 1 && (n.matches('.table-wrap') || (n.querySelector && n.querySelector('.table-wrap')))) { hay = true; break; }
          }
          // Filas nuevas dentro de una tabla existente: reanchar su barra.
          try {
            var t = muts[i].target;
            if (t && t.closest) {
              var w = t.closest('.table-wrap');
              if (w && w.__crmAncho) { w.__crmAncho(); }
            }
          } catch (e2) {}
        }
        if (hay) {
          antiRuido = true;
          try { aplicarBarras(); } finally { antiRuido = false; }
        }
      }).observe(raiz, { childList: true, subtree: true });
    } catch (e) {}
  }
  // theme.js se carga en <head>; el botón vive en el cuerpo (barra lateral),
  // así que el enlace se intenta ya y, si el botón aún no existe, al cargar
  // el DOM. Idempotente: nunca se registran dos listeners sobre el mismo botón.
  vincularBoton();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', vincularBoton);
  }
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (ev) {
      var stored = null;
      try { stored = localStorage.getItem(KEY); } catch (e) {}
      if (stored !== 'dark' && stored !== 'light') aplicar(ev.matches ? 'dark' : 'light', false);
    });
  }
})();
