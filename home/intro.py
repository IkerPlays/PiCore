"""Eleccion del video de la pantalla de Inicio (al encender).

Hasta 4 videos en extra-assets/start/:  Inicio1.mp4 (o Inicio.mp4), Inicio2.mp4, Inicio3.mp4, Inicio4.mp4.

Reglas (configurables en [boot]):
  * Cada video tiene una «probabilidad de salir» (por defecto 90, 85, 55 y 1). Se usan como PESOS: la eleccion es
    aleatoria y cada video sale en proporcion a su numero. Con 90/85/55/1 los porcentajes reales son aprox.
    38,9 % / 36,8 % / 23,8 % / 0,4 % (las cifras suman mas de 100, asi que no pueden ser porcentajes literales).
  * Garantia: si el video 4 (el raro; se cambia con `intro_pity_slots`) lleva `pity` (4) encendidos SIN salir, en el
    siguiente sale si o si. Si varios cumplen, gana el mas raro (el de menor probabilidad). Se aplica solo al raro por
    defecto porque en los demas distorsionaria sus probabilidades (el 3.º, con ~24 %, fallaria 4 veces seguidas
    una de cada tres veces).
  * Cada ENCENDIDO cuenta una sola vez, aunque la pagina se recargue: la eleccion se guarda junto al identificador de
    arranque del sistema (/proc/sys/kernel/random/boot_id).
  * Si faltan videos, se elige entre los que haya. Si solo hay uno, sale siempre ese.
Solo libreria estandar."""
import json
import os
import random
from pathlib import Path

DEFAULT_CHANCES = (90.0, 85.0, 55.0, 1.0)
DEFAULT_PITY_SLOTS = (4,)
DEFAULT_SKIP = (0.0, 0.0, 0.0, 6.0)        # segundos tras los que aparece el boton «Saltar» (0 = nunca)
SLOTS = 4


def state_file():
    return Path(os.environ.get("PCPI_INTRO_STATE", "/var/lib/pcpi/intro.json"))


def boot_id():
    try:
        return Path(os.environ.get("PCPI_BOOT_ID_FILE", "/proc/sys/kernel/random/boot_id")).read_text().strip() or None
    except OSError:
        return None


def slot_files(base):
    """{slot: nombre_de_archivo} de los videos que existen (slot 1..4)."""
    found = {}
    for slot in range(1, SLOTS + 1):
        names = ["Inicio%d.mp4" % slot] + (["Inicio.mp4"] if slot == 1 else [])
        for n in names:
            if (Path(base) / n).is_file():
                found[slot] = n
                break
    return found


def parse_list(text, default, kind=float, lo=0.0, hi=1000.0):
    """'90, 85, 55, 1' -> (90.0, 85.0, 55.0, 1.0). Valores raros -> el de por defecto en esa posicion."""
    parts = [p.strip() for p in (text or "").split(",")]
    out = []
    for i in range(SLOTS):
        try:
            v = kind(parts[i])
            if not lo <= v <= hi or v != v:
                raise ValueError
        except (IndexError, ValueError):
            v = default[i]
        out.append(v)
    return tuple(out)


def parse_slots(text, default=DEFAULT_PITY_SLOTS):
    """'1, 4' -> (1, 4). Solo 1..4; vacio o roto -> el de por defecto."""
    out = []
    for p in (text or "").split(","):
        try:
            v = int(p.strip())
        except ValueError:
            continue
        if 1 <= v <= SLOTS and v not in out:
            out.append(v)
    return tuple(out) if out else tuple(default)


def pick(slots, chances, misses, pity, rnd=random.random, pity_slots=DEFAULT_PITY_SLOTS):
    """Elige un slot de `slots`. `misses` = {slot: encendidos seguidos sin salir}. Devuelve el slot elegido."""
    slots = sorted(slots)
    if not slots:
        return None
    if pity > 0:
        due = [s for s in slots if s in pity_slots and misses.get(s, 0) >= pity]
        if due:
            return min(due, key=lambda s: (chances[s - 1], s))       # gana el mas raro
    weights = [max(chances[s - 1], 0.0) for s in slots]
    total = sum(weights)
    if total <= 0:
        return slots[0]
    x = rnd() * total
    acc = 0.0
    for s, w in zip(slots, weights):
        acc += w
        if x < acc:
            return s
    return slots[-1]


def _load():
    try:
        d = json.loads(state_file().read_text())
        return {"boot_id": d.get("boot_id"), "chosen": d.get("chosen"),
                "misses": {int(k): int(v) for k, v in (d.get("misses") or {}).items()}}
    except (OSError, ValueError, AttributeError, TypeError):
        return {"boot_id": None, "chosen": None, "misses": {}}


def _save(st):
    f = state_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"boot_id": st["boot_id"], "chosen": st["chosen"],
                                   "misses": {str(k): v for k, v in st["misses"].items()}}))
        os.replace(tmp, f)
    except OSError:
        pass


def choose_for_boot(base, chances=DEFAULT_CHANCES, pity=4, rnd=random.random, bid=None, pity_slots=DEFAULT_PITY_SLOTS):
    """Slot (1..4) del video de ESTE encendido, o None si no hay videos. Idempotente dentro del mismo arranque."""
    files = slot_files(base)
    if not files:
        return None
    bid = bid if bid is not None else boot_id()
    st = _load()
    if bid and st["boot_id"] == bid and st["chosen"] in files:
        return st["chosen"]                                     # ya se eligio en este arranque (recarga de la pagina)
    chosen = pick(list(files), chances, st["misses"], pity, rnd, pity_slots)
    misses = {s: (0 if s == chosen else st["misses"].get(s, 0) + 1) for s in files}
    _save({"boot_id": bid, "chosen": chosen, "misses": misses})
    return chosen
