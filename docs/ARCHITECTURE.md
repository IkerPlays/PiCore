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
- **Pi-hole:** instalación oficial. La UI solo lee sus estadísticas.

## Hoja de ruta

1. ✅ Selector de modos, UI de modo Casa, "Próximamente" en Gaming, instalador.
2. ⏳ Asistente de voz local (Home Assistant Assist + openWakeWord) con el micro USB.
3. ⏳ Cámara en modo Casa (vista/cámara de seguridad).
4. ⏳ Modo Gaming (Steam Link o Steam emulado).
5. ⏳ Indicador de batería y brillo desde la UI.
