// Pantalla de Carga en un navegador de verdad. Uso: node loading_smoke.js http://127.0.0.1:PUERTO fake_seconds
const { chromium } = require('playwright');
const base = process.argv[2];
const results = [];
const check = (name, ok, extra) => results.push({ name, ok: !!ok, extra: extra || '' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const pct = page => page.evaluate(() => parseInt(document.getElementById('pct').textContent, 10));
const tvOn = page => page.evaluate(() => document.getElementById('tv').classList.contains('on'));

(async () => {
  const browser = await chromium.launch();
  const problems = [];
  const newPage = async () => {
    const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 } });
    const p = await ctx.newPage();
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

  // ---- 1) carga completa: 85 % real, luego efecto TV x2 hasta 100 %, y entra en el modo
  page = await newPage();
  await page.goto(base + '/loading?to=home&boot=0');
  await page.waitForSelector('#stage.on');
  check('sale el pop-up «Cargando»', (await page.textContent('#title')) === 'Cargando');
  check('empieza en 0 %', (await pct(page)) <= 15);
  const media = await page.evaluate(() => document.querySelectorAll('#media .slide').length);
  check('el carrusel muestra las imagenes y gifs de extra-assets', media === 3, String(media));

  const seen = []; let tvAt = -1, t0 = Date.now();
  while (Date.now() - t0 < 20000 && !page.url().endsWith('/')) {
    const v = await pct(page).catch(() => -1);
    const tv = await tvOn(page).catch(() => false);
    if (v >= 0) seen.push(v);
    if (tv && tvAt < 0) tvAt = v;
    await sleep(60);
    if (page.url().includes('/loading') === false) break;
  }
  const beforeTv = seen.slice(0, seen.findIndex(v => v === tvAt) + 1);
  check('nunca baja (progreso monotono)', seen.every((v, i) => i === 0 || v >= seen[i - 1]), seen.join(','));
  check('antes del efecto TV no pasa del 85 %', Math.max(0, ...beforeTv) <= 85, String(Math.max(0, ...beforeTv)));
  check('el efecto TV «x2» aparece al 85 %', tvAt >= 84 && tvAt <= 90, String(tvAt));
  check('despues del 85 % sigue subiendo hasta 100 %', Math.max(...seen) >= 99, String(Math.max(...seen)));
  check('al terminar entra en la UI de Casa', new URL(page.url()).pathname === '/', page.url());
  await page.context().close();

  // ---- 2) boton Skip: salta la carga falsa
  page = await newPage();
  await page.goto(base + '/loading?to=iker&boot=0');
  await page.waitForFunction(() => document.getElementById('tv').classList.contains('on'), null, { timeout: 20000 });
  check('el texto del efecto TV dice «x2»', (await page.textContent('#tv .osd')).includes('x2'));
  check('aparece el boton Saltar', await page.isVisible('#skip'));
  const v0 = await pct(page);
  const t1 = Date.now();
  await page.click('#skip');
  await page.waitForFunction(() => location.pathname === '/iker' || document.getElementById('title').textContent === 'Listo', null, { timeout: 5000 }).catch(() => {});
  const done = await page.evaluate(() => document.getElementById('pct').textContent);
  check('Saltar completa al 100 % enseguida', done === '100%' && Date.now() - t1 < 4000, v0 + ' -> ' + done);
  await page.context().close();

  // ---- 3) escritorio: avisa al vigilante en vez de navegar
  page = await newPage();
  await page.goto(base + '/loading?to=desktop&boot=0');
  await page.waitForFunction(() => document.getElementById('tv').classList.contains('on'), null, { timeout: 20000 });
  await page.click('#skip');
  await sleep(1500);
  check('en modo Escritorio se queda en la pagina de carga', page.url().includes('/loading'));
  await page.context().close();

  check('sin errores en la consola', problems.length === 0, problems.join(' | '));
  await browser.close();
  let bad = 0;
  for (const r of results) { console.log((r.ok ? 'OK   ' : 'FALLO') + ' ' + r.name + (r.ok ? '' : '  [' + r.extra + ']')); if (!r.ok) bad++; }
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
