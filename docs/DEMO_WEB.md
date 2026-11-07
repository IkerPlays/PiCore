# Demo web de PiCore (Netlify)

**En vivo: <https://picoreweb.netlify.app/>** (página de inicio) y **<https://picoreweb.netlify.app/simulador>** (el simulador).

La portada (`web-demo/landing.html`, con su CSS y capturas en `web-demo/`) explica qué es PiCore, para qué sirve y cómo funciona, y lleva al simulador. `/demo` redirige a `/simulador`. Incluye `robots.txt`, `sitemap.xml` y etiquetas para compartir el enlace.

Una versión de la interfaz que corre **solo en el navegador**, sin Raspberry Pi y sin servidor Python. Sirve para enseñar el proyecto, probar cambios de diseño o dejar que otra persona lo pruebe con un enlace.

## Cómo funciona

La interfaz real habla con un servidor Python (`home/server.py`) por una API (`/api/...`). En la demo, `web-demo/demo.js` se carga **antes** que el resto y sustituye `fetch` para esas rutas: contesta él mismo, en JavaScript, con datos de ejemplo. Lo que "guardas" (notas, marcadores, ajustes, temporizadores) se queda en el almacenamiento local **de tu navegador**; el botón **Restablecer** de la insignia lo borra.

`tools/build_web_demo.py` copia las páginas de `home/web/`, les incrusta los iconos y el script de la demo, y deja un sitio estático en `dist-demo/`. No se publica ni un archivo de Python.

## Ponerla en internet con Netlify

1. Entra en <https://app.netlify.com> → **Add new site** → **Import an existing project** → **GitHub** y elige este repositorio (autoriza el acceso si te lo pide).
2. No hay nada que rellenar: Netlify lee `netlify.toml` (comando `python3 tools/build_web_demo.py`, carpeta `dist-demo`). Pulsa **Deploy**.
3. En unos minutos tendrás una dirección `https://algo.netlify.app`. Cada `git push` a `main` la vuelve a desplegar sola. Puedes cambiar el nombre en *Site configuration → Change site name* o poner tu propio dominio.

Si prefieres desplegar a mano: `make demo` para ver el resultado en local y sube la carpeta `dist-demo/` arrastrándola a Netlify (*Deploys → drag and drop*).

## El marco de dispositivo

Al abrir el simulador (`/simulador`) en un ordenador o un móvil, la carcasa (`simulador.html`) lo enseña dentro de una pantalla de **1024×600** (la de la Raspberry Pi) escalada para caber en la ventana, con botones **Casa / Iker / Dev** para cambiar de modo. Casa vive en `/app`; `/iker`, `/dev` y `/loading` abiertas sueltas se redirigen al marco (`/simulador?p=...`). En el móvil, gíralo en horizontal. Con `?bare=1` se ve la página sola, sin marco (la usan los tests).

## Qué incluye de verdad

La demo usa los **vídeos de inicio, GIFs e imágenes reales** de `extra-assets/` (los copia `tools/build_web_demo.py`): la primera vez que entras ves un vídeo de inicio al azar y la pantalla de carga con tu carrusel, como al encender la Pi. Los vídeos de inicio se publican en **H.264** (`web-demo/assets/start/`): los móviles suelen grabar H.265, que muchos navegadores no reproducen. Si cambias o añades vídeos en `extra-assets/start/`, regenera su copia con `ffmpeg -i Inicio1.mp4 -c:v libx264 -crf 27 -pix_fmt yuv420p -c:a aac -movflags +faststart web-demo/assets/start/Inicio1.mp4` (o, si el servidor de construcción tiene `ffmpeg`, se convierten solos). Sin archivos en `extra-assets/`, la demo usa dibujos generados.

## Qué funciona y qué no

| Funciona (simulado) | No existe en la demo |
|---|---|
| Casa: reloj, tiempo, Pi-hole (pausar), temporizadores y alarmas reales en el navegador, brillo, vigilancia, batería de ejemplo, Wi-Fi (cambiar de red; la contraseña `mala` falla), hoja Sistema (la actualización se simula paso a paso) | Voz, cámara real, IA local, Pi-hole real, apagar/reiniciar de verdad |
| Musix: **MP3 Player** con 3 canciones sintetizadas en el navegador (suenan de verdad), **YT Music** con el reproductor incrustado de YouTube, historial | Importar de USB, la web de descarga de DYMusic, la búsqueda por título (necesita clave) |
| Iker: notas con búsqueda, etiquetas y marcadores guardados en tu navegador | Exportar a USB y a PDF |
| Dev: consola de mentira (`help` lista lo que entiende), explorador de la API, experimentos | Ejecutar órdenes de verdad (en la demo nada se ejecuta) |
| Cambio de modo con su pantalla de carga (Casa, Iker, Dev y una **maqueta** del Escritorio con terminal, navegador y archivos de mentira) | El Raspberry Pi OS de verdad |

## Voz, visita guiada y atajos del simulador

- **Voz simulada:** la barra de abajo entiende frases escritas (hora, fecha, tiempo, temporizadores con nombre, alarmas, música, volumen, brillo, notas, «qué puedes hacer», estado de la Pi...) y responde en voz alta con la síntesis de tu navegador. La Pi real usa Whisper para entenderte; aquí no hay micrófono ni IA local, y lo que no entiende recibe una respuesta fija. Está en `understand()` de `web-demo/demo.js`.
- **Visita guiada:** el botón «Visita guiada» (o `/simulador?tour`) recorre 14 pasos y toca de verdad la interfaz.
- **Atajos:** `1` `2` `3` `4` cambian de modo, `T` abre la visita y `V` enfoca la barra de voz (no actúan si estás escribiendo en un cuadro). Con la visita abierta, las flechas ← → cambian de paso y `Esc` la cierra.
- **Enlaces directos:** `/simulador?p=/iker` abre el simulador en ese modo (solo `/app`, `/iker`, `/dev`, `/escritorio` y `/loading`).

## Seguridad

La demo es un sitio estático: no tiene servidor, ni cuentas, ni secretos, ni forma de ejecutar nada. Las cabeceras (`_headers`) son una CSP estricta (sin `eval`) que solo permite lo que la demo necesita (audio generado, el reproductor de YouTube). La consola Dev de la demo es un `switch` de JavaScript con órdenes de mentira: `rm -rf /` solo contesta «orden no encontrada».

## Para quien toque el código

- Si añades una ruta `/api/...` nueva a una página, **simúlala en `web-demo/demo.js`**: el test `tests/test_web_demo.py` falla si falta alguna.
- La prueba en navegador (`tests/demo_smoke.js`) recorre la demo entera y comprueba que ninguna petición `/api/` llega a un servidor.
- `python3 tools/serve_web_demo.py` sirve `dist-demo` con las mismas rutas que `netlify.toml`.
