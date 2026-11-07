# Cómo colaborar en PiCore

¡Gracias por interesarte! PiCore es un proyecto personal en español; las ideas, los fallos y las mejoras son bienvenidos.

## Antes de empezar

- **Pruébalo sin Pi:** la [demo web](https://picoreweb.netlify.app/) o, en local, `make demo` (sin servidor) y `make emulate` (servidor real con un Pi-hole falso).
- **Lee [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):** explica quién ejecuta qué (el servidor corre con un sandbox de systemd y no puede tocar el sistema; lo que hay que *hacer* lo ejecuta `pcpi-session` en la sesión gráfica).

## Preparar el entorno

Solo hace falta Python 3 (sin dependencias para el servidor). Para las pruebas de navegador, además `node` y Playwright:

```bash
npm install -g playwright && playwright install chromium    # opcional: sin esto, esas pruebas se omiten
make test        # todas las pruebas (unos 7 minutos con las de navegador)
make lint        # shell y Python
```

## Reglas del proyecto

1. **Todo el texto va en español** (interfaz, documentación, mensajes). Los nombres de código pueden ir en inglés.
2. **Sin emojis en la interfaz:** los iconos son SVG del sprite `home/web/static/icons.svg` (`<svg class="ic"><use href="#i-nombre"/></svg>`). Añade el icono ahí si falta.
3. **Una función nueva lleva pruebas** (`tests/`) y se documenta (tutorial, README o ARCHITECTURE según toque). Si cambia la interfaz, `tests/ui_smoke.js` la recorre.
4. **Si una página usa una ruta `/api/...` nueva, simúlala en `web-demo/demo.js`:** `tests/test_web_demo.py` falla si falta.
5. **Honestidad:** nada de esto se ha probado todavía en una Raspberry Pi real. No escribas «funciona» si solo lo has probado con simulaciones; di qué has probado y qué no.
6. **Seguridad primero:** las rutas que cambian cosas exigen la cabecera `X-PCPI` y cliente local; los nombres de archivo y los enlaces se validan; nada de `eval`. Mira `tests/test_security.py`.
7. Los textos de las pruebas y los commits, en español y concretos («Musix: temporizador para dormir», no «arreglos»).

## Cómo proponer un cambio

1. Abre un *issue* si es grande (para ponernos de acuerdo antes de que trabajes).
2. Haz una rama, cambia lo que toque y ejecuta `make test` y `make lint`.
3. Abre la *pull request* explicando **qué cambia, por qué y qué has probado (y qué no)**. El CI (`.github/workflows/test.yml`) debe quedar en verde.

## Licencia de lo que aportes

Al enviar una *pull request* aceptas que tu aportación se publique bajo la licencia MIT del proyecto ([LICENSE](LICENSE)). No subas archivos con derechos de terceros (vídeos, imágenes, música).

## Fallos de seguridad

No los abras como *issue* público: mira [SECURITY.md](SECURITY.md).
