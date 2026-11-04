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
- **Voz:** `voice/assistant.py` (servicio de usuario `pcpi-voice`) captura con `arecord`, reconoce en local con Vosk (modelo español pequeño) y habla con `espeak-ng`. `voice/intents.py` convierte la frase en una orden y no depende del audio, así que tiene tests. Las acciones pasan por la API del servidor (`/api/mode`, `/api/pihole`) y su estado va a `/var/lib/pcpi/voice.json`, que la UI muestra. Mientras habla reinicia la captura para no oírse a sí mismo.
- **Cámara:** `/api/camera/stream` lanza `ffmpeg` (V4L2 → MJPEG) solo mientras hay un visor y lo mata al cerrarse la conexión (máx. 2 a la vez). Solo responde a `127.0.0.1`. `POST /api/camera {"show": true|false}` abre o cierra el visor de la UI, lo que permite controlarlo por voz.
- **Pi-hole:** instalación oficial. La UI solo lee sus estadísticas.

## Hoja de ruta

1. ✅ Selector de modos, UI de modo Casa, "Próximamente" en Gaming, instalador.
2. ✅ Asistente de voz local (Vosk). ⏳ Mejorar: palabra de activación dedicada (openWakeWord) y voz más natural (Piper).
3. ✅ Cámara en modo Casa. ⏳ Detección de movimiento y avisos.
4. ⏳ Modo Gaming (Steam Link o Steam emulado).
5. ⏳ Indicador de batería y brillo desde la UI.
