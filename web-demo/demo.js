/* PiCore · demo en el navegador.
   Sustituye al servidor Python (home/server.py) por una API simulada en JavaScript, para poder probar la interfaz
   en una web estatica (Netlify) sin una Raspberry Pi. NO hace nada real: no apaga, no descarga, no ejecuta ordenes.
   Lo que "guardas" (notas, marcadores, ajustes) se queda en el almacenamiento local de TU navegador. */
(function () {
  "use strict";
  const PREFIX = "pcpi-demo-";
  const LS = {
    get(k, d) { try { const v = localStorage.getItem(PREFIX + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(PREFIX + k, JSON.stringify(v)); } catch (e) {} },
    clear() { try { Object.keys(localStorage).filter(k => k.startsWith(PREFIX)).forEach(k => localStorage.removeItem(k)); } catch (e) {} },
  };
  const T0 = Date.now();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const pad = n => String(n).padStart(2, "0");
  const rid = n => Array.from(crypto.getRandomValues(new Uint8Array(n))).map(b => "0123456789abcdef"[b & 15]).join("");


  /* ---------------- marco de dispositivo ---------------- */
  /* Abierta suelta (sin ?bare), cada pagina se redirige a la carcasa (index.html), que la muestra dentro de una pantalla de
     1024x600 escalada. Dentro de la carcasa las paginas van en un iframe y se comportan como en la pantalla de la Pi. */
  const framed = window.top !== window;
  let bare = /[?&]bare\b/.test(location.search);
  try { if (bare) sessionStorage.setItem("pcpi-demo-bare", "1"); else bare = sessionStorage.getItem("pcpi-demo-bare") === "1"; } catch (e) {}
  if (!framed && !bare) { location.replace("/simulador?p=" + encodeURIComponent(location.pathname + location.search)); return; }

  /* ---------------- estado ---------------- */
  const here = location.pathname.replace(/\/+$/, "");
  const PAGE_MODE = here === "/iker" ? "iker" : here === "/dev" ? "dev" : here === "/loading" ? null : "home";
  if (PAGE_MODE) LS.set("mode", PAGE_MODE);
  const S = {
    pihole: { blocking: true, until: 0 },
    display: LS.get("display", { level: 100, auto: true }),
    motion: LS.get("motion", false),
    camera: false,
    timers: LS.get("timers", []),
    nowplaying: { state: "stopped" },
    music: { seq: 0, cmd: null, arg: null },
    tracks: null,
    flags: LS.get("flags", { ai_chat: false, live_graph: false, voice_log: false, casa_debug: false }),
    wifi: LS.get("wifi", { active: "CasaIker", wantsPi: { CasaIker: true } }),
    update: { state: "idle", tail: [], available: true, behind: 3 },
    audio: LS.get("audio", { volume: 60, muted: false }),
    voice: { state: "listening", wake: "hey jarvis" },
    cmds: {},
  };

  /* ---------------- avisos flotantes ---------------- */
  function toast(msg, ms) {
    let t = document.getElementById("demo-toast");
    if (!t) {
      t = document.createElement("div"); t.id = "demo-toast";
      t.style.cssText = "position:fixed;left:50%;bottom:76px;transform:translateX(-50%);z-index:100000;max-width:min(560px,90vw);padding:12px 18px;border-radius:14px;background:#0b0d12f2;color:#fff;font:600 15px/1.35 system-ui,sans-serif;border:1px solid #ffffff2a;box-shadow:0 12px 40px #0008;text-align:center;pointer-events:none;transition:opacity .3s";
      document.body.appendChild(t);
    }
    t.textContent = msg; t.style.opacity = "1";
    clearTimeout(t._h); t._h = setTimeout(() => { t.style.opacity = "0"; }, ms || 3200);
  }

  /* ---------------- musica: canciones sinteticas (WAV generado al vuelo) ---------------- */
  const NOTE = n => 440 * Math.pow(2, (n - 9) / 12);
  const SONGS = [
    { title: "Aurora (demo)", tempo: 0.42, seq: [0, 4, 7, 12, 7, 4, 0, 4, 9, 12, 16, 12, 9, 4, 2, 5, 9, 14, 9, 5, 4, 7, 11, 7] , base: 60 },
    { title: "Marea baja (demo)", tempo: 0.55, seq: [0, 3, 7, 3, 5, 8, 12, 8, 7, 10, 14, 10, 5, 8, 12, 8], base: 55 },
    { title: "Cafe de domingo (demo)", tempo: 0.35, seq: [0, 2, 4, 7, 9, 7, 4, 2, 0, 4, 7, 11, 12, 11, 7, 4, 5, 9, 12, 9], base: 62 },
  ];
  const blobs = {};
  function makeWav(song) {
    const rate = 22050, step = Math.floor(rate * song.tempo), n = step * song.seq.length * 2;
    const buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); w(8, "WAVEfmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, n * 2, true);
    for (let k = 0; k < song.seq.length * 2; k++) {
      const note = song.seq[k % song.seq.length], f = NOTE(song.base - 57 + note);
      for (let i = 0; i < step; i++) {
        const t = i / rate, env = Math.min(1, i / 400) * Math.exp(-t * 2.2);
        const s = (Math.sin(2 * Math.PI * f * t) * 0.6 + Math.sin(2 * Math.PI * f * 2 * t) * 0.2 + Math.sin(2 * Math.PI * f * 0.5 * t) * 0.2) * env * 0.4;
        v.setInt16(44 + (k * step + i) * 2, Math.max(-1, Math.min(1, s)) * 32767, true);
      }
    }
    return new Blob([buf], { type: "audio/wav" });
  }
  function tracks() {
    if (!S.tracks) S.tracks = SONGS.map((s, i) => ({ id: ("d0e" + i + "00000000").slice(0, 12), title: s.title, size: 1800000 - i * 100000, added: T0 / 1000 - i * 86400 }));
    return S.tracks;
  }
  const trackUrl = id => {
    const i = tracks().findIndex(t => t.id === id);
    if (i < 0) return "";
    const song = SONGS.find(s => s.title === tracks()[i].title) || SONGS[0];
    return blobs[id] || (blobs[id] = URL.createObjectURL(makeWav(song)));
  };
  /* <audio src="/music/<id>"> -> el WAV generado; <img src="/api/camera/stream"> -> una camara de mentira animada */
  const mediaSrc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, "src");
  Object.defineProperty(HTMLMediaElement.prototype, "src", {
    configurable: true, get() { return mediaSrc.get.call(this); },
    set(v) { const m = /^\/music\/([0-9a-f]{12})$/.exec(String(v)); mediaSrc.set.call(this, m ? trackUrl(m[1]) : v); },
  });
  const CAM = "data:image/svg+xml;utf8," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b2a4a"/><stop offset="1" stop-color="#3b1f4a"/></linearGradient></defs>' +
    '<rect width="640" height="360" fill="url(#g)"/><circle r="26" fill="#7cabff"><animate attributeName="cx" values="80;560;80" dur="7s" repeatCount="indefinite"/><animate attributeName="cy" values="250;120;250" dur="5s" repeatCount="indefinite"/></circle>' +
    '<rect x="0" y="0" width="640" height="360" fill="none" stroke="#ffffff22" stroke-width="2"/><text x="24" y="40" fill="#ffffffcc" font-family="monospace" font-size="20">CAMARA DE DEMOSTRACION</text>' +
    '<circle cx="610" cy="30" r="7" fill="#fb7185"><animate attributeName="opacity" values="1;.2;1" dur="1.4s" repeatCount="indefinite"/></circle></svg>');
  const imgSrc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "src");
  Object.defineProperty(HTMLImageElement.prototype, "src", {
    configurable: true, get() { return imgSrc.get.call(this); },
    set(v) { imgSrc.set.call(this, String(v).startsWith("/api/camera/stream") ? CAM : v); },
  });
  const realOpen = window.open;
  window.open = function (u) { if (typeof u === "string" && /^\/api\/notes\/[0-9a-f]+\.pdf$/.test(u)) { toast("El PDF no se genera en la demo (en la Pi real, sí)."); return null; } return realOpen.apply(window, arguments); };

  /* ---------------- «Probar sonido»: dos tonos (como pcpi-sound test) con el volumen de la demo ---------------- */
  let actx = null;
  function beep() {
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      if (actx.state === "suspended") actx.resume();
      if (S.audio.muted) { toast("Demo: el sonido esta silenciado"); return; }
      const t0 = actx.currentTime + 0.02;
      [660, 880].forEach((f, i) => {
        const o = actx.createOscillator(), g = actx.createGain();
        o.frequency.value = f; g.gain.setValueAtTime(0, t0 + i * 0.38);
        g.gain.linearRampToValueAtTime(0.25 * S.audio.volume / 100, t0 + i * 0.38 + 0.05); g.gain.linearRampToValueAtTime(0, t0 + i * 0.38 + 0.34);
        o.connect(g); g.connect(actx.destination); o.start(t0 + i * 0.38); o.stop(t0 + i * 0.38 + 0.36);
      });
    } catch (e) {}
  }

  /* ---------------- datos de ejemplo ---------------- */
  const dayStr = off => { const d = new Date(Date.now() + off * 864e5); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
  function weather() {
    const h0 = new Date().getHours(), codes = [1, 61, 61, 61, 1, 1, 1, 1, 1, 1, 1, 1];
    const hourly = codes.map((c, i) => ({ h: pad((h0 + i) % 24) + ":00", temp: Math.round((21.5 + 2.6 * Math.sin((i - 3) / 3.8)) * 10) / 10, rain: c === 61 ? 70 : 10, code: c }));
    const days = [[25, 18, 70, 61], [23, 17, 20, 2], [22, 16, 5, 2], [24, 17, 0, 0], [24, 18, 10, 1]].map((d, i) => ({ date: dayStr(i + 1), tmax: d[0], tmin: d[1], rain: d[2], code: d[3] }));
    return { ok: true, city: LS.get("city", "Las Palmas de Gran Canaria"), temp: 21.4, code: 1, tmax: 24.1, tmin: 17.6, rain: 10, hourly, days, rain_alert: { in_hours: 1, prob: 70 } };
  }
  function calendar() {
    const d = new Date(Date.now() + 3 * 3600e3);
    return { configured: true, ok: true, error: null, loaded: true, events: [
      { when: "Hoy", time: pad(d.getHours()) + ":" + pad(d.getMinutes()), title: "Dentista", location: "Calle Mayor 1", all_day: false, date: dayStr(0) },
      { when: "Mañana", time: "", title: "Cumple de Ana", location: "", all_day: true, date: dayStr(1) },
      { when: "Jueves", time: "18:30", title: "Clase de guitarra", location: "", all_day: false, date: dayStr(3) },
    ] };
  }
  const CITIES = [{ name: "Las Palmas de Gran Canaria", region: "Canarias", country: "España", lat: 28.1248, lon: -15.43 }, { name: "Madrid", region: "Comunidad de Madrid", country: "España", lat: 40.4165, lon: -3.7026 },
    { name: "Santa Cruz de Tenerife", region: "Canarias", country: "España", lat: 28.4682, lon: -16.2546 }, { name: "Barcelona", region: "Cataluña", country: "España", lat: 41.3888, lon: 2.159 },
    { name: "Sevilla", region: "Andalucía", country: "España", lat: 37.3826, lon: -5.9963 }, { name: "Ciudad de México", region: "CDMX", country: "México", lat: 19.4285, lon: -99.1277 }];
  const NETS = [{ ssid: "CasaIker", signal: 82, secure: true }, { ssid: "Hotel:Canarias", signal: 64, secure: false }, { ssid: "Vecino", signal: 40, secure: true }];
  function wifiInfo() {
    const a = S.wifi.active;
    return { available: true, active: a ? { name: a, type: "wifi", device: "wlan0", ssid: a } : null, connectivity: a ? "full" : "none", dns: a && S.wifi.wantsPi[a] ? "pihole" : "router", portal: false,
      wants_pihole: !!(a && S.wifi.wantsPi[a]), saved: Object.keys(S.wifi.wantsPi), networks: NETS.map(n => ({ ...n, active: n.ssid === a })), nets: {} };
  }
  function displayInfo() {
    const d = S.display, h = new Date().getHours(), night = h >= 22 || h < 7;
    return { level: d.level, auto: d.auto, effective: d.auto && night ? 40 : d.level, night_from: 22, night_to: 7, night_level: 40, ramp: 60, hw: { present: false, writable: false } };
  }
  function motionInfo() { return { available: true, enabled: S.motion, last: null, count: 0 }; }
  function timersList() {
    const now = Date.now();
    const out = S.timers.map(t => ({ id: t.id, kind: t.kind, label: t.label || "", due: t.due / 1000, remaining: Math.max(0, Math.ceil((t.due - now) / 1000)), ringing: now >= t.due, hour: t.hour, minute: t.minute, daily: !!t.daily }));
    return out.sort((a, b) => (b.ringing - a.ringing) || (a.due - b.due));
  }
  function systemInfo() {
    const u = S.update;
    return { disk: { free_gb: 21.4, total_gb: 58.0, pct: 63 }, mem_avail_mb: 5120, update: { available: u.available, behind: u.behind, checked: Date.now() / 1000 - 3600 },
      health: [{ level: "ok", text: "Todo en orden (es una demo: estos datos son de ejemplo)." }], update_run: { state: u.state, tail: u.tail } };
  }
  function status() {
    const ph = S.pihole;
    if (!ph.blocking && ph.until && Date.now() > ph.until) ph.blocking = true;
    const t = Math.round((46 + 4 * Math.sin((Date.now() - T0) / 20000)) * 10) / 10;
    return {
      mode: LS.get("mode", "home"), cpu_temp: t, uptime: Math.floor((Date.now() - T0) / 1000) + 320,
      pihole: { ok: true, blocking: ph.blocking ? "enabled" : "disabled", total: 1211 + Math.floor((Date.now() - T0) / 4000), blocked: 326 + Math.floor((Date.now() - T0) / 14000), percent: 26.9, domains: 168432 },
      version: "demo", weather: weather(), nowplaying: S.nowplaying, voice: S.voice, camera: { available: true, show: S.camera },
      net: S.wifi.active ? { available: true, name: S.wifi.active, ssid: S.wifi.active, type: "wifi", connectivity: "full", portal: false, dns: S.wifi.wantsPi[S.wifi.active] ? "pihole" : "router" }
                         : { available: true, name: null, connectivity: "none", portal: false },
      display: displayInfo(), motion: motionInfo(), battery: { available: true, percent: 76, charging: false, low: false, critical: false },
      timers: timersList(), ai: { enabled: false, model: "qwen2.5:1.5b" }, calendar: calendar(),
      music: { seq: S.music.seq, cmd: S.music.cmd, arg: S.music.arg, embed: LS.get("embed", null), history: LS.get("history", []), search: false },
      audio: { available: true, volume: S.audio.volume, muted: S.audio.muted },
      dev: { enabled: true, flags: S.flags }, system: systemInfo(), ip: "192.0.2.10", host: "picore-demo",
    };
  }

  /* ---------------- notas, marcadores ---------------- */
  function notes() {
    let n = LS.get("notes", null);
    if (!n) {
      const t = Date.now() / 1000;
      n = [{ id: "a1b2c3d4e5f60718", text: "Bienvenido a PiCore (demo)\nEsto es el bloc de notas del modo Iker. Prueba a escribir, a usar #etiquetas y a buscar.\n#demo #bienvenida", updated: t - 60 },
           { id: "0f9e8d7c6b5a4321", text: "Lista de la compra\n- leche\n- pan\n- café\n#compra", updated: t - 3600 }];
      LS.set("notes", n);
    }
    return n;
  }
  const norm = s => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/-/g, " ");
  const title = t => (t.split("\n").find(l => l.trim()) || "Nota sin título").trim().slice(0, 60);
  const tagsOf = t => { const out = []; for (const m of t.matchAll(/(?<![\w#&/])#([^\W\d_][\w-]{0,29})/g)) { const g = norm(m[1]).replace(/^-+|-+$/g, ""); if (g && !out.includes(g)) out.push(g); } return out.slice(0, 20); };
  const listNotes = () => notes().slice().sort((a, b) => (!!b.pinned - !!a.pinned) || (b.updated - a.updated)).map(n => ({ id: n.id, title: title(n.text), updated: n.updated, tags: tagsOf(n.text), pinned: n.pinned === true }));
  function searchNotes(q) {
    const words = norm(q).split(/\s+/).filter(Boolean);
    return notes().filter(n => words.every(w => norm(n.text).includes(w))).sort((a, b) => b.updated - a.updated).map(n => {
      const pos = Math.max(0, norm(n.text).indexOf(words[0]) - 30);
      return { id: n.id, title: title(n.text), updated: n.updated, snippet: n.text.slice(pos, pos + 90).replace(/\s+/g, " "), tags: tagsOf(n.text) };
    });
  }

  /* ---------------- YouTube: enlace -> reproductor incrustado (mismas reglas que home/musix.py) ---------------- */
  function embedUrl(link) {
    let u; try { u = new URL(String(link || "").trim()); } catch (e) { throw new Error("Pega un enlace https de YouTube o YouTube Music"); }
    if (u.protocol !== "https:" || u.username || (u.port && u.port !== "443")) throw new Error("Pega un enlace https de YouTube o YouTube Music");
    const host = u.hostname.toLowerCase(), q = u.searchParams; let vid = null, lst = null;
    if (host === "youtu.be") vid = u.pathname.split("/").filter(Boolean)[0];
    else if (["www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com", "www.youtube-nocookie.com"].includes(host)) {
      const p = u.pathname.split("/").filter(Boolean);
      if (p[0] === "embed" && p[1] && p[1] !== "videoseries") vid = p[1]; else if ((p[0] === "shorts" || p[0] === "live") && p[1]) vid = p[1]; else vid = q.get("v");
      lst = q.get("list");
    } else throw new Error("Ese enlace no es de YouTube ni de YouTube Music");
    const okV = /^[A-Za-z0-9_-]{11}$/, okL = /^[A-Za-z0-9_-]{10,60}$/;
    if (vid && okV.test(vid)) return "https://www.youtube-nocookie.com/embed/" + vid + (lst && okL.test(lst) ? "?list=" + lst : "");
    if (lst && okL.test(lst)) return "https://www.youtube-nocookie.com/embed/videoseries?list=" + lst;
    throw new Error("No encuentro un video ni una lista de YouTube en ese enlace");
  }

  /* ---------------- consola Dev de mentira ---------------- */
  const DOCTOR = "PiCore · diagnóstico (DEMO: datos de ejemplo)\n\nSistema\n  ok  Raspberry Pi 5 Model B Rev 1.0 (8 GB)\n  ok  Raspberry Pi OS (Bookworm)\n  ok  temperatura 47 °C\nServidor\n  ok  pcpi-home activo en 127.0.0.1:8080\n  ok  Pi-hole responde\nWi-Fi\n  ok  conectado a CasaIker (internet OK)\nMusica\n  ok  Musix: 3 canciones en el MP3 Player\n\nTodo en orden.\n";
  function fakeShell(raw) {
    const cmd = raw.trim(), a = cmd.split(/\s+/);
    const R = (out, code) => ({ out, code: code || 0 });
    switch (a[0]) {
      case "help": case "ayuda": return R("Esto es una DEMO: la consola no ejecuta nada real, solo reconoce unas pocas órdenes:\n  pcpi-doctor  pcpi-mode status  pcpi-sound status  pcpi-wifi status  pcpi-update --check  pcpi-config get SECCION CLAVE  pcpi-config show  uname -a  uptime  df -h /  free -m\n  vcgencmd measure_temp  date  whoami  hostname  ls  echo TEXTO  cat /etc/os-release\nEn una Pi real, aquí va cualquier orden.\n");
      case "echo": return R(cmd.slice(4).trim().replace(/^(["'])(.*)\1$/, "$2") + "\n");
      case "pcpi-doctor": return R(DOCTOR);
      case "pcpi-sound": return R(a[1] === "status" ? '{"available": true, "volume": ' + S.audio.volume + ', "muted": ' + !!S.audio.muted + ', "backend": "demo"}\n' : "demo: sin cambios\n");
      case "pcpi-wifi": return R("Wi-Fi: " + (S.wifi.active || "sin conexión") + " (demo)\n");
      case "pcpi-update": return R(a[1] === "--check" ? "Hay 3 cambios nuevos (demo)\n" : "demo: no se actualiza nada\n");
      case "pcpi-mode": return R(LS.get("mode", "home") + "\n");
      case "pcpi-config": if (a[1] === "show") return R("[server]\nhost = 127.0.0.1\nport = 8080\n[pihole]\nurl = http://localhost\npassword = ******\n[weather]\ncity = " + LS.get("city", "Las Palmas de Gran Canaria") + "\n"); return R(a[1] === "get" ? (a[2] === "server" && a[3] === "port" ? "8080\n" : "\n") : "demo: sin cambios\n");
      case "uname": return R("Linux picore-demo 6.6.31+rpt-rpi-2712 #1 SMP PREEMPT Debian aarch64 GNU/Linux\n");
      case "uptime": return R(" " + new Date().toTimeString().slice(0, 8) + " up 3 days, 4:12,  1 user,  load average: 0.21, 0.18, 0.15\n");
      case "df": return R("S.ficheros      Tamaño Usados  Disp Uso% Montado en\n/dev/mmcblk0p2    58G    37G   21G  63% /\n");
      case "free": return R("               total       usado       libre  compartido  búf/caché  disponible\nMem:            7940        1980        3410          86        2790        5120\nSwap:            512           0         512\n");
      case "vcgencmd": return R(a[1] === "measure_temp" ? "temp=47.2'C\n" : a[1] === "get_throttled" ? "throttled=0x0\n" : "demo\n");
      case "date": return R(new Date().toString() + "\n");
      case "whoami": return R("pi\n");
      case "hostname": return R("picore-demo\n");
      case "pwd": return R("/home/pi\n");
      case "ls": return R(a[1] === "/var/lib/pcpi/music" ? SONGS.map(s => s.title + ".wav").join("\n") + "\n" : "Descargas  Documentos  Música  pcpi-backups\n");
      case "cat": return a[1] === "/etc/os-release" ? R('PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\n') : R("cat: " + (a[1] || "") + ": demo, sin acceso a archivos\n", 1);
      case "sudo": return R("sudo: en la demo no hay permisos de administrador\n", 1);
      default: return R("bash: " + a[0] + ": orden no encontrada (esto es una demo: escribe «help»)\n", 127);
    }
  }

  /* ---------------- API ---------------- */
  const J = (obj, status) => new Response(JSON.stringify(obj), { status: status || 200, headers: { "Content-Type": "application/json" } });
  const ERR = (msg, status) => J({ error: msg }, status || 400);
  const navigateAfter = (url, ms) => setTimeout(() => { location.href = url; }, ms || 450);

  async function api(u, init) {
    const method = (init.method || "GET").toUpperCase(), p = u.pathname;
    let body = {};
    if (method === "POST") { try { body = JSON.parse(init.body || "{}") || {}; } catch (e) { return ERR("peticion invalida"); } }

    if (p === "/api/status") return J(status());
    if (p === "/api/alive") return J({ ok: true });
    if (p === "/api/mode") {
      if (method === "GET") return J({ mode: LS.get("mode", "home") });
      if (!["home", "iker", "desktop", "dev"].includes(body.mode)) return ERR("modo invalido");
      LS.set("mode", body.mode);
      if (here !== "/loading") navigateAfter("/loading?to=" + body.mode + "&boot=0", 350);
      return J({ mode: body.mode });
    }
    if (p === "/api/loaded") {                                  // en la Pi, pcpi-session abre la ventana del modo; aqui navegamos
      const m = body.mode;
      if (m === "iker") navigateAfter("/iker", 100); else if (m === "dev") navigateAfter("/dev", 100);
      else if (m === "desktop") navigateAfter("/escritorio", 100);
      return J({ ok: true });
    }
    if (p === "/api/boot") {
      const man = await manifest();
      let intro = null, slot = null;
      if (u.searchParams.get("boot") === "1" && man && man.start && man.start.length) {          // como al encender la Pi: un video de inicio al azar (90 / 85 / 55 de probabilidad)
        const w = man.start.map(v => [90, 85, 55, 1][v.slot - 1] || 1), tot = w.reduce((a, b) => a + b, 0);
        let r = Math.random() * tot, i = 0; while (i < w.length - 1 && (r -= w[i]) > 0) i++;
        intro = man.start[i].url; slot = man.start[i].slot;
      }
      const media = man && man.loading && man.loading.length ? man.loading : BOOT_MEDIA;
      return J({ download: null, intro, intro_slot: slot, intro_skip_after: 0, media, fake: true, fake_seconds: 5, min_seconds: 3, skip_button: true, media_seconds: 2.5 });
    }
    if (p === "/api/download") return J({ state: "done", bytes: 0, total: 0, percent: 100, error: null });

    if (p === "/api/pihole") {
      if (body.action === "disable") { S.pihole = { blocking: false, until: Date.now() + Math.max(1, Math.min(+body.minutes || 5, 1440)) * 60000 }; }
      else if (body.action === "enable") S.pihole = { blocking: true, until: 0 };
      else return ERR("accion invalida");
      return J({ ok: true });
    }
    if (p === "/api/camera/snapshot.jpg") return ERR("sin camara en la demo", 404);
    if (p === "/api/camera") { S.camera = !!body.show; return J({ show: S.camera }); }
    if (p === "/api/display") {
      if (typeof body.level === "number") S.display.level = Math.max(10, Math.min(100, Math.round(body.level)));
      if (typeof body.auto === "boolean") S.display.auto = body.auto;
      LS.set("display", S.display); return J(displayInfo());
    }
    if (p === "/api/motion") { if (typeof body.enabled !== "boolean") return ERR("enabled invalido"); S.motion = body.enabled; LS.set("motion", S.motion); return J(motionInfo()); }
    if (p === "/api/screensaver") { const man = await manifest(); return J({ enabled: true, idle_seconds: 300, seconds_per_photo: 8, clock: true, shuffle: true, photos: man && man.photos && man.photos.length ? man.photos : SAVER }); }

    if (p === "/api/timers") {
      const now = Date.now();
      if (body.action === "timer") { const s = +body.seconds; if (!(s >= 1 && s <= 86400)) return ERR("tiempo invalido"); S.timers.push({ id: rid(8), kind: "timer", label: String(body.label || "").slice(0, 40), due: now + s * 1000 }); }
      else if (body.action === "extend") { const s = +body.seconds; const c = S.timers.filter(t => t.kind === "timer" && now < t.due && (!body.id || t.id === body.id)).sort((x, y) => x.due - y.due)[0]; if (!(s >= 1 && s <= 172800)) return ERR("tiempo invalido"); if (!c) return ERR("No hay ningun temporizador en marcha"); c.due += s * 1000; }
      else if (body.action === "alarm") { const d = new Date(); d.setHours(+body.hour, +body.minute, 0, 0); if (d.getTime() <= now) d.setDate(d.getDate() + 1); S.timers.push({ id: rid(8), kind: "alarm", label: String(body.label || ""), due: d.getTime(), hour: +body.hour, minute: +body.minute, daily: body.daily === true }); }
      else if (body.action === "cancel") S.timers = S.timers.filter(t => body.id && t.id !== body.id);
      else if (body.action === "dismiss") S.timers = S.timers.filter(t => now < t.due);
      else return ERR("accion invalida");
      LS.set("timers", S.timers); return J({ ok: true, timers: timersList() });
    }

    if (p === "/api/system") {
      if (method === "GET") return J(systemInfo());
      if (body.action === "shutdown" || body.action === "reboot") { toast("Demo: aquí se " + (body.action === "reboot" ? "reiniciaría" : "apagaría") + " la Pi. No se hace nada."); return J({ ok: true, action: body.action }); }
      if (body.action === "check") { toast("Demo: comprobando actualizaciones…"); return J({ ok: true }); }
      if (body.action === "update") {
        if (S.update.state === "running") return J({ ok: true });
        S.update.state = "running"; S.update.tail = ["Descargando 3 cambio(s)…"];
        (async () => {
          for (const l of ["Copia de seguridad previa en ~/pcpi-backups", "Reinstalando con tus opciones: --camera --voice", "==> Copiando archivos", "==> Reiniciando servicios"]) { await sleep(1100); S.update.tail.push(l); }
          await sleep(1100); S.update.tail.push("Actualizado (simulado)."); S.update.state = "ok"; S.update.available = false; S.update.behind = 0;
        })();
        return J({ ok: true, action: "update" });
      }
      return ERR("accion invalida");
    }
    if (p === "/api/audio") {                                   // el volumen es de mentira, pero «Probar sonido» suena de verdad (WebAudio)
      if (body.action === "volume") {
        const v = String(body.value); if (!/^[+-]?\d{1,3}$/.test(v)) return ERR("volumen invalido");
        S.audio.volume = Math.max(0, Math.min(100, /^[+-]/.test(v) ? S.audio.volume + parseInt(v, 10) : parseInt(v, 10)));
      } else if (body.action === "mute" || body.action === "unmute") S.audio.muted = body.action === "mute";
      else if (body.action === "test") beep();
      else return ERR("accion invalida");
      LS.set("audio", S.audio); return J({ ok: true });
    }
    const prefs = () => Object.assign({ screensaver: true, idle_minutes: 5, night_from: 22, night_to: 7, night_level: 40 }, LS.get("prefs", {}));
    if (p === "/api/settings") {                                // ciudad del tiempo: lista de ejemplo (la demo no usa internet)
      if (body.action === "city_search") {
        const q = norm(String(body.q || "").trim());
        if (q.length < 2) return ERR("Escribe al menos 2 letras del nombre de la ciudad", 502);
        return J({ results: CITIES.filter(c => norm(c.name).includes(q)).slice(0, 6) });
      }
      if (body.action === "city_set") {
        const lat = body.lat, lon = body.lon;
        if (typeof lat !== "number" || typeof lon !== "number" || !(lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180)) return ERR("peticion invalida");
        LS.set("city", String(body.name || "").replace(/[\x00-\x1f#;=\[\]]/g, " ").trim().slice(0, 60)); return J({ ok: true, lat, lon, city: LS.get("city", "") });
      }
      if (body.action === "pihole_set") {
        const pw = body.password; if (typeof pw !== "string" || !pw || pw.length > 128 || pw !== pw.trim()) return ERR("contraseña no valida");
        return J({ ok: pw !== "mala" });
      }
      if (body.action === "prefs_get") return J({ prefs: prefs() });
      if (body.action === "pref_set") {
        const lim = { idle_minutes: [1, 120], night_from: [0, 23], night_to: [0, 23], night_level: [10, 100] }, k = body.key, v = body.value;
        if (k === "screensaver") { if (typeof v !== "boolean") return ERR("valor invalido"); }
        else if (lim[k]) { if (typeof v !== "number" || v !== v) return ERR("valor invalido"); }
        else return ERR("ajuste no permitido");
        const P = prefs(); P[k] = lim[k] ? Math.max(lim[k][0], Math.min(lim[k][1], k === "idle_minutes" ? v : Math.round(v))) : v;
        LS.set("prefs", P); return J({ ok: true, prefs: P });
      }
      return ERR("accion invalida");
    }
    if (p === "/api/ask") return J({ error: "La IA local no está disponible en la demo (en una Pi real se instala con ./install.sh --ai)." }, 503);

    /* wifi */
    if (p === "/api/wifi") return J(wifiInfo());
    if (p === "/api/wifi/connect") {
      await sleep(900);
      const n = NETS.find(x => x.ssid === body.ssid);
      if (!n && body.hidden !== true) return ERR("No encuentro esa red");
      if (n && n.secure && body.password === "mala") return ERR("Contraseña incorrecta");
      if (n && n.secure && !body.password && !(body.ssid in S.wifi.wantsPi)) return ERR("Esa red necesita contraseña");
      S.wifi.active = body.ssid; if (!(body.ssid in S.wifi.wantsPi)) S.wifi.wantsPi[body.ssid] = true; LS.set("wifi", S.wifi); return J({ ok: true });
    }
    if (p === "/api/wifi/forget") { delete S.wifi.wantsPi[body.ssid]; if (S.wifi.active === body.ssid) S.wifi.active = null; LS.set("wifi", S.wifi); return J({ ok: true }); }
    if (p === "/api/wifi/pihole") { S.wifi.wantsPi[body.ssid] = !!body.on; LS.set("wifi", S.wifi); return J({ ok: true }); }
    if (p === "/api/wifi/portal") { toast("Demo: aquí se abriría la ventana de inicio de sesión de la wifi."); return J({ ok: true }); }

    /* notas */
    if (p === "/api/notes" && method === "GET") { const q = u.searchParams.get("q") || ""; return J(q.trim() ? searchNotes(q) : listNotes()); }
    if (p === "/api/notes" && method === "POST") {
      if (typeof body.text !== "string" || body.text.length > 200000) return ERR("texto invalido o demasiado grande");
      const all = notes(); let id = body.id;
      const n = id && all.find(x => x.id === id);
      const pin = typeof body.pinned === "boolean" ? body.pinned : undefined;
      if (n) { n.text = body.text; n.updated = Date.now() / 1000; if (pin !== undefined) n.pinned = pin; } else { id = rid(16); all.push({ id, text: body.text, updated: Date.now() / 1000, pinned: pin === true }); }
      LS.set("notes", all); return J({ id });
    }
    if (p === "/api/notes/delete") { LS.set("notes", notes().filter(n => n.id !== body.id)); return J({ ok: true }); }
    if (p === "/api/notes/tags") { const c = {}; listNotes().forEach(n => n.tags.forEach(t => { c[t] = (c[t] || 0) + 1; })); return J(Object.entries(c).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).map(([tag, count]) => ({ tag, count }))); }
    if (p === "/api/notes/usb") return J({ usb: [] });
    if (p === "/api/notes/export") return ERR("No veo ningún USB conectado (en la demo no hay USB).");
    const nm = /^\/api\/notes\/([0-9a-f]{16})$/.exec(p);
    if (nm) { const n = notes().find(x => x.id === nm[1]); return n ? J({ id: n.id, text: n.text, updated: n.updated, pinned: n.pinned === true }) : ERR("nota no encontrada", 404); }

    if (p === "/api/bookmarks") {
      if (method === "GET") return J(LS.get("bookmarks", []));
      let items = LS.get("bookmarks", []);
      if (body.action === "add") {
        let url = String(body.url || "").trim();
        if (!url || /\s/.test(url) || url.length > 500) return ERR("enlace invalido");
        if (!/:\/\//.test(url)) { if (/^[a-z][a-z0-9+.-]*:(?!\d)/i.test(url)) return ERR("solo se admiten enlaces http o https"); url = "https://" + url; }
        let x; try { x = new URL(url); } catch (e) { return ERR("enlace invalido"); }
        if (!["http:", "https:"].includes(x.protocol) || !x.hostname) return ERR("solo se admiten enlaces http o https");
        items = items.filter(b => b.url !== url); items.push({ id: rid(8), title: String(body.title || "").trim().slice(0, 40) || x.hostname.replace(/^www\./, ""), url });
      } else if (body.action === "delete") items = items.filter(b => b.id !== body.id);
      else return ERR("accion invalida");
      LS.set("bookmarks", items); return J(items);
    }

    /* musica */
    if (p === "/api/music" && method === "GET") return J({ tracks: tracks(), seq: S.music.seq, cmd: S.music.cmd, arg: S.music.arg, embed: LS.get("embed", null), history: LS.get("history", []), search: false });
    if (p === "/api/music" && method === "POST") {
      const act = body.action;
      if (act === "cmd") { if (!["play", "pause", "next", "previous", "sleep"].includes(body.cmd)) return ERR("orden invalida"); S.music = { seq: S.music.seq + 1, cmd: body.cmd, arg: body.cmd === "sleep" ? body.seconds : null }; return J({ ok: true, seq: S.music.seq }); }
      if (act === "now") { S.nowplaying = { state: body.state, title: String(body.title || "").slice(0, 120), artist: String(body.artist || "").slice(0, 80) }; return J({ ok: true }); }
      if (act === "embed") {
        if (!body.link) { LS.set("embed", null); return J({ ok: true, url: null, history: LS.get("history", []) }); }
        try {
          const url = embedUrl(body.link); LS.set("embed", url);
          const h = LS.get("history", []).filter(x => x.url !== url); h.unshift({ url, title: String(body.title || "").slice(0, 80) }); LS.set("history", h.slice(0, 8));
          return J({ ok: true, url, history: LS.get("history", []) });
        } catch (e) { return ERR(e.message, 502); }
      }
      if (act === "search") return ERR("En la demo no hay búsqueda (necesita una clave de la API de YouTube). Pega el enlace de una canción.", 502);
      if (act === "web") { toast("Demo: aquí se abriría la web de descarga en otra ventana. No se descarga nada."); return J({ ok: true, url: "demo" }); }
      if (act === "delete") { tracks(); S.tracks = S.tracks.filter(t => t.id !== body.id); return J({ ok: true }); }
      if (act === "import_usb") return ERR("No veo ningún USB conectado (en la demo no hay USB).", 502);
      return ERR("accion invalida");
    }

    /* modo dev */
    if (p === "/api/dev") {
      if (method === "GET") {
        const id = u.searchParams.get("id");
        if (id) { const c = S.cmds[id]; if (!c) return ERR("Esa orden ya no existe", 404); const done = Date.now() >= c.at; return J({ done, code: done ? c.code : null, out: done ? c.out : "", truncated: false, queued: false }); }
        return J({ enabled: true, mode: LS.get("mode", "home"), flags: S.flags, experiments: [
          { id: "ai_chat", title: "Chat con la IA", desc: "Un chat en esta consola con la IA local (necesita ./install.sh --ai)." },
          { id: "live_graph", title: "Gráfica en vivo", desc: "Temperatura de la CPU y memoria libre en directo." },
          { id: "voice_log", title: "Lo último que oyó la voz", desc: "Muestra en esta consola lo que entendió el asistente y lo que contestó (útil para ajustar el micrófono)." },
          { id: "casa_debug", title: "Insignia de depuración en Casa", desc: "Muestra en la pantalla de Casa cuánto tarda el servidor en responder." }] });
      }
      if (body.action === "run") {
        if (typeof body.cmd !== "string" || !body.cmd.trim()) return ERR("escribe una orden");
        const id = rid(16), r = fakeShell(body.cmd); S.cmds[id] = { ...r, at: Date.now() + 500 }; return J({ id });
      }
      if (body.action === "terminal") { toast("Demo: aquí se abriría un terminal real."); return J({ ok: true }); }
      if (body.action === "flag") { if (!(body.id in S.flags) || typeof body.on !== "boolean") return ERR("valor invalido"); S.flags[body.id] = body.on; LS.set("flags", S.flags); return J({ flags: S.flags }); }
      return ERR("accion invalida");
    }
    return ERR("no encontrado en la demo", 404);
  }

  const svgData = (a, b, label) => "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="' + a + '"/><stop offset="1" stop-color="' + b + '"/></linearGradient></defs><rect width="1280" height="720" fill="url(#g)"/><text x="640" y="380" text-anchor="middle" fill="#ffffffcc" font-family="system-ui,sans-serif" font-size="64" font-weight="700">' + label + '</text></svg>');
  const BOOT_MEDIA = [{ type: "image", url: svgData("#1b2a4a", "#4a1f5a", "PiCore") }, { type: "image", url: svgData("#0f3d3e", "#1b2a4a", "Iniciando") }, { type: "image", url: svgData("#4a2a1b", "#5a1f3a", "Casi listo") }];
  const SAVER = [svgData("#1b2a4a", "#3a1f5a", "Marco de fotos"), svgData("#0f3d3e", "#2a4a1b", "Tus fotos aqui"), svgData("#4a2a1b", "#1f3a5a", "Salvapantallas")];

  const realFetch = window.fetch.bind(window);
  /* videos, GIFs e imagenes REALES de extra-assets (los copia tools/build_web_demo.py); si faltan, se usan dibujos generados */
  let manifestP = null;
  const manifest = () => manifestP || (manifestP = realFetch("/assets/manifest.json").then(r => (r.ok ? r.json() : null)).catch(() => null));
  window.fetch = function (input, init) {
    try {
      const url = new URL(typeof input === "string" ? input : input.url, location.href);
      if (url.origin === location.origin && (url.pathname.startsWith("/api/"))) {
        const i = init || (typeof input === "object" && input.method ? { method: input.method } : {});
        return api(url, i).catch(e => ERR("error en la demo: " + e.message, 500));
      }
    } catch (e) {}
    return realFetch(input, init);
  };

  /* ---------------- voz simulada: escribes lo que dirias y la «Pi» contesta (y habla, si tu navegador sabe) ---------------- */
  const WORDS = { un: 1, uno: 1, una: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10, once: 11, doce: 12, trece: 13, catorce: 14, quince: 15, dieciseis: 16,
    diecisiete: 17, dieciocho: 18, diecinueve: 19, veinte: 20, treinta: 30, cuarenta: 40, cincuenta: 50, sesenta: 60 };
  const RESPUESTAS = [
    [["como te llamas", "quien eres", "cual es tu nombre"], "Soy PiCore, el asistente de tu Raspberry Pi. Todo lo que hago, lo hago aquí, sin nube"],
    [["estas ahi", "me oyes", "me escuchas"], "Sí, te oigo"],
    [["buenas noches"], "Buenas noches. Que descanses"],
    [["te quiero", "eres la mejor"], "Gracias, yo también te aprecio. Soy una Pi, pero se agradece"],
    [["cuantos anos tienes", "cuando naciste"], "Soy software: nací cuando me instalaste"],
  ];
  function duration(t) {                                            // «diez minutos», «5 min», «media hora», «una hora y media» -> segundos
    if (/media hora/.test(t) && !/hora y media/.test(t)) return 1800;
    const m = /(\d+|[a-z]+)\s*(segundos?|minutos?|min|horas?)\b/.exec(t); if (!m) return null;
    const n = /^\d+$/.test(m[1]) ? parseInt(m[1], 10) : WORDS[m[1]]; if (!n) return null;
    let sec = n * (/^seg/.test(m[2]) ? 1 : /^h/.test(m[2]) ? 3600 : 60);
    if (/hora y media/.test(t)) sec += 1800;
    return sec;
  }
  function sayDuration(sec) {
    const h = Math.floor(sec / 3600), mi = Math.floor(sec % 3600 / 60), se = sec % 60, out = [];
    if (h) out.push(h === 1 ? "una hora" : h + " horas"); if (mi) out.push(mi === 1 ? "un minuto" : mi + " minutos"); if (se || !out.length) out.push(se === 1 ? "un segundo" : se + " segundos");
    return out.join(" y ");
  }
  function understand(text) {
    const t = norm(text).replace(/^(oye pi|hey jarvis|ok pi)[,\s]*/, "").trim(), has = (...k) => k.some(x => t.includes(x)), now = new Date();
    if (!t) return "Dime algo, por ejemplo: qué hora es";
    const lm2 = /^(?:por favor )?(?:anade|añade|apunta|pon|mete|agrega)\s+(.{2,80}?)\s+(?:a|en)\s+(?:la\s+)?lista(?:\s+de\s+(?:la\s+)?(compra|compras|tareas|pendientes))?$/i.exec(String(text).replace(/^(oye pi|hey jarvis|ok pi)[,\s]*/i, "").trim().replace(/[\s.!?¡¿]+$/, ""));
    if (lm2) {
      const ttl = /tareas|pendientes/i.test(lm2[2] || "") ? "Tareas" : "Lista de la compra", all = notes(), f = all.find(n => norm(title(n.text)) === norm(ttl));
      if (f) { f.text = f.text.replace(/\n+$/, "") + "\n- " + lm2[1].trim() + "\n"; f.updated = Date.now() / 1000; } else all.push({ id: rid(16), text: ttl + "\n- " + lm2[1].trim() + "\n", updated: Date.now() / 1000, pinned: false });
      LS.set("notes", all); return "Añadido " + lm2[1].trim() + " a " + (ttl === "Tareas" ? "tus tareas" : "la lista de la compra");
    }
    if (/\b(lee|leeme|que hay en|que tengo en|dime) (?:la |mi |mis )?(?:lista|tareas|pendientes)/.test(t) && !has("anade", "apunta")) {
      const ttl = has("tareas", "pendientes") ? "Tareas" : "Lista de la compra", f = notes().find(n => norm(title(n.text)) === norm(ttl));
      const items = f ? f.text.split("\n").filter(l => l.startsWith("- ") && l.slice(2).trim()).map(l => l.slice(2).trim()) : [], nombre = ttl === "Tareas" ? "tus tareas" : "la lista de la compra";
      return items.length ? "En " + nombre + ": " + items.slice(0, 12).join(", ") + (items.length > 12 ? " y " + (items.length - 12) + " más" : "") : "No tienes nada en " + nombre;
    }
    const nm = /^(?:por favor )?(?:toma nota|apunta|anota|apuntame|anotame|guarda una nota)(?: de| que| lo siguiente)?[ :,]+(.{2,400})$/i.exec(String(text).replace(/^(oye pi|hey jarvis|ok pi)[,\s]*/i, "").trim().replace(/[\s.!?¡¿]+$/, ""));
    if (nm) { const all = notes(); all.push({ id: rid(16), text: nm[1].trim(), updated: Date.now() / 1000, pinned: false }); LS.set("notes", all); return "Anotado"; }
    if (has("a que wifi", "que wifi", "a que red", "tengo internet", "hay internet", "estoy conectad")) return S.wifi.active ? "Estoy conectada a la wifi " + S.wifi.active + " y hay internet" : "No estoy conectada a ninguna red";
    if (has("que suena", "que cancion es", "como se llama esta cancion", "que estoy escuchando")) { const np = S.nowplaying; return np && np.title && np.state !== "stopped" ? (np.state === "playing" ? "Suena " : "Está en pausa ") + np.title : "Ahora no suena nada"; }
    if (has("que hora es en", "hora en ")) {
      const CT = { "madrid": ["Europe/Madrid", "Madrid"], "canarias": ["Atlantic/Canary", "Canarias"], "las palmas": ["Atlantic/Canary", "Las Palmas"], "londres": ["Europe/London", "Londres"], "paris": ["Europe/Paris", "París"], "berlin": ["Europe/Berlin", "Berlín"], "roma": ["Europe/Rome", "Roma"], "nueva york": ["America/New_York", "Nueva York"], "los angeles": ["America/Los_Angeles", "Los Ángeles"], "mexico": ["America/Mexico_City", "México"], "buenos aires": ["America/Argentina/Buenos_Aires", "Buenos Aires"], "tokio": ["Asia/Tokyo", "Tokio"], "pekin": ["Asia/Shanghai", "Pekín"], "dubai": ["Asia/Dubai", "Dubái"], "sidney": ["Australia/Sydney", "Sídney"] };
      for (const k in CT) if (t.includes(k)) {
        const parts = new Intl.DateTimeFormat("es-ES", { timeZone: CT[k][0], hour: "numeric", minute: "numeric", hour12: false }).formatToParts(new Date()), h = +parts.find(p => p.type === "hour").value % 24, m = +parts.find(p => p.type === "minute").value;
        return "En " + CT[k][1] + " " + (h === 1 ? "es la una" : "son las " + h) + (m ? " y " + m : " en punto");
      }
    }
    const dt = /cuantos dias tiene (?:el mes de |el mes |)(\w+)/.exec(t);
    if (dt) {
      const MS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], k = MS.indexOf(dt[1]);
      if (k >= 0) return dt[1][0].toUpperCase() + dt[1].slice(1) + " tiene " + new Date(now.getFullYear(), k + 1, 0).getDate() + " días";
    }
    const dl = /^deletrea (?:la palabra )?(\w{1,20})$/.exec(t); if (dl) return dl[1].split("").join(", ");
    const rp = /^repite (?:despues de mi|conmigo) (.{1,100})$/.exec(t); if (rp) return rp[1];
    for (const [fr, resp] of RESPUESTAS) if (has(...fr)) return resp;
    if (has("chiste", "hazme reir", "algo gracioso")) { const J = ["¿Qué le dice un cero a un ocho? Bonito cinturón", "¿Por qué los pájaros vuelan hacia el sur? Porque andando tardarían mucho", "¿Qué hace una abeja en el gimnasio? Zum-ba", "¿Cómo se llama el campeón de buceo japonés? Tokofondo", "¿Qué le dice un semáforo a otro? No me mires, que me pongo rojo", "¿Qué hace un perro con un taladro? Taladrando", "Mi ordenador no me hace caso, pero yo a él tampoco"]; return J[Math.floor(Math.random() * J.length)]; }
    const cv = /^(?:pasa|convierte) (\d+) (kilometros|millas|kilos|libras|metros|pies|grados|fahrenheit) a (kilometros|millas|kilos|libras|metros|pies|grados|fahrenheit)$/.exec(t) || (m => m && [m[0], m[2], m[3], m[1]])(/^cuant[oa]s (kilometros|millas|kilos|libras|metros|pies|grados|fahrenheit) son (\d+) (kilometros|millas|kilos|libras|metros|pies|grados|fahrenheit)$/.exec(t));
    if (cv) {
      const F = { "kilometros>millas": x => x * 0.621371, "millas>kilometros": x => x / 0.621371, "kilos>libras": x => x * 2.20462, "libras>kilos": x => x / 2.20462, "metros>pies": x => x * 3.28084, "pies>metros": x => x / 3.28084, "grados>fahrenheit": x => x * 9 / 5 + 32, "fahrenheit>grados": x => (x - 32) * 5 / 9 };
      const f = F[cv[2] + ">" + cv[3]];
      if (f) return cv[1] + " " + cv[2] + " son " + f(+cv[1]).toFixed(1).replace(/\.0$/, "").replace(".", " coma ") + " " + cv[3];
    }
    const pc = /^(?:cuanto (?:es|son)|calcula) el (\d+) por ciento de (\d+)$/.exec(t);
    if (pc) return "Son " + (+pc[1] * +pc[2] / 100).toFixed(2).replace(/\.?0+$/, "").replace(".", " coma ");
    const calc = /^(?:cuanto (?:es|son)|calcula) (\d+) (mas|menos|por|entre|multiplicado por|dividido (?:entre|por)) (\d+)$/.exec(t);
    if (calc) {
      const a = +calc[1], b = +calc[3], o = calc[2];
      if (/^(entre|dividido)/.test(o)) {
        if (!b) return "No se puede dividir entre cero";
        const r = a / b; return "Son " + (Number.isInteger(r) ? r : r.toFixed(2).replace(/0+$/, "").replace(".", " coma "));
      }
      return "Son " + (o === "mas" ? a + b : o === "menos" ? a - b : a * b);
    }
    if (has("tira un dado", "lanza un dado")) return "Ha salido el " + (1 + Math.floor(Math.random() * 6));
    if (has("numero al azar", "numero aleatorio", "numero entre")) {
      const m = /entre (\d+) y (\d+)/.exec(t); let lo = 1, hi = 100; if (m && +m[1] < +m[2]) { lo = +m[1]; hi = +m[2]; }
      return "Ha salido el " + (lo + Math.floor(Math.random() * (hi - lo + 1)));
    }
    if (has("cara o cruz", "tira una moneda", "lanza una moneda")) return "Ha salido " + (Math.random() < 0.5 ? "cara" : "cruz");
    if (has("pospon", "posponer", "cinco minutos mas", "5 minutos mas") && !has("temporizador de")) {
      const r = S.timers.find(x => Date.now() >= x.due);
      if (!r) return "No hay nada sonando";
      const label = r.label || (r.kind === "alarm" ? "Alarma" : "");
      S.timers = S.timers.filter(x => x !== r); S.timers.push({ id: rid(8), kind: "timer", label, due: Date.now() + 300000 }); LS.set("timers", S.timers); return "Pospuesto cinco minutos";
    }
    if (has("avisame", "recuerdame") && duration(t)) {
      const sec = duration(t), m2 = /(?:minutos?|segundos?|horas?)\s+(?:de que |que |para |a |de )?(.{2,40})$/.exec(String(text).toLowerCase().replace(/[\s.,!?¡¿]+$/, "")), label = m2 && !duration(norm(m2[1])) ? m2[1].trim() : "";
      S.timers.push({ id: rid(8), kind: "timer", label, due: Date.now() + sec * 1000 }); LS.set("timers", S.timers); return "Temporizador de " + sayDuration(sec) + (label ? " para " + label : "") + " en marcha";
    }
    if (has("ponle", "ponme") && has("mas") && !has("volumen", "brillo", "musica") && duration(t)) {
      const c = S.timers.filter(x => x.kind === "timer" && Date.now() < x.due).sort((x, y) => x.due - y.due)[0];
      if (!c) return "No hay ningún temporizador en marcha";
      c.due += duration(t) * 1000; LS.set("timers", S.timers); return "Añadido " + sayDuration(duration(t)) + " al temporizador";
    }
    if (has("cuantas notas", "cuantos temporizadores")) {
      const k = has("notas") ? notes().length : S.timers.filter(x => x.kind === "timer").length, w = has("notas") ? ["nota", "notas", "una"] : ["temporizador", "temporizadores", "un"];
      return k === 0 ? (has("notas") ? "No tienes ninguna nota" : "No tienes ningún temporizador") : "Tienes " + (k === 1 ? w[2] : k) + " " + (k === 1 ? w[0] : w[1]);
    }
    if (has("nota") && has("lee", "leeme", "dime", "que pone", "cual es") && has("ultima", "reciente", "anterior")) {
      const all = notes().slice().sort((a, b) => b.updated - a.updated); if (!all.length) return "No tienes ninguna nota";
      const tx = all[0].text.split(/\s+/).join(" "); return "Tu última nota dice: " + (tx.length > 300 ? tx.slice(0, 300) + "…" : tx);
    }
    if (has("proximo evento", "siguiente evento", "proxima cita")) { const ev = calendar().events[0]; return "Tu próximo evento es " + ev.title + ", hoy a las " + ev.time.replace(":", " y "); }
    if (has("cuanto falta para", "dias para") && /navidad|nochevieja|reyes|ano nuevo|verano/.test(t)) {
      const M = { navidad: [11, 25, "la Navidad"], nochevieja: [11, 31, "Nochevieja"], reyes: [0, 6, "los Reyes"], "ano nuevo": [0, 1, "Año Nuevo"], verano: [5, 21, "el verano"] }, k = Object.keys(M).find(x => t.includes(x)), now2 = new Date(), t0 = new Date(now2.getFullYear(), now2.getMonth(), now2.getDate());
      let d = new Date(t0.getFullYear(), M[k][0], M[k][1]); if (d < t0) d = new Date(t0.getFullYear() + 1, M[k][0], M[k][1]);
      const n = Math.round((d - t0) / 864e5); return n === 0 ? "Hoy es " + M[k][2] : n === 1 ? "Falta 1 día para " + M[k][2] : "Faltan " + n + " días para " + M[k][2];
    }
    if (has("repite", "que has dicho") && !has("cancion", "musica")) return S.voice && S.voice.reply ? S.voice.reply : "Todavía no he dicho nada";
    if (has("vigilancia", "movimiento")) { const on = !has("desactiva", "apaga", "quita", "deja de"); S.motion = on; LS.set("motion", on); return on ? "Vigilancia activada" : "Vigilancia desactivada"; }
    if (has("silencia", "silencio", "mute", "quita el sonido", "sin sonido")) { S.audio.muted = !S.audio.muted; LS.set("audio", S.audio); return S.audio.muted ? "Silenciado" : "Sonido activado"; }
    if (has("que puedes hacer", "que sabes hacer", "ayuda", "que comandos")) return "Puedes pedirme la hora, el tiempo, temporizadores y alarmas, la música, el volumen y el brillo, cambiar de modo, tomar notas o decirte cómo está la Pi.";
    if (has("gracias")) return "De nada";
    if (["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hola pi"].includes(t)) return "Hola, dime";
    if (has("cuanto llevas encendida", "cuanto tiempo llevas encendida")) { const mn = Math.max(1, Math.round((Date.now() - T0) / 60000)); return "Llevo encendida " + mn + (mn === 1 ? " minuto" : " minutos"); }
    if (has("espacio libre", "cuanto espacio")) return "Quedan 21 coma 4 gigas libres en la tarjeta, el 33 por ciento ocupado (datos de ejemplo)";
    if (has("memoria libre", "cuanta memoria")) return "Hay 5120 megas de memoria libres (datos de ejemplo)";
    if (has("temperatura de la pi", "temperatura tiene la pi", "como esta la pi", "estado de la pi")) return "El procesador está a 46 grados (dato de ejemplo)";
    if (has("temporizador", "cuenta atras") && (has("anade", "sumale", "mas tiempo", "alarga", "amplia") || (has("ponle") && has("mas")))) {
      const sec = duration(t), c = S.timers.filter(x => x.kind === "timer" && Date.now() < x.due).sort((x, y) => x.due - y.due)[0];
      if (!sec) return "No he entendido cuánto tiempo. Prueba: añade cinco minutos al temporizador";
      if (!c) return "No hay ningún temporizador en marcha";
      c.due += sec * 1000; LS.set("timers", S.timers); return "Añadido " + sayDuration(sec) + " al temporizador";
    }
    if ((has("cuanto queda", "cuanto falta") && !has("navidad", "nochevieja", "reyes", "ano nuevo", "verano")) || has("queda del temporizador")) {
      const c = S.timers.filter(x => Date.now() < x.due).sort((x, y) => x.due - y.due)[0]; if (!c) return "No hay ningún temporizador en marcha";
      return "Quedan " + sayDuration(Math.max(1, Math.round((c.due - Date.now()) / 1000)));
    }
    if (has("para la alarma", "silencia la alarma", "para el temporizador", "silencia el temporizador") && !has("pon", "programa")) {
      const k = S.timers.filter(x => Date.now() >= x.due).length; S.timers = S.timers.filter(x => Date.now() < x.due); LS.set("timers", S.timers); return k ? "Parado" : "No hay nada sonando";
    }
    if (has("temporizador", "cuenta atras")) {
      if (has("cancela", "quita", "borra")) { S.timers = S.timers.filter(x => x.kind !== "timer"); LS.set("timers", S.timers); return "Temporizadores cancelados"; }
      const sec = duration(t); if (!sec) return "No he entendido cuánto tiempo. Prueba: pon un temporizador de diez minutos";
      const lm = /\bpara (?:el |la |los |las |mi |mis |un |una )?([a-záéíóúñü]+(?: [a-záéíóúñü]+){0,2})$/.exec(String(text).toLowerCase().replace(/[\s.,!?¡¿]+$/, "")), label = lm && !duration(norm(lm[1])) ? lm[1].slice(0, 40) : "";
      S.timers.push({ id: rid(8), kind: "timer", label, due: Date.now() + sec * 1000 }); LS.set("timers", S.timers); return "Temporizador de " + sayDuration(sec) + (label ? " para " + label : "") + " en marcha";
    }
    /* alarmas y recordatorios: «a las siete y media», «a las 7:30», «a las ocho menos cuarto», «de la tarde» */
    const clock = () => {
      const m = /\ba las (\d{1,2}|[a-z]+)(?:[:\s](\d{2}))?(?: (y media|y cuarto|menos cuarto))?/.exec(t); if (!m) return null;
      let h = /^\d+$/.test(m[1]) ? +m[1] : WORDS[m[1]]; if (h == null || h > 24) return null;
      let mi = m[2] ? +m[2] : m[3] === "y media" ? 30 : m[3] === "y cuarto" ? 15 : 0; if (m[3] === "menos cuarto") { h = (h + 23) % 24; mi = 45; }
      if (/\b(tarde|noche)\b/.test(t) && h >= 1 && h <= 11) h += 12;
      return [h % 24, mi];
    };
    if (has("despiertame", "alarma") || (has("recuerdame", "avisame") && !duration(t) && /\ba las /.test(t))) {
      const c = clock(); if (!c) return "No he entendido la hora. Prueba: despiértame a las siete y media";
      const [h, mi] = c, d = new Date(); d.setHours(h, mi, 0, 0); if (d <= now) d.setDate(d.getDate() + 1);
      const daily = has("todos los dias", "cada dia", "diaria", "a diario");
      const t2 = String(text).toLowerCase().replace(/\bde la (?:mañana|manana|tarde|noche|madrugada)\b/g, "").replace(/[\s.,!?¡¿]+$/, ""), lm = has("recuerdame", "avisame") ? /\ba las [^,]*?\b(?:que|para|de)\s+(.{2,40})$/.exec(t2) : null, label = lm ? lm[1].trim() : "";
      S.timers.push({ id: rid(8), kind: "alarm", label, due: d.getTime(), hour: h, minute: mi, daily }); LS.set("timers", S.timers);
      return "Alarma a las " + pad(h) + ":" + pad(mi) + (daily ? ", todos los días" : "") + (label ? " para " + label : "");
    }
    if (has("que hora sera dentro de", "que hora seran dentro de", "que hora sera en")) {
      const sec = duration(t.replace(/^.*(dentro de|sera en) /, ""));
      if (sec) { const d = new Date(Date.now() + sec * 1000); return "Serán las " + pad(d.getHours()) + ":" + pad(d.getMinutes()); }
    }
    if (has("que hora", "dime la hora")) return "Son las " + pad(now.getHours()) + ":" + pad(now.getMinutes());
    if (has("que ano es", "en que ano estamos", "que ano estamos")) return "Estamos en " + now.getFullYear();
    if (has("que mes es", "en que mes estamos", "que mes estamos")) return "Estamos en " + now.toLocaleDateString("es-ES", { month: "long" });
    const dm = /que dia (?:de la semana )?(?:cae|es) el (\d{1,2}) de (\w+)/.exec(t);
    if (dm) {
      const MS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], mi = MS.indexOf(dm[2]);
      if (mi >= 0 && +dm[1] >= 1 && +dm[1] <= 31) {
        const hoy = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        for (const y of [now.getFullYear(), now.getFullYear() + 1]) {
          const f = new Date(y, mi, +dm[1]);
          if (f.getMonth() !== mi) return "Ese día no existe";
          if (f >= hoy) return "El " + dm[1] + " de " + dm[2] + (y === now.getFullYear() ? " de este año" : " del año que viene") + " cae en " + f.toLocaleDateString("es-ES", { weekday: "long" });
        }
      }
    }
    if (has("que dia", "que fecha")) return "Hoy es " + now.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
    if (has("tiempo", "llover", "llovera", "lluvia", "temperatura", "hara") && has("manana")) {
      const off = has("pasado manana") ? 2 : 1, d = weather().days[off - 1];
      return (off === 1 ? "Mañana" : "Pasado mañana") + " habrá una máxima de " + d.tmax + " grados y una mínima de " + d.tmin + (d.rain >= 30 ? ", y un " + d.rain + " por ciento de probabilidad de lluvia" : "");
    }
    if (has("tiempo", "llover", "lluvia", "temperatura", "calor", "frio")) {
      const w = weather(); return "Ahora hay " + Math.round(w.temp) + " grados y poco nuboso. Máxima " + Math.round(w.tmax) + ", mínima " + Math.round(w.tmin) + ". " + (w.rain_alert ? "Habrá lluvia en " + w.rain_alert.in_hours + " hora, con un " + w.rain_alert.prob + " por ciento." : "");
    }
    if (has("calendario", "agenda", "que tengo")) { const ev = calendar().events; return "Hoy tienes " + ev[0].title + " a las " + ev[0].time + ". Mañana: " + ev[1].title; }
    if (has("modo casa", "modo hogar")) { LS.set("mode", "home"); fetch("/api/mode", { method: "POST", body: JSON.stringify({ mode: "home" }) }); return "Cambiando a modo casa"; }
    if (has("modo iker", "modo notas", "bloc")) { fetch("/api/mode", { method: "POST", body: JSON.stringify({ mode: "iker" }) }); return "Cambiando a modo iker"; }
    if (has("modo escritorio", "modo desktop", "ve al escritorio")) { fetch("/api/mode", { method: "POST", body: JSON.stringify({ mode: "desktop" }) }); return "Cambiando a modo escritorio"; }
    if (has("modo dev", "modo desarrollador", "modo consola")) { fetch("/api/mode", { method: "POST", body: JSON.stringify({ mode: "dev" }) }); return "Cambiando a modo desarrollador"; }
    if (has("musica", "cancion")) {
      if (has("sube", "baja") && !has("volumen")) { S.audio.volume = Math.max(0, Math.min(100, S.audio.volume + (has("sube") ? 15 : -15))); S.audio.muted = false; LS.set("audio", S.audio); return "Volumen al " + S.audio.volume + " por ciento"; }
      const cmd = has("siguiente", "salta") ? "next" : has("anterior") ? "previous" : has("pausa", "para", "deten", "silencia") ? "pause" : has("pon", "ponme", "reanuda", "sigue", "reproduce") ? "play" : null;
      if (cmd) { S.music = { seq: S.music.seq + 1, cmd, arg: null }; return { pause: "Música en pausa", play: "Seguimos con la música", next: "Siguiente canción", previous: "Canción anterior" }[cmd]; }
    }
    if (has("volumen")) {
      if (has("mitad", "maximo", "a tope")) { S.audio.volume = has("mitad") ? 50 : 100; S.audio.muted = false; LS.set("audio", S.audio); return "Volumen al " + S.audio.volume + " por ciento"; }
      if (has("sube", "mas alto")) S.audio.volume = Math.min(100, S.audio.volume + 15); else if (has("baja", "mas bajo")) S.audio.volume = Math.max(0, S.audio.volume - 15);
      else { const m = /(\d+|[a-z]+)\s*(?:por ciento)?$/.exec(t); const n = m ? (/^\d+$/.test(m[1]) ? +m[1] : WORDS[m[1]]) : null; if (n == null) return "No he entendido el volumen"; S.audio.volume = Math.min(100, n); }
      S.audio.muted = false; LS.set("audio", S.audio); return "Volumen al " + S.audio.volume + " por ciento";
    }
    if (has("apaga la pantalla", "oscurece la pantalla", "pon la pantalla en negro")) { S.display.auto = false; S.display.level = 10; LS.set("display", S.display); return "Brillo al 10 por ciento"; }
    if (has("brillo")) { if (has("auto")) S.display.auto = true; else { S.display.auto = false; S.display.level = Math.max(10, Math.min(100, S.display.level + (has("sube", "mas") ? 20 : -20))); } LS.set("display", S.display); return has("auto") ? "Brillo automático" : "Brillo al " + S.display.level + " por ciento"; }
    if (has("salvapantalla", "marco de fotos")) {
      const on = !has("desactiva", "apaga", "quita"), P = Object.assign({ screensaver: true, idle_minutes: 5, night_from: 22, night_to: 7, night_level: 40 }, LS.get("prefs", {}));
      P.screensaver = on; LS.set("prefs", P); return on ? "Salvapantallas activado" : "Salvapantallas desactivado";
    }
    if (has("cuantos anuncios", "cuanto has bloqueado", "como va el pihole", "como va pihole", "estadisticas del pihole")) return "Pi-hole ha bloqueado 326 de 1211 consultas, un 27 por ciento (datos de ejemplo)";
    if (has("pihole", "pi hole", "anuncios")) {
      if (has("pausa", "desactiva", "apaga")) { S.pihole = { blocking: false, until: Date.now() + (duration(t) || 300) * 1000 }; return "Pi-hole en pausa"; }
      S.pihole = { blocking: true, until: 0 }; return "Pi-hole activado";
    }
    if (has("camara")) { S.camera = !has("cierra", "oculta"); return S.camera ? "Abriendo la cámara" : "Cámara cerrada"; }
    if (has("apaga la pi", "reinicia")) return "En el simulador no se apaga nada. En tu Pi real te pediría confirmar en pantalla";
    return "No te he entendido. La IA local no está activada en el simulador; prueba con: qué hora es, qué tiempo hace o pon un temporizador de un minuto";
  }
  function say(text) {
    const heard = String(text || "").trim().slice(0, 140), reply = understand(heard);
    S.voice = { state: "listening", wake: "hey jarvis", heard, reply, ts: Date.now() / 1000 };
    try { if (typeof window.refresh === "function") window.refresh(); } catch (e) {}
    try {                                                           // la «Pi» habla (con la voz de tu navegador, si hay una en español)
      if (window.speechSynthesis && !S.audio.muted && S.audio.volume > 0) {
        speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(reply); u.lang = "es-ES"; u.volume = S.audio.volume / 100; speechSynthesis.speak(u);
      }
    } catch (e) {}
    return reply;
  }

  /* ---------------- insignia de la demo ---------------- */
  function badge() {
    if (framed || !document.body || document.getElementById("demo-badge")) return;
    const b = document.createElement("div"); b.id = "demo-badge";
    b.style.cssText = "position:fixed;right:10px;bottom:6px;z-index:99999;font:600 11px/1 system-ui,sans-serif;display:flex;gap:8px;align-items:center;padding:5px 9px;border-radius:99px;background:#000b;color:#fff;border:1px solid #ffffff30;cursor:pointer;user-select:none";
    b.innerHTML = '<span style="width:7px;height:7px;border-radius:50%;background:#4ade80"></span><span>DEMO en el navegador</span><a href="https://github.com/IkerPlays/PiCore" target="_blank" rel="noopener" style="color:#9ecbff;text-decoration:none">GitHub</a><button id="demo-reset" style="all:unset;color:#fbbf24;cursor:pointer">Restablecer</button>';
    document.body.appendChild(b);
    b.querySelector("#demo-reset").onclick = e => { e.stopPropagation(); LS.clear(); toast("Demo restablecida"); setTimeout(() => { location.href = "/"; }, 600); };
    b.querySelector("a").onclick = e => e.stopPropagation();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", badge); else badge();
  window.PCPI_DEMO = { LS, status, toast, say, understand };
})();
