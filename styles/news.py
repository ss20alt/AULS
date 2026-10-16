# Estilo 1 — NOTICIERO LIMPIO (referencias R3/R4/R5): entrevista a pantalla completa con la cara anclada, zoom suave por toma,
# tarjeta blanca con la pregunta (gancho), placa de nombre, subtítulos blancos de 2-3 palabras con claves doradas, sello de redes y cierre blanco.
from styles.common import *
import plan as P

CAPX = 495                                                   # centro de subtítulos/tarjetas: deja libres los 190 px de iconos de la app a la derecha
ZCYC = [1.10, 1.17, 1.12, 1.19, 1.14, 1.21, 1.11, 1.18]


class Style:
    ext_color = NAVY

    def __init__(self, ctx):
        self.c = ctx

    def setup(self):
        c = self.c
        self.end = Endcard()
        self.vig = make_vignette(0.34)
        self.navyt = tcolor(NAVY)
        self.ext = self.navyt.expand(3, H, W) * (0.75 + 0.55 * (yy_ / 420.0).clamp(0, 1))[None].to(DT)
        self.shade = (0.46 * sm(1000.0, 1500.0, yy_) + 0.26 * sm(1500.0, 1920.0, yy_)).expand(H, W)[None].to(DT)
        import brand as B; self.wmark = spr_t(B.watermark())
        import brand as B; self.name = spr_t(B.name_card()[0])
        hook = [w for w in c.WORDS if w["sc"] == 0]
        qtxt = " ".join(w["t"] for w in hook)
        spr, pad = question_card(qtxt, maxw=780)
        self.qcard, self.qpad = spr_t(spr), pad
        self.chunk_cache = {}
        self.keys_range = [(k["s"], k["e"]) for k in c.CHUNKS if k["key"] and k["e"] - k["s"] >= 0.45]
        self.scene_starts = [int(round(v["o0"] * FPS)) for k, v in c.SC.items() if k >= 1]
        self.end0 = c.END0

    # ---- cámara
    def punch(self, t):
        a = 0.0
        for s, e in self.keys_range:
            if s <= t < e: a = max(a, 0.07)
            elif e <= t < e + 0.15: a = max(a, 0.07 * (1 - ease((t - e) / 0.15)))
        return 1 + a

    def zoom(self, n, it, t):
        c = self.c
        if t < c.hook_end: return 1.16 * (1 + 0.02 * (t / max(1e-3, c.hook_end)))
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        z = ZCYC[it["shot"] % len(ZCYC)] * (1 + 0.012 * tt) * ((1 + 0.04 * (1 - ease(tt / 0.35))) if n - t0 < 12 else 1.0)
        return z * self.punch(t)

    # ---- capas
    def chunk_spr(self, ci):
        if ci not in self.chunk_cache:
            k = self.c.CHUNKS[ci]
            self.chunk_cache[ci] = spr_t(sub_sprite(k["words"], key_color=GOLD if k["key"] else None, flags=k.get("flags")))
        return self.chunk_cache[ci]

    def draw_captions(self, fr, t):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]:
                spr = self.chunk_spr(ci); age = (t - k["s"]) * FPS
                s2 = scaled(spr, (0.92 + 0.08 * ease(age / 4)) * (1.0 + (0.05 * ease(age / 6) if k["key"] else 0)))
                blend(fr, s2, CAPX - s2.shape[2] / 2, 1170 - s2.shape[1] / 2, min(1.0, (age + 1) / 3))
                break

    def draw_question(self, fr, t):
        c = self.c
        a0, a1 = 0.18, c.hook_end - 0.06
        if not (a0 <= t < a1 + 0.3): return
        pin = easeo((t - a0) / 0.40); pout = ease((t - a1) / 0.28) if t >= a1 else 0.0
        w = self.qcard.shape[2]
        blend(fr, self.qcard, CAPX - w / 2, 1120 - self.qpad + 70 * (1 - pin) + 50 * pout, min(1.0, (t - a0) / 0.15) * (1 - pout))

    def draw_name(self, fr, t):
        c = self.c
        la = c.SC[1]["o0"] + 0.55; le = la + 2.8
        if la <= t < le + 0.4:
            p_in = easeo((t - la) / 0.45); p_out = ease((t - le) / 0.30) if t >= le else 0.0
            off = 90 * (1 - p_in) + 90 * p_out
            blend(fr, self.name, SAFE["left"] - 20, X.LANE_Y - 20 + off, (1 - p_out) * min(1.0, (t - la) / 0.15))

    # ---- fotogramas
    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
        z = self.zoom(n, it, t)
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        x = warp_src(src, c.cam.theta(f, z, 540.0, 700.0, ext_y=0.0), ext_bg=self.ext, fade=(0.985, 0.03))
        x = grade_color(x) * self.vig
        x = x * (1 - self.shade) + self.navyt * self.shade
        x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.005).clamp(0, 1)
        if t >= c.SC[1]["o0"] + 0.2: blend(x, self.wmark, SAFE["right"] - self.wmark.shape[2], 276, ease((t - c.SC[1]["o0"] - 0.2) / 0.4))
        if t < c.hook_end: self.draw_question(x, t)
        else: self.draw_captions(x, t)
        self.draw_name(x, t)
        for s0 in self.scene_starts:                                  # corte entre escenas: destello breve
            k = n - s0
            if 0 <= k < 4: x = x + (1 - k / 4) * 0.16
        return exit_to_white(x, self.end0 - n)

    def whips(self): return []

    def cues(self):
        c = self.c; out = []
        for k, v in c.SC.items():
            if k >= 1: out.append((v["o0"] - 0.02, "click", 0.20))
        out.append((c.SC[1]["o0"] + 0.55, "swish", 0.30))
        out.append((0.18, "swish", 0.26))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
