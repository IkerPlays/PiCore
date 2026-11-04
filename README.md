# PCRaspberryPI5

Un PC portátil con **Raspberry Pi 5 (8 GB)** y pantalla táctil de 7" con tres modos:

| Modo | Qué hace | Estado |
|---|---|---|
| 🖥 **Escritorio** | Raspberry Pi OS normal | ✅ |
| 🎮 **Gaming** | Pantalla "Próximamente" (Steam llegará después) | 🚧 placeholder |
| 🏠 **Casa** | Estilo Alexa con pantalla: hora, tiempo, Pi-hole, Spotify Connect, asistente de voz local y cámara | ✅ base |

- 🛒 Qué comprar (≤ 250 €): [docs/SHOPPING_LIST.md](docs/SHOPPING_LIST.md)
- 🧱 Cómo funciona y hoja de ruta: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Probar sin Raspberry Pi (emulador)

```bash
make emulate        # o: python3 tools/emulate.py
```

Abre <http://127.0.0.1:8080> y tienes el modo Casa funcionando en tu ordenador con un Pi-hole falso, tiempo, cámara de prueba y Spotify de mentira. En la misma terminal **escribes lo que dirías**: `oye pi qué hora es`, `oye pi` + (siguiente línea) `muestra la cámara`, `/spotify play Canción - Artista`, `/mode gaming`... Usa el mismo código que la Pi (máquina de estados, intérprete de órdenes y acciones). Detalles en `python3 tools/emulate.py --help`.

## Instalar

En Raspberry Pi OS con escritorio (64 bits), como usuario normal:

```bash
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
./install.sh --all        # o solo lo que quieras: --battery --pihole --spotify --voice --camera
```

Después cierra sesión y vuelve a entrar. Para comprobar que todo va: `pcpi-doctor`. Para quitarlo: `./uninstall.sh`.

## Usar

```bash
pcpi-mode home      # modo Casa
pcpi-mode gaming    # modo Gaming (Próximamente)
pcpi-mode desktop   # escritorio normal
pcpi-mode status
```

También hay un icono **"PCPi · Elegir modo"** en el menú de aplicaciones, y botones táctiles dentro de la UI de Casa y Gaming. El modo se recuerda entre reinicios.

Configuración (Pi-hole, ciudad del tiempo): `/etc/pcpi/pcpi.conf`. Hay una plantilla en [config/pcpi.conf.example](config/pcpi.conf.example).

## Cámara

Con `--camera` (usa `ffmpeg`), el botón **📷 Cámara** del modo Casa abre la imagen en pantalla completa, o di «Oye Pi, muestra la cámara» / «cierra la cámara». La cámara solo se enciende mientras la ves, solo se puede ver desde la propia Pi aunque el servidor escuche en la red, y se ajusta en `[camera]` de `/etc/pcpi/pcpi.conf`. Por defecto usa `/dev/video0` en 640×480 a 15 fps y copia el MJPEG de la webcam sin recodificar (casi sin CPU).

## Voz

Con `--voice` queda un asistente 100 % local (sin nube) con **detector dedicado de palabra de activación** ([openWakeWord](https://github.com/dscripka/openWakeWord)) + Vosk + espeak-ng. Di **«Hey Jarvis»**, espera el pitido y pide:

> «qué hora es» · «qué día es hoy» · «qué tiempo hace» · «modo casa / escritorio / gaming» · «muestra la cámara» · «pausa el Pi-hole diez minutos» · «activa el Pi-hole» · «sube / baja el volumen» · «volumen al cincuenta»

La palabra, el umbral y el micro se cambian en `[voice]` de `/etc/pcpi/pcpi.conf`. Detalles, y cómo entrenar tu propio «Oye Pi»: [docs/VOICE.md](docs/VOICE.md).

## Estado

> ⚠️ El código está probado con tests del servidor (`python3 -m unittest discover tests`, 24 tests, incluido el intérprete de órdenes de voz), pero **aún no en una Raspberry Pi real**. El instalador, el kiosk de Chromium, el hook de Spotify y la cámara, el reconocimiento de voz (calidad del micro, activaciones falsas) necesitan una prueba en el hardware.
