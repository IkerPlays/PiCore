#!/usr/bin/env python3
"""Evalua un modelo de activacion ya entrenado con el detector REAL (openwakeword.Model en streaming).

  * recall:  "oye pi" de voces que NO se usaron al entrenar (y, como referencia, de voces de entrenamiento),
             dentro de ruido / voz ajena, con la palabra al final de la ventana
  * falsos positivos: frases parecidas ("oye pepe", "pipa"...) y, sobre todo, HORAS de voz humana real
             que el modelo no vio al entrenar (activaciones por hora, con antirrebote de 2 s)

Uso: python evaluate.py --model oye_pi.onnx --voices DIR --fleurs dev.tar.gz test.tar.gz train.tar.gz --out report.json
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_wake as tw  # noqa: E402

THRS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def clip_max(args):
    path, clips = args
    return [float(tw.score_stream(path, c.astype(np.float32) / 32768).max()) for c in clips]


def stream_chunk(args):
    path, audio = args
    return tw.score_stream(path, audio)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--fleurs", required=True, nargs="+")
    ap.add_argument("--holdout-voices", default="davefx,mls_9972")
    ap.add_argument("--out", default="report.json")
    ap.add_argument("--hours", type=float, default=0, help="limita las horas de voz real (0 = todas)")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    t0 = time.time()
    log = lambda *m: print("[%4.0fs]" % (time.time() - t0), *m, flush=True)

    voices = tw.load_voices(a.voices)
    hold = tuple(a.holdout_voices.split(","))
    va_v = [v for v in voices if any(h in v[0] for h in hold)]
    tr_v = [v for v in voices if not any(h in v[0] for h in hold)]
    train_sp, val_sp = tw.load_fleurs(a.fleurs)
    log("voz real sin ver: %d locuciones (%.1f h)" % (len(val_sp), sum(len(x) for x in val_sp) / tw.SR / 3600))

    pool = mp.Pool(4)

    def run_clips(clips):
        parts = [clips[i::4] for i in range(4)]
        res = pool.map(clip_max, [(a.model, p) for p in parts])
        out = np.zeros(len(clips))
        for i, r in enumerate(res):
            out[i::4] = r
        return out

    log("positivos de voces NO vistas...")
    pos_unseen = run_clips(tw.build_positive_audio(va_v, rng, 3, val_sp))
    log("positivos de voces de entrenamiento (referencia)...")
    pos_seen = run_clips(tw.build_positive_audio(tr_v[:3], rng, 1, val_sp))
    log("frases parecidas y ordenes (voces NO vistas)...")
    neg_clips = []
    for name, v, sid in va_v:
        for text in tw.HARD_NEG + tw.COMMANDS:
            w = tw.synth(v, sid, text, 1.0, 0.8)
            if len(w) > tw.SR * 0.15:
                neg_clips.append(tw.make_clip(w, val_sp, rng, positive=True))
    neg_phr = run_clips(neg_clips)

    log("voz real sin ver, en streaming...")
    utts = val_sp
    if a.hours:
        keep, tot = [], 0
        for x in utts:
            keep.append(x)
            tot += len(x)
            if tot / tw.SR / 3600 >= a.hours:
                break
        utts = keep
    stream = np.concatenate([np.r_[x, np.zeros(tw.SR // 2)] for x in utts])
    hours = len(stream) / tw.SR / 3600
    n = 4
    cut = [int(len(stream) * i / n) // 1280 * 1280 for i in range(n + 1)]
    scores = np.concatenate(pool.map(stream_chunk, [(a.model, stream[cut[i]:cut[i + 1]]) for i in range(n)]))
    log("%.2f h evaluadas" % hours)

    rep = {"model": os.path.basename(a.model), "val_voices": [v[0] for v in va_v],
           "n": {"pos_unseen": len(pos_unseen), "pos_seen": len(pos_seen), "similar_phrases": len(neg_phr)},
           "hours_real_speech_unseen": round(hours, 2), "by_threshold": {}}
    for t in THRS:
        rep["by_threshold"][str(t)] = {
            "recall_unseen_voices": round(float((pos_unseen >= t).mean()), 3),
            "recall_training_voices": round(float((pos_seen >= t).mean()), 3),
            "false_accept_similar_phrases": round(float((neg_phr >= t).mean()), 3),
            "false_activations_per_hour_real_speech": round(tw.count_fires(scores, t) / hours, 2),
        }
    json.dump(rep, open(a.out, "w"), indent=2)
    log(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
