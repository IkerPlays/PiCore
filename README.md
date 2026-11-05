# PCRaspberryPI5

Un PC portátil con **Raspberry Pi 5 (8 GB)** y pantalla táctil de 7" con tres modos:

| Modo | Qué hace | Estado |
|---|---|---|
| 🖥 **Escritorio** | Raspberry Pi OS normal | ✅ |
| 📝 **Iker** | Solo dos apps: **bloc de notas** (guardar/cargar notas) e **Internet** | ✅ |
| 🏠 **Casa** | Estilo Alexa con pantalla: hora, tiempo, Pi-hole, Spotify Connect, asistente de voz local y cámara | ✅ base |

- 🛒 Qué comprar (≤ 250 €): [docs/SHOPPING_LIST.md](docs/SHOPPING_LIST.md)
- 🖥 **Mini pantalla de estado** (CPU/RAM/disco/GPU, opcional): [docs/PANTALLA_MINI.md](docs/PANTALLA_MINI.md)
- 📖 **Tutorial desde cero (qué comprar, montar, instalar, configurar):** [docs/TUTORIAL.md](docs/TUTORIAL.md)
- 🧱 Cómo funciona y hoja de ruta: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Probar sin Raspberry Pi (emulador)

```bash
make emulate        # o: python3 tools/emulate.py
```

Abre <http://127.0.0.1:8080> y tienes el modo Casa funcionando en tu ordenador con un Pi-hole falso, tiempo, cámara de prueba y Spotify de mentira. En la misma terminal **escribes lo que dirías**: `oye pi qué hora es`, `oye pi` + (siguiente línea) `muestra la cámara`, `/spotify play Canción - Artista`, `/mode iker`... Usa el mismo código que la Pi (máquina de estados, intérprete de órdenes y acciones). Detalles en `python3 tools/emulate.py --help`.

## Instalar

En Raspberry Pi OS con escritorio (64 bits), como usuario normal:

```bash
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
./install.sh --all        # = --camera --voice --spotify --pihole. Aparte: --stats (mini pantalla) y --battery
```

Después cierra sesión y vuelve a entrar. Para comprobar que todo va: `pcpi-doctor`. **Guía completa paso a paso: [docs/TUTORIAL.md](docs/TUTORIAL.md).** Para quitarlo: `./uninstall.sh`.

## Usar

```bash
pcpi-mode home      # modo Casa
pcpi-mode iker      # modo Iker (notas + internet)
pcpi-mode desktop   # escritorio normal
pcpi-mode status
pcpi-setup          # asistente: ciudad, contraseña de Pi-hole, micrófono (con prueba), mini pantalla
pcpi-doctor         # diagnóstico
```

También hay un icono **"PCPi · Elegir modo"** en el menú de aplicaciones, y botones táctiles dentro de la UI de Casa y de Iker. El modo se recuerda entre reinicios.

Configuración (Pi-hole, ciudad del tiempo): `/etc/pcpi/pcpi.conf`. Hay una plantilla en [config/pcpi.conf.example](config/pcpi.conf.example).

## Cámara

Con `--camera` (usa `ffmpeg`), el botón **📷 Cámara** del modo Casa abre la imagen en pantalla completa, o di «Hey Jarvis», espera el pitido y «muestra la cámara» / «cierra la cámara». La cámara solo se enciende mientras la ves, solo se puede ver desde la propia Pi aunque el servidor escuche en la red, y se ajusta en `[camera]` de `/etc/pcpi/pcpi.conf`. Por defecto usa `/dev/video0` en 640×480 a 15 fps y copia el MJPEG de la webcam sin recodificar (casi sin CPU).

## Voz

Con `--voice` queda un asistente 100 % local (sin nube) con **detector dedicado de palabra de activación** ([openWakeWord](https://github.com/dscripka/openWakeWord)) + Vosk + espeak-ng. Di **«Hey Jarvis»**, espera el pitido y pide:

> «qué hora es» · «qué día es hoy» · «qué tiempo hace» · «modo casa / escritorio / iker» · «muestra la cámara» · «pausa el Pi-hole diez minutos» · «activa el Pi-hole» · «sube / baja el volumen» · «volumen al cincuenta»

La palabra, el umbral y el micro se cambian en `[voice]` de `/etc/pcpi/pcpi.conf`. Detalles, y por qué «Oye Pi» aún no es fiable: [docs/VOICE.md](docs/VOICE.md).

## Estado

**140 tests** (`make test`, unos 40 s):

- **Instalador y desinstalador ejecutados de verdad** en un árbol alternativo, con `apt`, `systemctl`, `sudo`… de mentira que anotan lo que se les pide: rutas, permisos, idempotencia (no pisa tu configuración ni tu modo), orden de las llamadas (el servidor se reinicia **después** de añadir los grupos), y que desinstalar deja el panel del escritorio intacto.
- **Todos los scripts de `bin/`** (modos, selector, hook de Spotify, grabación de muestras, `pcpi-doctor`, y el vigilante de modos con un Chromium de mentira).
- **Servidor y API**, seguridad (DNS rebinding, cabeceras, entradas raras), notas, cámara, configuración desordenada (contraseñas con `%`, claves repetidas, líneas basura).
- **Voz** (intérprete de órdenes, máquina de estados) y **mini pantalla** (métricas, dibujo, bytes del SSD1306/SH1106, reconexión).
- **La interfaz en un navegador real** (26 comprobaciones con Playwright: botones, notas, tema, cámara, XSS, errores de consola/CSP). Se omite si no tienes `node` + `playwright`.

> ⚠️ **Nada de esto se ha probado todavía en una Raspberry Pi real.** Falta comprobar sobre el hardware: el instalador con apt de verdad, el kiosco de Chromium, el hook de Spotify, la cámara, el reconocimiento de voz (calidad del micro, umbral de activación) y la mini pantalla. Si algo falla, `pcpi-doctor` y la sección «Si algo falla» del [tutorial](docs/TUTORIAL.md) son el punto de partida.
