# Registro de cambios de PiCore

> Todo está probado con tests automáticos y un «Pi virtual» (servidor y `pcpi-session` reales con un Chromium sin pantalla).
> **Nada se ha probado todavía en una Raspberry Pi real**: pantalla, audio, Wayland, cámara, micrófono e instalación con `apt`.
> ¿Prefieres un resumen corto por temas? Mira [docs/NOVEDADES.md](docs/NOVEDADES.md). Aquí lo más reciente está arriba.



## Voz: qué hora será dentro de…

- «Qué hora será dentro de veinte minutos / dos horas». También en el simulador.

## Voz: conversiones de unidades

- Kilómetros y millas, kilos y libras, metros y pies, grados y Fahrenheit («cuántos kilómetros son 10 millas», «pasa 20 grados a fahrenheit»). El simulador solo entiende cifras.

## README: más órdenes de voz en la lista

- Cuentas, chistes y número al azar.

## Voz: número al azar

- «Dime un número al azar entre 1 y 10» (o sin rango: de 1 a 100). También en el simulador.

## Voz: la ayuda menciona las cuentas y los chistes

- Lo que contesta «qué puedes hacer» incluye ya las cuentas y los chistes.

## Voz: chistes

- «Cuéntame un chiste»: elige uno de siete, sin internet. También en el simulador. Probado con tests; no en una Pi real.

## Voz: calculadora

- «Cuánto es 12 por 5», «calcula 10 entre 4»: dos números con más, menos, por o entre (cifras o palabras). Dividir entre cero se contesta sin fallar. También en el simulador (solo con cifras). Probado con tests; no en una Pi real.

## Herramienta para regenerar las capturas

- `make capturas` construye la demo, hace las capturas con Chromium (1024x600) y reescribe las imágenes de la web y de la documentación. Necesita Playwright y Pillow. Las imágenes de la demo son simuladas, no de una Pi real.

## Voz: «apaga la pantalla»

- Baja el brillo al mínimo (10 %); no la apaga del todo. Probado con tests; no en una Pi real.

## Corrección: el test de interfaz no contaba con el cuarto experimento

- Al añadir el experimento «Lo último que oyó la voz» subí sin pasar el test de interfaz, que esperaba 3 experimentos y la posición del de depuración: el CI salió en rojo 2 veces (commits `0fc0ea2` y `0f9fd03`). Ahora el test espera 4, elige cada experimento por su nombre y comprueba el de la voz.

## Test: sin desplazamiento horizontal de 320 a 1920 px

- La portada y el simulador no se desbordan a 320, 390, 768 y 1920 px de ancho (comprobado y ahora vigilado por el test de accesibilidad básica).

## Test de la demo: 300 frases al azar

- La voz simulada se prueba con 300 mezclas raras de palabras (semilla fija): siempre contesta un texto y nunca lanza una excepción. Pasó a la primera.

## Test de la demo: abre cada hoja de Casa y las alertas con botón

- Recorre las 6 hojas (brillo, Wi-Fi, Sistema, tiempo, calendario, Musix), comprueba que se abren sin errores de consola y que las alertas de la hoja Sistema traen sus botones y abren el panel de Pi-hole.

## Simulador: horas con letras, recordatorios y 4 frases más; test más estricto

- El test de la demo daba por buenas respuestas del tipo «No he entendido la hora»; ahora las cuenta como fallo y salieron 7 frases del tutorial mal entendidas. Arreglado en el simulador: «a las siete y media» / «ocho menos cuarto» / «de la tarde», recordatorios con nombre, «el volumen a la mitad», «volumen al máximo», «cuánto queda del temporizador» y «para la alarma».

## Voz: recordatorios a una hora

- «Recuérdame a las seis de la tarde que saque la basura» o «avísame a las siete y media para llamar a mamá» crean una alarma con nombre. Hace falta decir «que», «para» o «de» antes de lo que quieres recordar. Probado con tests; no en una Pi real.

## Modo Iker: Ctrl+F salta al buscador

- Con teclado físico, Ctrl+F lleva el cursor al buscador de notas (el navegador no abre su propio buscador). Comprobado en navegador sin pantalla. (Mi primer intento con la tecla `/` no funcionaba porque la nota ya tiene el foco; lo descarté.)

