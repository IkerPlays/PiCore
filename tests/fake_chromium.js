// «Chromium de mentira» para la prueba de Pi virtual: pcpi-session lo lanza como si fuera el navegador del kiosco, pero
// por dentro abre la direccion en un Chromium real sin pantalla (Playwright), asi las paginas se ejecutan de verdad.
// Cada navegacion se apunta en $FAKE_CHROMIUM_LOG ("PID URL"). Se cierra al recibir SIGTERM.
const fs = require('fs');
const { chromium } = require('playwright');
const url = process.argv[process.argv.length - 1];
const log = line => fs.appendFileSync(process.env.FAKE_CHROMIUM_LOG, process.pid + ' ' + line + '\n');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 }, locale: 'es-ES' });
  const page = await ctx.newPage();
  page.on('framenavigated', f => { if (f === page.mainFrame()) log('nav ' + f.url()); });
  const bye = async () => { try { await browser.close(); } catch (e) {} process.exit(0); };
  process.on('SIGTERM', bye); process.on('SIGINT', bye);
  log('start ' + process.argv.slice(2).join(' '));
  await page.goto(url).catch(e => log('error ' + e.message));
  setInterval(() => {}, 1000);
})();
