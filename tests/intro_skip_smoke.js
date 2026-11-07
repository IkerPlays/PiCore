// Boton «Saltar» del Inicio. Uso: node intro_skip_smoke.js URL [noskip]
const { chromium } = require('playwright');
const { patchWaitForFunction } = require('./pw_helpers');
const base = process.argv[2], expectNoSkip = process.argv[3] === 'noskip', noFlag = process.argv[3] === 'nosound';
const results = [];
const check = (name, ok, extra) => results.push({ name, ok: !!ok, extra: extra || '' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  // como la Pi (con la bandera de autoplay) o como un navegador normal (sin ella: el sonido esta bloqueado hasta tocar)
  const browser = await chromium.launch({ args: ['--autoplay-policy=' + (noFlag ? 'document-user-activation-required' : 'no-user-gesture-required')] });
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 } });
  const page = await ctx.newPage();
  patchWaitForFunction(page);
  const problems = [];
  page.on('pageerror', e => problems.push(e.message));
  await page.goto(base + '/loading?to=home&boot=1');
  await page.waitForFunction(() => { const v = document.getElementById('intro-video'); return v && v.currentTime > 0.3; }, null, { timeout: 15000 })
        .catch(() => {});
  const playing = await page.evaluate(() => document.getElementById('intro-video').currentTime);
  check('el video de inicio se reproduce', playing > 0, String(playing));

  if (noFlag) {
    await page.waitForSelector('#unmute', { state: 'visible', timeout: 4000 }).catch(() => {});      // el aviso sale un instante despues de que el navegador rechace el sonido
    check('sin permiso de sonido el video va mudo y lo avisa', (await page.evaluate(() => document.getElementById('intro-video').muted)) && await page.isVisible('#unmute'));
    await page.click('#intro');                                     // un toque en cualquier sitio
    check('un toque activa el sonido', !(await page.evaluate(() => document.getElementById('intro-video').muted)) && await page.isHidden('#unmute'));
    check('y el video sigue reproduciendose', (await page.evaluate(() => !document.getElementById('intro-video').paused)));
  } else {
    check('con permiso (como en la Pi) suena desde el principio, sin aviso', !(await page.evaluate(() => document.getElementById('intro-video').muted)) && await page.isHidden('#unmute'));
  }

  // el boton NO esta antes de los 6 s del video
  await page.waitForFunction(() => document.getElementById('intro-video').currentTime >= 4, null, { timeout: 15000 }).catch(() => {});
  check('a los 4 s todavia no hay boton', await page.isHidden('#intro-skip'));

  if (noFlag) {
    // (solo se comprueba el sonido)
  } else if (expectNoSkip) {
    await page.waitForFunction(() => document.getElementById('intro-video').currentTime >= 7.5, null, { timeout: 15000 }).catch(() => {});
    check('este video no lleva boton ni a los 7 s', await page.isHidden('#intro-skip'));
  } else {
    await page.waitForFunction(() => !document.getElementById('intro-skip').hidden, null, { timeout: 15000 }).catch(() => {});
    const t = await page.evaluate(() => document.getElementById('intro-video').currentTime);
    check('el boton aparece a los 6 s del video (no antes)', t >= 5.95 && t < 6.6, String(t));
    const box = await page.evaluate(() => { const r = document.getElementById('intro-skip').getBoundingClientRect(); return { r: r.right, b: r.bottom, w: r.width, h: r.height }; });
    check('es pequeño', box.w < 110 && box.h < 36, JSON.stringify(box));
    check('esta en la esquina inferior derecha', box.r > 1024 - 40 && box.b > 600 - 40, JSON.stringify(box));
    await sleep(500);
    await page.click('#intro-skip');
    await page.waitForSelector('#stage.on', { timeout: 6000 }).catch(() => {});
    check('al pulsarlo salta a la pantalla de carga sin esperar al final del video', await page.evaluate(() => document.getElementById('stage').classList.contains('on')));
  }
  check('sin errores de JavaScript', problems.length === 0, problems.join(' | '));
  await browser.close();
  let bad = 0;
  for (const r of results) { console.log((r.ok ? 'OK   ' : 'FALLO') + ' ' + r.name + (r.ok ? '' : '  [' + r.extra + ']')); if (!r.ok) bad++; }
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
