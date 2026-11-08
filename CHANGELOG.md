# Registro de cambios de PiCore

> Todo está probado con tests automáticos y un «Pi virtual» (servidor y `pcpi-session` reales con un Chromium sin pantalla).
> **Nada se ha probado todavía en una Raspberry Pi real**: pantalla, audio, Wayland, cámara, micrófono e instalación con `apt`.
> ¿Prefieres un resumen corto por temas? Mira [docs/NOVEDADES.md](docs/NOVEDADES.md). Aquí lo más reciente está arriba.



## Test: nada se sale de la pantalla (Casa, Iker y Dev a 800, 1024 y 1280 px)

- Nace de arreglar «Salir» en Iker: ahora un test comprueba que ningún botón ni campo queda fuera de la ventana ni hay scroll horizontal.

## Modo Iker: a 800 px de ancho también cabe «Salir»

- Por debajo de 900 px, Nueva y Borrar también pasan a solo icono (sobraban 2 px).

## Modo Iker: tema coherente (antes mezclaba claro y oscuro)

- Iker decidía su tema por la preferencia del navegador mientras que `ui.css` fijaba colores oscuros: el panel lateral salía claro con letra blanca. Ahora sigue el mismo criterio que Casa (claro de día, oscuro de noche, o el que elegiste tocando la hora) y el panel tiene su color en los dos temas.

## Modo Iker: la barra de botones cabe en 1024 px (antes «Salir» se salía por la derecha)

- USB, Duplicar, Fijar, PDF e Internet pasan a solo icono por debajo de 1180 px de ancho; conservan nombre y texto para lectores de pantalla y la ayuda al pasar el ratón.

## Modo Iker: Ctrl+D duplica la nota

- Se suma a Ctrl+S, Ctrl+N, Ctrl+P y Ctrl+F; el pie de la página lo recuerda.

## Tema claro (todas las pantallas): textos secundarios y estados con contraste AA

- `ui.css` pisaba los colores ya corregidos de Casa e Iker con otros más claros (`--dim` 3,7:1 sobre el panel de Iker; verde y rojo también justos). Ahora usa los mismos valores AA que Casa.

## Test: contraste de Iker sobre su panel lateral en los dos temas

- Cubre el arreglo del tema mezclado de Iker.

## Test: la portada y la carcasa del simulador en un navegador

- Cubre lo añadido hoy: pestañas con flechas, «Volver arriba», barra de progreso, sección marcada, frases de ejemplo, tecla `?`, `aria-pressed` y `?say=`.

## Tutorial: explica el apagado seguro con batería

- En la sección «Más adelante: batería y SSD», con su límite: sin medida de batería no hace nada.

## Alarmas: ya no suenan en silencio si el sistema está silenciado

- (Interno) `server.py` importa `sound` y un test arranca los temporizadores de verdad con el módulo real: sin eso la Pi habría fallado al arrancar con un `NameError` que ningún test veía.
- Mientras suena una alarma o un temporizador, si el volumen está en mute se quita el mute y, al parar, se vuelve a poner. Antes («silencia» por voz o el botón de mute) la alarma de las 7 sonaba sin que se oyera nada. Probado con un audio falso; sin probar con altavoz real.

## Batería: apagado seguro opcional (`auto_shutdown_percent`)

- Con un UPS que mida la carga, si pones `auto_shutdown_percent = 5` en `[battery]`, la Pi se apaga sola (por el mismo mecanismo que el botón Apagar) cuando lleva **1 minuto** por debajo de ese % **y sin cargar** (si no se sabe si carga, nunca apaga). Así una batería que se agota no corrompe la tarjeta SD. Desactivado por defecto (0). Sin probar con un UPS real: lo cubren tests con reloj falso.

## Notas y temporizadores: se fuerzan a disco antes de renombrar (`fsync`)

- Con un corte de luz entre escribir y renombrar, el archivo podía quedar vacío. Ahora `save_note` y el guardado de temporizadores hacen `fsync` antes de `os.replace`. Un test comprueba la llamada; no he simulado un corte de luz real.

## Zona horaria UTC: la hoja Sistema y `pcpi-doctor` lo avisan

