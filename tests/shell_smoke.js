// Portada y carcasa del simulador: pestañas con teclado, «Volver arriba», barra de progreso, tecla «?», enlace ?say=, aria-pressed.
// Uso: node shell_smoke.js URL
const { chromium } = require('playwright');
const base = process.argv[2];
const resultados = [];
const check = (nombre, ok, extra) => resultados.push({ nombre, ok: !!ok, extra });
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'es-ES' });
  const errores = [];
  // --- portada
  const p = await ctx.newPage();
  p.on('pageerror', e => errores.push('portada: ' + e.message));
  await p.goto(base + '/');
  await p.focus('.tabs button[data-m=casa]'); await p.keyboard.press('ArrowRight');
  check('las pestañas se mueven con las flechas', await p.evaluate(() => document.querySelector('.mode.on').dataset.m) === 'iker');
  await p.keyboard.press('End'); await p.keyboard.press('ArrowRight');
  check('las flechas dan la vuelta (Fin y luego derecha vuelve a Casa)', await p.evaluate(() => document.querySelector('.mode.on').dataset.m) === 'casa');
  check('«Volver arriba» empieza oculto', await p.evaluate(() => !document.getElementById('top').classList.contains('on')));
  await p.evaluate(() => scrollTo(0, 1500)); await p.waitForTimeout(500);
  check('«Volver arriba» sale al bajar', await p.evaluate(() => document.getElementById('top').classList.contains('on')));
  check('la barra de progreso avanza', await p.evaluate(() => /scaleX\(0?\.\d+|scaleX\(1/.test(document.getElementById('prog').style.transform)));
  check('la barra superior marca la sección que se lee', await p.evaluate(() => !!document.querySelector('.nav nav a[aria-current]')));
  await p.click('#top'); await p.waitForTimeout(1200);
  check('«Volver arriba» sube', await p.evaluate(() => scrollY < 50));
  const chips = await p.$$eval('a.chip-say', a => a.map(x => x.getAttribute('href')));
  check('hay frases de ejemplo que abren el simulador', chips.length >= 6 && chips.every(h => h.startsWith('/simulador?say=')), chips.length);
  // --- simulador
  const s = await ctx.newPage();
  s.on('pageerror', e => errores.push('simulador: ' + e.message));
  await s.goto(base + '/simulador'); await s.waitForTimeout(800);
  await s.keyboard.press('?');
  check('la tecla ? abre la ayuda de atajos', await s.evaluate(() => !document.getElementById('keys').hidden));
  await s.keyboard.press('Escape');
  check('Esc cierra la ayuda', await s.evaluate(() => document.getElementById('keys').hidden));
  check('los botones de modo dicen cuál está activo (aria-pressed)', await s.evaluate(() => [...document.querySelectorAll('button[data-m]')].some(b => b.getAttribute('aria-pressed') === 'true')));
  const s2 = await ctx.newPage();
  await s2.goto(base + '/simulador?say=' + encodeURIComponent('cuánto es 12 por 5')); await s2.waitForTimeout(5000);
  check('?say= ejecuta la orden al abrir', /Son 60/.test(await s2.textContent('#reply')), await s2.textContent('#reply'));
  // --- la voz abre y cierra hojas de Casa (canal /api/ui)
  const c = await ctx.newPage();
  c.on('pageerror', e => errores.push('casa: ' + e.message));
  await c.goto(base + '/app?bare=1'); await c.waitForTimeout(2500);
  for (const [frase, panel] of [['abre el tiempo', 'wpanel'], ['abre los temporizadores', 'tpanel'], ['abre musix', 'mxpanel']]) {
    await c.evaluate(f => window.PCPI_DEMO.say(f), frase);
    const abre = await c.waitForFunction(id => document.getElementById(id).classList.contains('on'), panel, { timeout: 9000 }).then(() => true).catch(() => false);
    check('la voz abre la hoja: ' + frase, abre);
    await c.evaluate(() => window.PCPI_DEMO.say('cierra esto'));
    const cierra = await c.waitForFunction(id => !document.getElementById(id).classList.contains('on'), panel, { timeout: 9000 }).then(() => true).catch(() => false);
    check('«cierra esto» la cierra (' + panel + ')', cierra);
  }
  check('sin errores de JavaScript', errores.length === 0, errores.join(' | '));
  await browser.close();
  for (const r of resultados) console.log((r.ok ? 'OK   ' : 'FAIL ') + r.nombre + (r.ok ? '' : '  -> ' + r.extra));
  process.exit(resultados.every(r => r.ok) ? 0 : 1);
})();