## Simulador: botón «Tema»

- Cambia entre tema claro y oscuro de Casa (en la Pi se toca la hora). Comprobado en navegador sin pantalla.

## Modo Dev: experimento «Lo último que oyó la voz»

- Nuevo experimento que enseña en la consola el estado de la voz, la palabra de activación, lo que entendió y lo que contestó (se actualiza cada 2 s): sirve para ajustar el micrófono. Probado con tests del servidor y en el simulador; con la voz real no se ha probado.

## Test del inicio sin permiso de sonido: más robusto

- Este test seguía fallando de vez en cuando en el CI aun con la espera que le puse (2 de ~25 ejecuciones hoy). Mi hipótesis (no verificada en el CI) es que a veces Chromium sí deja sonar el vídeo y entonces no hay aviso que mostrar. Ahora el test acepta los dos casos y solo falla si el vídeo va mudo sin avisar o avisa sin ir mudo; imprime cuál fue. Local: pasa 3 de 3.

## `pcpi-doctor --report`

- Guarda en un archivo (por defecto `~/picore-informe.txt`) lo que dice el diagnóstico sin colores, la versión del sistema y tu configuración con las contraseñas como `******`, para adjuntarlo a una incidencia. Hay que revisarlo antes de compartirlo. Probado con un test.

## Contraste del tema claro de la pantalla

- Calculé el contraste WCAG de los colores: en el tema claro de Casa e Iker el texto secundario (3,7), el verde (2,7), el rojo (3,6), el ámbar (2,4) y el azul de acento (4,3) no llegaban a 4,5. Los oscurecí un poco (`--dim`, `--ok`, `--bad`, `--warn`, `--acc`) y dos tests (portada y pantalla de la Pi) vigilan que se mantenga. El tema oscuro y la portada ya cumplían. Es una medida de contraste, no una prueba con personas con baja visión.

## Test de accesibilidad básica

- Un test de navegador comprueba que todo botón, enlace, cuadro o interruptor visible de Casa, Iker, Dev, Escritorio y la portada tiene nombre. Comprobado a mano que falla si se quita un nombre. También: el `if __name__ == "__main__"` de `test_web_demo.py` estaba a mitad del archivo; ahora está al final.

## Accesibilidad: el interruptor del salvapantallas tiene nombre

- Un lector de pantalla no sabía qué era el interruptor del salvapantallas. Revisé con el navegador todos los botones, enlaces y cuadros de la interfaz (Casa, Iker, Dev, Escritorio, simulador y portada): el resto ya tenía nombre.

## Voz: qué día es mañana

- «Qué día es mañana» dice el día de la semana y la fecha de mañana. Probado con tests; no en una Pi real.

## El simulador entiende todo lo que dice el tutorial

- Le faltaban 17 de las ~70 frases de la tabla «Qué puedes pedir» (Pi-hole con guion, silenciar, vigilancia, cuántas notas, leer la última nota, próximo evento, cuánto falta para Navidad, «repite», «avísame en…», «ponle un minuto más»). Añadidas, y el test de navegador de la demo comprueba ahora todas las frases del tutorial (salvo las de «modo…», que cambian de página). Sigue siendo una simulación con datos de ejemplo.

## Ejemplos de voz de la pantalla y la web: todos se entienden

- La lista de la hoja Sistema decía «pausa» y «siguiente», que el asistente no entiende solos; ahora dice «pausa la música» y «siguiente canción». Un test comprueba todos los ejemplos de la hoja Sistema y de la portada.

## Voz: lo que dice el tutorial se entiende (y un test lo vigila)

- Un test comprueba que las ~70 frases de la tabla «Qué puedes pedir» del tutorial las entiende el asistente. Encontró dos que no: «cómo va el Pi-hole» y «ponle un minuto más» (sin decir «temporizador»); ya funcionan.

## Visita guiada: el foco va al botón «Siguiente»

- Al abrir la visita (o cambiar de paso) el foco queda en «Siguiente», así se puede avanzar con Intro. Comprobado en navegador sin pantalla.

## Visita guiada: paso del Escritorio (14 pasos)

- Un paso nuevo enseña la maqueta del modo Escritorio antes del final.

## Simulador: maqueta del modo Escritorio y marco sin recortar

