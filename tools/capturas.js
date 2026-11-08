// Capturas de la interfaz (1024x600, la pantalla de la Pi) desde la demo. Uso: node capturas.js URL CARPETA_DE_SALIDA
// Las usa tools/capturas.py (make capturas) para regenerar las imagenes de la web y de la documentacion.
const { chromium } = require('playwright');
const base = process.argv[2], out = process.argv[3];
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const nueva = async (esquema) => {
    const ctx = await browser.newContext({ viewport: { width: 1024, height: 600 }, deviceScaleFactor: 1, colorScheme: esquema, locale: 'es-ES' });
    const p = await ctx.newPage();
    p.on('pageerror', e => { console.error('ERROR de pagina:', e.message); process.exitCode = 2; });
    return p;
  };
  const abrir = async (p, ruta, tema) => {
    await p.goto(base + ruta + '?bare=1'); await sleep(2200);
    await p.evaluate(t => { document.documentElement.dataset.theme = t; const b = document.getElementById('demo-badge'); if (b) b.remove(); }, tema);
    await sleep(900);
  };
  const foto = async (p, nombre) => { await p.evaluate(() => { const b = document.getElementById('demo-badge'); if (b) b.remove(); }); await sleep(250); await p.screenshot({ path: out + '/' + nombre + '.png' }); console.log('ok ' + nombre); };
  const cerrarHojas = async (p) => { await p.click('#scrim', { position: { x: 5, y: 5 } }).catch(() => {}); await sleep(500); };

  for (const [tema, esquema, nombre] of [['light', 'light', 'casa-claro'], ['dark', 'dark', 'casa-oscuro']]) {
    const p = await nueva(esquema); await abrir(p, '/app', tema); await foto(p, nombre); await p.context().close();
  }
  {
    const p = await nueva('light'); await abrir(p, '/app', 'light');
    await p.click('#mxbtn'); await sleep(900); await foto(p, 'musix');
    await p.click('#mxhome button[data-go="mp3"]'); await sleep(800); await p.click('#mxlist .trk >> nth=0'); await sleep(1200); await foto(p, 'musix-mp3'); await cerrarHojas(p);
    await p.click('#weather'); await sleep(900); await foto(p, 'tiempo'); await cerrarHojas(p);
    await p.click('#chip-wifi'); await sleep(900); await foto(p, 'wifi'); await cerrarHojas(p);
    await p.evaluate(() => { for (const m of ['pon un temporizador de diez minutos para la pasta', 'pon un temporizador de una hora para estudiar']) PCPI_DEMO.say(m); }); await sleep(9000);
    await p.click('#chip-timer'); await sleep(900); await foto(p, 'temporizadores'); await p.click('#t-close'); await sleep(500);
    await p.evaluate(() => { localStorage.removeItem('pcpi-demo-timers'); }); await p.reload(); await sleep(2200);
    await p.evaluate(() => { document.documentElement.dataset.theme = 'light'; }); await p.click('#chip-sys'); await sleep(900); await foto(p, 'sistema');
    await p.evaluate(() => document.getElementById('prefs').scrollIntoView({ block: 'center' })); await sleep(500); await foto(p, 'ajustes');
    await p.context().close();
  }
  {
    const p = await nueva('light'); await abrir(p, '/iker', 'light'); await p.click('#list .item >> nth=0'); await sleep(900); await foto(p, 'iker'); await p.context().close();
  }
  {
    const p = await nueva('dark'); await abrir(p, '/dev', 'dark');
    for (const c of ['pcpi-doctor', 'pcpi-config show']) { await p.fill('#cmd', c); await p.press('#cmd', 'Enter'); await sleep(1100); }
    await foto(p, 'dev'); await p.context().close();
  }
  await browser.close();
})().catch(e => { console.error('ERROR', e); process.exit(2); });
