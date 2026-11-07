# PiCore

> ℹ️ El proyecto se llama **PiCore** (antes «PCPi»). Los nombres técnicos se mantienen por compatibilidad: comandos `pcpi-*`, carpetas `/opt/pcpi` y `/etc/pcpi`, archivo `pcpi.conf`, servicios `pcpi-home`/`pcpi-voice`/`pcpi-stats`.

Un PC portátil con **Raspberry Pi 5 (8 GB)** y pantalla táctil de 7" con tres modos:

| Modo | Qué hace | Estado |
|---|---|---|
| 🖥 **Escritorio** | Raspberry Pi OS normal | ✅ |
| 📝 **Iker** | Solo dos apps: **bloc de notas** (guardar/cargar notas) e **Internet** | ✅ |
| 🏠 **Casa** | Estilo Alexa con pantalla y animaciones suaves: hora, tiempo, Pi-hole, Spotify Connect, asistente de voz local, cámara y panel de Wi-Fi | ✅ base |

- 🛒 Qué comprar (≤ 250 €): [docs/SHOPPING_LIST.md](docs/SHOPPING_LIST.md)
- 🖥 **Mini pantalla de estado** (CPU/RAM/disco/GPU, opcional): [docs/PANTALLA_MINI.md](docs/PANTALLA_MINI.md)
- 📖 **Tutorial desde cero (qué comprar, montar, instalar, configurar):** [docs/TUTORIAL.md](docs/TUTORIAL.md)
- 🎬 **Pantallas de Inicio y de Carga** con tus vídeos/GIFs/imágenes: carpeta [extra-assets/](extra-assets/README.md)
- 📶 **Wi-Fi** (cambiar de red desde la pantalla, Pi-hole en cada red, wifis públicas con login): [Paso 9 del tutorial](docs/TUTORIAL.md#paso-9-wi-fi-en-casa-de-viaje-y-wifis-públicas)
- 🧱 Cómo funciona y hoja de ruta: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Probar sin Raspberry Pi (emulador)

```bash
make emulate        # o: python3 tools/emulate.py   (Windows: python tools\emulate.py)
```

Abre <http://127.0.0.1:8080> y tienes el modo Casa funcionando en tu ordenador con un Pi-hole falso, tiempo, cámara de prueba y Spotify de mentira. En la misma terminal **escribes lo que dirías**: `oye pi qué hora es`, `oye pi` + (siguiente línea) `muestra la cámara`, `/spotify play Canción - Artista`, `/mode iker`... Usa el mismo código que la Pi (máquina de estados, intérprete de órdenes y acciones). **Ver los intros y la pantalla de carga:** abre <http://127.0.0.1:8080/loading?to=home&boot=1> (o arranca con `--open`); en la terminal, `/boot` simula encender la Pi de nuevo, `/intro 1..4` fuerza un intro, `/intro4 reset` repite la pantalla de descarga, `/battery 15`, `/portal on` y `/motion` enseñan la batería, la wifi pública y el aviso de movimiento. Tus vídeos se leen de `extra-assets/` (si son H.265, tu navegador debe saber reproducirlos: Edge y Safari sí, Chrome según el equipo). Detalles en `python3 tools/emulate.py --help`.

## Instalar

En Raspberry Pi OS con escritorio (64 bits), como usuario normal:

```bash
git clone https://github.com/IkerPlays/PiCore.git
cd PiCore
./install.sh --camera --voice --spotify   # Pi-hole se instala aparte: ./install.sh --pihole (ver Paso 6 del tutorial). Opciones: --all Aparte: --stats (mini pantalla) y --battery
```

Después cierra sesión y vuelve a entrar. Para comprobar que todo va: `pcpi-doctor`. **Guía completa paso a paso: [docs/TUTORIAL.md](docs/TUTORIAL.md).** Para quitarlo: `./uninstall.sh`.

## Usar

```bash
pcpi-mode home      # modo Casa
pcpi-mode iker      # modo Iker (notas + internet)
pcpi-mode desktop   # escritorio normal
pcpi-mode status
pcpi-wifi list      # Wi-Fi desde la terminal (connect, status, forget, pihole, portal)
pcpi-setup          # asistente: ciudad, contraseña de Pi-hole, micrófono (con prueba), mini pantalla
pcpi-doctor         # diagnóstico
pcpi-update         # actualizar PiCore (copia previa + git pull + reinstalar con tus opciones)
pcpi-backup create  # copia de seguridad de tu configuración, notas y extra-assets
```

También hay un icono **"PiCore · Elegir modo"** en el menú de aplicaciones, y botones táctiles dentro de la UI de Casa y de Iker. El modo se recuerda entre reinicios.

Configuración (Pi-hole, ciudad del tiempo): `/etc/pcpi/pcpi.conf`. Hay una plantilla en [config/pcpi.conf.example](config/pcpi.conf.example).

## Pantallas de Inicio y de Carga

Al **encender**, una pantalla en blanco reproduce **uno de hasta 4 vídeos** de `extra-assets/start/` (`Inicio1.mp4`…`Inicio4.mp4`, al azar con pesos 90/85/55/1; el 4.º sale sí o sí tras 4 encendidos sin verlo y lleva un botón «Saltar» pequeño a los 6 s) y después carga el **último modo** usado. El vídeo 4 (~500 MB, no cabe en GitHub) **se descarga solo la primera vez que enciendes la Pi**, con pantalla de progreso. Si tus vídeos llevan H.265, `pcpi-intros check` / `pcpi-intros convert`. En **cada cambio de modo** (y tras el Inicio) sale la pantalla de **Carga**: pop-up «Cargando», barra y porcentaje, y debajo tus imágenes/GIFs/vídeos de `extra-assets/loading/`. La carga real llega al 100 % pero **se muestra 85 %**; entonces un efecto de tele con **«▶▶ x2»** acelera la barra hasta el 100 % (un tramo visual) y un botón **Saltar** lo pasa. Todo se ajusta en `[boot]`. Detalles: [extra-assets/README.md](extra-assets/README.md) y [Paso 8.2](docs/TUTORIAL.md#82-las-pantallas-de-inicio-y-de-carga-tus-vídeos-y-gifs).

## Wi-Fi

La wifi de casa va en la microSD (Imager). Para otra red, toca el icono de Wi-Fi del modo Casa (hay teclado en pantalla) o usa `pcpi-wifi`. **Pi-hole se aplica en cada red** (con un interruptor por red) y **no se fuerza si está caído**. En wifis públicas con portal (hotel, aeropuerto) se abre sola la ventana de inicio de sesión. Detalles y límites: [Paso 9](docs/TUTORIAL.md#paso-9-wi-fi-en-casa-de-viaje-y-wifis-públicas).

## Más funciones

- **Brillo** (☀ en Casa): deslizante y modo noche automático con rampa suave. Si la pantalla no tiene control por software, se oscurece con una capa.
- **Vigilancia** (👁): detección de movimiento con la cámara y aviso en pantalla; no guarda ni envía imágenes. Apagada por defecto.
- **Botones de Spotify** (pausa/siguiente/anterior, también por voz) con la API web de Spotify: opcional, exige Premium y una app propia gratuita (`pcpi-spotify login`).
- **Hoja «Sistema»** en la pantalla: disco, memoria, temperatura, avisos de salud, apagar/reiniciar con doble toque y aviso de actualizaciones (comprobación semanal opcional, nunca instala sola).
- **Calendario** de solo lectura (`.ics` de Google/Apple): próximos eventos en la pantalla y por voz.
- **Salvapantallas / marco de fotos** con tus fotos de `extra-assets/photos/`.
- **Tiempo** por horas y próximos días, con aviso de lluvia.
- **Temporizadores y alarmas** por voz («pon un temporizador de diez minutos», «despiértame a las siete y media») con aviso a pantalla y sonido; persisten tras reiniciar.
- **IA local opcional** (`./install.sh --ai`: Ollama + Qwen, sin internet, con datos reales de la Pi; ver el [tutorial 7.6](docs/TUTORIAL.md#76-ia-local-con-ollama--qwen-opcional) para lo que cabe de verdad en la Pi 5).
- **Whisper** (reconocimiento de voz sin conexión, el modelo se descarga al instalar) para entender mucho mejor las órdenes.
- **Batería** (🔋): solo si tienes un UPS/HAT con medidor o un comando propio (la Pi 5 no mide la batería).
- **Modo Iker**: buscar en las notas, **etiquetas** (`#compra`), **exportar a PDF**, **marcadores** de webs, copias automáticas y exportar a USB (📤).
- **`pcpi-backup`** (copia de todo lo tuyo en un archivo) y **`pcpi-update`** (actualiza y reinstala con tus mismas opciones).
- **Autorreparación**: si Chromium se cae o se queda en blanco, se relanza solo por la pantalla de Carga.

## Cámara

Con `--camera` (usa `ffmpeg`), el botón **📷 Cámara** del modo Casa abre la imagen en pantalla completa, o di «Hey Jarvis», espera el pitido y «muestra la cámara» / «cierra la cámara». La cámara solo se enciende mientras la ves, solo se puede ver desde la propia Pi aunque el servidor escuche en la red, y se ajusta en `[camera]` de `/etc/pcpi/pcpi.conf`. Por defecto usa `/dev/video0` en 640×480 a 15 fps y copia el MJPEG de la webcam sin recodificar (casi sin CPU).

## Voz

Con `--voice` queda un asistente 100 % local (sin nube) con **detector dedicado de palabra de activación** ([openWakeWord](https://github.com/dscripka/openWakeWord)) + Vosk + espeak-ng. Di **«Hey Jarvis»**, espera el pitido y pide:

> «qué hora es» · «qué día es hoy» · «qué tiempo hace» · «modo casa / escritorio / iker» · «muestra la cámara» · «pausa el Pi-hole diez minutos» · «activa el Pi-hole» · «sube / baja el volumen» · «volumen al cincuenta» · «sube el brillo» · «brillo automático» · «activa la vigilancia»

La palabra, el umbral y el micro se cambian en `[voice]` de `/etc/pcpi/pcpi.conf`. Detalles, y por qué «Oye Pi» aún no es fiable: [docs/VOICE.md](docs/VOICE.md).

## Estado

**323 tests** (`make test`, ~2 min):

- **Instalador y desinstalador ejecutados de verdad** en un árbol alternativo, con `apt`, `systemctl`, `sudo`… de mentira que anotan lo que se les pide: rutas, permisos, idempotencia (no pisa tu configuración ni tu modo), orden de las llamadas (el servidor se reinicia **después** de añadir los grupos), y que desinstalar deja el panel del escritorio intacto.
- **Todos los scripts de `bin/`** (modos, selector, hook de Spotify, grabación de muestras, `pcpi-doctor`, y el vigilante de modos con un Chromium de mentira).
- **Servidor y API**, seguridad (DNS rebinding, cabeceras, entradas raras), notas, cámara, configuración desordenada (contraseñas con `%`, claves repetidas, líneas basura).
- **Voz** (intérprete de órdenes, máquina de estados) y **mini pantalla** (métricas, dibujo, bytes del SSD1306/SH1106, reconexión).
- **Pantallas de Inicio/Carga, Wi-Fi, assets**: listado y rutas seguras, Range, el vigilante `pcpi-session` con Chromium de mentira, `nmcli` simulado (contraseñas, DNS por red, portal cautivo) y la pantalla de carga y el panel de Wi-Fi con teclado en un navegador real.
- **La interfaz en un navegador real** (más de 50 comprobaciones con Playwright: botones, notas, tema, cámara, XSS, errores de consola/CSP). Se omite si no tienes `node` + `playwright`.

> ⚠️ **Nada de esto se ha probado todavía en una Raspberry Pi real.** Falta comprobar sobre el hardware: el instalador con apt de verdad, el kiosco de Chromium (y el vídeo de Inicio con sus códecs), el Wi-Fi con NetworkManager y los portales cautivos reales, el hook de Spotify, la cámara, el reconocimiento de voz (calidad del micro, umbral de activación) y la mini pantalla. Si algo falla, `pcpi-doctor` y la sección «Si algo falla» del [tutorial](docs/TUTORIAL.md) son el punto de partida.