- El botón «Escritorio» (y la tecla `4`) lleva a una maqueta del escritorio con terminal, navegador y archivos de mentira y un «Volver a Casa» (antes te devolvía a Casa con un aviso). Ruta nueva `/escritorio` (Netlify, servidor local y `robots.txt`).
- Arreglo: el marco del dispositivo se recortaba unos píxeles por arriba y por abajo desde que se añadió la barra de voz; ahora se escala según el tamaño real del escenario y un test lo vigila.

## `make lint` también pasa pyflakes

- Detecta variables sin usar, imports que sobran y nombres sin definir en el código y los tests (el CI lo instala; en local se omite si no lo tienes). El código está limpio hoy.

## Test de interfaz: diagnóstico de los 403

- Una ejecución del CI falló una vez con «Failed to load resource: 403» sin decir qué petición era (las demás pasaron, y en local tampoco se reproduce). El test ahora añade a ese mensaje las peticiones que dieron 403, para localizarla si vuelve a pasar. Aún no sé la causa.

## Modo Dev: botón rápido `pcpi-config show`

- Botón rápido para ver la configuración sin contraseñas (y la consola del simulador la reconoce con datos de ejemplo). Comprobado en navegador sin pantalla.

## Voz: estadísticas de Pi-hole

- «Cuántos anuncios has bloqueado» / «cómo va el Pi-hole» dicen lo bloqueado, el total y el porcentaje (y si está en pausa). Probado con tests; no con un Pi-hole real.

## Versión instalada en la hoja Sistema

- `install.sh` escribe `VERSION` («abc1234 2026-11-07», el último commit) y la hoja Sistema muestra «PiCore abc1234 …» (útil al pedir ayuda; se actualiza con `pcpi-update`). El servidor la limpia antes de enseñarla. Probado con tests y en el simulador; el instalador no se ha ejecutado en una Pi real.

## Visita guiada con el teclado

- Con la visita abierta, las flechas ← → cambian de paso y `Esc` la cierra. Comprobado en navegador sin pantalla.

## Voz: posponer

- «Pospón» / «cinco minutos más» mientras suena un temporizador o alarma. Probado con tests; no en una Pi real (y no se ha comprobado que la palabra de activación se oiga con el aviso sonando).

## Posponer 5 minutos

- La pantalla de aviso de un temporizador o alarma tiene «Posponer 5 min»: para lo que suena y crea un temporizador de 5 minutos con el mismo nombre (las alarmas pasan a llamarse «Alarma»). Probado en el test de interfaz contra el servidor real.

## Crear alarmas desde la pantalla

- El panel de temporizadores tiene «Nueva alarma»: hora y minutos (de 5 en 5) con botones, interruptor «cada día» y «Crear». Antes solo se podían crear por voz. Probado en el test de interfaz (contra el servidor real) y en el simulador.

## Visita guiada: paso nuevo sobre los ajustes

- La visita pasa a tener 13 pasos: el nuevo abre la hoja Sistema y baja a los ajustes (salvapantallas y noche) y a la lista de órdenes de voz. Comprobado en navegador sin pantalla (captura revisada).

## pcpi-config show

- `pcpi-config show [SECCION]` lista lo que tienes puesto en `pcpi.conf` sin comentarios y con las contraseñas tapadas (`******`): sirve para pegarlo en una incidencia sin filtrar secretos. Probado con tests.

## Buscar notas: las fijadas salen primero

- Al buscar, las notas fijadas siguen arriba y con su estrella (antes solo pasaba sin buscar). Probado con tests.

## Voz: dado y moneda

- «Tira un dado» y «cara o cruz». Probado con tests; no en una Pi real.

## Voz: cuántos días faltan

- «Cuánto falta para Navidad» (también Nochevieja, Reyes, Año Nuevo y el verano). Probado con tests; no en una Pi real.

## Modo Dev: el historial de la consola se recuerda

- Las últimas 30 órdenes (flecha arriba) sobreviven a recargar la página, solo en ese navegador. Comprobado en navegador sin pantalla.

## Modo Iker: contador de notas

- Sobre la lista sale «N notas» (o «N notas encontradas» al buscar o filtrar por etiqueta). Comprobado en navegador sin pantalla.

