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
    g = lambda k, d: cp.get("mini", k, fallback=d)
    return {"address": int(g("address", "0x3C"), 0), "bus": int(g("i2c_bus", "1")),
            "rotate": g("rotate", "false").lower() in ("1", "true", "yes", "si"),
            "interval": float(g("interval", "1")),
            "contrast": int(g("contrast", "120")),
            "off_from": int(g("off_from", "-1")), "off_to": int(g("off_to", "-1"))}


def screen_should_be_off(hour, off_from, off_to):
    """Los OLED se desgastan: se apagan en las horas indicadas (p. ej. off_from=1, off_to=7). -1 = nunca."""
    if off_from < 0 or off_to < 0 or off_from == off_to:
        return False
    return off_from <= hour < off_to if off_from < off_to else (hour >= off_from or hour < off_to)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["oled", "png"], default="oled")
    ap.add_argument("--out", default="preview.png")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    cfg = load_conf()
    st = sysstats.Stats()

    dev = None
    if a.backend == "oled":
        import smbus  # python3-smbus (apt)
        import ssd1306
        dev = ssd1306.SSD1306(smbus.SMBus(cfg["bus"]), cfg["address"], cfg["rotate"])
        dev.start()
        dev.contrast(cfg["contrast"])
        signal.signal(signal.SIGTERM, lambda *_: (dev.on(False), sys.exit(0)))

    st.snapshot()          # la primera lectura solo sirve de referencia para los porcentajes
    time.sleep(0.5 if a.once else cfg["interval"])
    is_off = False
    try:
        while True:
            snap = st.snapshot()
            off = screen_should_be_off(datetime.datetime.now().hour, cfg["off_from"], cfg["off_to"])
            if dev is not None and off != is_off:
                dev.on(not off)
                is_off = off
            if not off:
                img = render.render(snap)
                if dev is not None:
                    dev.show(img)
                else:
                    render.preview(img, 4, a.out)
            if a.once:
                break
            time.sleep(cfg["interval"])
    except KeyboardInterrupt:
        pass
    finally:
        if dev is not None:
            dev.on(False)


if __name__ == "__main__":
    main()
