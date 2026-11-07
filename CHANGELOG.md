# Registro de cambios de PiCore

> Todo está probado con tests automáticos y un «Pi virtual» (servidor y `pcpi-session` reales con un Chromium sin pantalla).
> **Nada se ha probado todavía en una Raspberry Pi real**: pantalla, audio, Wayland, cámara, micrófono e instalación con `apt`.



## Voz: próximo evento del calendario

- «Cuál es mi próximo evento» dice el siguiente aunque no sea hoy ni mañana. Probado con tests; no en una Pi real.

## Web: página 404 con estilo

- La página de «no encontrado» de la web tiene el mismo estilo (claro/oscuro), es adaptable al móvil y enlaza al inicio y al simulador.

## Voz: alarmas diarias

- «Despiértame todos los días a las siete y media» crea una alarma diaria (el servidor ya las soportaba; faltaba poder pedirlas por voz). Probado con tests; no en una Pi real.

## Voz: el tiempo de mañana

- «Qué tiempo hará mañana» / «pasado mañana» dicen máxima, mínima, cielo y lluvia del día. Probado con tests; no en una Pi real.

## Voz: lista de la compra y tareas

- «Añade leche a la lista de la compra» añade una línea a la nota «Lista de la compra» (la crea si no existe); lo mismo con «lista de tareas». Probado con tests; no en una Pi real.

## Simulador: «Restablecer» pide confirmación

- El botón borra tus notas y ajustes de la demo, así que ahora hace falta pulsarlo dos veces (comprobado en navegador sin pantalla).

## MP3 Player: buscar en tu música

- Con 8 o más canciones aparece un cuadro para filtrar por título (sin distinguir mayúsculas ni tildes, con teclado en pantalla). Comprobado en navegador sin pantalla.

## Portada: botón de tema claro / oscuro

- La web de inicio sigue el tema del sistema y ahora tiene un botón para cambiarlo a mano (se recuerda en el navegador). Comprobado en navegador sin pantalla.

## «Qué puedo decirle a la Pi» en la pantalla

- La hoja Sistema tiene un desplegable con ejemplos de órdenes de voz. Comprobado en navegador sin pantalla (captura revisada).

## Voz: estado de la red

- «¿A qué wifi estoy conectado?» / «¿tengo internet?» responden con la red activa y si hay internet o hace falta iniciar sesión. Probado con tests; no en una Pi real.

## Temporizadores: botón +1 min

- Cada temporizador de la lista tiene «+1 min». También en el simulador, que además entiende «añade cinco minutos al temporizador». Comprobado en navegador sin pantalla.

## Voz: alargar un temporizador

- «Añade cinco minutos al temporizador» o «ponle un minuto más» suman tiempo al temporizador que antes vence (`POST /api/timers` con `action: extend`; no pasa de 48 h y no toca los que ya suenan). Probado con tests; no en una Pi real.

## Modo Iker: duplicar nota

- Botón «Duplicar» que crea una copia de la nota abierta y la abre. Comprobado en navegador sin pantalla con el simulador.

## Modo Dev: más órdenes rápidas

- Botones rápidos nuevos: `pcpi-sound status`, `pcpi-wifi status` y `pcpi-update --check`; la consola del simulador también las reconoce (con datos de ejemplo).

## Simulador: más órdenes de voz

- El simulador entiende también «toma nota…» (la nota aparece en Iker), «qué puedes hacer», saludos, gracias y el estado de la Pi (con datos de ejemplo). Comprobado en navegador sin pantalla.

## Voz: estado de la Pi

- «Cuánto espacio libre queda», «cuánta memoria libre hay», «qué temperatura tiene la Pi» y «cómo está la Pi» responden con datos reales de `/api/status`. Probado con tests; no en una Pi real.

## Voz: leer la última nota

- «Lee mi última nota» la dice en voz alta (hasta 300 caracteres). Probado con tests; no con una voz real.

## Voz: tomar notas

- «Toma nota: comprar leche», «apunta que mañana llamo al dentista» o «anota revisar el router» guardan una nota nueva en Modo Iker. Probado con tests de intenciones y del asistente; no en una Pi real.

## MP3 Player: repetir

- Botón «Repetir todo / Repetir una / Sin repetir» (se recuerda). Con «Sin repetir» la música se para al acabar la última canción. Comprobado en navegador sin pantalla con el simulador.

## Simulador: atajos de teclado

- `1` `2` `3` cambian de modo, `T` abre la visita guiada y `V` lleva el cursor a la barra de voz (no actúan si estás escribiendo). Comprobado en navegador sin pantalla.

## Voz: temporizadores con nombre

- «Pon un temporizador de diez minutos para la pasta» crea el temporizador con el nombre «pasta» (sale en la lista y en el aviso). Arreglado: «temporizador para diez minutos» se entendía como parar. También en el simulador. Probado con tests; no en una Pi real.

## Notas fijadas

- Modo Iker: botón «Fijar» para dejar una nota arriba de la lista (con estrella). Editar la nota no la desfija. También en el simulador. Probado con tests y en navegador sin pantalla; no en una Pi real.

