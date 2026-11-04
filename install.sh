#!/usr/bin/env bash
# Instalador PCPi para Raspberry Pi OS (Bookworm/Trixie). Ejecutalo como usuario normal (usa sudo).
#   ./install.sh [--battery] [--pihole] [--spotify] [--all]
#     --battery  sube el limite de corriente USB (power bank sin 5V/5A)
#     --pihole   lanza el instalador oficial de Pi-hole (interactivo)
#     --spotify  instala Raspotify (Spotify Connect, requiere Premium) y el hook de "sonando ahora"
set -euo pipefail

BATTERY=0; PIHOLE=0; SPOTIFY=0
for a in "$@"; do
  case "$a" in
    --battery) BATTERY=1 ;; --pihole) PIHOLE=1 ;; --spotify) SPOTIFY=1 ;;
    --all) BATTERY=1; PIHOLE=1; SPOTIFY=1 ;;
    *) echo "Opcion desconocida: $a" >&2; exit 1 ;;
  esac
done

[ "$(id -u)" -ne 0 ] || { echo "Ejecuta como usuario normal, no como root." >&2; exit 1; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ME="$(id -un)"; HOME_DIR="$(getent passwd "$ME" | cut -d: -f6)"
PREFIX=/opt/pcpi

echo "==> Paquetes"
sudo apt-get update
CHROMIUM_PKG=chromium; apt-cache show chromium >/dev/null 2>&1 || CHROMIUM_PKG=chromium-browser
sudo apt-get install -y python3 curl zenity "$CHROMIUM_PKG"

echo "==> Archivos en $PREFIX"
sudo mkdir -p "$PREFIX"
sudo rsync -a --delete "$SRC/home" "$SRC/bin" "$PREFIX/"
for f in "$PREFIX"/bin/*; do sudo ln -sf "$f" "/usr/local/bin/$(basename "$f")"; done
sudo chmod +x "$PREFIX"/bin/*

echo "==> Configuracion en /etc/pcpi"
sudo mkdir -p /etc/pcpi /var/lib/pcpi
sudo chown "$ME": /etc/pcpi
sudo chmod 1777 /var/lib/pcpi
[ -f /etc/pcpi/pcpi.conf ] || install -m 640 "$SRC/config/pcpi.conf.example" /etc/pcpi/pcpi.conf
[ -f /etc/pcpi/mode ] || echo desktop > /etc/pcpi/mode

echo "==> Servicio pcpi-home"
sed "s/__USER__/$ME/" "$SRC/systemd/pcpi-home.service" | sudo tee /etc/systemd/system/pcpi-home.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now pcpi-home.service

echo "==> Autostart del vigilante de modo"
mkdir -p "$HOME_DIR/.config/autostart" "$HOME_DIR/.config/labwc" "$HOME_DIR/.local/share/applications"
cat > "$HOME_DIR/.config/autostart/pcpi-session.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PCPi session
Exec=pcpi-session
EOF
grep -qx 'pcpi-session &' "$HOME_DIR/.config/labwc/autostart" 2>/dev/null \
  || echo 'pcpi-session &' >> "$HOME_DIR/.config/labwc/autostart"
cp "$SRC/desktop/pcpi-mode-menu.desktop" "$HOME_DIR/.local/share/applications/"

if [ "$BATTERY" = 1 ]; then
  echo "==> Limite USB para power bank"
  CFG=/boot/firmware/config.txt
  grep -q '^usb_max_current_enable=1' "$CFG" || echo 'usb_max_current_enable=1' | sudo tee -a "$CFG" >/dev/null
fi

if [ "$SPOTIFY" = 1 ]; then
  echo "==> Raspotify (script oficial de dtcooper/raspotify)"
  curl -sL https://dtcooper.github.io/raspotify/install.sh | sh
  sudo mkdir -p /etc/systemd/system/raspotify.service.d
  printf '[Service]\nReadWritePaths=/var/lib/pcpi\n' | sudo tee /etc/systemd/system/raspotify.service.d/pcpi.conf >/dev/null
  CONF=/etc/raspotify/conf
  sudo sed -i '/^#\?LIBRESPOT_ONEVENT=/d;/^#\?LIBRESPOT_NAME=/d' "$CONF"
  printf 'LIBRESPOT_NAME="PCPi"\nLIBRESPOT_ONEVENT="/usr/local/bin/pcpi-spotify-event"\n' | sudo tee -a "$CONF" >/dev/null
  sudo systemctl daemon-reload && sudo systemctl restart raspotify
fi

if [ "$PIHOLE" = 1 ]; then
  echo "==> Pi-hole (instalador oficial, interactivo)"
  curl -sSL https://install.pi-hole.net | sudo bash
  echo "Pon la password de Pi-hole en /etc/pcpi/pcpi.conf (seccion [pihole])."
fi

cat <<EOF

Listo. Cierra sesion y vuelve a entrar (o reinicia) para activar el vigilante.
  pcpi-mode home      -> modo Casa
  pcpi-mode gaming    -> modo Gaming (Proximamente)
  pcpi-mode desktop   -> escritorio normal
EOF
