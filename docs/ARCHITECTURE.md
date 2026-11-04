# Arquitectura

```
/etc/pcpi/mode  ◄── pcpi-mode (CLI) ◄── pcpi-mode-menu (zenity, táctil)
     ▲                                         
     │ escribe                          lee cada 1 s
home/server.py ── POST /api/mode        bin/pcpi-session (sesión gráfica)
     │                                         │
     │ sirve                                   ├─ desktop → mata el kiosk
     ▼                                         ├─ home    → Chromium --kiosk /
home/web/index.html  (reloj, tiempo,           └─ gaming  → Chromium --kiosk /gaming
 Pi-hole, Spotify, CPU)
```

- **Un archivo de estado** (`/etc/pcpi/mode`) separa quién pide el modo de quién lo aplica. El servidor corre como servicio systemd sin pantalla. Solo `pcpi-session` vive en la sesión gráfica y puede lanzar Chromium.
- **`home/server.py`** usa solo la librería estándar. Escucha en `127.0.0.1:8080`. Expone `/api/status`, que agrega Pi-hole v6, el tiempo (Open-Meteo), "sonando ahora" y la temperatura de la CPU. Los cambios de modo exigen petición local con cabecera `X-PCPI: 1`.
- **Spotify:** Raspotify (Spotify Connect, hace falta Premium) aparece como el dispositivo "PCPi". Su hook `pcpi-spotify-event` escribe `/var/lib/pcpi/nowplaying.json`, que la UI lee.
- **Voz:** `voice/wake.py` detecta la palabra con openWakeWord (modelo dedicado, ONNX) y `voice/assistant.py` lleva una máquina de estados `idle → command → idle`: tras el pitido, Vosk transcribe una orden, `voice/intents.py` la interpreta, se ejecuta vía la API del servidor y se contesta con `espeak-ng`. La máquina de estados recibe todo inyectado, así que tiene tests sin audio. Estado en `/var/lib/pcpi/voice.json` (lo muestra la UI). Más en [VOICE.md](VOICE.md).
- **Cámara:** `/api/camera/stream` lanza `ffmpeg` (V4L2 → MJPEG) solo mientras hay un visor y lo mata al cerrarse la conexión (máx. 2 a la vez). Solo responde a `127.0.0.1`. `POST /api/camera {"show": true|false}` abre o cierra el visor de la UI, lo que permite controlarlo por voz.
- **Pi-hole:** instalación oficial. La UI solo lee sus estadísticas.

## Hoja de ruta

1. ✅ Selector de modos, UI de modo Casa, "Próximamente" en Gaming, instalador.
2. ✅ Asistente de voz local con palabra de activación dedicada. ⏳ Entrenar «Oye Pi» y voz más natural (Piper).
3. ✅ Cámara en modo Casa. ⏳ Detección de movimiento y avisos.
4. ⏳ Modo Gaming (Steam Link o Steam emulado).
5. ⏳ Indicador de batería y brillo desde la UI.
