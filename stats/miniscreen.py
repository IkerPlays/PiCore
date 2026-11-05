#!/usr/bin/env python3
"""Mini pantalla de estado: CPU, RAM, disco, temperatura, GPU, ventilador, red, IP. No tactil.

  miniscreen.py                       # pantalla OLED SSD1306 por I2C (modo servicio)
  miniscreen.py --backend png --once  # genera preview.png para ver el diseño sin hardware
Ajustes en /etc/pcpi/pcpi.conf, seccion [mini].
"""
import argparse
import configparser
import datetime
import os
import re
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render  # noqa: E402
import sysstats  # noqa: E402


def load_conf():
    cp = configparser.ConfigParser()
    cp.read(os.environ.get("PCPI_CONF", "/etc/pcpi/pcpi.conf"))
    # tolerante: si alguien escribe "valor   # comentario", se ignora el comentario
    g = lambda k, d: re.split(r"\s+#", cp.get("mini", k, fallback=d), maxsplit=1)[0].strip()
    return {"address": int(g("address", "0x3C"), 0), "bus": int(g("i2c_bus", "1")),
            "rotate": g("rotate", "false").lower() in ("1", "true", "yes", "si"),
            "interval": float(g("interval", "1")),
            "contrast": int(g("contrast", "120")), "chip": g("chip", "ssd1306").strip().lower(),
            "off_from": int(g("off_from", "-1")), "off_to": int(g("off_to", "-1"))}


def screen_should_be_off(hour, off_from, off_to):
    """Los OLED se desgastan: se apagan en las horas indicadas (p. ej. off_from=1, off_to=7). -1 = nunca."""
    if off_from < 0 or off_to < 0 or off_from == off_to:
        return False
    return off_from <= hour < off_to if off_from < off_to else (hour >= off_from or hour < off_to)


def open_oled(cfg):
    import smbus  # python3-smbus (apt)
    import ssd1306
    dev = ssd1306.SSD1306(smbus.SMBus(cfg["bus"]), cfg["address"], cfg["rotate"], cfg["chip"])
    dev.start()
    dev.contrast(cfg["contrast"])
    return dev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["oled", "png"], default="oled")
    ap.add_argument("--out", default="preview.png")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    cfg = load_conf()
    st = sysstats.Stats()
    dev = None
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))

    st.snapshot()          # la primera lectura solo sirve de referencia para los porcentajes
    time.sleep(0.5 if a.once else cfg["interval"])
    is_off, warned = False, False
    try:
        while not stop:
            if a.backend == "oled" and dev is None:
                try:
                    dev, warned, is_off = open_oled(cfg), False, False
                except ImportError as e:
                    print("Falta python3-smbus (%s). Ejecuta: ./install.sh --stats" % e, file=sys.stderr, flush=True)
                    sys.exit(3)          # el servicio no reintenta con este codigo (reintentar no ayudaria)
                except OSError as e:     # pantalla desconectada o I2C sin activar: reintenta sin caerse
                    if not warned:
                        print("No encuentro la pantalla (%r). Reintento cada 10 s. Revisa los cables y el I2C." % e, flush=True)
                        warned = True
                    time.sleep(10)
                    continue
            snap = st.snapshot()
            off = screen_should_be_off(datetime.datetime.now().hour, cfg["off_from"], cfg["off_to"])
            try:
                if dev is not None and off != is_off:
                    dev.on(not off)
                    is_off = off
                if not off:
                    img = render.render(snap)
                    if dev is not None:
                        dev.show(img)
                    else:
                        render.preview(img, 4, a.out)
            except OSError as e:         # cable suelto a mitad: reconecta en la proxima vuelta
                print("Error I2C (%r): reconecto." % e, flush=True)
                dev = None
                time.sleep(2)
                continue
            if a.once:
                break
            time.sleep(cfg["interval"])
    except KeyboardInterrupt:
        pass
    finally:
        if dev is not None:
            try:
                dev.on(False)
            except OSError:
                pass


if __name__ == "__main__":
    main()
