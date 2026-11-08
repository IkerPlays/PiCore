/* PiCore · efectos compartidos (ligeros: solo transform, opacity y box-shadow, pensados para la GPU de la Pi).
   Destello al tocar un boton y entrada escalonada de las listas. Respeta «reducir movimiento». */
(function () {
  "use strict";
  var quieto = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (quieto) return;
  document.addEventListener("pointerdown", function (e) {
    var el = e.target.closest && e.target.closest("button, .chip, .trk, nav button");
    if (!el || el.disabled) return;
    el.classList.remove("tap"); void el.offsetWidth; el.classList.add("tap");
  }, { passive: true });
  document.addEventListener("animationend", function (e) {
    if (e.animationName === "tapglow") e.target.classList.remove("tap");
  });
})();