- Una Pi sin zona horaria elegida va en UTC y las alarmas sonarían desfasadas respecto a tu hora. Se avisa (solo información en la hoja Sistema; aviso en el doctor) con la forma de cambiarla. Sin probar en una Pi real.

## Instalador: arregla o detecta la hora falsa antes de `apt`

- Sin pila de reloj, una Pi recién encendida sin internet puede creer que es 1970 y `apt update` falla con «Release file is not valid yet». `install.sh` ahora lo detecta, intenta sincronizar (`timedatectl set-ntp true`) hasta 20 s y, si no puede, dice cómo ponerla a mano. Sin probar en una Pi real.

## pcpi-backup: guarda también los experimentos del modo Dev

- `dev.json` (los experimentos que tengas encendidos) faltaba en la copia y se perdía al restaurar.

## Temporizadores y alarmas: lo que venció hace más de 10 minutos ya no suena

- Si la Pi estaba apagada (o el reloj se corrigió tras arrancar sin internet), una alarma de las 7 sonaba a las 9 y un temporizador de pasta sonaba horas tarde. Ahora, si lo vencido lleva más de 10 minutos, se descarta (una alarma diaria se reprograma para su próxima hora). Sin probar en una Pi real; los tests usan un reloj falso.

## pcpi-doctor: sección «Reloj»

- Dice si el año es imposible (hora falsa, error) o si la hora no está sincronizada (aviso), con la misma lógica que la hoja Sistema.

## Pi: aviso si la hora no es de fiar (la Pi 5 no tiene pila de reloj)

- La hoja Sistema avisa si el año es anterior a 2024 (hora falsa: mal para alarmas, temporizadores y calendario; nivel «mal») o si `timedatectl` dice que no está sincronizada con internet (solo informa). No he podido probarlo en una Pi real; el test usa un `timedatectl` falso.

## README y Novedades: la voz que abre hojas y pone canciones

- Las frases nuevas pasan por el test que comprueba que el asistente las entiende.

## Test: la voz abre y cierra de verdad las hojas de Casa

- En `shell_smoke.js`: «abre el tiempo», «abre los temporizadores» y «abre Musix» abren su hoja, y «cierra esto» la cierra.

## Arquitectura: describe el canal voz → pantalla (`/api/ui`, `/api/music`)

- Explica por qué la voz deja órdenes con número de secuencia y qué acepta cada una.

## Voz: abrir y cerrar hojas de Casa («abre el tiempo», «cierra esto»)

- Nuevo canal `POST /api/ui` (lista cerrada de hojas: tiempo, temporizadores, sistema, wifi, musix, calendario; o cerrar): la pantalla lo recoge al leer `/api/status`, igual que las órdenes de música. También en el simulador.

## Voz: aleatorio y repetir canción en el MP3 Player

- «Pon el modo aleatorio», «quita el aleatorio», «repite la canción», «repite todas las canciones», «no repitas». El servidor valida (`on` booleano; `mode` en all/one/off) y la pantalla aplica el cambio como si pulsaras los botones. También en el simulador.

## Modo Dev: orden rápida `pcpi-frase` (y la entiende la consola del simulador)

- En el simulador no dice la orden entendida (eso es solo de la Pi real) sino qué contestaría la demo.

## Docs: VOICE.md explica `pcpi-frase`

- Sección «Probar una frase sin micrófono» con dos ejemplos.

## Herramienta `pcpi-frase`: qué orden entendería la Pi con una frase

- `pcpi-frase "sube el volumen y pon música"` imprime la orden (o órdenes) que entendería, sin ejecutar nada. Sirve para depurar la voz sin micrófono; sin argumentos lee frases de la entrada. Se instala con el resto de `bin/`.

## Visita guiada: paso «Cuentas, fechas y unidades» (15 pasos)

- Enseña las órdenes nuevas y ejecuta «cuánto es 12 por 5» en la barra de voz.

## Hoja del Tiempo: los días de lluvia (50 % o más) también se tiñen

- Igual que las horas: se ve de un vistazo qué días llueve.

## Hoja del Tiempo: la primera hora se llama «Ahora» y las horas de lluvia se tiñen

