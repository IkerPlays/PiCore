// Casa, Iker y Dev a varios tamaños de pantalla: ningun boton ni campo puede quedar fuera de la ventana (ni haber scroll horizontal).
// Uso: node overflow_smoke.js URL
const { chromium } = require('playwright');
const base = process.argv[2];
(async () => {
  const browser = await chromium.launch(); const problemas = [];
  for (const [w, h] of [[1024, 600], [800, 480], [1280, 720]]) {
    for (const [ruta, modo] of [['/app?bare=1', 'home'], ['/iker', 'iker'], ['/dev', 'dev']]) {
      const p = await browser.newPage({ viewport: { width: w, height: h } });
      await p.goto(base + '/app?bare=1');
      await p.evaluate(m => localStorage.setItem('pcpi-demo-mode', JSON.stringify(m)), modo);
      await p.goto(base + ruta); await p.waitForTimeout(2200);
      const r = await p.evaluate(() => ({
        sw: document.documentElement.scrollWidth, iw: innerWidth,
        fuera: [...document.querySelectorAll('button, input, .chip')].filter(e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && (b.right > innerWidth + 1 || b.left < -1); }).map(e => e.id || e.className || e.tagName).slice(0, 5),
      }));
      if (r.sw > r.iw || r.fuera.length) problemas.push(`${w}x${h} ${ruta}: scrollWidth ${r.sw} > ${r.iw}, fuera de la ventana: ${r.fuera.join(', ') || '-'}`);
      await p.close();
    }
  }
  await browser.close();
  if (problemas.length) { console.log(problemas.join('\n')); process.exit(1); }
  console.log('OK   Casa, Iker y Dev caben en 800, 1024 y 1280 px de ancho');
})();
