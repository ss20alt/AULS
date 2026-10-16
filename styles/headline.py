# Estilo 4 — TITULARES (editorial): un titular grande por tema (palabras clave sobre barra roja) en el tercio superior, barra de progreso por temas,
# la cara más abajo (centro-inferior), subtítulos blancos con claves doradas y transición de zoom entre temas. Sin globos ni fotos.
import os, sys, re
from styles.common import *
import plan as P

CAPX = 495
HL_X = 70


def _parse(ln):
    toks, key = [], False
    for t in ln.split():
        if t.startswith("{"): key = True
        clean = t.replace("{", "").replace("}", "")
        toks.append((clean, key))
        if "}" in t: key = False
    return toks


def headline_sprite(lines, px=92, maxw=840):
    """lines: ['LAS {LEYES} QUE', '{CAMBIARON} VIDAS'] — lo que va entre llaves va en barra roja. Cada línea se ajusta a la zona
    segura por separado (la bajada más chica) y, si aun así no entra, se parte en dos: nunca se sale del cuadro."""
    rows = [_parse(ln) for ln in lines]
    width = lambda r, f: sum(f.getlength(w) for w, _ in r) + f.getlength(" ") * (len(r) - 1) + 28
    fitted = []                                                            # [(fila, tamaño)]
    for ri, r in enumerate(rows):
        p_ = px if ri == 0 else int(px * 0.62)
        lo = 56 if ri == 0 else 34
        while p_ > lo and width(r, font("Black", p_)) > maxw: p_ -= 2
        if width(r, font("Black", p_)) <= maxw or len(r) < 2:
            fitted.append((r, p_)); continue
        h = len(r) // 2                                                    # no entra ni en el mínimo: dos líneas
        for part in (r[:h], r[h:]):
            q = p_
            while q > lo and width(part, font("Black", q)) > maxw: q -= 2
            fitted.append((part, q))
    pad = 30
    big = fitted[0][1]
    iw = int(max(width(r, font("Black", q)) for r, q in fitted)) + 2 * pad + 40
    sprites = []
    for r, q in fitted:
        f = font("Black", q); sp = f.getlength(" "); lh_r = int(q * 1.22)
        im = Image.new("RGBA", (iw, int(big * 1.22) + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x = pad
        for w, key in r:
            wl = f.getlength(w)
            if key:
                d.rounded_rectangle((x - 14, pad + 6, x + wl + 14, pad + lh_r - 6), radius=10, fill=RED + (255,))
                d.text((x, pad + 2), w, font=f, fill=WHITE + (255,))
            else:
                d.text((x, pad + 2), w, font=f, fill=WHITE + (255,), stroke_width=max(4, q // 15), stroke_fill=(6, 12, 30, 255))
            x += wl + sp
        sprites.append(np_(shadowed(im, blur=10, dy=6, alpha=0.55, pad=0)))
    offs, y = [], 0                                                        # posición de cada fila (las filas tienen distinto alto)
    for r, q in fitted: offs.append(y); y += int(q * 1.22)
    return sprites, pad, offs


def progress_sprite(n, idx, frac, w=830):
    gap = 10; sw = (w - gap * (n - 1)) / n
    im = Image.new("RGBA", (w, 14), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i in range(n):
        x0 = i * (sw + gap)
        d.rounded_rectangle((x0, 2, x0 + sw, 11), radius=4, fill=(255, 255, 255, 90))
        f_ = 1.0 if i < idx else (min(1.0, frac) if i == idx else 0.0)
        if f_ > 0: d.rounded_rectangle((x0, 2, x0 + max(8, sw * f_), 11), radius=4, fill=RED + (255,))
    return np_(im)


class Style:
    def __init__(self, ctx):
        self.c = ctx

    def setup(self):
        c = self.c; cfg = c.cfg
        self.end = Endcard()
        self.vig = make_vignette(0.36)
        self.navyt = tcolor(NAVY)
        self.top = (0.82 * (1 - sm(250.0, 880.0, yy_))).expand(H, W)[None].to(DT)               # degradado azul bajo el titular
        self.shade = (0.42 * sm(1180.0, 1500.0, yy_) + 0.26 * sm(1500.0, 1920.0, yy_)).expand(H, W)[None].to(DT)
        import brand as B; self.wmark = spr_t(B.watermark())
        self.sc_ids = sorted(c.SC)
        self.n_scenes = len(self.sc_ids)
        self.hl = {}
        for sid, lines in cfg["headlines"].items():
            sc = c.scene_of(sid)[0]
            sps, pad, lh = headline_sprite(lines)
            self.hl[sc] = ([spr_t(s) for s in sps], pad, lh)
        self.prog = {}
        self.chunk_cache = {}
        self.starts = {k: int(round(c.SC[k]["o0"] * FPS)) for k in c.SC}
        self.end0 = c.END0

    def scene_info(self, t):
        c = self.c
        cur = max([k for k in c.SC if c.SC[k]["o0"] <= t + 1e-6] or [0])
        return cur, c.SC[cur]["o0"], c.SC[cur]["o1"]

    def zoom(self, n, it, t):
        c = self.c
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        base = 1.10 + 0.045 * math.sin(it["shot"] * 1.7) ** 2
        z = base * (1 + 0.016 * tt)
        for k, s0 in self.starts.items():                        # transición: entra con zoom que se asienta; sale empujando
            d = n - s0
            if k >= 1 and 0 <= d < 8: z *= 1 + 0.16 * (1 - ease(d / 8.0))
            e = s0 - n
            if k >= 1 and 0 < e <= 5: z *= 1 + 0.10 * ease((6 - e) / 5.0)
        return z

    def chunk_spr(self, ci):
        if ci not in self.chunk_cache:
            k = self.c.CHUNKS[ci]; self.chunk_cache[ci] = spr_t(sub_sprite(k["words"], key_color=GOLD if k["key"] else None, flags=k.get("flags")))
        return self.chunk_cache[ci]

    def draw_captions(self, fr, t):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]:
                spr = self.chunk_spr(ci); age = (t - k["s"]) * FPS
                s2 = scaled(spr, 0.93 + 0.07 * ease(age / 4))
                blend(fr, s2, CAPX - s2.shape[2] / 2, 1330 - s2.shape[1] / 2, min(1.0, (age + 1) / 3))
                break

    def draw_headline(self, fr, t, sc, a, b):
        if sc not in self.hl: return
        sprs, pad, lh = self.hl[sc]
        hold = min(b - a - 0.5, 4.6)
        for i, spr in enumerate(sprs):
            t_in = a + 0.12 + 0.14 * i
            if t < t_in: continue
            p = (t - t_in) / 0.42
            sp = wipe_gpu(spr, ease(p), "in") if p < 1 else spr
            out = ease((t - (a + 0.12 + hold)) / 0.30)
            if out >= 1: continue
            y = 392 - pad + (lh[i] if isinstance(lh, list) else i * lh) - 34 * out
            blend(fr, sp, HL_X - pad + 30 * (1 - easeo(p)), y, (1 - out) * min(1.0, p * 3))

    def draw_progress(self, fr, t, sc, a, b):
        idx = self.sc_ids.index(sc)
        frac = (t - a) / max(1e-6, b - a)
        key = (idx, int(frac * 40))
        if key not in self.prog: self.prog[key] = spr_t(progress_sprite(self.n_scenes, idx, int(frac * 40) / 40.0))
        blend(fr, self.prog[key], 60, 284, 0.95)

    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        z = self.zoom(n, it, t)
        x = warp_src(src, c.cam.theta(f, z, 540.0, 1085.0, ext_y=330.0), ext_bg=self.navyt.expand(3, H, W), fade=(0.965, 0.05))
        x = grade_color(x) * self.vig
        x = x * (1 - self.top) + self.navyt * self.top
        x = x * (1 - self.shade) + self.navyt * self.shade
        x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.005).clamp(0, 1)
        sc, a, b = self.scene_info(t)
        self.draw_progress(x, t, sc, a, b)
        blend(x, self.wmark, SAFE["right"] - self.wmark.shape[2], 312, ease((t - 0.3) / 0.4))
        self.draw_headline(x, t, sc, a, b)
        self.draw_captions(x, t)
        for k, s0 in self.starts.items():                      # desenfoque de zoom en la costura
            if k >= 1 and -5 <= n - s0 < 6:
                a_ = 1 - abs(n - s0 + 0.5) / 6.0
                if a_ > 0.05: x = gblur(x[None], 14 * a_ + 0.5)[0] * 1.0
                if n - s0 == 0: x = x * 0.85 + 0.15
        return exit_to_white(x, c.END0 - n)

    def whips(self): return []

    def cues(self):
        c = self.c; out = []
        for k, v in c.SC.items():
            out.append((v["o0"] - 0.10, "whoosh", 0.34)); out.append((v["o0"] + 0.12, "click", 0.34)); out.append((v["o0"] + 0.14, "swish", 0.20))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