- La tarjeta de la hora actual lleva borde de color y la etiqueta «Ahora»; las horas con 50 % o más de lluvia salen con un fondo azulado, para ver de un vistazo cuándo llueve.

## Voz: el tiempo a una hora («qué temperatura habrá a las seis»)

- Usa la previsión por horas que ya carga la pantalla (las próximas 12). Si preguntas por una hora fuera de ese margen, lo dice. También en el simulador.

## Voz: «abre las notas» y «abre la consola»

- Pasan a modo Iker y a modo Dev. También en el simulador.

## Simulador: el botón del modo Escritorio se marca bien y la cabecera se desplaza si no cabe

- Al abrir `/escritorio` la demo se declaraba en modo Casa y el botón resaltado era el equivocado. Además, por debajo de unos 1100 px los últimos botones (GitHub, Copiar enlace, Restablecer) quedaban cortados: ahora la cabecera se desplaza de lado.

## Voz: la pista de Whisper incluye las órdenes nuevas

- Se suman cuentas, unidades, amanecer, batería, fechas y chistes a la frase de ayuda que se le da a Whisper (`PROMPT` en `voice/stt.py`). Es una ayuda, no una garantía: sin probar en una Pi con micrófono real, no sé cuánto mejora el acierto.

## Voz: fechas relativas, días que quedan del mes y semana del año

- «Qué fecha será dentro de una semana», «qué día fue hace dos semanas» (también meses, con calendario real), «cuántos días quedan de este mes», «en qué semana estamos». En el simulador, solo con cifras.

## Capturas regeneradas con `make capturas`

- Las imágenes de la web y de la documentación reflejan la interfaz actual: barra de Iker con iconos, tema coherente y «Amanece / Anochece» en la hoja del Tiempo. Siguen siendo capturas de la demo simulada.

## Voz: números grandes con palabras (ciento veinte, doscientos, dos mil)

- Antes solo entendía hasta «cien»: «ciento veinte» daba 100. Ahora llega hasta el millar («cuánto es doscientos por tres», «dime un número entre cien y mil»). Las horas con letras («las veinte treinta») siguen igual. En el simulador las cifras grandes solo se entienden escritas con números.

## Arquitectura: describe los tests de contraste, ficheros estáticos, desbordes y carcasa

- Para que quien añada una pantalla sepa qué se le va a comprobar.

## Test: cada página pide solo ficheros de /static/ que existen

- Evita pantallas rotas por renombrar o borrar `fx.js`, `ui.css`, `osk.js`… y comprueba que `fx.js` está en las cuatro pantallas de la Pi.

## Voz: cuántas canciones tengo

- Cuenta los MP3 de la carpeta. También en el simulador.

## Voz: «pon la canción Aurora»

- La Pi busca entre tus MP3 por título (sin tildes ni mayúsculas, basta una parte; si hay varias, la de título más corto) y la pone. El servidor solo acepta el identificador de una canción que exista en la carpeta. También en el simulador.

## Voz (honestidad): cancelar alarmas dice cuántas quita y las excepciones se rechazan

- «Quita la alarma de las siete» quita todas las alarmas (la voz no distingue cuál) y ahora lo dice («He cancelado las 3 alarmas (la voz quita todas)»). «Despiértame a las siete todos los días menos los domingos» se guardaba como diaria sin avisar; ahora contesta que solo sabe alarmas de un día o diarias.

## Voz: la mitad, el doble y el triple de un número

- «Cuánto es la mitad de 50», «el doble de 8», «el triple de 7». También en el simulador.

## Voz (arreglo): «qué tengo el viernes» y «qué tengo pasado mañana»

- Antes «el viernes» se contestaba con lo de hoy y «pasado mañana» con lo de mañana (se comía la palabra). Ahora mira el día pedido. También en el simulador.

## Voz: máxima y mínima de hoy

- «Cuál es la máxima de hoy», «la mínima de hoy», «máxima y mínima». También en el simulador.

## Voz: qué notas tengo

- Dice los títulos de las tres primeras notas (las fijadas salen antes) y cuántas más hay. También en el simulador.

## Voz: buscar en las notas

- «Busca en mis notas leche» dice cuántas notas la tienen y los títulos de las tres primeras. También en el simulador.

## Test: apagar o reiniciar la Pi nunca es una orden de voz

