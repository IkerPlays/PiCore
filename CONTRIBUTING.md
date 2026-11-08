# Cómo colaborar en PiCore

¡Gracias por interesarte! PiCore es un proyecto personal en español; las ideas, los fallos y las mejoras son bienvenidos.

## Antes de empezar

- **Pruébalo sin Pi:** la [demo web](https://picoreweb.netlify.app/) o, en local, `make demo` (sin servidor) y `make emulate` (servidor real con un Pi-hole falso).
- **Lee [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md):** explica quién ejecuta qué (el servidor corre con un sandbox de systemd y no puede tocar el sistema; lo que hay que *hacer* lo ejecuta `pcpi-session` en la sesión gráfica).

## Preparar el entorno

Solo hace falta Python 3 (sin dependencias para el servidor). Para las pruebas de navegador, además `node` y Playwright:

```bash
npm install -g playwright && playwright install chromium    # opcional: sin esto, esas pruebas se omiten
make test        # todas las pruebas (unos 8 minutos con las de navegador)
make rapido      # las que no abren navegador (unos 3 minutos)
make capturas    # regenera las capturas de la web y la documentación (Playwright y Pillow)
make lint        # shell y Python (con pyflakes si lo tienes: pip install pyflakes)
```

## Reglas del proyecto

1. **Todo el texto va en español** (interfaz, documentación, mensajes). Los nombres de código pueden ir en inglés.
2. **Sin emojis en la interfaz:** los iconos son SVG del sprite `home/web/static/icons.svg` (`<svg class="ic"><use href="#i-nombre"/></svg>`). Añade el icono ahí si falta.
3. **Una función nueva lleva pruebas** (`tests/`) y se documenta (tutorial, README o ARCHITECTURE según toque). Si cambia la interfaz, `tests/ui_smoke.js` la recorre.
4. **Si una página usa una ruta `/api/...` nueva, simúlala en `web-demo/demo.js`:** `tests/test_web_demo.py` falla si falta.
5. **Honestidad:** nada de esto se ha probado todavía en una Raspberry Pi real. No escribas «funciona» si solo lo has probado con simulaciones; di qué has probado y qué no.
6. **Seguridad primero:** las rutas que cambian cosas exigen la cabecera `X-PCPI` y cliente local; los nombres de archivo y los enlaces se validan; nada de `eval`. Mira `tests/test_security.py`.
7. Los textos de las pruebas y los commits, en español y concretos («Musix: temporizador para dormir», no «arreglos»).

## Receta: añadir una orden de voz

1. **Entender la frase:** en `voice/intents.py`, dentro de `parse()`, devuelve un `Intent("nombre", argumento)`. Pon la orden *antes* de otras que puedan solaparse y añade casos en `tests/test_intents.py` (incluye una frase parecida que NO debe activarla).
2. **Ejecutarla:** en `voice/assistant.py`, `execute()`: llama a la API local con `api(cfg, "/api/...", {...})` y devuelve la frase que dirá la Pi. Si hace falta un dato, léelo de `/api/status`. Prueba con `tests/test_assistant.py` (hay un servidor de mentira).
3. **Si la API no existe,** añádela en `home/server.py` con las mismas reglas de siempre (cabecera `X-PCPI`, cliente local, valores validados y una lista cerrada de lo que se puede tocar) y sus tests.
4. **Simulador:** copia la orden a `understand()` en `web-demo/demo.js` para que se pueda probar en la web.
5. **Docs:** una línea en la tabla de órdenes de `docs/TUTORIAL.md`, una entrada en `CHANGELOG.md` y, si quieres que Whisper la acierte mejor, la frase en `PROMPT` de `voice/stt.py`.

## Cómo proponer un cambio

1. Abre un *issue* si es grande (para ponernos de acuerdo antes de que trabajes).
2. Haz una rama, cambia lo que toque y ejecuta `make test` y `make lint`.
3. Abre la *pull request* explicando **qué cambia, por qué y qué has probado (y qué no)**. El CI (`.github/workflows/test.yml`) debe quedar en verde.

## Licencia de lo que aportes

Al enviar una *pull request* aceptas que tu aportación se publique bajo la licencia MIT del proyecto ([LICENSE](LICENSE)). No subas archivos con derechos de terceros (vídeos, imágenes, música).

## Fallos de seguridad

No los abras como *issue* público: mira [SECURITY.md](SECURITY.md).
