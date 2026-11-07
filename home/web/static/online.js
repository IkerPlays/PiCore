/* Aviso «Reconectando con el servidor…» cuando varias peticiones seguidas a la API fallan (por ejemplo, mientras systemd
   reinicia el servidor tras un cuelgue). Se esconde solo en cuanto una peticion vuelve a salir bien. Se carga PRIMERO en
   cada pagina para envolver `fetch` antes de que lo use nadie. */
(function () {
  "use strict";
  const real = window.fetch.bind(window);
  let fails = 0, bar = null;
  function show(on) {
    if (on && !bar) {
      bar = document.createElement("div"); bar.id = "offline"; bar.setAttribute("role", "status");
      bar.innerHTML = '<span class="dot"></span>Reconectando con el servidor…';
      (document.body || document.documentElement).appendChild(bar);
    } else if (!on && bar) { bar.remove(); bar = null; }
  }
  window.fetch = function (input, init) {
    return real(input, init).then(r => { if (fails) { fails = 0; show(false); } return r; }, err => {
      try {
        const u = new URL(typeof input === "string" ? input : input.url, location.href);
        if (u.origin === location.origin && u.pathname.startsWith("/api/") && ++fails >= 3) show(true);
      } catch (e) { /* una URL rara no debe romper el aviso */ }
      throw err;
    });
  };
  window.PCPI_OFFLINE = { get failing() { return fails; } };
})();
