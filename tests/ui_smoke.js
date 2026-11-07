// Prueba de humo de la interfaz en un navegador de verdad (Playwright). Uso: node ui_smoke.js http://127.0.0.1:PUERTO
const { chromium } = require('playwright');
const { patchWaitForFunction } = require('./pw_helpers');
const base = process.argv[2];
const results = [];
const check = (name, ok, extra) => { results.push({ name, ok: !!ok, extra: extra || '' }); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 }, locale: 'es-ES', timezoneId: 'Atlantic/Canary' });
  const page = await ctx.newPage();
  patchWaitForFunction(page);
  const problems = [];
  page.on('pageerror', e => problems.push('pageerror: ' + e.message));
  const forbidden = [];                                                                             // para saber QUE peticion dio un 403 si alguna vez falla
  page.on('response', r => { if (r.status() === 403) forbidden.push(r.request().method() + ' ' + r.url().replace(base, '')); });
  page.on('console', m => { if (m.type() === 'error' && !/scdn|ERR_NAME|ERR_INTERNET|net::|status of (400|502)|Permissions policy|compute-pressure/.test(m.text())) problems.push('console: ' + m.text() + (/403/.test(m.text()) ? ' [403: ' + forbidden.join(', ') + ']' : '')); });

  // ------------------------------------------------------------------ modo Casa
  await page.goto(base + '/');
  await page.waitForFunction(() => document.getElementById('ph-pct').textContent.includes('%'), null, { timeout: 8000 }).catch(() => {});
  check('el reloj muestra HH:MM', /^\d{2}:\d{2}$/.test(await page.textContent('#time')));
  check('la fecha esta en español y con mayuscula', /^[A-ZÁÉÍÓÚ][a-záéíóú]+, \d+ de [a-z]+/.test(await page.textContent('#date')), await page.textContent('#date'));
  check('Pi-hole muestra un porcentaje', /\d+%/.test(await page.textContent('#ph-pct')), await page.textContent('#ph-pct'));
  check('el tiempo se muestra', (await page.textContent('#weather')).includes('°C'));
  check('la tarjeta de Musix muestra lo que suena', (await page.textContent('#track')).length > 0 && (await page.textContent('#track')) !== 'Nada sonando');

  const state0 = await page.textContent('#ph-state');
  await page.click('#ph-btn');
  await page.waitForFunction(() => document.getElementById('ph-state').textContent === 'En pausa', null, { timeout: 8000 }).catch(() => {});
  check('el boton pausa Pi-hole', (await page.textContent('#ph-state')) === 'En pausa', state0 + ' -> ' + await page.textContent('#ph-state'));
  check('el boton cambia a «Activar»', (await page.textContent('#ph-btn')).includes('Activar'));
  await page.click('#ph-btn');
  await page.waitForFunction(() => document.getElementById('ph-state').textContent === 'Activo', null, { timeout: 8000 }).catch(() => {});
  check('el boton reactiva Pi-hole', (await page.textContent('#ph-state')) === 'Activo');

  const t0 = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.click('#time');
  const t1 = await page.evaluate(() => document.documentElement.dataset.theme);
  check('tocar la hora cambia el tema', t0 !== t1, t0 + ' -> ' + t1);
  await page.click('#greet');
  check('tocar el saludo vuelve a automatico', (await page.evaluate(() => localStorage.getItem('pcpi-theme'))) === null);

  await page.click('#open-cam');
  check('el visor de camara se abre', (await page.evaluate(() => document.getElementById('cam').style.display)) === 'block');
  const src = await page.evaluate(() => document.getElementById('cam-img').getAttribute('src'));
  check('el visor pide el stream', /\/api\/camera\/stream/.test(src || ''), src);
  await page.click('#close-cam');
  check('el visor de camara se cierra y suelta el stream', (await page.evaluate(() => document.getElementById('cam').style.display)) === 'none'
        && (await page.evaluate(() => document.getElementById('cam-img').getAttribute('src'))) === null);

  // la voz: el aviso aparece y desaparece segun el estado
  await page.goto(base + '/');
  const mode = await (await page.request.get(base + '/api/mode')).json();
  check('GET /api/mode responde', ['home', 'iker', 'desktop'].includes(mode.mode));
  await page.click('button[data-mode="iker"]');
  await sleep(300);
  check('el boton «Modo Iker» cambia el modo', (await (await page.request.get(base + '/api/mode')).json()).mode === 'iker');
  await page.request.post(base + '/api/mode', { headers: { 'X-PCPI': '1' }, data: { mode: 'home' } });

  // ------------------------------------------------------------------ brillo
  await page.goto(base + '/');
  await page.click('#chip-bright');
  await sleep(700);
  check('el panel de brillo se abre', await page.evaluate(() => document.getElementById('bpanel').classList.contains('on')));
  await page.click('#b-auto');                                    // pasa a manual
  await page.fill('#b-range', '30');
  await page.dispatchEvent('#b-range', 'input');
  await sleep(900);
  const dsp = await (await page.request.get(base + '/api/status')).json();
  check('el deslizante guarda el brillo en el servidor', dsp.display.level === 30 && dsp.display.auto === false, JSON.stringify(dsp.display));
  const dimv = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--dim'));
  check('sin backlight se atenua por software (nunca negro del todo)', parseFloat(dimv) > 0.4 && parseFloat(dimv) <= 0.8, dimv);
  await page.request.post(base + '/api/display', { headers: { 'X-PCPI': '1' }, data: { level: 100, auto: true } });
  // sonido del sistema (el emulador hace de pcpi-session)
  await page.waitForFunction(() => !document.getElementById('snd').hidden, null, { timeout: 9000 }).catch(() => {});
  check('el panel enseña la seccion de sonido (hay audio)', await page.isVisible('#v-range'));
  await page.fill('#v-range', '25'); await page.dispatchEvent('#v-range', 'input');
  await sleep(900);
  let aud = (await (await page.request.get(base + '/api/status')).json()).audio;
  check('el deslizante cambia el volumen del sistema', aud.volume === 25, JSON.stringify(aud));
  await page.click('#v-mute'); await sleep(700);
  aud = (await (await page.request.get(base + '/api/status')).json()).audio;
  check('silenciar lo silencia', aud.muted === true && await page.evaluate(() => document.getElementById('v-mute').classList.contains('off')), JSON.stringify(aud));
  await page.click('#v-mute'); await sleep(700);
  check('y se puede volver a activar', !((await (await page.request.get(base + '/api/status')).json()).audio.muted));
  await page.click('#v-test');
  check('«Probar sonido» avisa de que suena', (await page.textContent('#vnote')).includes('Sonando'));
  await page.request.post(base + '/api/audio', { headers: { 'X-PCPI': '1' }, data: { action: 'volume', value: 60 } });
  await page.click('#b-close');

  // ------------------------------------------------------------------ vigilancia de movimiento
  await page.goto(base + '/');
  await page.waitForFunction(() => !document.getElementById('chip-motion').hidden, null, { timeout: 8000 }).catch(() => {});
  const hasMotion = await page.isVisible('#chip-motion');
  check('el icono de vigilancia aparece (hay camara)', hasMotion);
  if (hasMotion) {
    await page.click('#chip-motion');
    await sleep(500);
    check('el icono activa la vigilancia', (await (await page.request.get(base + '/api/status')).json()).motion.enabled === true);
    // se simula un aviso: el estado trae un movimiento de «ahora mismo» (el primero que ve la pagina no avisa: es el historico)
    let fakeLast = null;
    await page.route('**/api/status', async route => {
      const resp = await route.fetch();
      const j = await resp.json();
      if (fakeLast) j.motion.last = fakeLast;
      await route.fulfill({ response: resp, json: j });
    });
    await sleep(4500);                                              // la pagina ya vio el estado sin movimiento
    fakeLast = Date.now() / 1000;
    await page.waitForFunction(() => document.getElementById('motion').classList.contains('on'), null, { timeout: 9000 }).catch(() => {});
    check('aparece el aviso «Movimiento detectado»', await page.evaluate(() => document.getElementById('motion').classList.contains('on')));
    await page.unroute('**/api/status');
    await page.click('#motion');
    await sleep(500);
    check('tocar el aviso abre la camara', (await page.evaluate(() => document.getElementById('cam').style.display)) === 'block');
    await page.click('#close-cam');
    await page.request.post(base + '/api/motion', { headers: { 'X-PCPI': '1' }, data: { enabled: false } });
  }

  // ------------------------------------------------------------------ bateria (solo si el servidor la reporta)
  await page.goto(base + '/');
  await sleep(1500);
  check('sin bateria no se muestra el indicador', await page.isHidden('#chip-bat'));
  let fakeBat = null;
  await page.route('**/api/status', async route => {
    const resp = await route.fetch(); const j = await resp.json();
    if (fakeBat) j.battery = fakeBat;
    await route.fulfill({ response: resp, json: j });
  });
  fakeBat = { available: true, percent: 12, charging: false, low: true, critical: false };
  await page.waitForFunction(() => !document.getElementById('chip-bat').hidden, null, { timeout: 9000 }).catch(() => {});
  check('la bateria baja se muestra en aviso', (await page.getAttribute('#chip-bat', 'class')).includes('low') && (await page.textContent('#chip-bat')).includes('12%'));
  fakeBat = { available: true, percent: 80, charging: true, low: false, critical: false };
  await page.waitForFunction(() => document.getElementById('chip-bat').querySelector('use[href="#i-bolt"]') !== null, null, { timeout: 9000 }).catch(() => {});
  check('cargando muestra el rayo y quita el aviso', (await page.locator('#chip-bat use[href="#i-bolt"]').count()) === 1 && (await page.textContent('#chip-bat')).includes('80%') && !(await page.getAttribute('#chip-bat', 'class')).includes('low'));
  await page.unroute('**/api/status');

  // ------------------------------------------------------------------ ciudad del tiempo (primer arranque sin ciudad)
  await page.goto(base + '/');
  await sleep(900);
  let cityPosts = [];
  await page.route('**/api/status', async route => {
    const resp = await route.fetch(); const j = await resp.json();
    j.weather = { ok: false, error: 'no configurado' };
    await route.fulfill({ response: resp, json: j });
  });
  await page.route('**/api/settings', async route => {
    const b = JSON.parse(route.request().postData());
    if (b.action === 'city_search') await route.fulfill({ json: { results: [{ name: 'Telde', region: 'Canarias', country: 'España', lat: 27.9924, lon: -15.4192 }] } });
    else { cityPosts.push(b); await route.fulfill({ json: { ok: true } }); }
  });
  await page.waitForSelector('#pickcity', { timeout: 9000 }).catch(() => {});
  check('sin ciudad, el tiempo invita a elegirla', (await page.textContent('#weather')).includes('Elegir tu ciudad'));
  await page.click('#pickcity'); await sleep(600);
  check('se abre el panel de ciudad', await page.evaluate(() => document.getElementById('cityp').classList.contains('on')));
  await page.click('#cityin'); await sleep(400);
  check('con el teclado en pantalla', await page.evaluate(() => document.body.classList.contains('osk-open')));
  await page.fill('#cityin', 'telde'); await page.click('#citygo');
  await page.waitForSelector('#cityres button', { timeout: 5000 }).catch(() => {});
  check('salen las ciudades encontradas', (await page.textContent('#cityres')).includes('Telde') && (await page.textContent('#cityres')).includes('Canarias'));
  await page.click('#cityres button'); await sleep(500);
  check('al elegir una se guarda su latitud, longitud y nombre', cityPosts.length === 1 && cityPosts[0].action === 'city_set' && cityPosts[0].name === 'Telde' && Math.abs(cityPosts[0].lat - 27.9924) < 1e-6, JSON.stringify(cityPosts));
  check('y el panel se cierra', !(await page.evaluate(() => document.getElementById('cityp').classList.contains('on'))));
  await page.unroute('**/api/status'); await page.unroute('**/api/settings');

  // ------------------------------------------------------------------ aviso de reconexion (el servidor se reinicia)
  await page.goto(base + '/');
  await sleep(900);
  await page.route('**/api/**', route => route.abort());                // servidor caido: ninguna ruta contesta
  await page.waitForSelector('#offline', { timeout: 25000 }).catch(() => {});
  check('si el servidor no contesta, sale «Reconectando»', (await page.isVisible('#offline')) && (await page.textContent('#offline')).includes('Reconectando'));
  await page.unroute('**/api/**');
  await page.waitForFunction(() => !document.getElementById('offline'), null, { timeout: 15000 }).catch(() => {});
  check('y se quita solo al volver', (await page.locator('#offline').count()) === 0);

  // ------------------------------------------------------------------ Modo Dev
  await page.goto(base + '/');
  await sleep(800);
  check('Casa tiene el boton «Modo Dev»', await page.isVisible('#nav-dev'));
  await page.request.post(base + '/api/mode', { headers: { 'X-PCPI': '1' }, data: { mode: 'dev' } });
  await page.goto(base + '/dev');
  await sleep(600);
  check('la pagina Dev muestra la consola y las ordenes rapidas', (await page.locator('#quick button').count()) >= 8 && await page.isVisible('#cmd'));
  await page.fill('#cmd', 'echo hola');
  await page.press('#cmd', 'Enter');
  await sleep(700);
  check('al ejecutar, la orden se anota en la consola y queda en marcha', (await page.textContent('#out')).includes('$ echo hola'), await page.textContent('#out'));
  const sent = await page.evaluate(async () => { const r = await fetch('/api/dev'); return (await r.json()).mode; });
  check('el servidor sabe que esta en modo dev', sent === 'dev');
  await page.click('#tabs button[data-t="api"]');
  await page.click('#apigo');
  await page.waitForFunction(() => document.getElementById('apiout').textContent.startsWith('200'), null, { timeout: 5000 }).catch(() => {});
  check('el explorador de API pide /api/status', (await page.textContent('#apiout')).includes('"cpu_temp"') || (await page.textContent('#apiout')).includes('"mode"'), (await page.textContent('#apiout')).slice(0, 80));
  await page.selectOption('#apim', 'POST'); await page.fill('#apipath', '/api/mode'); await page.fill('#apibody', '{no json');
  await page.click('#apigo');
  check('un cuerpo que no es JSON se rechaza antes de enviar', (await page.textContent('#apiout')).includes('JSON'));
  await page.click('#tabs button[data-t="exp"]');
  await page.waitForFunction(() => document.querySelectorAll('#explist .sw').length === 3, null, { timeout: 5000 }).catch(() => {});
  check('los 3 experimentos aparecen apagados', (await page.locator('#explist .sw.on').count()) === 0 && (await page.locator('#explist .sw').count()) === 3);
  await page.locator('#explist .sw').nth(1).click();
  await page.waitForFunction(() => !document.getElementById('expgraph').hidden, null, { timeout: 5000 }).catch(() => {});
  check('encender «Gráfica en vivo» la muestra', await page.isVisible('#graph'));
  await page.locator('#explist .sw').nth(2).click();
  await sleep(600);
  await page.request.post(base + '/api/mode', { headers: { 'X-PCPI': '1' }, data: { mode: 'home' } });
  await page.goto(base + '/');
  await page.waitForSelector('#dbg', { timeout: 9000 }).catch(() => {});
  check('«casa_debug» pone la insignia de depuracion en Casa', await page.isVisible('#dbg'));
  await page.request.post(base + '/api/mode', { headers: { 'X-PCPI': '1' }, data: { mode: 'dev' } });
  for (const id of ['live_graph', 'casa_debug']) await page.request.post(base + '/api/dev', { headers: { 'X-PCPI': '1' }, data: { action: 'flag', id, on: false } });
  await page.request.post(base + '/api/mode', { headers: { 'X-PCPI': '1' }, data: { mode: 'home' } });
  await page.goto(base + '/');
  await sleep(500);

  // ------------------------------------------------------------------ Musix: YT Music, MP3 Player y DYMusic
  await page.goto(base + '/');
  await sleep(1200);
  await page.click('#mxbtn');
  await sleep(700);
  check('Musix ofrece YT Music, MP3 Player y DYMusic', (await page.locator('#mxhome button').allTextContents()).map(t => t.split(/(?=[A-Z][a-z]+ [a-z])/)[0]).join('|').length > 0 && (await page.locator('#mxhome button').count()) === 3);
  await page.click('#mxhome button[data-go="yt"]');
  await page.click('#mxin');
  await sleep(500);
  check('al tocar el cuadro del enlace sale el teclado en pantalla', await page.evaluate(() => document.body.classList.contains('osk-open')));
  for (const ch of 'hola') await page.locator('#osk button', { hasText: new RegExp('^' + ch + '$', 'i') }).first().click();
  check('el teclado en pantalla escribe en el cuadro', (await page.inputValue('#mxin')).toLowerCase() === 'hola', await page.inputValue('#mxin'));
  await page.fill('#mxin', '');
  await page.fill('#mxin', 'https://evil.com/watch?v=dQw4w9WgXcQ');
  await page.click('#mxgo');
  await page.waitForFunction(() => document.getElementById('mxerr').textContent.length > 0, null, { timeout: 5000 }).catch(() => {});
  check('un enlace que no es de YouTube se rechaza', (await page.textContent('#mxerr')).includes('YouTube'), await page.textContent('#mxerr'));
  await page.fill('#mxin', 'https://youtu.be/dQw4w9WgXcQ?t=3');
  await page.click('#mxgo');
  await page.waitForFunction(() => (document.getElementById('mxframe').getAttribute('src') || '').includes('youtube-nocookie'), null, { timeout: 5000 }).catch(() => {});
  check('un enlace de YouTube carga el reproductor incrustado', (await page.getAttribute('#mxframe', 'src')) === 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  check('el enlace queda en el historial de YT Music', (await page.locator('#mxhist button').count()) === 1);
  await page.fill('#mxin', 'https://music.youtube.com/watch?v=9bZkp7q19f0');
  await page.click('#mxgo');
  await page.waitForFunction(() => document.querySelectorAll('#mxhist button').length === 2, null, { timeout: 5000 }).catch(() => {});
  await page.locator('#mxhist button').nth(1).click();
  await sleep(400);
  check('tocar un enlace del historial lo vuelve a cargar', (await page.getAttribute('#mxframe', 'src')) === 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  await page.click('#mx-full');
  await sleep(500);
  const fb = await page.evaluate(() => { const r = document.getElementById('mxpanel').getBoundingClientRect(); return [r.width, r.height]; });
  check('pantalla completa ocupa toda la pantalla', fb[0] >= 1020 && fb[1] >= 595, JSON.stringify(fb));
  await page.click('#mx-full');
  await page.click('#mx-back');
  await page.click('#mxhome button[data-go="mp3"]');
  await page.waitForFunction(() => document.querySelectorAll('#mxlist .trk').length >= 2, null, { timeout: 6000 }).catch(() => {});
  check('el MP3 Player lista las canciones de la Pi', (await page.locator('#mxlist .trk').count()) >= 2, await page.textContent('#mxlist'));
  await page.locator('#mxlist .trk').first().click();
  await page.waitForFunction(() => !document.getElementById('mxaudio').paused, null, { timeout: 6000 }).catch(() => {});
  check('tocar una cancion la reproduce', await page.evaluate(() => !document.getElementById('mxaudio').paused && document.getElementById('mxaudio').src.includes('/music/')));
  await sleep(600);
  const np = await (await page.request.get(base + '/api/status')).json();
  check('lo que suena sale en la tarjeta (estado del servidor)', np.nowplaying && np.nowplaying.state === 'playing' && np.nowplaying.title.length > 0, JSON.stringify(np.nowplaying));
  const first = await page.evaluate(() => document.getElementById('mxaudio').src);
  await page.click('#mx-n');
  await sleep(500);
  check('siguiente cambia de cancion', (await page.evaluate(() => document.getElementById('mxaudio').src)) !== first);
  await page.evaluate(() => { const v = document.getElementById('mx-vol'); v.value = 40; v.dispatchEvent(new Event('input')); });
  check('el volumen de Musix se aplica y se recuerda', await page.evaluate(() => Math.abs(document.getElementById('mxaudio').volume - 0.4) < 0.01 && localStorage.getItem('mxvol') === '0.4'));
  await page.click('#mx-sleep');
  check('el boton Dormir programa 15 minutos', (await page.textContent('#mx-sleep')).includes('15 min'), await page.textContent('#mx-sleep'));
  await page.click('#mx-sleep'); await page.click('#mx-sleep'); await page.click('#mx-sleep');
  check('y a la cuarta pulsacion lo quita', (await page.textContent('#mx-sleep')) === 'Dormir');
  await page.request.post(base + '/api/music', { headers: { 'X-PCPI': '1' }, data: { action: 'cmd', cmd: 'sleep', seconds: 2 } }).catch(() => {});
  await page.request.post(base + '/api/music', { headers: { 'X-PCPI': '1' }, data: { action: 'cmd', cmd: 'pause' } });
  await page.waitForFunction(() => document.getElementById('mxaudio').paused, null, { timeout: 9000 }).catch(() => {});
  check('la orden de voz «pausa» para la musica', await page.evaluate(() => document.getElementById('mxaudio').paused));
  await page.click('#mx-back');
  await page.click('#mxhome button[data-go="dy"]');
  await sleep(800);
  check('sin clave de busqueda DYMusic deja pegar el enlace', await page.isVisible('#dylink'));
  await page.fill('#dylink', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ');
  await page.click('#dylinkgo');
  await page.waitForFunction(() => !document.getElementById('dysteps').hidden, null, { timeout: 5000 }).catch(() => {});
  check('DYMusic explica los pasos y deja el enlace limpio', (await page.textContent('#dysteps')).includes('MP3') && (await page.inputValue('#dysteps input')) === 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', await page.textContent('#dysteps'));
  await page.click('#mx-close');
  await sleep(500);
  check('cerrar Musix no corta la musica ni el reproductor', await page.evaluate(() => !!document.getElementById('mxaudio').src));

  // ------------------------------------------------------------------ hoja «Sistema»
  await page.goto(base + '/');
  await sleep(1200);
  await page.route('**/api/status', async route => {
    const resp = await route.fetch(); const j = await resp.json();
    j.system = { disk: { free_gb: 0.6, total_gb: 30, pct: 98 }, mem_avail_mb: 900, update: { available: true, behind: 2 },
                 health: [{ level: 'bad', text: 'Casi no queda espacio en la tarjeta (0.6 GB libres).' }, { level: 'info', text: 'Hay una actualización' }] };
    await route.fulfill({ response: resp, json: j });
  });
  await page.waitForFunction(() => document.getElementById('chip-sys').classList.contains('bad'), null, { timeout: 9000 }).catch(() => {});
  check('poco disco pone el chip Sistema en rojo', (await page.getAttribute('#chip-sys', 'class')).includes('bad'));
  await page.click('#chip-sys');
  await sleep(600);
  check('la hoja Sistema lista los avisos', (await page.locator('#s-health .hl').count()) === 2 && (await page.textContent('#s-stats')).includes('0.6 GB'));
  check('con novedades el boton dice «Actualizar ahora»', (await page.textContent('#upd-btn')).includes('Actualizar ahora') && (await page.textContent('#upd-txt')).includes('2 cambios'), await page.textContent('#upd-txt'));
  let updPosts = [];
  await page.route('**/api/system', async route => { updPosts.push(route.request().postData()); await route.fulfill({ json: { ok: true } }); });
  await page.click('#upd-btn');
  await sleep(300);
  check('pulsarlo pide la actualizacion', updPosts.length === 1 && updPosts[0].includes('"update"'), JSON.stringify(updPosts));
  await page.unroute('**/api/system');
  await page.route('**/api/status', async route => {
    const resp = await route.fetch(); const j = await resp.json();
    j.system = { disk: { free_gb: 20, total_gb: 30, pct: 30 }, mem_avail_mb: 900, update: { available: true, behind: 2 }, health: [{ level: 'ok', text: 'Todo en orden.' }],
                 update_run: { state: 'running', tail: ['Descargando 2 cambio(s)…'] } };
    await route.fulfill({ response: resp, json: j });
  });
  await page.waitForFunction(() => document.getElementById('upd-log').textContent.includes('Descargando'), null, { timeout: 12000 }).catch(() => {});
  check('mientras actualiza: boton desactivado y registro a la vista', (await page.textContent('#upd-log')).includes('Descargando') && (await page.textContent('#upd-txt')).includes('no apagues'));
  await page.unroute('**/api/status');
  await page.route('**/api/status', async route => {
    const resp = await route.fetch(); const j = await resp.json();
    j.system = { disk: { free_gb: 0.6, total_gb: 30, pct: 98 }, mem_avail_mb: 900, update: { available: true, behind: 2 },
                 health: [{ level: 'bad', text: 'Casi no queda espacio en la tarjeta (0.6 GB libres).' }, { level: 'info', text: 'Hay una actualización' }] };
    await route.fulfill({ response: resp, json: j });
  });
  await page.waitForFunction(() => !document.getElementById('upd-btn').disabled && document.getElementById('upd-log').hidden, null, { timeout: 12000 }).catch(() => {});
  let powerPosts = [];
  await page.route('**/api/system', async route => { powerPosts.push(route.request().postData()); await route.fulfill({ json: { ok: true } }); });
  await page.click('#s-off');
  check('el primer toque en Apagar solo pide confirmacion', powerPosts.length === 0 && (await page.textContent('#s-off')).includes('otra vez'));
  await page.click('#s-off');
  await sleep(400);
  check('el segundo toque apaga', powerPosts.length === 1 && powerPosts[0].includes('shutdown'), JSON.stringify(powerPosts));
  await page.unroute('**/api/system');
  await page.unroute('**/api/status');
  await page.click('#s-close');
  await sleep(500);

  // ------------------------------------------------------------------ temporizadores y alarmas
  await page.goto(base + '/');
  await page.waitForSelector('#chip-timer');
  check('el icono de temporizador esta y dice «Temporizador» sin ninguno', (await page.textContent('#chip-timer')).includes('Temporizador'));
  await page.click('#chip-timer');
  await sleep(600);
  await page.click('#tpanel .presets button[data-s="300"]');
  await page.waitForFunction(() => /\d\d:\d\d/.test(document.getElementById('timer-txt').textContent), null, { timeout: 8000 }).catch(() => {});
  check('un temporizador de 5 min cuenta atras en el icono', /0[45]:\d\d/.test(await page.textContent('#timer-txt')), await page.textContent('#timer-txt'));
  check('sale en la lista con su boton Cancelar', (await page.textContent('#t-list')).includes('Cancelar'));
  await page.click('#t-list button[aria-label="Añadir un minuto"]');                                    // +1 min: el servidor suma 60 s
  await sleep(1200);
  check('+1 min lo alarga', /0[56]:\d\d/.test(await page.textContent('#t-list .trow b')), await page.textContent('#t-list .trow b'));
  await page.click('#t-list button:has-text("Cancelar")');
  await sleep(1200);
  check('Cancelar lo quita', (await page.textContent('#timer-txt')).includes('Temporizador'));
                                                                                              // alarma desde la pantalla (hora +1, cada dia); el panel sigue abierto
  await page.click('#al-h-up'); await page.click('#al-daily'); await page.click('#al-go'); await sleep(1500);
  check('crear una alarma desde la pantalla', /Alarma \d\d:30 · cada día/.test(await page.textContent('#t-list')), await page.textContent('#t-list'));
  await page.click('#t-list button:has-text("Cancelar")'); await sleep(1000);
  // suena: un temporizador de 1 s vence y sale la pantalla de aviso
  await page.request.post(base + '/api/timers', { headers: { 'X-PCPI': '1' }, data: { action: 'timer', seconds: 1, label: 'pasta' } });
  await page.click('#t-close');
  await page.waitForFunction(() => document.getElementById('tring').classList.contains('on'), null, { timeout: 12000 }).catch(() => {});
  check('al vencer sale el aviso a pantalla completa', await page.evaluate(() => document.getElementById('tring').classList.contains('on')));
  check('con su nombre', (await page.textContent('#tring-big')).includes('pasta'));
  await page.click('#tring-snooze');                                                                    // Posponer: 5 min con el mismo nombre
  await sleep(1500);
  const post = (await (await page.request.get(base + '/api/status')).json()).timers || [];
  check('Posponer deja un temporizador de 5 min con el mismo nombre', post.length === 1 && post[0].label === 'pasta' && post[0].remaining > 280 && !post[0].ringing, JSON.stringify(post));
  await page.request.post(base + '/api/timers', { headers: { 'X-PCPI': '1' }, data: { action: 'cancel' } });
  await page.request.post(base + '/api/timers', { headers: { 'X-PCPI': '1' }, data: { action: 'timer', seconds: 1, label: 'pasta' } });
  await page.waitForFunction(() => document.getElementById('tring').classList.contains('on'), null, { timeout: 12000 }).catch(() => {});
  await page.click('#tring-stop');
  await sleep(1500);
  check('Parar lo silencia y lo borra', !(await page.evaluate(() => document.getElementById('tring').classList.contains('on'))));
  check('ya no queda ninguno', ((await (await page.request.get(base + '/api/status')).json()).timers || []).length === 0);

  // ------------------------------------------------------------------ calendario (solo lectura)
  await page.goto(base + '/');
  await page.waitForFunction(() => !document.getElementById('cal').hidden && document.querySelectorAll('#cal .ev').length > 0, null, { timeout: 9000 }).catch(() => {});
  check('el calendario enseña los proximos eventos', (await page.locator('#cal .ev').count()) >= 1, await page.textContent('#cal'));
  check('con «Hoy» o «Mañana» y el titulo', /Hoy|Mañana/.test(await page.textContent('#cal')) && (await page.textContent('#cal')).includes('Dentista') || (await page.textContent('#cal')).includes('Cumple'));
  await page.click('#cal');
  await sleep(700);
  check('tocarlo abre la agenda', await page.evaluate(() => document.getElementById('cpanel').classList.contains('on')));
  check('con los eventos de ejemplo', (await page.textContent('#c-list')).includes('Cumple de Ana') && (await page.textContent('#c-list')).includes('Gimnasio'));
  await page.click('#c-close');
  await sleep(600);

  // ------------------------------------------------------------------ tiempo: por horas, dias y aviso de lluvia
  await page.goto(base + '/');
  await page.waitForFunction(() => document.getElementById('weather').textContent.includes('°C'), null, { timeout: 8000 }).catch(() => {});
  check('el aviso de lluvia sale junto al tiempo', (await page.textContent('#wsub')).includes('Lluvia'), await page.textContent('#wsub'));
  await page.click('#weather');
  await sleep(700);
  check('tocar el tiempo abre el detalle', await page.evaluate(() => document.getElementById('wpanel').classList.contains('on')));
  check('con 12 horas', (await page.locator('#w-hours .hr').count()) === 12);
  check('y 5 dias', (await page.locator('#w-days .dy').count()) === 5);
  check('los dias estan en español', /lunes|martes|miércoles|jueves|viernes|sábado|domingo/i.test(await page.textContent('#w-days')));
  await page.click('#w-close');
  await sleep(600);

  // ------------------------------------------------------------------ Wi-Fi (panel + teclado en pantalla)
  await page.goto(base + '/');
  await page.waitForFunction(() => !document.getElementById('chip-wifi').hidden, null, { timeout: 8000 }).catch(() => {});
  check('el icono de Wi-Fi muestra la red actual', (await page.textContent('#wifi-name')) === 'CasaIker', await page.textContent('#wifi-name'));
  await page.click('#chip-wifi');
  await page.waitForSelector('#sheet.on .net', { timeout: 6000 }).catch(() => {});
  check('el panel lista las redes', (await page.locator('#sheet .net[data-ssid]').count()) === 3);
  check('la red actual sale marcada como conectada', (await page.textContent('#sheet .net.active')).includes('conectada'));
  check('el nombre con «:» se ve entero', (await page.textContent('#sh-body')).includes('Hotel:Canarias'));
  check('indica que el Pi-hole filtra esta red', (await page.textContent('#sh-body')).includes('Pi-hole filtra'));
  await page.click('.net[data-ssid="Vecino"]');
  await page.waitForSelector('#pw-in');
  await sleep(200);
  check('al tocar la contraseña sale el teclado en pantalla', await page.evaluate(() => document.getElementById('osk') && document.getElementById('osk').classList.contains('on')));
  await page.click('#osk button:text-is("q")');
  await page.click('#osk button:text-is("w")');
  await page.click('#osk button:has(use[href="#i-backspace"])');
  check('el teclado escribe y borra', (await page.inputValue('#pw-in')) === 'q', await page.inputValue('#pw-in'));
  await page.click('#osk button:has(use[href="#i-shift"])');
  await page.click('#osk button:text-is("A")');
  check('mayusculas y minusculas', (await page.inputValue('#pw-in')) === 'qA');
  await page.fill('#pw-in', 'equivocada1');
  await page.click('#pw-go');
  await page.waitForFunction(() => document.getElementById('sh-err') && document.getElementById('sh-err').textContent.length > 0, null, { timeout: 15000 }).catch(() => {});
  check('contraseña mala: mensaje claro', (await page.textContent('#sh-err')) === 'Contraseña incorrecta', await page.textContent('#sh-err'));
  await page.click('.net[data-ssid="Vecino"]');
  await page.fill('#pw-in', 'otraclave1');
  await page.click('#pw-go');
  await page.waitForFunction(() => document.querySelector('.net.active') && document.querySelector('.net.active').dataset.ssid === 'Vecino', null, { timeout: 15000 }).catch(() => {});
  check('contraseña buena: se conecta', (await page.getAttribute('#sheet .net.active', 'data-ssid')) === 'Vecino');
  await page.click('#sw-pi');
  await page.waitForFunction(() => { const e = document.getElementById('sw-pi'); return e && !e.classList.contains('on'); }, null, { timeout: 6000 }).catch(() => {});   // (la lista se refresca sola cada 5 s: se espera a que el estado se asiente)
  check('el interruptor de Pi-hole se apaga', !(await page.evaluate(() => document.getElementById('sw-pi').classList.contains('on'))));
  // red oculta: no sale en la lista; se conecta escribiendo su nombre
  check('las redes ocultas no salen en la lista', !(await page.textContent('#sh-body')).includes('RedOculta'));
  await page.click('#b-hidden');
  await page.waitForSelector('#hid-ssid');
  await sleep(200);
  check('«Red oculta» saca el formulario con teclado', await page.evaluate(() => document.getElementById('osk').classList.contains('on')));
  await page.fill('#hid-ssid', 'RedOculta');
  await page.fill('#hid-pw', 'ocultaclave1');
  await page.click('#hid-go');
  await page.waitForFunction(() => document.querySelector('.net.active') && document.querySelector('.net.active').dataset.ssid === 'RedOculta', null, { timeout: 15000 }).catch(() => {});
  check('se conecta a la red oculta', (await page.textContent('#sheet')).includes('RedOculta'));
  await page.click('#sh-close');
  await sleep(600);
  check('el panel se cierra', !(await page.evaluate(() => document.getElementById('sheet').classList.contains('on'))));
  await page.request.post(base + '/api/wifi/connect', { headers: { 'X-PCPI': '1' }, data: { ssid: 'CasaIker' } });

  // ------------------------------------------------------------------ modo Iker (notas)
  await page.goto(base + '/iker');
  const before = await page.locator('#list .item').count();
  await page.click('#new');
  await page.fill('#text', 'Nota de prueba\nsegunda linea ñandú');
  check('se cuenta palabras', /\d+ palabras/.test(await page.textContent('#count')), await page.textContent('#count'));
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('Guardado'), null, { timeout: 6000 }).catch(() => {});
  check('se guarda solo', (await page.textContent('#status')).includes('Guardado'), await page.textContent('#status'));
  check('la nota aparece en la lista con su titulo', (await page.locator('#list .item b', { hasText: 'Nota de prueba' }).count()) === 1);
  check('hay una nota mas', (await page.locator('#list .item').count()) === before + 1);

  await page.reload();
  await page.locator('#list .item b', { hasText: 'Nota de prueba' }).click();
  await sleep(300);
  check('la nota se carga tras recargar, con tildes', (await page.inputValue('#text')) === 'Nota de prueba\nsegunda linea ñandú');

  await page.fill('#text', 'Nota de prueba editada');
  await page.keyboard.press('Control+s');
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('Guardado'), null, { timeout: 6000 }).catch(() => {});
  await sleep(500);
  check('Ctrl+S guarda y no duplica la nota', (await page.locator('#list .item b', { hasText: 'Nota de prueba editada' }).count()) === 1
        && (await page.locator('#list .item').count()) === before + 1);

  await page.click('#del');
  check('borrar pide confirmacion (primer toque)', (await page.textContent('#del')).includes('Seguro'));
  await page.click('#del');
  await sleep(500);
  check('borrar elimina la nota', (await page.locator('#list .item').count()) === before);

  // busqueda (sin mayusculas ni tildes) y resaltado sin HTML
  await page.click('#new');
  await page.fill('#text', 'Receta de café\nazúcar y leche');
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('Guardado'), null, { timeout: 6000 }).catch(() => {});
  await page.fill('#q', 'AZUCAR');
  await sleep(700);
  check('la busqueda encuentra «azúcar» escribiendo AZUCAR', (await page.locator('#list .item').count()) === 1);
  check('resalta lo buscado', (await page.locator('#list mark').count()) >= 1);
  await page.fill('#q', 'zzzz');
  await sleep(700);
  check('sin resultados lo dice', (await page.textContent('#list')).includes('No hay notas con'));
  await page.fill('#q', '');
  await sleep(700);
  check('vaciar la busqueda muestra todo', (await page.locator('#list .item').count()) >= 1);
  await page.click('#usb');
  await page.waitForFunction(() => /USB|usb/.test(document.getElementById('status').textContent) && !document.getElementById('status').textContent.includes('Copiando'), null, { timeout: 5000 }).catch(() => {});
  check('exportar sin USB avisa con claridad', (await page.textContent('#status')).includes('ningún USB'), await page.textContent('#status'));
  await page.locator('#list .item').first().click(); await page.click('#del'); await page.click('#del'); await sleep(400);

  // etiquetas, PDF y marcadores
  await page.click('#new');
  await page.fill('#text', 'Lista de la compra #super #casa\nleche y pan');
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('Guardado'), null, { timeout: 6000 }).catch(() => {});
  await page.waitForFunction(() => document.querySelectorAll('#tags button').length >= 2, null, { timeout: 6000 }).catch(() => {});
  check('las etiquetas # aparecen como botones', (await page.locator('#tags button').count()) >= 2, await page.textContent('#tags'));
  await page.locator('#tags button', { hasText: '#super' }).click();
  await sleep(500);
  check('tocar una etiqueta filtra las notas', (await page.locator('#list .item').count()) === 1);
  await page.locator('#tags button', { hasText: '#super' }).click();
  await sleep(400);
  await page.evaluate(() => { window.__opened = null; window.open = u => { window.__opened = u; return null; }; });   // el Chromium sin pantalla descarga los PDF: solo miramos la direccion
  await page.click('#pdf');
  await sleep(500);
  const opened = await page.evaluate(() => window.__opened);
  check('el boton PDF abre el PDF de la nota', /^\/api\/notes\/[0-9a-f]{16}\.pdf$/.test(opened || ''), opened);
  const pdfResp = await page.request.get(base + opened);
  check('ese enlace sirve un PDF de verdad', pdfResp.ok() && (pdfResp.headers()['content-type'] || '') === 'application/pdf' && (await pdfResp.body()).slice(0, 5).toString() === '%PDF-');
  await page.click('#madd');
  await page.fill('#mt', 'Wiki'); await page.fill('#mu', 'es.wikipedia.org');
  await page.click('#msave');
  await page.waitForSelector('#mlist .mk', { timeout: 5000 }).catch(() => {});
  check('un marcador nuevo sale en la barra', (await page.locator('#mlist .mk a').first().getAttribute('href')) === 'https://es.wikipedia.org/' || (await page.locator('#mlist .mk a').first().getAttribute('href')) === 'https://es.wikipedia.org');
  await page.click('#madd'); await page.fill('#mu', 'javascript:alert(1)'); await page.click('#msave');
  await sleep(400);
  check('un marcador peligroso se rechaza', (await page.locator('#mlist .mk').count()) === 1 && (await page.textContent('#status')).includes('no vale'), await page.textContent('#status'));
  await page.fill('#mu', ''); await page.click('#madd');
  await page.click('#mlist .mk button');
  await sleep(500);
  check('quitar un marcador lo borra', (await page.locator('#mlist .mk').count()) === 0);
  await page.locator('#list .item').first().click(); await page.click('#del'); await page.click('#del'); await sleep(400);

  // una nota vacia nueva no se guarda
  await page.click('#new');
  await sleep(1500);
  check('una nota vacia no se guarda', (await page.locator('#list .item').count()) === before);

  // XSS: el titulo se pinta como texto
  await page.fill('#text', '<img src=x onerror="window.__xss=1"><b>hola</b>');
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('Guardado'), null, { timeout: 6000 }).catch(() => {});
  await page.reload();
  await sleep(500);
  check('el HTML de una nota no se ejecuta', (await page.evaluate(() => window.__xss)) === undefined);
  await page.locator('#list .item').first().click();
  await page.click('#del'); await page.click('#del'); await sleep(400);

  check('sin errores de JavaScript ni de CSP en la consola', problems.length === 0, problems.join(' | '));
  await browser.close();

  const failed = results.filter(r => !r.ok);
  for (const r of results) console.log((r.ok ? 'OK   ' : 'FAIL ') + r.name + (r.ok ? '' : '   -> ' + r.extra));
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('ERROR', e); process.exit(2); });
