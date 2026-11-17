// Pantalla de Carga en un navegador de verdad. Uso: node loading_smoke.js http://127.0.0.1:PUERTO
const { chromium } = require('playwright');
const { patchWaitForFunction } = require('./pw_helpers');
const base = process.argv[2];
const results = [];
const check = (name, ok, extra) => results.push({ name, ok: !!ok, extra: extra || '' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const pct = page => page.evaluate(() => parseInt(document.getElementById('pct').textContent, 10));

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const newPage = async () => {
    const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 } });
    const p = await ctx.newPage();
    patchWaitForFunction(p);
    p.on('pageerror', e => problems.push('pageerror: ' + e.message));
    return p;
  };

  // ---- 0) encendido con un Inicio.mp4 ROTO: pantalla en blanco y luego sigue sola a la carga
  let page = await newPage();
  await page.goto(base + '/loading?to=home&boot=1');
  await page.waitForFunction(() => !document.getElementById('intro').hidden, null, { timeout: 5000 }).catch(() => {});
  const bg = await page.evaluate(() => getComputedStyle(document.getElementById('intro')).backgroundColor);
  check('al encender sale una pantalla en blanco', bg === 'rgb(255, 255, 255)', bg);
  await page.waitForSelector('#stage.on', { timeout: 15000 }).catch(() => {});
  check('un video roto no bloquea: pasa a la pantalla de carga', await page.evaluate(() => document.getElementById('stage').classList.contains('on')));
  await page.context().close();

  // ---- 1) carga normal: la barra sigue el progreso real de 0 a 100 %, sin efecto TV ni boton Saltar, y entra en el modo
  page = await newPage();
  await page.goto(base + '/loading?to=home&boot=0');
  await page.waitForSelector('#stage.on');
  check('sale el pop-up «Cargando»', (await page.textContent('#title')) === 'Cargando');
  check('empieza en 0 %', (await pct(page)) <= 15);
  const media = await page.evaluate(() => document.querySelectorAll('#media .slide').length);
  check('el carrusel muestra las imagenes y gifs de extra-assets', media === 3, String(media));
  check('ya no existe el efecto TV «x2» ni el boton Saltar de la carga', await page.evaluate(() => !document.getElementById('tv') && !document.getElementById('skip')));

  const seen = []; const t0 = Date.now();
  while (Date.now() - t0 < 20000 && !page.url().endsWith('/')) {
    const v = await pct(page).catch(() => -1);
    if (v >= 0) seen.push(v);
    await sleep(60);
    if (page.url().includes('/loading') === false) break;
  }
  check('nunca baja (progreso monotono)', seen.every((v, i) => i === 0 || v >= seen[i - 1]), seen.join(','));
  check('la barra llega al 100 %', Math.max(...seen) >= 99, String(Math.max(...seen)));
  check('al terminar entra en la UI de Casa', new URL(page.url()).pathname === '/', page.url());
  await page.context().close();

  // ---- 2) escritorio: avisa al vigilante en vez de navegar
  page = await newPage();
  await page.goto(base + '/loading?to=desktop&boot=0');
  await page.waitForFunction(() => document.getElementById('pct').textContent === '100%', null, { timeout: 20000 });
  await sleep(1500);
  check('en modo Escritorio se queda en la pagina de carga', page.url().includes('/loading'));
  await page.context().close();

  check('sin errores en la consola', problems.length === 0, problems.join(' | '));
  await browser.close();
  let bad = 0;
  for (const r of results) { console.log((r.ok ? 'OK   ' : 'FALLO') + ' ' + r.name + (r.ok ? '' : '  [' + r.extra + ']')); if (!r.ok) bad++; }
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
