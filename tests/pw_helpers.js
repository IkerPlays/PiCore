// Ayudantes comunes de las pruebas de navegador.
//
// page.waitForFunction() de algunas versiones de Playwright usa `eval` dentro de la pagina, y nuestras paginas llevan una
// politica CSP estricta (sin 'unsafe-eval') que lo prohibe. Esta version espera con page.evaluate() (que no usa eval),
// asi las pruebas dan igual resultado en cualquier version de Playwright y se sigue comprobando la CSP de verdad.
const sleep = ms => new Promise(r => setTimeout(r, ms));

function patchWaitForFunction(page) {
  page.waitForFunction = async (fn, arg, opts = {}) => {
    const timeout = opts.timeout === undefined ? 30000 : opts.timeout, t0 = Date.now();
    for (;;) {
      let ok = false;
      try { ok = await page.evaluate(fn, arg); } catch (e) { /* la pagina esta navegando: se reintenta */ }
      if (ok) return ok;
      if (timeout && Date.now() - t0 > timeout) throw new Error('waitForFunction: Timeout ' + timeout + 'ms exceeded');
      await sleep(typeof opts.polling === 'number' ? opts.polling : 50);
    }
  };
  return page;
}

module.exports = { patchWaitForFunction, sleep };
