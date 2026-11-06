// Pantalla de descarga del intro 4. Uso: node download_smoke.js URL [skip]
const { chromium } = require('playwright');
const base = process.argv[2], mode = process.argv[3] || 'wait';
const results = [];
const check = (name, ok, extra) => results.push({ name, ok: !!ok, extra: extra || '' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext({ viewport: { width: 1024, height: 600 } })).newPage();
  const problems = [];
  page.on('pageerror', e => problems.push(e.message));
  await page.goto(base + '/loading?to=home&boot=1');
  await page.waitForFunction(() => !document.getElementById('dl').hidden, null, { timeout: 8000 }).catch(() => {});
  check('sale la pantalla «Descargando contenido extra»', await page.isVisible('#dl'));
  check('dice que es solo la primera vez', (await page.textContent('#dl-sub')).includes('primera vez'));
  check('hay boton para continuar sin esperar', await page.isVisible('#dl-skip'));
  await sleep(1200);
  const mid = parseInt(await page.textContent('#dl-pct'), 10);
  check('el porcentaje avanza (no se queda en 0)', mid > 0 && mid < 100, String(mid));
  check('se ven los MB descargados', /MB|KB|de/.test(await page.textContent('#dl-bytes')), await page.textContent('#dl-bytes'));
  const w = await page.evaluate(() => parseFloat(document.getElementById('dl-fill').style.width));
  check('la barra se mueve', w > 0 && w < 100, String(w));

  if (mode === 'skip') {
    await page.click('#dl-skip');
    await page.waitForSelector('#stage.on', { timeout: 20000 }).catch(() => {});
    check('«Continuar sin esperar» sigue con el arranque', await page.evaluate(() => document.getElementById('stage').classList.contains('on')));
    check('la pantalla de descarga se oculta', await page.isHidden('#dl'));
  } else {
    await page.waitForFunction(() => document.getElementById('dl').hidden, null, { timeout: 40000 }).catch(() => {});
    check('al terminar la descarga se oculta la pantalla', await page.isHidden('#dl'));
    await page.waitForSelector('#stage.on', { timeout: 40000 }).catch(() => {});
    check('y el arranque continua hasta la carga', await page.evaluate(() => document.getElementById('stage').classList.contains('on')));
  }
  check('sin errores de JavaScript', problems.length === 0, problems.join(' | '));
  await browser.close();
  let bad = 0;
  for (const r of results) { console.log((r.ok ? 'OK   ' : 'FALLO') + ' ' + r.name + (r.ok ? '' : '  [' + r.extra + ']')); if (!r.ok) bad++; }
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
