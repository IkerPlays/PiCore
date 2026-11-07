// Demo web (sitio estatico, API simulada en JS). Uso: node demo_smoke.js URL
const { chromium } = require('playwright');
const { patchWaitForFunction, sleep } = require('./pw_helpers');
const base = process.argv[2];
const results = [];
const check = (name, ok, extra) => results.push({ name, ok: !!ok, extra });
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 }, locale: 'es-ES', timezoneId: 'Atlantic/Canary' });
  const page = patchWaitForFunction(await ctx.newPage());
  const problems = [], apiLeaks = [];
  page.on('pageerror', e => problems.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/youtube|net::|ERR_|Failed to load resource|Permissions policy|compute-pressure/.test(m.text())) problems.push('console: ' + m.text()); });
  page.on('request', r => { const u = new URL(r.url()); if (u.origin === new URL(base).origin && u.pathname.startsWith('/api/') && !r.serviceWorker()) apiLeaks.push(u.pathname); });
  // ningun /api/ debe llegar al servidor: lo atiende la demo en el propio navegador
  const ORIGIN = new URL(base).origin;
  await page.route(ORIGIN + '/api/**', route => { apiLeaks.push('RED ' + route.request().url()); route.abort(); });      // solo NUESTRO origen: el reproductor de YouTube tiene sus propias rutas /api/

  await page.goto(base + '/app?bare=1');
  await page.waitForFunction(() => /\d\d:\d\d/.test(document.getElementById('time').textContent), null, { timeout: 8000 }).catch(() => {});
  check('la demo arranca y el reloj funciona', /\d\d:\d\d/.test(await page.textContent('#time')));
  check('hay una insignia «DEMO»', await page.isVisible('#demo-badge'));
  await page.waitForFunction(() => document.getElementById('weather').textContent.includes('21'), null, { timeout: 8000 }).catch(() => {});
  check('el tiempo sale con datos de ejemplo', (await page.textContent('#weather')).includes('21'));
  await page.waitForFunction(() => /\d+%/.test(document.getElementById('ph-pct').textContent), null, { timeout: 8000 }).catch(() => {});
  check('el Pi-hole sale con datos de ejemplo', /27%/.test(await page.textContent('#ph-pct')) || /\d+%/.test(await page.textContent('#ph-pct')));
  check('sin emojis en la pagina', !/[\u{1F300}-\u{1FAFF}\u2600-\u27BF]/u.test(await page.evaluate(() => document.body.innerText)));
  await page.click('#ph-btn');
  await page.waitForFunction(() => document.getElementById('ph-state').textContent === 'En pausa', null, { timeout: 8000 }).catch(() => {});
  check('el boton pausa Pi-hole (simulado)', (await page.textContent('#ph-state')) === 'En pausa');

  // Musix: MP3 player con audio generado de verdad
  await page.click('#mxbtn'); await sleep(500);
  await page.click('#mxhome button[data-go="mp3"]');
  await page.waitForFunction(() => document.querySelectorAll('#mxlist .trk').length === 3, null, { timeout: 6000 }).catch(() => {});
  check('el MP3 Player tiene 3 canciones de demo', (await page.locator('#mxlist .trk').count()) === 3);
  await page.locator('#mxlist .trk').first().click();
  await page.waitForFunction(() => { const a = document.getElementById('mxaudio'); return !a.paused && a.currentTime > 0.3; }, null, { timeout: 8000 }).catch(() => {});
  check('la cancion suena de verdad (audio generado)', await page.evaluate(() => { const a = document.getElementById('mxaudio'); return !a.paused && a.currentTime > 0.3 && a.src.startsWith('blob:'); }));
  await page.click('#mx-back'); await page.click('#mxhome button[data-go="yt"]');
  await page.fill('#mxin', 'https://youtu.be/dQw4w9WgXcQ'); await page.click('#mxgo');
  await page.waitForFunction(() => (document.getElementById('mxframe').getAttribute('src') || '').includes('youtube-nocookie'), null, { timeout: 5000 }).catch(() => {});
  check('YT Music carga el reproductor incrustado', (await page.getAttribute('#mxframe', 'src')) === 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  await page.click('#mx-close'); await sleep(400);

  // Sistema: actualizar (simulado)
  await page.click('#chip-sys'); await sleep(500);
  check('la hoja Sistema ofrece actualizar', (await page.textContent('#upd-btn')).includes('Actualizar'));
  await page.click('#upd-btn');
  await page.waitForFunction(() => document.getElementById('upd-txt').textContent.includes('Actualizado'), null, { timeout: 14000 }).catch(() => {});
  check('la actualizacion simulada termina', (await page.textContent('#upd-txt')).includes('Actualizado'), await page.textContent('#upd-txt'));
  await page.click('#s-close'); await sleep(400);

  // temporizador real (en el navegador)
  await page.click('#chip-timer'); await sleep(500);
  await page.click('#tpanel .presets button[data-s="300"]');
  await page.waitForFunction(() => /\d\d:\d\d/.test(document.getElementById('timer-txt').textContent), null, { timeout: 8000 }).catch(() => {});
  check('un temporizador cuenta atras', /\d\d:\d\d/.test(await page.textContent('#timer-txt')));
  await page.click('#t-close'); await sleep(300);

  // cambio de modo: Casa -> carga -> Iker, sin servidor
  await page.click('button[data-mode="iker"]');
  await page.waitForURL('**/iker', { timeout: 20000 }).catch(() => {});
  check('Modo Iker: pasa por la carga y llega a /iker', page.url().endsWith('/iker'), page.url());
  await page.waitForSelector('#list .item', { timeout: 5000 }).catch(() => {});
  check('las notas de ejemplo estan', (await page.locator('#list .item').count()) === 2);
  await page.click('#new'); await page.fill('#text', 'Nota de prueba #demo\nhola');
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('Guardado'), null, { timeout: 6000 }).catch(() => {});
  await page.reload(); await sleep(700);
  check('las notas se guardan en el navegador (sobreviven a recargar)', (await page.locator('#list .item').count()) === 3);
  check('las etiquetas funcionan', (await page.locator('#tags button').count()) >= 2);

  // voz simulada: lo que escribes lo entiende la «Pi» (si esto se rompe, el simulador contesta cosas absurdas)
  const say = t => page.evaluate(x => window.PCPI_DEMO.say(x), t);
  check('voz: la hora', /^Son las \d{1,2}:\d\d$/.test(await say('qué hora es')));
  check('voz: temporizador con nombre', /para pasta/.test(await say('pon un temporizador de diez minutos para la pasta')));
  check('voz: alargar el temporizador', /^Añadido 1 minuto/.test((await say('añade un minuto al temporizador')).replace('Añadido un minuto', 'Añadido 1 minuto')));
  check('voz: tomar nota', await say('toma nota comprar pan') === 'Anotado');
  check('voz: lista de la compra', /lista de la compra/.test(await say('añade leche a la lista de la compra')));
  check('voz: el tiempo de mañana', /^Mañana habrá una máxima/.test(await say('qué tiempo hará mañana')));
  check('voz: lo que no entiende no rompe nada', /No te he entendido/.test(await say('blablabla')));

  await page.request.get(base + '/').catch(() => {});

  // Modo Dev: consola de mentira
  await page.click('#exit'); await page.waitForURL(u => !u.pathname.endsWith('/iker'), { timeout: 20000 }).catch(() => {});
  await page.waitForURL('**/app', { timeout: 20000 }).catch(() => {});
  await page.waitForSelector('#nav-dev', { timeout: 8000 }).catch(() => {});
  await page.click('#nav-dev');
  await page.waitForURL('**/dev', { timeout: 20000 }).catch(() => {});
  check('Modo Dev: llega a /dev', page.url().endsWith('/dev'), page.url());
  await page.fill('#cmd', 'echo hola demo'); await page.press('#cmd', 'Enter');
  await page.waitForFunction(() => document.getElementById('out').textContent.includes('[código 0]'), null, { timeout: 6000 }).catch(() => {});
  check('la consola de la demo responde', (await page.textContent('#out')).includes('hola demo'));
  await page.fill('#cmd', 'rm -rf /'); await page.press('#cmd', 'Enter');
  await page.waitForFunction(() => document.getElementById('out').textContent.includes('no encontrada'), null, { timeout: 6000 }).catch(() => {});
  check('una orden peligrosa no hace nada (orden no encontrada en la demo)', (await page.textContent('#out')).includes('no encontrada'));

  // marco de dispositivo (en una pantalla grande): la interfaz va dentro de un iframe de 1024x600 escalado
  const big = await browser.newContext({ viewport: { width: 1600, height: 900 }, locale: 'es-ES' });
  const p2 = patchWaitForFunction(await big.newPage());
  await p2.goto(base + '/simulador?p=%2Fapp');
  await p2.waitForSelector('#f', { timeout: 8000 }).catch(() => {});
  const fr = p2.frameLocator('#f');
  await fr.locator('#time').waitFor({ timeout: 8000 }).catch(() => {});
  check('en pantalla grande la demo sale dentro de un marco de dispositivo', await p2.isVisible('#dev') && /\d\d:\d\d/.test(await fr.locator('#time').textContent()));
  const box = await p2.locator('#dev').boundingBox();
  check('el marco cabe en la ventana y mantiene 1024x600', box && box.width <= 1600 && box.height <= 900 && Math.abs(box.width / box.height - 1024 / 600) < 0.02, JSON.stringify(box));
  const stage = await p2.locator('#stage').boundingBox();
  check('el marco no se recorta: cabe dentro del escenario (no queda bajo la cabecera ni la barra de voz)', box && stage && box.y >= stage.y - 1 && box.y + box.height <= stage.y + stage.height + 1 && box.x >= -1 && box.x + box.width <= stage.width + 1, JSON.stringify({ box, stage }));
  await p2.click('button[data-m="iker"]');
  await p2.waitForFunction(() => document.getElementById('f').contentWindow.location.pathname === '/iker', null, { timeout: 20000 }).catch(() => {});
  check('los botones del marco cambian de modo (con su carga)', await p2.evaluate(() => document.getElementById('f').contentWindow.location.pathname) === '/iker');
  await big.close();
  // primera visita: «encender la Pi» (video de inicio REAL de extra-assets y carrusel con imagenes y GIFs reales)
  const first = await browser.newContext({ viewport: { width: 1280, height: 760 }, locale: 'es-ES' });
  const p4 = patchWaitForFunction(await first.newPage());
  await p4.goto(base + '/simulador');
  await p4.waitForSelector('#f', { timeout: 8000 }).catch(() => {});
  const f4 = p4.frameLocator('#f');
  await f4.locator('#intro-video').waitFor({ state: 'attached', timeout: 8000 }).catch(() => {});
  await sleep(2500);
  const introSrc = await f4.locator('#intro-video').getAttribute('src').catch(() => null);
  check('la primera visita arranca con un video de inicio real', /^\/assets\/start\/Inicio\d\.mp4$/.test(introSrc || ''), String(introSrc));
  const vr = await p4.request.get(base + (introSrc || '/nada'));
  check('ese video existe y es un mp4', vr.ok() && (vr.headers()['content-type'] || '').includes('video'), String(vr.status()));
  await first.close();
  const man = await (await ctx.request.get(base + '/assets/manifest.json')).json();
  check('el carrusel de carga usa imagenes y GIFs reales', man.loading.length >= 3 && man.loading.every(m => m.url.startsWith('/assets/loading/')), JSON.stringify(man.loading.slice(0, 2)));
  const gif = await ctx.request.get(base + man.loading.find(m => m.type === 'gif').url);
  check('un GIF real se sirve bien', gif.ok() && (gif.headers()['content-type'] || '').includes('gif'));
  const phone = await browser.newContext({ viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true });
  const p3 = await phone.newPage();
  await p3.goto(base + '/simulador'); await p3.waitForSelector('#dev', { timeout: 8000 }).catch(() => {});
  const pb = await p3.locator('#dev').boundingBox();
  check('en un movil la interfaz se escala para caber', pb && pb.width <= 390, JSON.stringify(pb));
  await phone.close();
  check('ninguna peticion /api/ llega a un servidor', apiLeaks.length === 0, apiLeaks.slice(0, 4).join(', '));
  check('sin errores de JavaScript ni de CSP en la consola', problems.length === 0, problems.join(' | '));
  await browser.close();
  const failed = results.filter(r => !r.ok);
  for (const r of results) console.log((r.ok ? 'OK   ' : 'FAIL ') + r.name + (r.ok ? '' : '   -> ' + r.extra));
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('ERROR', e); process.exit(2); });
