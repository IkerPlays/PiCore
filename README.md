# PCRaspberryPI5

Un PC portátil con **Raspberry Pi 5 (8 GB)** y pantalla táctil de 7" con tres modos:

| Modo | Qué hace | Estado |
|---|---|---|
| 🖥 **Escritorio** | Raspberry Pi OS normal | ✅ |
| 🎮 **Gaming** | Pantalla "Próximamente" (Steam llegará después) | 🚧 placeholder |
| 🏠 **Casa** | Estilo Alexa con pantalla: hora, tiempo, Pi-hole, Spotify Connect | ✅ base |

- 🛒 Qué comprar (≤ 250 €): [docs/SHOPPING_LIST.md](docs/SHOPPING_LIST.md)
- 🧱 Cómo funciona y hoja de ruta: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Instalar

En Raspberry Pi OS con escritorio (64 bits), como usuario normal:

```bash
git clone https://github.com/IkerPlays/PCRaspberryPI5.git
cd PCRaspberryPI5
./install.sh --all        # o solo lo que quieras: --battery --pihole --spotify
```

Después cierra sesión y vuelve a entrar.

## Usar

```bash
pcpi-mode home      # modo Casa
pcpi-mode gaming    # modo Gaming (Próximamente)
pcpi-mode desktop   # escritorio normal
pcpi-mode status
```

También hay un icono **"PCPi · Elegir modo"** en el menú de aplicaciones, y botones táctiles dentro de la UI de Casa y Gaming. El modo se recuerda entre reinicios.

Configuración (Pi-hole, ciudad del tiempo): `/etc/pcpi/pcpi.conf`. Hay una plantilla en [config/pcpi.conf.example](config/pcpi.conf.example).

## Estado

> ⚠️ El código está probado con tests del servidor (`python3 -m unittest discover tests`), pero **aún no en una Raspberry Pi real**. El instalador, el kiosk de Chromium y el hook de Spotify necesitan una prueba en el hardware.
