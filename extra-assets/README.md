# extra-assets: tu contenido para las pantallas de Inicio y de Carga

Aquí pones **tus** vídeos, GIFs e imágenes. El proyecto los detecta solo: no hay que tocar código ni configuración.

```
extra-assets/
├── start/
│   ├── Inicio1.mp4         ← vídeos de la Pantalla de Inicio (al encender el PC): hasta 4
│   ├── Inicio2.mp4            (Inicio.mp4 vale como Inicio1.mp4)
│   ├── Inicio3.mp4
│   └── Inicio4.mp4
└── loading/
    ├── images/             ← imágenes pequeñas  (.png .jpg .jpeg .webp .svg)
    ├── gifs/               ← GIFs               (.gif)
    └── videos/             ← vídeos cortos      (.mp4 .webm)
```

## Pantalla de Inicio (`start/`)

- Se reproduce **al encender el PC**, sobre una pantalla en blanco, y al terminar carga el último modo que usaste.
- Puedes poner **hasta 4 vídeos**, con estos nombres **exactos** (respeta mayúsculas): `Inicio1.mp4` (o `Inicio.mp4`), `Inicio2.mp4`, `Inicio3.mp4`, `Inicio4.mp4`. Al encender sale **uno al azar**:

| Vídeo | Probabilidad (peso) | Porcentaje real* | Botón «Saltar» |
|---|---|---|---|
| `Inicio1.mp4` | 90 | ≈ 38,9 % | no |
| `Inicio2.mp4` | 85 | ≈ 36,8 % | no |
| `Inicio3.mp4` | 55 | ≈ 23,8 % | no |
| `Inicio4.mp4` | 1 | ≈ 0,4 % (pero ver la garantía) | **sí, a los 6 s** |

> 📥 **`Inicio4.mp4` no está en GitHub** (pesa ~500 MB y GitHub no deja subirlo). **La primera vez que enciendas la Pi con internet se descarga sola** de `https://pcraspberrypi-video.netlify.app/ayuda.mp4` a `extra-assets/start/Inicio4.mp4`, con una **pantalla de progreso** («Descargando contenido extra… 37 % · 190 MB de 531 MB») y un botón pequeño **«Continuar sin esperar»** (la descarga sigue en segundo plano). **No se vuelve a descargar** una vez que existe, ni al reinstalar ni al actualizar. Si se corta, se reanuda donde se quedó; si no hay internet, se reintenta en el siguiente encendido. Mientras se descarga no se elige ningún vídeo ni cuenta como encendido. Se cambia o desactiva con `[boot] intro4_url` (vacío = no descargar).

\* 90 + 85 + 55 + 1 suman más de 100, así que se usan como **pesos**: cada vídeo sale en proporción a su número. Se cambian en `[boot] intro_chances`.

- **Garantía:** si el vídeo 4 lleva **4 encendidos sin salir**, en el **siguiente sale sí o sí** (después la cuenta vuelve a empezar). Por eso, en la práctica, el 4.º sale **al menos 1 de cada 5 encendidos**. La garantía se aplica solo al 4.º por defecto (en los demás distorsionaría sus probabilidades); se puede ampliar con `intro_pity_slots = 1, 2, 3, 4`, y quitarla con `intro_pity = 0`.
- **Un encendido cuenta una sola vez**, aunque la pantalla se recargue (la elección se guarda junto al identificador de arranque del sistema, en `/var/lib/pcpi/intro.json`). Cambiar de modo **no** cuenta como encendido.
- **Botón «Saltar»:** el del vídeo 4 es **pequeño**, está en la **esquina inferior derecha** y aparece cuando el **vídeo** llega al segundo 6 (si el vídeo dura menos de 6 s, no hace falta). Los demás no llevan botón; se cambia con `intro_skip_seconds = 0, 0, 0, 6`.
- Si faltan vídeos, se elige entre los que haya (si solo hay uno, sale siempre ese). Si no hay ninguno, se salta el Inicio.
- Si un vídeo no se puede reproducir (formato raro), se salta solo a los ~5 segundos.

## ⚠️ ¿Se reproducirán tus vídeos? (H.265 / HEVC) — se arregla solo

Chromium en la Raspberry Pi reproduce **H.264** sin problemas, pero **H.265 (HEVC)** y AV1 **pueden no verse** (el vídeo se saltaría solo a los ~5 s). Por eso:

- **`./install.sh` hace solo una copia H.264** de los vídeos de inicio que lleven H.265 (si pesan menos de 150 MB; tarda unos segundos). La copia va a `extra-assets/start/.h264/` y **el servidor la usa en lugar del original**. **Tus originales no se tocan** y, si cambias un vídeo, se vuelve a convertir.
- El **vídeo 4** (el que se descarga, ~500 MB) se convierte **en segundo plano** nada más descargarse, con prioridad baja, si lleva H.265.
- A mano: `pcpi-intros check` (qué codec lleva cada uno y si hay copia) y `pcpi-intros convert` (`--only Inicio4.mp4`, `--max-mb N`, `--yes`).

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
ffmpeg -i mi_video.mov -vf scale=1280:-2 -c:v libx264 -crf 23 -preset medium -c:a aac -movflags +faststart Inicio1.mp4

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
