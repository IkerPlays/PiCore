#!/usr/bin/env bash
# Instalador PCPi para Raspberry Pi OS (Bookworm/Trixie). Ejecutalo como usuario normal (usa sudo).
#   ./install.sh [--camera] [--voice] [--spotify] [--pihole] [--stats] [--battery] [--all]
#     --camera   camara USB en el modo Casa (ffmpeg)
#     --voice    asistente de voz local (Vosk + openWakeWord + espeak-ng): "Hey Jarvis, que hora es"
#     --spotify  Raspotify (Spotify Connect, requiere Premium) y el hook de "sonando ahora"
#     --pihole   lanza el instalador oficial de Pi-hole (interactivo)
#     --stats    mini pantalla OLED I2C con CPU/RAM/disco/temperatura (ver docs/PANTALLA_MINI.md)
#     --battery  sube el limite de corriente USB (solo si usas una power bank sin 5V/5A)
#   Se puede ejecutar de nuevo para actualizar o añadir piezas: es idempotente.
#   (Para pruebas: PCPI_ROOT=/otra/raiz instala en un arbol alternativo; PCPI_HOME y PCPI_PIP sustituyen la carpeta
#    personal y el pip del entorno virtual. En uso normal no se toca nada de esto.)
set -euo pipefail

CAMERA=0; VOICE=0; SPOTIFY=0; PIHOLE=0; STATS=0; BATTERY=0
for a in "$@"; do
  case "$a" in
    --camera) CAMERA=1 ;; --voice) VOICE=1 ;; --spotify) SPOTIFY=1 ;; --pihole) PIHOLE=1 ;;
    --stats) STATS=1 ;; --battery) BATTERY=1 ;;
    --all) CAMERA=1; VOICE=1; SPOTIFY=1; PIHOLE=1 ;;   # --all NO incluye --stats ni --battery (hardware opcional)
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Opcion desconocida: $a  (usa --help)" >&2; exit 1 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
[ "$(id -u)" -ne 0 ] || { echo "Ejecuta como usuario normal, no como root (el script usa sudo)." >&2; exit 1; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ME="$(id -un)"; HOME_DIR="${PCPI_HOME:-$(getent passwd "$ME" | cut -d: -f6)}"
R="${PCPI_ROOT:-}"                       # vacio = sistema real
PREFIX="$R/opt/pcpi"
UID_ME="$(id -u)"
PIP="${PCPI_PIP:-$PREFIX/venv/bin/pip}"
user_ctl() { XDG_RUNTIME_DIR="/run/user/$UID_ME" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$UID_ME/bus" systemctl --user "$@"; }

step "Comprobaciones previas"
[ "$(uname -m)" = "aarch64" ] || echo "Aviso: no es un sistema de 64 bits (aarch64). Usa Raspberry Pi OS 64-bit."
curl -fsI -m 10 https://deb.debian.org >/dev/null || { echo "No hay internet. Conecta el wifi/Ethernet y repite." >&2; exit 1; }
[ "$(df --output=avail -k / | tail -1)" -gt 2000000 ] || { echo "Queda menos de 2 GB libres en la tarjeta." >&2; exit 1; }

step "Paquetes"
sudo apt-get update
CHROMIUM_PKG=chromium; apt-cache show chromium >/dev/null 2>&1 || CHROMIUM_PKG=chromium-browser
sudo apt-get install -y python3 curl rsync zenity "$CHROMIUM_PKG"

step "Archivos en $PREFIX"
sudo mkdir -p "$PREFIX"
sudo rsync -a --delete --exclude __pycache__ "$SRC/home" "$SRC/bin" "$SRC/voice" "$SRC/stats" "$PREFIX/"
# Tus videos/imagenes de las pantallas de Inicio y Carga: se COPIAN sin borrar lo que ya hubiera en la Pi
sudo mkdir -p "$PREFIX/extra-assets"
sudo rsync -a --exclude .gitkeep --exclude README.md "$SRC/extra-assets/" "$PREFIX/extra-assets/"
sudo mkdir -p "$R/usr/local/bin"
for f in "$PREFIX"/bin/*; do sudo ln -sf "$f" "$R/usr/local/bin/$(basename "$f")"; done
sudo chmod +x "$PREFIX"/bin/*

step "Configuracion en /etc/pcpi"
sudo mkdir -p "$R/etc/pcpi" "$R/var/lib/pcpi"
sudo chown "$ME": "$R/etc/pcpi" "$R/var/lib/pcpi"
sudo chmod 700 "$R/var/lib/pcpi"                  # aqui van tus notas: privadas
[ -f "$R/etc/pcpi/pcpi.conf" ] || install -m 640 "$SRC/config/pcpi.conf.example" "$R/etc/pcpi/pcpi.conf"
[ -f "$R/etc/pcpi/mode" ] || echo desktop > "$R/etc/pcpi/mode"
# Estado que cambia a cada rato (voz, "sonando ahora") en RAM (/run), no en la microSD
sudo mkdir -p "$R/etc/tmpfiles.d"
echo 'd /run/pcpi 1777 root root -' | sudo tee "$R/etc/tmpfiles.d/pcpi.conf" >/dev/null
sudo systemd-tmpfiles --create "$R/etc/tmpfiles.d/pcpi.conf"

step "Wi-Fi (NetworkManager)"
# El servidor cambia de red y de DNS por ti: necesita el grupo netdev (permiso de NetworkManager).
# NetworkManager NO se instala aqui: viene de serie en Raspberry Pi OS Bookworm/Trixie, y en versiones antiguas
# instalarlo reemplazaria el sistema de red y podria dejarte sin conexion.
command -v nmcli >/dev/null || echo "Aviso: no hay NetworkManager (nmcli): el panel de Wi-Fi no estara disponible. Usa Raspberry Pi OS Bookworm o Trixie." >&2
sudo usermod -aG netdev "$ME"

step "Brillo de la pantalla"
# Si la pantalla tiene retroiluminacion controlable (/sys/class/backlight), el grupo video podra cambiarla.
# Muchas pantallas HDMI baratas no la tienen: entonces la interfaz atenua por software.
sudo mkdir -p "$R/etc/udev/rules.d"
printf '%s\n' 'SUBSYSTEM=="backlight", ACTION=="add|change", RUN+="/bin/chgrp video /sys/class/backlight/%k/brightness", RUN+="/bin/chmod g+w /sys/class/backlight/%k/brightness"' | sudo tee "$R/etc/udev/rules.d/90-pcpi-backlight.rules" >/dev/null
sudo usermod -aG video "$ME"

step "Servicio pcpi-home"
sudo mkdir -p "$R/etc/systemd/system"
sed "s/__USER__/$ME/" "$SRC/systemd/pcpi-home.service" | sudo tee "$R/etc/systemd/system/pcpi-home.service" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable pcpi-home.service

step "Autostart del vigilante de modo"
mkdir -p "$HOME_DIR/.local/share/applications"
"$PREFIX/bin/pcpi-autostart" install "$HOME_DIR"
cp "$SRC/desktop/pcpi-mode-menu.desktop" "$HOME_DIR/.local/share/applications/"

if [ "$BATTERY" = 1 ]; then
  step "Limite USB para power bank"
  CFG="$R/boot/firmware/config.txt"
  [ -f "$CFG" ] || { echo "No existe $CFG: ¿es Raspberry Pi OS? Salto este paso." >&2; CFG=""; }
  if [ -n "$CFG" ]; then
    grep -q '^usb_max_current_enable=1' "$CFG" || echo 'usb_max_current_enable=1' | sudo tee -a "$CFG" >/dev/null
  fi
fi

if [ "$SPOTIFY" = 1 ]; then
  step "Raspotify (script oficial de dtcooper/raspotify)"
  curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
  sudo mkdir -p "$R/etc/systemd/system/raspotify.service.d"
  printf '[Service]\nReadWritePaths=-/run/pcpi\n' | sudo tee "$R/etc/systemd/system/raspotify.service.d/pcpi.conf" >/dev/null
  CONF="$R/etc/raspotify/conf"
  if [ -f "$CONF" ]; then
    sudo sed -i '/^#\?LIBRESPOT_ONEVENT=/d;/^#\?LIBRESPOT_NAME=/d' "$CONF"
    printf 'LIBRESPOT_NAME="PCPi"\nLIBRESPOT_ONEVENT="/usr/local/bin/pcpi-spotify-event"\n' | sudo tee -a "$CONF" >/dev/null
    sudo systemctl daemon-reload && sudo systemctl restart raspotify
  else
    echo "Aviso: no existe $CONF (¿fallo la instalacion de Raspotify?). Repite ./install.sh --spotify cuando funcione." >&2
  fi
fi

if [ "$CAMERA" = 1 ]; then
  step "Camara (ffmpeg)"
  sudo apt-get install -y ffmpeg
  sudo usermod -aG video "$ME"
fi

if [ "$VOICE" = 1 ]; then
  step "Asistente de voz (Vosk, modelo español pequeño ~40 MB)"
  sudo apt-get install -y alsa-utils espeak-ng python3-venv unzip
  sudo usermod -aG audio "$ME"
  sudo python3 -m venv "$PREFIX/venv"
  # openwakeword 0.4.0 lleva sus modelos ONNX dentro del paquete (no necesita tflite ni descargas)
  sudo "$PIP" install --quiet vosk "openwakeword==0.4.0"
  MODEL=vosk-model-small-es-0.42
  if [ ! -d "$PREFIX/models/$MODEL" ]; then
    sudo mkdir -p "$PREFIX/models"
    curl -fL "https://alphacephei.com/vosk/models/$MODEL.zip" -o "/tmp/$MODEL.zip"
    sudo unzip -q "/tmp/$MODEL.zip" -d "$PREFIX/models" && rm -f "/tmp/$MODEL.zip"
  fi
  # modelos de activacion propios del repo (hay uno experimental)
  sudo mkdir -p "$PREFIX/models/wake"
  ls "$SRC"/models/wake/*.onnx >/dev/null 2>&1 && sudo cp -f "$SRC"/models/wake/*.onnx "$PREFIX/models/wake/"
  # servicio de usuario: necesita tu sesion de audio (PipeWire)
  mkdir -p "$HOME_DIR/.config/systemd/user"
  cp "$SRC/systemd/pcpi-voice.service" "$HOME_DIR/.config/systemd/user/"
  sudo loginctl enable-linger "$ME"
  user_ctl daemon-reload || true
  user_ctl enable pcpi-voice.service || true
  user_ctl restart pcpi-voice.service || echo "Aviso: tras reiniciar, el servicio de voz arrancara solo (o: systemctl --user restart pcpi-voice)"
fi

if [ "$STATS" = 1 ]; then
  step "Mini pantalla OLED (I2C)"
  sudo apt-get install -y python3-pil python3-smbus i2c-tools
  sudo raspi-config nonint do_i2c 0                # activa el bus I2C
  sudo usermod -aG i2c "$ME"
  sudo mkdir -p "$R/etc/systemd/system"
  sed "s/__USER__/$ME/" "$SRC/systemd/pcpi-stats.service" | sudo tee "$R/etc/systemd/system/pcpi-stats.service" >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable pcpi-stats.service
  echo "La mini pantalla se activa tras REINICIAR (el bus I2C y el grupo i2c necesitan un reinicio)."
fi

if [ "$PIHOLE" = 1 ]; then
  step "Pi-hole (instalador oficial, interactivo)"
  curl -sSL https://install.pi-hole.net | sudo bash
  echo "Ahora pon la contraseña:  sudo pihole setpassword   y copiala en /etc/pcpi/pcpi.conf (seccion [pihole])."
fi

# Recuerda de donde se instalo y con que opciones: lo usa `pcpi-update` para reinstalar igual
PREV_FILE="$R/etc/pcpi/install"
OPTS_PREV="$(sed -n 's/^options=//p' "$PREV_FILE" 2>/dev/null || true)"
{
  echo "src=$SRC"
  OPTS=""
  [ "$CAMERA" = 1 ] && OPTS="$OPTS --camera"; [ "$VOICE" = 1 ] && OPTS="$OPTS --voice"
  [ "$SPOTIFY" = 1 ] && OPTS="$OPTS --spotify"; [ "$STATS" = 1 ] && OPTS="$OPTS --stats"
  [ "$BATTERY" = 1 ] && OPTS="$OPTS --battery"
  # lo ya instalado antes no se olvida aunque esta vez no lo pidas (p. ej. ./install.sh a secas para copiar tus extra-assets)
  for o in $OPTS_PREV; do
    case "$o" in --camera|--voice|--spotify|--stats|--battery) case " $OPTS " in *" $o "*) ;; *) OPTS="$OPTS $o" ;; esac ;; esac
  done
  # --pihole NO se recuerda: es el instalador interactivo de Pi-hole y no hay que repetirlo al actualizar
  echo "options=${OPTS# }"
} > "$R/etc/pcpi/install"

# el servidor se reinicia al final: los grupos nuevos (video, audio...) solo se leen al arrancar el servicio
sudo systemctl restart pcpi-home.service

printf '\n\033[1mInstalacion terminada.\033[0m  Siguiente:\n'
echo "  1) Reinicia:            sudo reboot"
echo "  2) Comprueba todo:      pcpi-doctor"
echo "  3) Configura:           pcpi-setup      (ciudad, Pi-hole, microfono, mini pantalla)"
echo "  4) Cambia de modo:      pcpi-mode home | iker | desktop"
