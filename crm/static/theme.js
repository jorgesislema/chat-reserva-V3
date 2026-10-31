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