- Fija lo que dice `docs/VOICE.md`: ninguna de esas frases produce una orden de apagado o reinicio.

## Docs: «Qué no hace la voz (a propósito)» en docs/VOICE.md

- Resume las reglas que impiden que una pregunta, una negación o una opinión ejecuten una orden.

## Voz: «más alto», «más bajo» y «pon la radio»

- «Más alto / más fuerte» y «más bajo / más flojo» cambian el volumen; «pon la radio» dice con honestidad que no hay radio y qué sí se puede poner. También en el simulador.

## Voz: «quita el silencio» y «activa el sonido» devuelven el sonido

- Antes «quita el silencio» silenciaba (se entendía «silencio»). Ahora quita el silencio de verdad (`wpctl set-mute 0`, o `amixer unmute`). También en el simulador.

## Voz: el tiempo de otra ciudad ya no se contesta con el de la tuya

- «Qué tiempo hace en Madrid» daba el tiempo de la ciudad elegida como si fuera el de Madrid. Ahora lo dice: solo hay el de la ciudad de la pantalla. Además «necesito un paraguas» y «hay riesgo de lluvia» dan el tiempo, «a cuántos estamos» da la fecha y «tengo reuniones hoy» mira el calendario.

## Voz: temporizadores con nombre «…para la pizza de 12 minutos», «cuánto le queda…» y «ponme un temporizador»

- El nombre se perdía cuando iba antes de la duración; «cuánto le queda al temporizador de la pasta» no se entendía; y «ponme un temporizador» sin tiempo ahora pregunta de cuánto.

## Hoja Sistema: la lista «Qué puedo decirle a la Pi» incluye las órdenes nuevas

- Cuentas, unidades, batería, amanecer, días que faltan, dos órdenes seguidas y chistes. Un test comprueba que el asistente entiende cada frase de la lista.

## Voz: cuánto falta para el viernes, el fin de semana o una fecha

- Además de Navidad, Nochevieja, Reyes, Año Nuevo y el verano. También en el simulador.

## Voz: centímetros y pulgadas, litros y galones

- Se suman a las conversiones de kilómetros, kilos, metros y grados. También en el simulador.

## Web: el pie de la portada dice de qué versión es la web

- Lee `/version.txt` (el commit con el que se construyó) y lo enseña como «· web 1a2b3c4». Si no está (en local), no muestra nada.

## Web: la pregunta «¿Qué le puedo decir a la Pi?» incluye cuentas, unidades, fechas y dos órdenes

- Las frases nuevas de la respuesta pasan por el test que comprueba que el asistente las entiende.

## Voz: una sola palabra

- «Hora», «fecha», «música», «alarma», «temporizador», «notas»: la orden más probable o una pista de cómo pedirlo. En el simulador «música» no hace nada (sin reproductor suelto).

## Voz: dos órdenes en una frase

- «Sube el volumen y pon música», «qué hora es y qué día es»: si las dos mitades son órdenes por sí solas, se hacen una detrás de otra y la Pi dice las dos respuestas. Las órdenes que ya llevan «y» dentro («toma nota comprar pan y leche», «dos horas y media») no se parten. En el simulador la detección es más simple (por el verbo con el que empieza cada mitad).

## Voz (arreglo): preguntas sobre cómo funciona algo y opiniones ya no ejecutan nada

- «Para qué sirve el Pi-hole» lo pausaba y «el modo Dev es genial» cambiaba de modo. Ahora las preguntas («para qué sirve», «qué hace», «cómo activo…») remiten al tutorial y las opiniones sobre una función («me gusta el modo Casa») se contestan con «Me alegro» (una opinión sobre otra cosa sigue yendo a la IA local). «Puedes poner música» ya pone música. También en el simulador.

## Voz (arreglo): las órdenes negadas y las preguntas de estado no ejecutan nada

- «No pongas la cámara» abría la cámara y «la vigilancia está activa» activaba la vigilancia. Ahora «no + verbo» contesta «Vale, lo dejo como está», y preguntar si algo «está activo / encendido / apagado» (cámara, vigilancia, salvapantallas, pantalla, música) no cambia nada. También en el simulador.

