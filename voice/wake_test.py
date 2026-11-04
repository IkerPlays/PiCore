#!/usr/bin/env python3
"""Prueba en vivo de la palabra de activacion: muestra la puntuacion del micro en tiempo real.

  /opt/pcpi/venv/bin/python /opt/pcpi/voice/wake_test.py            # usa [voice] de /etc/pcpi/pcpi.conf
  /opt/pcpi/venv/bin/python /opt/pcpi/voice/wake_test.py oye_pi 0.5 # modelo y umbral a mano

Di «oye pi» varias veces, y habla/pon la tele de fondo: sube el umbral si se activa con otras cosas,
bajalo si no te detecta. (Para el servicio antes: systemctl --user stop pcpi-voice)
"""
import subprocess
import sys

import assistant
import wake


def main():
    cfg = assistant.load_conf()
    model = sys.argv[1] if len(sys.argv) > 1 else cfg["wake_model"]
    thr = float(sys.argv[2]) if len(sys.argv) > 2 else cfg["threshold"]
    det = wake.OpenWakeWord(model, thr)
    cap = assistant.start_capture(cfg)
    print("Modelo %r, umbral %.2f. Habla; Ctrl+C para salir.\n" % (det.name, thr), flush=True)
    try:
        while True:
            data = cap.stdout.read(2560)
            if not data:
                print("sin audio: ¿microfono conectado? (arecord -l)")
                break
            hit = det.feed(data)
            bar = "█" * int(det.last_score * 40)
            if det.last_score > 0.03 or hit:
                print("%-42s %.2f %s" % (bar, det.last_score, "  🔔 ACTIVADO" if hit else ""), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        cap.kill()


if __name__ == "__main__":
    main()
