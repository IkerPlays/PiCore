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
ME="$(id -un)"; HOME_DIR="$(getent passwd "$ME" | cut -d: -f6)"
PREFIX=/opt/pcpi
UID_ME="$(id -u)"
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
sudo rsync -a --delete "$SRC/home" "$SRC/bin" "$SRC/voice" "$SRC/stats" "$PREFIX/"
for f in "$PREFIX"/bin/*; do sudo ln -sf "$f" "/usr/local/bin/$(basename "$f")"; done
sudo chmod +x "$PREFIX"/bin/*

step "Configuracion en /etc/pcpi"
sudo mkdir -p /etc/pcpi /var/lib/pcpi
sudo chown "$ME": /etc/pcpi /var/lib/pcpi
sudo chmod 700 /var/lib/pcpi                      # aqui van tus notas: privadas
[ -f /etc/pcpi/pcpi.conf ] || install -m 640 "$SRC/config/pcpi.conf.example" /etc/pcpi/pcpi.conf
[ -f /etc/pcpi/mode ] || echo desktop > /etc/pcpi/mode
# Estado que cambia a cada rato (voz, "sonando ahora") en RAM (/run), no en la microSD
echo 'd /run/pcpi 1777 root root -' | sudo tee /etc/tmpfiles.d/pcpi.conf >/dev/null
sudo systemd-tmpfiles --create /etc/tmpfiles.d/pcpi.conf

step "Servicio pcpi-home"
sed "s/__USER__/$ME/" "$SRC/systemd/pcpi-home.service" | sudo tee /etc/systemd/system/pcpi-home.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable pcpi-home.service

step "Autostart del vigilante de modo"
mkdir -p "$HOME_DIR/.local/share/applications"
"$PREFIX/bin/pcpi-autostart" install "$HOME_DIR"
cp "$SRC/desktop/pcpi-mode-menu.desktop" "$HOME_DIR/.local/share/applications/"

if [ "$BATTERY" = 1 ]; then
  step "Limite USB para power bank"
  CFG=/boot/firmware/config.txt
  grep -q '^usb_max_current_enable=1' "$CFG" || echo 'usb_max_current_enable=1' | sudo tee -a "$CFG" >/dev/null
fi

if [ "$SPOTIFY" = 1 ]; then
  step "Raspotify (script oficial de dtcooper/raspotify)"
  curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
  sudo mkdir -p /etc/systemd/system/raspotify.service.d
  printf '[Service]\nReadWritePaths=-/run/pcpi\n' | sudo tee /etc/systemd/system/raspotify.service.d/pcpi.conf >/dev/null
  CONF=/etc/raspotify/conf
  sudo sed -i '/^#\?LIBRESPOT_ONEVENT=/d;/^#\?LIBRESPOT_NAME=/d' "$CONF"
  printf 'LIBRESPOT_NAME="PCPi"\nLIBRESPOT_ONEVENT="/usr/local/bin/pcpi-spotify-event"\n' | sudo tee -a "$CONF" >/dev/null
  sudo systemctl daemon-reload && sudo systemctl restart raspotify
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
  sudo "$PREFIX/venv/bin/pip" install --quiet vosk "openwakeword==0.4.0"
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
  sed "s/__USER__/$ME/" "$SRC/systemd/pcpi-stats.service" | sudo tee /etc/systemd/system/pcpi-stats.service >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable pcpi-stats.service
  echo "La mini pantalla se activa tras REINICIAR (el bus I2C y el grupo i2c necesitan un reinicio)."
fi

if [ "$PIHOLE" = 1 ]; then
  step "Pi-hole (instalador oficial, interactivo)"
  curl -sSL https://install.pi-hole.net | sudo bash
  echo "Ahora pon la contraseña:  sudo pihole setpassword   y copiala en /etc/pcpi/pcpi.conf (seccion [pihole])."
fi

# el servidor se reinicia al final: los grupos nuevos (video, audio...) solo se leen al arrancar el servicio
sudo systemctl restart pcpi-home.service

printf '\n\033[1mInstalacion terminada.\033[0m  Siguiente:\n'
echo "  1) Reinicia:            sudo reboot"
echo "  2) Comprueba todo:      pcpi-doctor"
echo "  3) Cambia de modo:      pcpi-mode home | iker | desktop"