## Voz (arreglo): preguntar por el Pi-hole ya no lo pausa

- «Cuánto tiempo queda de pausa del Pi-hole» se entendía como «pausa el Pi-hole». Ahora cualquier pregunta («cuánto», «está activo», «porcentaje») da las estadísticas y no cambia nada. También en el simulador.

## Voz: «vuelve a casa», «adiós» y «perdona»

- «Vuelve a casa» (o «ve al inicio») cambia a modo Casa; «adiós» y «perdona» tienen su respuesta. También en el simulador.

## Voz: «despiértame en una hora» y «a qué hora suena la alarma»

- Antes no se entendía lo primero y lo segundo se contestaba con la hora actual. Ahora lo primero pone un aviso y lo segundo dice la próxima alarma (con «todos los días» y el nombre si los tiene). También en el simulador.

## CONTRIBUTING: receta de voz con el paso del navegador y las respuestas fijas

- Documenta la trampa de los reemplazos de texto que no se aplican y cómo añadir una respuesta fija.

## Simulador: los botones de modo dicen cuál está activo (`aria-pressed`)

- Un lector de pantalla ahora sabe si Casa, Iker, Dev o Escritorio es el modo actual.

## Web: la barra superior marca la sección que lees

- El enlace de la sección visible se resalta con una raya de color (`aria-current`).

## Web: «Pídele algo a la Pi» en la portada

- Ocho frases que abren el simulador y la ejecutan al llegar (`?say=`). Un test comprueba que el asistente de la Pi entiende cada una.

## Simulador: `?say=` prueba una orden al abrir

- `/simulador?say=qué hora es` escribe y envía esa orden a los dos segundos de abrir (máximo 140 caracteres). Sirve para enlazar ejemplos desde la portada o una incidencia.

## Voz: qué brillo tengo

- Dice el brillo efectivo (el de noche si toca) y si está en automático. También en el simulador.

## Accesibilidad: nombre para el deslizador de brillo y el explorador de la API

- El deslizador de brillo, el selector GET/POST y la ruta de la API del modo Dev no tenían nombre para un lector de pantalla.

## Simulador: «Copiar enlace» abre la hoja de compartir en el móvil

- Si el navegador tiene Web Share y la pantalla es táctil, abre el menú de compartir del sistema; si no, copia el enlace como siempre.

## Voz: «quién canta esto» y «qué está sonando»

- Se suman a «qué suena» y «qué canción es». También en el simulador.

## Interfaz: la bolita de los deslizadores crece al arrastrar

- Brillo y volumen: la bolita se agranda un poco y deja un halo de color mientras la arrastras.

## Simulador: el dispositivo aparece con un desenfoque suave

- Solo cambia la opacidad y el desenfoque (no toca el escalado de la carcasa) y se apaga con «reducir movimiento».

## Voz: cuenta hasta N

- «Cuenta hasta diez» dice 1, 2, 3… hasta veinte como máximo. También en el simulador.

## Voz: más charla sencilla

- «Qué te gusta», «dónde vives», «quién te hizo», «eres un robot», «tienes hambre». Son frases fijas de la tabla `RESPUESTAS` (la misma en el simulador). Ojo: son respuestas escritas a mano, no una IA.

## Voz: qué día fue ayer

- Dice el día de la semana y la fecha de ayer. También en el simulador.

## Voz: raíz cuadrada y al cuadrado

- «Cuánto es la raíz cuadrada de 144», «cuánto es 7 al cuadrado». También en el simulador.

## Modo Dev: botón «Copiar» en la consola

- Copia todo lo que sale en la consola, para pegarlo en una incidencia o en una nota. Si el navegador no deja usar el portapapeles, avisa de que hay que seleccionar y copiar a mano.

## Hoja del Tiempo: «Cambiar ciudad» ya no se parte en dos líneas

- Un selector de la cabecera le ponía 44 px de ancho (pensado para el botón redondo de cerrar). Ahora el botón se ajusta a su texto y el título largo se corta con puntos suspensivos.

## Hoja del Tiempo: amanece y anochece

- Debajo de las próximas horas sale «Amanece 07:42» y «Anochece 18:21» (con iconos, sin emojis). Si la API no los da, no se muestra nada.

