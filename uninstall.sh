#!/usr/bin/env bash
# Desinstala PiCore (servicios, archivos y autostart). No toca Pi-hole ni tus paquetes.
# (Para pruebas: PCPI_ROOT=/otra/raiz y PCPI_HOME=/otra/carpeta actuan sobre un arbol alternativo.)
set -uo pipefail
[ "$(id -u)" -ne 0 ] || { echo "Ejecuta como usuario normal, no como root." >&2; exit 1; }
HOME_DIR="${PCPI_HOME:-$(getent passwd "$(id -un)" | cut -d: -f6)}"
R="${PCPI_ROOT:-}"
[ "$R" != "/" ] || { echo "PCPI_ROOT no puede ser /" >&2; exit 1; }
[ -n "$HOME_DIR" ] && [ "$HOME_DIR" != "/" ] || { echo "No se pudo determinar tu carpeta personal." >&2; exit 1; }

echo "==> Devolviendo el DNS de tus wifis al de la red"
# Si no se hiciera, las redes guardadas seguirian usando 127.0.0.1 (el Pi-hole) y, sin Pi-hole, no habria internet.
[ -x "$R/opt/pcpi/bin/pcpi-wifi" ] && "$R/opt/pcpi/bin/pcpi-wifi" reset-dns 2>/dev/null || true

echo "==> Parando servicios"
XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" \
  systemctl --user disable --now pcpi-voice.service 2>/dev/null
pkill -f pcpi-session 2>/dev/null
pkill -f -- "--user-data-dir=$HOME_DIR/.cache/pcpi-kiosk" 2>/dev/null
pkill -f -- "--user-data-dir=$HOME_DIR/.cache/pcpi-portal" 2>/dev/null
sudo systemctl disable --now pcpi-home.service pcpi-stats.service 2>/dev/null
sudo rm -f "$R/etc/systemd/system/pcpi-home.service" "$R/etc/systemd/system/pcpi-stats.service" \
           "$R/etc/tmpfiles.d/pcpi.conf" \
           "$R/etc/udev/rules.d/90-pcpi-backlight.rules"
sudo systemctl daemon-reload

echo "==> Borrando archivos"
[ -x "$R/opt/pcpi/bin/pcpi-autostart" ] && "$R/opt/pcpi/bin/pcpi-autostart" remove "$HOME_DIR"
sudo rm -rf "$R/opt/pcpi" "$R/run/pcpi"
sudo rm -f "$R"/usr/local/bin/pcpi-*
rm -f "$HOME_DIR/.config/systemd/user/pcpi-voice.service" "$HOME_DIR/.local/share/applications/pcpi-mode-menu.desktop"
rm -rf "$HOME_DIR"/.cache/pcpi-kiosk* "$HOME_DIR"/.cache/pcpi-portal

echo "Tus copias de seguridad de ~/pcpi-backups no se tocan."
read -r -p "¿Borrar tambien la configuracion /etc/pcpi y tus NOTAS (/var/lib/pcpi)? [s/N] " r
if [ "${r:-}" = "s" ]; then
  sudo rm -rf "$R/etc/pcpi" "$R/var/lib/pcpi"
fi
echo "Hecho. (En /boot/firmware/config.txt puede quedar usb_max_current_enable=1.)"
