# extra-assets: tu contenido para las pantallas de Inicio y de Carga

Aquí pones **tus** vídeos, GIFs e imágenes. El proyecto los detecta solo: no hay que tocar código ni configuración.

```
extra-assets/
├── start/
│   └── Inicio.mp4          ← vídeo de la Pantalla de Inicio (al encender el PC)
└── loading/
    ├── images/             ← imágenes pequeñas  (.png .jpg .jpeg .webp .svg)
    ├── gifs/               ← GIFs               (.gif)
    └── videos/             ← vídeos cortos      (.mp4 .webm)
```

## Pantalla de Inicio (`start/Inicio.mp4`)

- Se reproduce **al encender el PC**, sobre una pantalla en blanco, y al terminar carga el último modo que usaste.
- El archivo debe llamarse **exactamente** `Inicio.mp4` (respeta mayúsculas y minúsculas).
- Si no existe, se salta el vídeo y va directo a la pantalla de carga.
- Si el vídeo no se puede reproducir (formato raro), se salta solo a los 3 segundos.

## Pantalla de Carga (`loading/`)

- Sale **después del Inicio** y **cada vez que cambias de modo**.
- Debajo de la barra de progreso se van mostrando, una tras otra, las imágenes, GIFs y vídeos de estas tres carpetas, en pequeño. Si las carpetas están vacías, solo se ve la barra.
- Puedes poner **los que quieras** (se recomienda entre 3 y 20 archivos en total).

## Recomendaciones para que vaya fluido en la Raspberry Pi 5

| Tipo | Recomendado | Evita |
|---|---|---|
| Vídeo de Inicio | MP4 con **H.264** (vídeo) + AAC (audio), 1280×720 o 1920×1080, 30 fps, de 3 a 15 s | H.265/HEVC y 4K (pueden no reproducirse o ir a tirones) |
| Vídeos de carga | MP4/WebM H.264 o VP9, **máx. 480×270**, de 2 a 6 s, **sin audio** | Archivos de más de 5 MB |
| GIFs | Máx. 400 px de ancho, menos de 2 MB | GIFs de 20 MB |
| Imágenes | Máx. 800 px de ancho, menos de 500 KB | Fotos de móvil sin reducir (4000 px) |

Si tienes un vídeo en otro formato, conviértelo en tu ordenador con **ffmpeg**:

```bash
# vídeo de inicio compatible (H.264 + AAC, 1280 de ancho)
ffmpeg -i mi_video.mov -vf scale=1280:-2 -c:v libx264 -crf 23 -preset medium -c:a aac -movflags +faststart Inicio.mp4

# vídeo de carga pequeño y sin audio
ffmpeg -i clip.mp4 -vf scale=480:-2 -an -c:v libx264 -crf 28 -movflags +faststart clip_pequeno.mp4
```

## Cómo se instalan en la Raspberry Pi

1. Pon tus archivos en estas carpetas **del repositorio** (en tu ordenador o en la propia Pi).
2. En la Pi, dentro de la carpeta del proyecto: `git pull` (si los subiste a GitHub) y luego `./install.sh`.
   El instalador **copia** `extra-assets/` a `/opt/pcpi/extra-assets/` sin borrar lo que ya hubiera.
3. Sin reiniciar: la próxima vez que cambies de modo ya verás tu contenido.

> **Prueba rápida sin instalar:** `pcpi-mode home` y mira la pantalla de carga. Para ver todo el arranque,
> reinicia (`sudo reboot`).

## Ajustes

En `/etc/pcpi/pcpi.conf`, sección `[boot]` (se explica en `config/pcpi.conf.example`): activar/desactivar el vídeo de
inicio, cuánto dura la «carga rápida x2», si se muestra el botón Skip, etc.