## Portada: más funciones

- La lista de funciones de la portada suma Pi-hole, temporizadores, ajustes en pantalla y privacidad (12 tarjetas).

## Conectar Pi-hole desde la pantalla

- Si Pi-hole no está configurado o la contraseña falla, la tarjeta ofrece «Conectar Pi-hole»: se escribe la contraseña con el teclado en pantalla, se guarda en `pcpi.conf` y se prueba al momento. Rechaza contraseñas con saltos de línea, espacios en los bordes o más de 128 caracteres. Probado con tests y en el simulador; no con un Pi-hole real.

## Portada: probar cada modo

- Las fichas Casa, Iker y Dev de la portada tienen «Probar este modo», que abre el simulador directamente en ese modo (`/simulador?p=/iker`). Comprobado en navegador sin pantalla con Iker.

## Voz: salvapantallas

- «Activa / desactiva el salvapantallas» por voz (y en el simulador). Probado con tests de intenciones; no en una Pi real.

## Preferencias desde la pantalla

- La hoja Sistema deja activar el salvapantallas, elegir tras cuántos minutos salta y la hora y el brillo de la noche, sin editar `pcpi.conf`. El servidor solo escribe 5 claves de una lista cerrada y recorta los valores. Probado con tests y en el simulador; no en una Pi real.

## Simulador: voz y visita guiada

- El simulador entiende frases escritas (hora, tiempo, temporizadores, música, volumen, modos...) y las responde en voz alta, como la Pi real. Probado en navegador sin pantalla; sin la IA local, lo desconocido recibe una respuesta fija.
- Botón «Visita guiada» de 12 pasos que toca de verdad la interfaz (`/simulador?tour`).

## Sesión de mejoras continuas

