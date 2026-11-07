// Accesibilidad basica de la demo: todo boton, enlace, cuadro o interruptor VISIBLE tiene un nombre (texto, aria-label, title o placeholder).
// Uso: node a11y_smoke.js URL
const { chromium } = require('playwright');
const base = process.argv[2];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1024, height: 600 } });
  let fallos = 0;
  for (const ruta of ['/app', '/iker', '/dev', '/escritorio', '/']) {
    await page.goto(base + ruta + (ruta === '/' ? '' : '?bare=1'));
    await page.waitForTimeout(1500);
    const sinNombre = await page.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll('button,a[href],input,select,textarea,[role=button],[role=switch]')) {
        const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden || el.type === 'hidden') continue;
        const nombre = (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.getAttribute('placeholder') || el.value || '').trim();
        if (!nombre) out.push(el.tagName + '#' + el.id + '.' + el.className);
      }
      return out;
    });
    console.log((sinNombre.length ? 'FALLO ' : 'OK    ') + 'controles con nombre en ' + ruta + (sinNombre.length ? ' -> ' + sinNombre.join(', ') : ''));
    fallos += sinNombre.length;
  }
  // sin desplazamiento horizontal en la portada y el simulador, de movil pequeño a pantalla grande
  for (const [w, h] of [[320, 568], [390, 844], [768, 1024], [1920, 1080]]) {
    await page.setViewportSize({ width: w, height: h });
    for (const ruta of ['/', '/simulador']) {
      await page.goto(base + ruta); await page.waitForTimeout(1000);
      const [ancho, ventana] = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
      const mal = ancho > ventana + 1;
      console.log((mal ? 'FALLO ' : 'OK    ') + 'sin desplazamiento horizontal en ' + ruta + ' a ' + w + 'x' + h + (mal ? ' (' + ancho + ' > ' + ventana + ')' : ''));
      fallos += mal ? 1 : 0;
    }
  }
  await browser.close();
  process.exit(fallos ? 1 : 0);
})().catch(e => { console.error('ERROR', e); process.exit(2); });