## Voz: a qué hora amanece y anochece

- El servidor pide también `sunrise` y `sunset` a Open-Meteo (la misma llamada del tiempo) y la voz los dice. Antes «a qué hora amanece» se entendía como «qué hora es». En el simulador son horas de ejemplo.

## Voz: cuánta batería queda

- Antes «cuánto queda de batería» se entendía como «cuánto queda del temporizador». Ahora dice el porcentaje y si se está cargando (o que no hay batería). El simulador da un dato de ejemplo.

## Voz: qué versión tienes

- Dice la versión de PiCore que lee de `/api/status` (la que escribe `install.sh`). En el simulador contesta «demo».

## Voz: cuántas alarmas tengo

- Se une a «cuántas notas» y «cuántos temporizadores». También en el simulador.

## Voz: leer la lista de la compra o las tareas

- «Lee la lista de la compra», «qué hay en mis tareas»: dice los elementos (hasta 12). Solo lee; no borra nada. También en el simulador.

## Modo Iker: tiempo de lectura y singular correcto

- El contador de abajo dice «1 palabra» (no «1 palabras») y, desde unas 100 palabras, añade «· N min de lectura» (a 200 palabras por minuto).

## Simulador: ayuda de atajos con la tecla «?»

- Una ventanita lista los atajos (1-4, V, T, flechas, Esc). Se cierra con Esc o con «Entendido».

## Web: las pestañas de los modos se manejan con el teclado

- Flechas izquierda y derecha, Inicio y Fin cambian de modo (Casa, Iker, Dev) en la portada; solo la pestaña activa entra con Tab, como en cualquier lista de pestañas accesible.

## Web: botón «Volver arriba»

- Aparece al bajar un buen trozo de la portada y sube con un deslizamiento suave. Tiene nombre accesible y no sale si pides menos movimiento (ni con JavaScript apagado).

## Web: se puede instalar en el móvil

- Nuevo `manifest.webmanifest`: en el móvil, «Añadir a la pantalla de inicio» abre el simulador a pantalla completa con el icono de PiCore. No es una app con modo sin conexión, solo el acceso directo.

## Voz: deletrear y repetir

- «Deletrea hola» dice «h, o, l, a»; «repite después de mí …» repite la frase. También en el simulador.

## Voz: cuántos días tiene un mes

- «Cuántos días tiene febrero» (cuenta los bisiestos del año actual). También en el simulador.

## Voz: año, mes y día de la semana de una fecha

- «En qué año estamos», «qué mes es», «qué día cae el 25 de diciembre» (la próxima vez que llega esa fecha). También en el simulador.

## Voz: respuestas de cortesía

- «Cómo te llamas», «me oyes», «buenas noches», «te quiero»: respuestas fijas guardadas en una tabla (`RESPUESTAS`), la misma en la Pi y en el simulador.

## Web: movimiento en la portada y barra superior fija

- Las secciones aparecen al hacer scroll (con retraso escalonado en las rejillas), el título del hero brilla despacio, el dispositivo flota, hay una barra de progreso arriba y la barra superior gana sombra al bajar. Todo se apaga con «reducir movimiento» y sin JavaScript la página se ve completa.
- Arreglo: la barra superior no se quedaba fija al hacer scroll (`overflow-x:hidden` en `html` y `body` lo impedía); ahora usa `overflow-x:clip`.

## Interfaz: destello al tocar y tarjetas con presión (todas las pantallas)

- Nuevo `home/web/static/fx.js`: al tocar un botón, chip o canción sale un destello suave (solo `box-shadow`, sin repintar la pantalla). Las tarjetas se hunden un poco al pulsarlas y las cifras (reloj, Pi-hole, temporizador) usan números de ancho fijo para que no bailen. Se desactiva con «reducir movimiento». Probado en Chromium sin pantalla; no he medido el coste en una Pi real.

## Voz: porcentajes, «ponme música», «sube la música» y «quita el sonido»

- Arreglo: «cuánto es el 20 por ciento de 50» salía como 20 por 100; ahora calcula el porcentaje.
- «Ponme música» pone la música; «sube / baja la música» cambia el volumen; «quita el sonido» silencia. También en el simulador.

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
