#!/usr/bin/env bash
# Desinstala PCPi (servicios, archivos y autostart). No toca Pi-hole, Raspotify ni tus paquetes.
set -uo pipefail
[ "$(id -u)" -ne 0 ] || { echo "Ejecuta como usuario normal, no como root." >&2; exit 1; }
HOME_DIR="$(getent passwd "$(id -un)" | cut -d: -f6)"

echo "==> Parando servicios"
XDG_RUNTIME_DIR="/run/user/$(id -u)" systemctl --user disable --now pcpi-voice.service 2>/dev/null
pkill -f pcpi-session 2>/dev/null; pkill -f -- "--user-data-dir=$HOME_DIR/.cache/pcpi-kiosk" 2>/dev/null
sudo systemctl disable --now pcpi-home.service pcpi-stats.service 2>/dev/null
sudo rm -f /etc/systemd/system/pcpi-home.service /etc/systemd/system/pcpi-stats.service /etc/systemd/system/raspotify.service.d/pcpi.conf /etc/tmpfiles.d/pcpi.conf
sudo systemctl daemon-reload

echo "==> Borrando archivos"
[ -x /opt/pcpi/bin/pcpi-autostart ] && /opt/pcpi/bin/pcpi-autostart remove "$HOME_DIR"
sudo rm -rf /opt/pcpi /usr/local/bin/pcpi-* /run/pcpi
rm -f "$HOME_DIR/.config/systemd/user/pcpi-voice.service" "$HOME_DIR/.local/share/applications/pcpi-mode-menu.desktop"
rm -rf "$HOME_DIR"/.cache/pcpi-kiosk*

read -r -p "¿Borrar tambien la configuracion /etc/pcpi y tus NOTAS (/var/lib/pcpi)? [s/N] " r
[ "$r" = "s" ] && sudo rm -rf /etc/pcpi /var/lib/pcpi
echo "Hecho. (En /boot/firmware/config.txt puede quedar usb_max_current_enable=1.)"