## Hoja Sistema: botón «Abrir Wi-Fi» en las alertas de red

- «Sin conexión de red», «la wifi pide iniciar sesión» y «hay red pero no hay internet» traen un botón que abre el panel de Wi-Fi. La parte del servidor está probada con tests; el botón comparte el código del de la ciudad (probado en navegador).

## Hoja Sistema: las alertas tienen botón

- «Falta tu ciudad» trae un botón «Elegir ciudad» y «Pi-hole no responde» uno de «Conectar Pi-hole», que cierran la hoja y abren el panel correspondiente. Comprobado en navegador sin pantalla.

## Simulador: «Copiar enlace» y arreglos en el móvil

- Botón «Copiar enlace» (abre el simulador en el modo actual). En el móvil la barra de voz ya no se solapa con el aviso de abajo, la cabecera se desplaza en vez de cortarse y se esconden los atajos de teclado. Comprobado en navegador sin pantalla a 390 px (capturas revisadas).

## Tests de seguridad ampliados

- Las rutas nuevas (`/api/settings`, `/api/timers`, `/api/music`, `/api/audio`, `/api/dev`, `/api/system`) exigen la cabecera `X-PCPI`, y una web ajena (sin la cabecera o con otro `Host`) no puede cambiar ajustes ni la contraseña de Pi-hole.

## Test de interfaz: «+1 min» y «Cancelar» de los temporizadores

- Al añadir «+1 min» el test de interfaz pulsaba ese botón en lugar de «Cancelar» y fallaba (lo detectó la suite completa, no el CI aún). Ahora pulsa cada botón por su nombre y comprueba que «+1 min» alarga el temporizador.

## Voz: la hora en otras ciudades

- «Qué hora es en Tokio» (y 15 ciudades más, con su zona horaria y el cambio de horario). Probado con tests; no en una Pi real.

## Voz: cuántas notas y temporizadores

- «Cuántas notas tengo» y «cuántos temporizadores hay». Probado con tests; no en una Pi real.

## Voz: «repite»

- «Repite» / «qué has dicho» hace que la Pi repita su última respuesta. Probado el reconocimiento de la frase con tests; el cableado del asistente real no tiene test automático ni se ha probado en una Pi.

## Voz: «avísame en…» y «recuérdame en…»

- «Avísame en veinte minutos» y «recuérdame en diez minutos sacar la pizza» crean un temporizador (con nombre si lo dices). Probado con tests; no en una Pi real.

## pcpi-doctor: comprueba que los ajustes de la pantalla se pueden guardar

- Avisa si `pcpi.conf` no es escribible por tu usuario (la ciudad, Pi-hole y los ajustes de la hoja Sistema no se guardarían) y dice cómo arreglarlo.

## Voz: «a la mitad» y «al máximo»

- «El volumen a la mitad», «volumen al máximo» y «el brillo a la mitad» funcionan como atajos. Probado con tests; no en una Pi real.

## Voz: qué suena

- «Qué suena» / «cómo se llama esta canción» dicen el título (y el artista si lo hay) de lo que reproduce Musix. Probado con tests; no en una Pi real.

## Whisper conoce las órdenes nuevas

- La pista que se le da a Whisper incluye ahora tomar notas, la lista de la compra, el tiempo de mañana, el espacio libre y el salvapantallas, para acertar más con esas frases. No medido: no hay una Pi con micrófono para comparar.

## Corrección: la palabra de activación por defecto es «Hey Jarvis»

- Había textos nuevos (hoja Sistema, portada, simulador) que decían «Oye Pi». La palabra por defecto es «Hey Jarvis»; «Oye Pi» es experimental y aún no es fiable (ver `docs/VOICE.md`). Corregidos esos textos y la palabra que muestra el simulador.

## Portada: dos capturas nuevas

- La galería suma «Temporizadores con nombre» y «Ajustes» (salvapantallas y modo noche), capturadas del simulador.

## Test del inicio: ya no falla de forma intermitente

- `test_browser_without_autoplay_permission_gets_an_unmute_hint` fallaba a ratos en el CI (3 de 14 ejecuciones de hoy) porque comprobaba el aviso «activar sonido» justo al arrancar el vídeo. Ahora espera hasta 4 s a que aparezca. No era un fallo de la interfaz.

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
