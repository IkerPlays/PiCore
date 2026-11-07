/* Teclado en pantalla (español) para la pantalla tactil: contraseñas de Wi-Fi, etc.
   Uso:  PCPIKeyboard.open(inputEl, {onEnter: () => ...});   PCPIKeyboard.close();
   No usa librerias: solo DOM. Los inputs reciben el texto y un evento "input" (para que la pagina reaccione). */
(function () {
  "use strict";
  const ROWS = {
    abc: [
      "q w e r t y u i o p".split(" "),
      "a s d f g h j k l ñ".split(" "),
      ["shift", ..."z x c v b n m".split(" "), "bksp"],
    ],
    sym: [
      "1 2 3 4 5 6 7 8 9 0".split(" "),
      "@ # $ % & * - + = _".split(" "),
      ["¡", ..."! ? . , : ; / \\".split(" "), "bksp"],
      /* (las comillas, parentesis y demas simbolos extra van en la fila 4) */
    ],
  };
  const EXTRA = ["( ) \" ' < > [ ] { } ~ ^ | ´ ç ¿ €".split(" ")];
  let root, target, mode = "abc", shift = false, caps = false, onEnter = null, lastShift = 0;

  function css() {
    if (document.getElementById("osk-css")) return;
    const s = document.createElement("style");
    s.id = "osk-css";
    s.textContent = `
    #osk { position:fixed; left:0; right:0; bottom:0; z-index:60; padding:10px 10px 12px; background:var(--card,#181b22); border-top:1px solid var(--line,#252a33);
           box-shadow:0 -18px 50px #0006; transform:translateY(105%); transition:transform .38s cubic-bezier(.2,.9,.25,1); touch-action:manipulation; }
    #osk.on { transform:none; }
    #osk .row { display:flex; justify-content:center; gap:6px; margin-bottom:6px; }
    #osk button { flex:1 1 0; max-width:84px; height:46px; font:inherit; font-size:20px; border-radius:12px; background:var(--bg,#0e1014); color:var(--fg,#f2f4f8);
                  border:1px solid var(--line,#252a33); transition:transform .08s, background .15s; }
    #osk button:active { transform:scale(.92); background:var(--acc,#7aa7ff); color:var(--acc-fg,#07101f); }
    #osk button.wide { max-width:none; flex:2.4 1 0; }
    #osk button.act { background:var(--acc,#7aa7ff); color:var(--acc-fg,#07101f); }
    #osk .enter { flex:1.6 1 0; max-width:none; background:var(--acc,#7aa7ff); color:var(--acc-fg,#07101f); font-weight:650; }
    @media (prefers-reduced-motion: reduce) { #osk { transition:none; } }`;
    document.head.appendChild(s);
  }

  function key(label, cls, handler) {
    const b = document.createElement("button");
    b.type = "button"; if (cls) b.className = cls;
    if (label.startsWith("#")) {                        // "#nombre" = icono del sprite de la pagina
      const sv = document.createElementNS("http://www.w3.org/2000/svg", "svg"); sv.setAttribute("class", "ic"); sv.setAttribute("aria-hidden", "true");
      const u = document.createElementNS("http://www.w3.org/2000/svg", "use"); u.setAttribute("href", "#i-" + label.slice(1)); sv.appendChild(u); b.appendChild(sv);
    } else b.textContent = label;
    /* pointerdown + preventDefault: el input NO pierde el foco al tocar una tecla */
    b.addEventListener("pointerdown", e => { e.preventDefault(); handler(); });
    return b;
  }

  function insert(ch) {
    if (!target) return;
    const s = target.selectionStart ?? target.value.length, e = target.selectionEnd ?? s;
    target.value = target.value.slice(0, s) + ch + target.value.slice(e);
    const p = s + ch.length;
    try { target.setSelectionRange(p, p); } catch (err) {}
    target.dispatchEvent(new Event("input", {bubbles: true}));
  }
  function backspace() {
    if (!target) return;
    const s = target.selectionStart ?? target.value.length, e = target.selectionEnd ?? s;
    if (s === e && s > 0) { target.value = target.value.slice(0, s - 1) + target.value.slice(e); try { target.setSelectionRange(s - 1, s - 1); } catch (err) {} }
    else { target.value = target.value.slice(0, s) + target.value.slice(e); try { target.setSelectionRange(s, s); } catch (err) {} }
    target.dispatchEvent(new Event("input", {bubbles: true}));
  }

  function render() {
    root.textContent = "";
    const rows = mode === "abc" ? ROWS.abc : [...ROWS.sym, ...EXTRA];
    rows.forEach((r, ri) => {
      const row = document.createElement("div"); row.className = "row";
      r.forEach(k => {
        if (k === "shift") row.appendChild(key("#shift", "wide" + (shift || caps ? " act" : ""), () => {
          const now = Date.now();
          if (now - lastShift < 350) { caps = !caps; shift = false; } else { shift = !shift; caps = false; }
          lastShift = now; render();
        }));
        else if (k === "bksp") row.appendChild(key("#backspace", "wide", backspace));
        else {
          const up = mode === "abc" && (shift || caps);
          row.appendChild(key(up ? k.toUpperCase() : k, "", () => { insert(up ? k.toUpperCase() : k); if (shift && !caps) { shift = false; render(); } }));
        }
      });
      root.appendChild(row);
    });
    const last = document.createElement("div"); last.className = "row";
    last.appendChild(key(mode === "abc" ? "123 #+=" : "ABC", "wide", () => { mode = mode === "abc" ? "sym" : "abc"; render(); }));
    last.appendChild(key("espacio", "", () => insert(" ")));
    last.lastChild.style.flex = "5 1 0"; last.lastChild.style.maxWidth = "none";
    last.appendChild(key("Ocultar", "wide", close));
    last.appendChild(key("Hecho", "enter", () => { const f = onEnter; if (f) f(); }));
    root.appendChild(last);
  }

  function open(input, opts) {
    css();
    target = input; onEnter = (opts && opts.onEnter) || null;
    if (!root) { root = document.createElement("div"); root.id = "osk"; document.body.appendChild(root); }
    shift = caps = false; mode = "abc"; render();
    requestAnimationFrame(() => root.classList.add("on"));
    document.body.classList.add("osk-open");
    if (input && input.scrollIntoView) setTimeout(() => input.scrollIntoView({block: "center", behavior: "smooth"}), 120);
  }
  function close() {
    if (root) root.classList.remove("on");
    document.body.classList.remove("osk-open");
    target = null;
  }
  window.PCPIKeyboard = {open, close, get visible() { return !!(root && root.classList.contains("on")); }};
})();
