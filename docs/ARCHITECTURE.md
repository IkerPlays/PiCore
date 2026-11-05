# Arquitectura

```
/etc/pcpi/mode  ◄── pcpi-mode (CLI) ◄── pcpi-mode-menu (zenity, táctil)
     ▲                                         
     │ escribe                          lee cada 1 s
home/server.py ── POST /api/mode        bin/pcpi-session (sesión gráfica)
     │                                         │
     │ sirve                                   ├─ desktop → mata el kiosk
     ▼                                         ├─ home    → Chromium --kiosk /
home/web/index.html  (reloj, tiempo,           └─ iker    → Chromium (ventana normal) /iker
 Pi-hole, Spotify, CPU)
```

- **Un archivo de estado** (`/etc/pcpi/mode`) separa quién pide el modo de quién lo aplica. El servidor corre como servicio systemd sin pantalla. Solo `pcpi-session` vive en la sesión gráfica y puede lanzar Chromium.
- **`home/server.py`** usa solo la librería estándar. Escucha en `127.0.0.1:8080`. Expone `/api/status`, que agrega Pi-hole v6, el tiempo (Open-Meteo), "sonando ahora" y la temperatura de la CPU. Los cambios de modo exigen petición local con cabecera `X-PCPI: 1`.
- **Modo Iker:** `home/web/iker.html` es el bloc de notas (guardado automático). Las notas viven en `/var/lib/pcpi/notes/<id>.json`; la API (`/api/notes`) solo responde a la propia máquina y las escrituras exigen la cabecera `X-PCPI`. En este modo `pcpi-session` abre Chromium en ventana normal: las notas son la primera pestaña e «Internet» abre pestañas nuevas.
- **Spotify:** Raspotify (Spotify Connect, hace falta Premium) aparece como el dispositivo "PCPi". Su hook `pcpi-spotify-event` escribe `/run/pcpi/nowplaying.json`, que la UI lee.
- **Voz:** `voice/wake.py` detecta la palabra con openWakeWord (modelo dedicado, ONNX) y `voice/assistant.py` lleva una máquina de estados `idle → command → idle`: tras el pitido, Vosk transcribe una orden, `voice/intents.py` la interpreta, se ejecuta vía la API del servidor y se contesta con `espeak-ng`. La máquina de estados recibe todo inyectado, así que tiene tests sin audio. Estado en `/run/pcpi/voice.json` (lo muestra la UI). Más en [VOICE.md](VOICE.md).
- **Cámara:** `/api/camera/stream` lanza `ffmpeg` (V4L2 → MJPEG) solo mientras hay un visor y lo mata al cerrarse la conexión (máx. 2 a la vez). Solo responde a `127.0.0.1`. `POST /api/camera {"show": true|false}` abre o cierra el visor de la UI, lo que permite controlarlo por voz.
- **Estado en RAM:** lo que cambia a cada rato (qué suena, qué oyó la voz) va en `/run/pcpi` (tmpfs, creado en cada arranque por `/etc/tmpfiles.d/pcpi.conf`), no en la microSD: así no se desgasta con miles de escrituras pequeñas. Solo las notas (`/var/lib/pcpi/notes`, carpeta privada `0700`) y la configuración persisten.
- **Mini pantalla:** `stats/` es independiente del servidor. `sysstats.py` lee CPU/RAM/disco/temperatura/GPU/ventilador/red (solo librería estándar), `render.py` dibuja 128×64 con Pillow y `ssd1306.py` es un driver mínimo por I2C con `smbus` (sin `luma.oled`, que depende de `RPi.GPIO`, incompatible con la Pi 5). Ver [PANTALLA_MINI.md](PANTALLA_MINI.md).
- **Arranque de sesión:** `bin/pcpi-autostart` crea el `.desktop` y, para labwc, **copia primero** `/etc/xdg/labwc/autostart` antes de añadir su línea (si no, labwc ignoraría el del sistema y se perdería el panel del escritorio).
- **Seguridad del servidor:** escucha solo en `127.0.0.1`. Como el modo Iker navega por internet **en esta misma máquina**, una web hostil podría intentar un *DNS rebinding* (hacer que su dominio apunte a `127.0.0.1`) para leer las notas o la cámara; por eso **todas** las rutas exigen un `Host` propio (`localhost`, `127.0.0.1`, `[::1]`; otros nombres se añaden en `[server] allowed_hosts`). Además: las escrituras exigen la cabecera `X-PCPI`, las notas y la cámara solo responden a la propia máquina, y las páginas llevan una política CSP (solo recursos propios, portadas por https), `X-Frame-Options: DENY` y `nosniff`.
- **Pi-hole:** instalación oficial. La UI solo lee sus estadísticas.

## Hoja de ruta

1. ✅ Selector de modos, UI de modo Casa, modo Iker (notas + internet), instalador, emulador.
2. ✅ Asistente de voz local con palabra de activación dedicada. ⏳ Entrenar «Oye Pi» y voz más natural (Piper).
3. ✅ Cámara en modo Casa. ⏳ Detección de movimiento y avisos.
4. ✅ Mini pantalla de estado (OLED, sin probar en hardware). ⏳ Indicador de batería y brillo desde la UI.
