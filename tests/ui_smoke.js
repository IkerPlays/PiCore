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
  page.on('console', m => { if (m.type() === 'error' && !/scdn|ERR_NAME|ERR_INTERNET|net::|status of 400/.test(m.text())) problems.push('console: ' + m.text()); });

  // ------------------------------------------------------------------ modo Casa
  await page.goto(base + '/');
  await page.waitForFunction(() => document.getElementById('ph-pct').textContent.includes('%'), null, { timeout: 8000 }).catch(() => {});
  check('el reloj muestra HH:MM', /^\d{2}:\d{2}$/.test(await page.textContent('#time')));
  check('la fecha esta en español y con mayuscula', /^[A-ZÁÉÍÓÚ][a-záéíóú]+, \d+ de [a-z]+/.test(await page.textContent('#date')), await page.textContent('#date'));
  check('Pi-hole muestra un porcentaje', /\d+%/.test(await page.textContent('#ph-pct')), await page.textContent('#ph-pct'));
  check('el tiempo se muestra', (await page.textContent('#weather')).includes('°C'));
  check('Spotify muestra la cancion', (await page.textContent('#track')).length > 0 && (await page.textContent('#track')) !== 'Nada sonando');

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
  await page.waitForFunction(() => document.getElementById('chip-bat').textContent.includes('⚡'), null, { timeout: 9000 }).catch(() => {});
  check('cargando muestra el rayo y quita el aviso', (await page.textContent('#chip-bat')).includes('⚡80%') && !(await page.getAttribute('#chip-bat', 'class')).includes('low'));
  await page.unroute('**/api/status');

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
  await page.click('#t-list button');
  await sleep(1200);
  check('Cancelar lo quita', (await page.textContent('#timer-txt')).includes('Temporizador'));
  // suena: un temporizador de 1 s vence y sale la pantalla de aviso
  await page.request.post(base + '/api/timers', { headers: { 'X-PCPI': '1' }, data: { action: 'timer', seconds: 1, label: 'pasta' } });
  await page.click('#t-close');
  await page.waitForFunction(() => document.getElementById('tring').classList.contains('on'), null, { timeout: 12000 }).catch(() => {});
  check('al vencer sale el aviso a pantalla completa', await page.evaluate(() => document.getElementById('tring').classList.contains('on')));
  check('con su nombre', (await page.textContent('#tring-big')).includes('pasta'));
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
  await page.click('#osk button:text-is("⌫")');
  check('el teclado escribe y borra', (await page.inputValue('#pw-in')) === 'q', await page.inputValue('#pw-in'));
  await page.click('#osk button:text-is("⇧")');
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
  await sleep(300);
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
