# Capa de TOMAS DE APOYO del público sobre la voz (referencia T01 "…seré la próxima presidenta…"): en un discurso filmado con una
# sola cámara, cada salto entre dos tramos de su discurso se ve; el equipo lo tapa con planos de la gente mientras la voz sigue.
# Las tomas salen de los videos del MISMO acto que se pasan con `--broll` (cfg["broll"]): se eligen nítidas, quietas, con
# público (varias caras) y SIN la cara de Lilian (su boca no coincidiría con lo que se oye). Cubren el corte: empiezan 0.4 s
# antes del salto y duran 1.8–2.6 s. Nunca en el gancho, ni sobre una tarjeta de cifras, ni en los últimos 4 s.
import os, json
import numpy as np
from styles.base import *
import evento as EV

LENS = (2.6, 2.2, 1.8)


class Broll:
    def __init__(self, style, avoid=()):
        self.S, self.c = style, style.c
        self.items, self.readers = [], {}
        paths = self.c.cfg.get("broll") or []
        if not paths: return
        bd = os.path.join(self.c.dir, "broll"); os.makedirs(bd, exist_ok=True)
        clips = EV.prepare(paths, bd)
        A = {cl["k"]: EV.analyze(cl, bd) for cl in clips}
        self.clips = {cl["k"]: cl for cl in clips}
        # ventanas candidatas: público nítido y quieto, sin Lilian en cuadro
        cands = []
        for cl in clips:
            a = A[cl["k"]]; sh = np.array(a["sharp"]); mot = np.array(a["mot"]); bri = np.array(a["bri"])
            nf = np.array(a["nf"]); lil = np.array(a["lil"]); fsz = np.array(a["fsz"]); n = len(sh)
            if n < EV.AF * 2: continue
            cut = EV.off_record(a)
            if cut is not None: n = min(n, int(cut * EV.AF))
            shz = (sh - np.median(sh)) / (np.std(sh) + 1e-6)
            for L in LENS:
                for t0 in np.arange(0.3, n / EV.AF - L - 0.2, 0.3):
                    i0, i1 = int(t0 * EV.AF), int((t0 + L) * EV.AF)
                    m_ = mot[i0 + 1:i1]
                    if len(m_) == 0 or m_.max() > 18 or bri[i0:i1].mean() < 45: continue
                    if np.mean(lil[i0:i1] >= 0.38) > 0.15: continue              # ella en cuadro: no (labios)
                    sc = (float(np.mean(shz[i0:i1])) - 0.06 * float(np.mean(m_)) + 1.2 * float(np.mean(nf[i0:i1] >= 2))
                          + 0.5 * float(np.mean(nf[i0:i1] >= 1)) - 2.0 * max(0.0, float(np.median(fsz[i0:i1])) - 0.22))
                    cands.append(dict(k=cl["k"], a=float(t0), L=L, score=sc))
        # cortes a tapar: saltos entre tramos de su discurso (no contiguos en la fuente)
        segs = [it for it in self.c.EDL["items"] if it["kind"] == "speech"] if hasattr(self.c, "EDL") else []
        if not segs: segs = [it for it in getattr(self.c, "SEGS", [])]
        hook_end = getattr(style, "hook_end_t", getattr(style, "bw_end", self.c.hook_end))
        end_t = self.c.END0 / FPS
        cuts = []
        for p, q in zip(segs, segs[1:]):
            if abs(q["fs"] - p["fe"]) <= 2: continue                          # tramo seguido: no hay salto
            t = q["out"] / FPS
            if t < hook_end + 1.0 or t > end_t - 4.0: continue
            if any(a_ - 0.6 <= t <= b_ + 0.6 for a_, b_ in avoid): continue
            cuts.append(t)
        per_min = float(self.c.cfg.get("broll_por_min", 3.0))
        max_n = max(1, int(per_min * end_t / 60))
        used = []
        for t in cuts:
            if len(self.items) >= max_n: break
            if self.items and t - self.items[-1]["t1"] < 4.0: continue
            nxt = next((u for u in cuts if u > t + 0.5), end_t - 0.5)
            best = None
            for cd in sorted(cands, key=lambda x: -x["score"]):
                if any(cd["k"] == k and abs(cd["a"] - a) < cd["L"] + 1.0 for k, a in used): continue
                t0 = t - 0.4; t1 = t0 + cd["L"]
                if t1 > nxt - 0.3 or t1 > end_t - 0.5: continue
                best = cd; break
            if best is None: continue
            used.append((best["k"], best["a"]))
            self.items.append(dict(k=best["k"], a=best["a"], t0=t - 0.4, t1=t - 0.4 + best["L"], score=round(best["score"], 2)))
        print("[tomas de apoyo]", [(round(x["t0"], 1), round(x["t1"] - x["t0"], 1), self.clips[x["k"]]["file"][:22]) for x in self.items] or "ninguna")
        declarar_tramos(self.c.dir, "broll", [(x["t0"], x["t1"]) for x in self.items])          # el QA sabe que ahí no está su cara

    def active(self, t):
        return next((x for x in self.items if x["t0"] <= t < x["t1"]), None)

    def frame(self, t):
        x = self.active(t)
        if x is None: return None
        key = id(x)
        if key not in self.readers:
            for k_, r in list(self.readers.items()): r.close()
            self.readers = {key: Reader(self.clips[x["k"]]["video"], int(round(x["a"] * FPS)))}
        src = (T(self.readers[key].get()).permute(2, 0, 1).float() / 255)[None]
        u = (t - x["t0"]) / max(1e-3, x["t1"] - x["t0"]); z = 1.04 + 0.04 * u            # empuje lento
        cw, ch = W / z, H / z; x0, y0 = (W - cw) / 2, (H - ch) / 2
        th = torch.tensor([[cw / W, 0, 2 * (x0 + cw / 2) / W - 1], [0, ch / H, 2 * (y0 + ch / 2) / H - 1]], dtype=torch.float32, device=dev).view(1, 2, 3)
        return grade_color(warp_src(src, th, ext_bg=None, fade_top=False), contrast=1.03, sat=1.02)
