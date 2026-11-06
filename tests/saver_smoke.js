// Salvapantallas: tras estar quieto salen las fotos con el reloj; un toque lo quita. Uso: node saver_smoke.js URL [solo-reloj]
const { chromium } = require('playwright');
const { patchWaitForFunction, sleep } = require('./pw_helpers');
const base = process.argv[2], clockOnly = process.argv[3] === 'solo-reloj';
const results = [];
const check = (name, ok, extra) => results.push({ name, ok: !!ok, extra: extra || '' });

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1024, height: 600 } })).newPage();
  patchWaitForFunction(page);
  const problems = [];
  page.on('pageerror', e => problems.push(e.message));
  await page.goto(base + '/');
  await sleep(1500);
  check('al principio NO esta puesto', !(await page.evaluate(() => document.getElementById('saver').classList.contains('on'))));
  await page.waitForFunction(() => document.getElementById('saver').classList.contains('on'), null, { timeout: 15000 }).catch(() => {});
  check('tras unos segundos quieto, aparece', await page.evaluate(() => document.getElementById('saver').classList.contains('on')));
  check('con la hora', /\d\d:\d\d/.test(await page.textContent('#sc-time')));
  if (clockOnly) {
    check('sin fotos: solo reloj (fondo oscuro)', await page.evaluate(() => document.getElementById('saver').classList.contains('only')));
  } else {
    await page.waitForFunction(() => document.querySelectorAll('#saver .ph.show').length >= 1, null, { timeout: 8000 }).catch(() => {});
    const bg = await page.evaluate(() => (document.querySelector('#saver .ph.show') || {style:{}}).style.backgroundImage);
    check('enseña una foto de extra-assets/photos', /assets\/photos\//.test(bg), bg);
    await page.waitForFunction(() => document.querySelectorAll('#saver .ph').length >= 2, null, { timeout: 8000 }).catch(() => {});
    check('y pasa a la siguiente foto', (await page.evaluate(() => document.querySelectorAll('#saver .ph').length)) >= 2);
  }
  // un toque lo quita y ESE toque no pulsa nada de debajo
  const before = await page.evaluate(() => document.getElementById('switching').classList.contains('on'));
  await page.mouse.click(200, 520);          // donde esta el boton «Modo Iker»
  await sleep(500);
  check('un toque lo quita', !(await page.evaluate(() => document.getElementById('saver').classList.contains('on'))));
  check('y el toque no activa lo que hay debajo', !before && !(await page.evaluate(() => document.getElementById('switching').classList.contains('on'))));
  await sleep(2500);
  check('no vuelve enseguida', !(await page.evaluate(() => document.getElementById('saver').classList.contains('on'))));
  // con un panel abierto no se pone
  await page.click('#chip-bright');
  await sleep(8500);
  check('con un panel abierto no se pone', !(await page.evaluate(() => document.getElementById('saver').classList.contains('on'))));
  check('sin errores de JavaScript', problems.length === 0, problems.join(' | '));
  await browser.close();
  let bad = 0;
  for (const r of results) { console.log((r.ok ? 'OK   ' : 'FALLO') + ' ' + r.name + (r.ok ? '' : '  [' + r.extra + ']')); if (!r.ok) bad++; }
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