- **09:51** Este registro de cambios. CI de GitHub en verde (run 69).
- **09:53** Musix: YT Music recuerda los últimos 8 enlaces (botones para volver a ellos; se revalidan al leerlos) y el MP3 Player tiene volumen propio que se recuerda.
- **09:54** Revisión adversa de las rutas de Musix (otro `Host`, petición de otra web, rangos rotos, id nulo): todas se rechazan; ahora hay tests que lo fijan.
- **09:56** MP3 Player: al importar de un USB deja 300 MB libres en la tarjeta, cuenta y muestra lo que no pudo copiar (poco espacio) y limpia las copias a medias.
- **09:57** Hoja «Sistema»: si la música ocupa más de 1 GB y la tarjeta tiene menos de 5 GB libres, lo avisa (como información, con el consejo de quitar canciones).
- **09:58** **Arreglo importante:** los cuadros de texto de Musix (enlace de YT Music, buscador y enlace de DYMusic) ahora abren el **teclado en pantalla**; antes, sin teclado físico, no se podía escribir. Con test en navegador.
- **09:58** Las pruebas ya no dejan carpetas en `/var/lib/pcpi`: leer la música no crea su carpeta, y el emulador usa un historial propio.
- **09:59** Copia de seguridad: ahora incluye las alarmas y el historial de YT Music (la carpeta de música no entra: pesa demasiado). Whisper recibe las frases de música como pista para entenderlas mejor.
- **10:00** «Pi virtual» ahora también recorre DYMusic: la petición de descarga llega a `pcpi-session`, que abre la ventana del descargador con la carpeta de música como destino de descargas, y un MP3 que caiga ahí aparece solo en el reproductor.
- **10:03** MP3 Player: botón **Dormir** (15 / 30 / 60 min / apagado) y por voz «apaga la música en media hora» / «cancela el apagado de la música». La música se pausa sola al acabar el tiempo.
- **10:04** Desinstalador: también cierra y borra el perfil de la ventana de descargas de DYMusic, y avisa de que borrar `/var/lib/pcpi` incluye tu música.
- **10:12** **Auto-actualizador desde Casa:** la hoja «Sistema» tiene botón *Buscar actualizaciones* / *Actualizar ahora* con el registro en pantalla (la instalación la lanza `pcpi-session`, el servidor no tiene permisos), y actualización automática opcional por franja horaria (`[update] auto_install`, apagada por defecto). Una sola a la vez; avisa si falta sudo sin contraseña.
- **10:12** **Arreglo de robustez:** el navegador y el reloj de `pcpi-session` heredaban el cerrojo de instancia única, así que un vigilante reiniciado con Chromium vivo salía sin hacer nada. Ya no lo heredan (con test).
- **10:21** **Modo Dev:** nuevo modo (`pcpi-mode dev`, botón en Casa, voz) con ventana normal en `/dev`: **Consola** (órdenes reales que ejecuta `pcpi-session` con tus permisos, salida en vivo, código de salida, historial, órdenes rápidas), **Terminal real**, **explorador de la API** y **Experimentos** (chat con la IA, gráfica en vivo, insignia de depuración en Casa). Solo acepta órdenes dentro del modo Dev; se puede apagar con `[dev] enabled = false`. Probado también en la «Pi virtual».
- **10:35** **Interfaz nueva:** se quitan **todos los emojis** de la pantalla (Casa, Iker, Dev, carga, teclado en pantalla y selector de modo) y se sustituyen por ~70 iconos SVG propios (sprite que el servidor incrusta en cada página), con un juego del tiempo en dos tonos. Hoja de estilos compartida `ui.css`: botones, tarjetas, chips, hojas inferiores, Musix, Wi-Fi, Iker y Dev, en claro y oscuro. Arregla los iconos que tapaban el saludo, la tarjeta de música desbordada y una mancha negra en el modo claro.
- **10:50** **Demo web para Netlify** (`netlify.toml`, `make demo`, `docs/DEMO_WEB.md`): la interfaz completa funcionando en una web estática con una API simulada en JavaScript (Casa, Musix con audio generado, Iker con notas en tu navegador, Dev con consola de mentira, cambio de modo con carga). Sin servidor Python. Probada en navegador real, comprobando que ninguna petición `/api/` sale a un servidor.
- **11:15** La demo se ve dentro de un **marco de dispositivo** (pantalla de 1024×600 escalada, con botones Casa/Iker/Dev; también en el móvil). Casa: el chip de temperatura solo aparece si la CPU pasa de 65 °C, para dejar sitio al saludo.
- **11:22** Imágenes de la documentación (`docs/img/casa-claro.png`, `casa-oscuro.png`, `iker.png`) regeneradas con la interfaz nueva.
- **11:40** **Preparación para hacerlo público:** README renovado (descripción, insignias, demo en vivo <https://picoreweb.netlify.app/>, capturas nuevas), `CONTRIBUTING.md`, `SECURITY.md`, plantillas de issues y de pull request, tarjeta para compartir (`docs/img/social.png`). La demo usa ahora los **vídeos de inicio, GIFs e imágenes reales** de `extra-assets/` (copias H.264) y la primera visita arranca como un encendido de la Pi.
- **11:48** Licencia **MIT** (`LICENSE`), con avisos sobre los archivos de `extra-assets/` y las licencias de los modelos de voz de terceros.
- **12:10** **Mejoras para la Pi:** (1) el servidor avisa a systemd con `Type=notify` y **se reinicia solo si deja de contestar** (watchdog), y `StartLimitIntervalSec=0` evita que systemd lo dé por perdido tras varios fallos seguidos; (2) **volumen del sistema** desde la pantalla (panel «Pantalla y sonido»: deslizante, silencio y «Probar sonido») y `pcpi-sound` en la terminal; (3) la hoja «Sistema» avisa de lo que **falta configurar** (ciudad del tiempo, voz, sonido) sin poner el icono en naranja; (4) `pcpi-doctor` revisa watchdog, señales de vida de la pantalla y salida de sonido. La demo web simula el volumen y «Probar sonido» suena de verdad.
- **12:40** **Ciudad desde la pantalla:** el botón «Elegir tu ciudad» (o «Cambiar ciudad» en el detalle del tiempo) busca por nombre con teclado en pantalla y guarda `lat`/`lon`/`city` sin tocar el resto de `pcpi.conf` (`confedit.py`, también usado por `pcpi-config`). **Aviso «Reconectando…»** en todas las páginas cuando el servidor deja de contestar. Demo y emulador incluidos.
- **13:08** **Web nueva:** la portada de <https://picoreweb.netlify.app/> es ahora una **página de inicio** que explica qué es PiCore, para qué sirve, cómo funciona (diagrama de las tres piezas y qué pasa al encender), los modos con capturas, las funciones, cómo instalarlo en 3 pasos, privacidad y preguntas frecuentes. El **simulador** pasa a `/simulador` (`/demo` redirige). Con favicon, `robots.txt`, `sitemap.xml` y etiquetas para compartir.

## Antes de esta sesión (resumen)

- **Musix**: reproductor propio con YT Music (YouTube incrustado), MP3 Player (offline, importa desde USB) y DYMusic (búsqueda en YouTube + ventana de descarga). Sustituye a Spotify.
- **Prueba «Pi virtual»**: encendido completo, cambio de modo y vuelta a Casa con el servidor y `pcpi-session` reales.
- **Hoja «Sistema»**: disco, memoria, temperatura, avisos de salud, apagar/reiniciar con doble toque y aviso de actualizaciones.
- **Notas**: etiquetas `#`, exportar a PDF, marcadores de webs, búsqueda y copias automáticas.
- **Calendario** `.ics` de solo lectura, **salvapantallas** con fotos, **tiempo** por horas/días con aviso de lluvia.
- **Voz**: Whisper offline (faster-whisper), temporizadores y alarmas, órdenes de música, IA local opcional (Ollama + Qwen).
- **Wi-Fi** (redes ocultas, portal cautivo, DNS por red), **brillo**, **vigilancia por cámara**, **batería**, **intros aleatorios** con descarga del cuarto.
- Instalador, desinstalador, `pcpi-doctor`, `pcpi-backup`, `pcpi-update`, tutorial completo.
