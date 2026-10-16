# Estilo 5 — ANIMADO ROJO + FX: animaciones y efectos en rojo de marca, siempre ligados al contenido.
#  · gancho B/N con glitch y banner rojo · transición "stinger" rojo (barrido diagonal) entre escenas
#  · palabras clave = GOLPE: texto que revienta con barra roja, onda expansiva, chispas, aberración cromática, sacudida y destello
#  · subtítulos karaoke (la palabra que se dice va en caja roja) · placa de nombre animada · brasas rojas de fondo · cierre blanco
import os, sys, math
import numpy as np
from styles.common import *
import plan as P

CAPX = 495
DKRED = (140, 12, 26)
ZOOM = [1.12, 1.18, 1.14, 1.20, 1.15, 1.21]


def rgb_split(x, a):
    a = int(round(a))
    if a <= 0: return x
    return torch.stack([torch.roll(x[0], a, 1), x[1], torch.roll(x[2], -a, 1)])


def hit_sprite(text, maxw=860):
    """palabra-golpe: texto blanco ultra grueso sobre paralelogramo rojo inclinado con filo blanco"""
    px = 150
    while px > 60:
        f = font("Black", px)
        if tlen(text, f, 2) + 120 <= maxw: break
        px -= 6
    f = font("Black", px)
    tw = int(tlen(text, f, 2)); h = int(px * 1.15)
    pad = 40; w = tw + 120
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sk = 26
    d.polygon([(pad + sk, pad), (pad + w, pad), (pad + w - sk, pad + h), (pad, pad + h)], fill=RED + (255,))
    d.polygon([(pad + sk + 10, pad + 10), (pad + w - 4, pad + 10), (pad + w - sk - 10, pad + h - 10), (pad + 4, pad + h - 10)], outline=(255, 255, 255, 235), width=3)
    x = pad + 60
    for c in text:
        d.text((x, pad + h / 2 + 4), c, font=f, fill=WHITE + (255,), anchor="lm"); x += f.getlength(c) + 2
    return np_(shadowed(im, blur=14, dy=8, alpha=0.6, pad=0)), (w + 2 * pad, h + 2 * pad)


def kara_sprite(words, active, px=58):
    """subtítulo karaoke: la palabra activa va en caja roja"""
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    pad = 36
    iw, ih = int(total) + 2 * pad, int(px * 1.25) + 2 * pad
    im = Image.new("RGBA", (iw, ih), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = pad
    for i, wd in enumerate(words):
        if i == active:
            d.rounded_rectangle((x - 12, pad - 2, x + ws[i] + 12, pad + int(px * 1.2)), radius=14, fill=(250, 250, 252, 255))   # caja blanca: se ve sobre el saco rojo
            d.text((x, pad), wd, font=f, fill=RED + (255,))
        else:
            d.text((x, pad), wd, font=f, fill=WHITE + (255,), stroke_width=max(5, int(px * 0.10)), stroke_fill=(8, 10, 14, 255))
        x += ws[i] + sp
    return np_(shadowed(im, blur=8, dy=5, alpha=0.55, pad=0))


def lower_third():
    f1, f2 = font("Black", 46), font("Bold", 25)
    import brand as B
    name, role = B.NAME.upper(), B.ROLE.upper()
    spc = 2.4
    rw = sum(f2.getlength(c) + spc for c in role)
    w = int(max(f1.getlength(name), rw) + 110); h = 120
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(8, 16, 40, 232))
    d.rounded_rectangle((0, 0, 30, h - 1), radius=10, fill=RED + (255,)); d.rectangle((14, 0, 30, h - 1), fill=RED + (255,))
    d.text((56, 14), name, font=f1, fill=WHITE + (255,))
    x = 56
    for c in role:
        d.text((x, 76), c, font=f2, fill=(255, 120, 130, 255)); x += f2.getlength(c) + spc
    return np_(shadowed(im, blur=12, dy=7, alpha=0.5, pad=20)), 20


class Style:
    def __init__(self, ctx):
        self.c = ctx

    def setup(self):
        c = self.c; cfg = c.cfg
        self.end = Endcard()
        self.vig = make_vignette(0.42)
        self.navyt = tcolor(NAVY)
        self.redt = tcolor(RED); self.dkred = tcolor(DKRED)
        self.top = (0.55 * (1 - sm(250.0, 800.0, yy_))).expand(H, W)[None].to(DT)
        self.shade = (0.42 * sm(1050.0, 1500.0, yy_) + 0.26 * sm(1500.0, 1920.0, yy_)).expand(H, W)[None].to(DT)
        import brand as B; self.wmark = spr_t(B.watermark())
        self.u = (xx_ * 0.45 + yy_ * 0.89)
        self.umax = float(W * 0.45 + H * 0.89)
        spr, pad = lower_third(); self.l3 = spr_t(spr); self.l3pad = pad
        # gancho
        hook_words = [w for w in c.WORDS if w["sc"] == 0]
        self.hook_t = cfg.get("hook_text", "")
        if self.hook_t:
            px = 84
            while px > 40 and tlen(self.hook_t, font("Black", px), 2) + 110 > 850: px -= 4
            fb = font("Black", px)
            w_ = int(tlen(self.hook_t, fb, 2)) + 110; h_ = int(px * 1.55)
            im = Image.fromarray(G11.ink_bg(w_, h_, 9, RED, pad=14, amp=5.0)); d = ImageDraw.Draw(im)
            x = 14 + 55
            for ch in self.hook_t:
                d.text((x, 14 + h_ / 2 + 2), ch, font=fb, fill=WHITE + (255,), anchor="lm"); x += fb.getlength(ch) + 2
            self.banner = spr_t(np_(im))
        self.vf = spr_t(G11.viewfinder()); self.rec = spr_t(G11.rec_dot())
        # golpes
        self.hits = []
        for sid, tok, nth, text in cfg.get("hits", []):
            sc = c.scene_of(sid)[0]
            s = c.w_(sc, tok, nth) - 0.04
            spr, (w, h) = hit_sprite(text)
            self.hits.append(dict(s=s, spr=spr_t(spr), w=w, h=h, sc=sc, rng=np.random.default_rng(int(s * 100))))
        for i in range(len(self.hits) - 1): assert self.hits[i + 1]["s"] - self.hits[i]["s"] >= 1.6, ("golpes muy juntos", i)
        # transiciones
        self.cuts = [int(round(c.SC[k]["o0"] * FPS)) for k in c.SC if k >= 1]
        self.chunk_cache = {}
        # brasas
        r = np.random.default_rng(5)
        self.NE = 46
        self.ex = r.uniform(0, W, self.NE); self.ey = r.uniform(0, H, self.NE); self.ev = r.uniform(30, 95, self.NE); self.er = r.uniform(2.2, 5.0, self.NE); self.eph = r.uniform(0, 6.28, self.NE)
        k = torch.arange(-12, 13, device=dev, dtype=torch.float32)
        self.eg = torch.meshgrid(k, k, indexing="xy")
        self.end0 = c.END0
        self.l3_t = c.SC[1]["o0"] + 0.6 if 1 in c.SC else 3.0

    # ---- eventos
    def hit_state(self, t):
        for h in self.hits:
            a = t - h["s"]
            if 0 <= a < 1.7: return h, a
        return None, 0.0

    def zoom(self, n, it, t):
        c = self.c
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        z = ZOOM[it["shot"] % len(ZOOM)] * (1 + 0.014 * tt) * ((1 + 0.04 * (1 - ease(tt / 0.35))) if n - t0 < 12 else 1.0)
        h, a = self.hit_state(t)
        if h is not None and a < 0.5: z *= 1 + 0.07 * (1 - ease(a / 0.5)) * min(1.0, a / 0.05 + 0.2)
        return z

    # ---- capas
    def kara(self, ci, active):
        k = (ci, active)
        if k not in self.chunk_cache:
            self.chunk_cache[k] = spr_t(two_rows(lambda ws, j0: kara_sprite(ws, active - j0 if j0 <= active < j0 + len(ws) else -1), self.c.CHUNKS[ci]["words"]))
        return self.chunk_cache[k]

    def draw_captions(self, fr, t):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]:
                active = max([i for i, ts in enumerate(k["ts"]) if ts - 0.02 <= t] or [0])
                spr = self.kara(ci, active); age = (t - k["s"]) * FPS
                s2 = scaled(spr, 0.94 + 0.06 * ease(age / 4))
                blend(fr, s2, CAPX - s2.shape[2] / 2, 1215 - s2.shape[1] / 2, min(1.0, (age + 1) / 3))
                break

    def draw_hit(self, fr, t):
        h, a = self.hit_state(t)
        if h is None: return
        cx, cy = 490.0, 520.0
        # onda expansiva roja
        if a < 0.7:
            r = 760 * easeo(a / 0.7)
            d = torch.sqrt((xx_ - cx) ** 2 + (yy_ - cy) ** 2)
            ring = (torch.exp(-((d - r) / (10 + 26 * a)) ** 2) * (1 - a / 0.7) ** 1.4 * 0.80)[None].to(DT)
            fr.copy_(fr * (1 - ring) + self.redt * ring)
        # texto: revienta con rebote y sale
        sc = 0.35 + 0.65 * easeb(a / 0.26) if a < 0.26 else 1.0 + 0.012 * math.sin(a * 9)
        out = ease((a - 1.35) / 0.3)
        sc *= 1 + 0.12 * out
        spr = scaled(h["spr"], sc)
        blend(fr, spr, cx - spr.shape[2] / 2, cy - spr.shape[1] / 2, min(1.0, a / 0.05) * (1 - out))
        # chispas
        if a < 0.9:
            rg = np.random.default_rng(int(h["s"] * 100))
            for i in range(34):
                ang = rg.uniform(0, 6.283); sp = rg.uniform(220, 640)
                x = cx + math.cos(ang) * sp * easeo(a / 0.9); y = cy + math.sin(ang) * sp * easeo(a / 0.9) + 380 * a * a
                al = (1 - a / 0.9) ** 1.2; sz = int(rg.integers(4, 10))
                xi, yi = int(x), int(y)
                if 0 <= xi < W - sz and 0 <= yi < H - sz:
                    col = self.redt if i % 3 else tcolor((255, 255, 255))
                    fr[:, yi:yi + sz, xi:xi + sz] = fr[:, yi:yi + sz, xi:xi + sz] * (1 - al) + col * al

    def draw_embers(self, fr, t):
        for i in range(self.NE):
            x = (self.ex[i] + 20 * math.sin(t * 0.8 + self.eph[i])) % W
            y = (self.ey[i] - self.ev[i] * t) % H
            xi, yi = int(x), int(y)
            if xi < 13 or yi < 13 or xi >= W - 13 or yi >= H - 13: continue
            tw = 0.5 + 0.5 * math.sin(t * 2.4 + self.eph[i]); r = self.er[i] * (0.7 + 0.5 * tw)
            gx, gy = self.eg
            g = (torch.exp(-((gx - (x - xi)) ** 2 + (gy - (y - yi)) ** 2) / (2 * r * r)) * 0.75 * tw).to(DT)
            col = tcolor((255, 70, 60)) if i % 4 else tcolor((255, 190, 110))
            reg = fr[:, yi - 12:yi + 13, xi - 12:xi + 13]
            fr[:, yi - 12:yi + 13, xi - 12:xi + 13] = reg * (1 - g) + col * g

    def draw_l3(self, fr, t):
        la, le = self.l3_t, self.l3_t + 3.0
        if la <= t < le + 0.4:
            p = (t - la) / 0.5
            spr = wipe_gpu(self.l3, ease(p), "in") if p < 1 else self.l3
            out = ease((t - le) / 0.3)
            blend(fr, spr, SAFE["left"] - self.l3pad - 40 * out, 1318 - self.l3pad, (1 - out) * min(1.0, p * 3))

    def stinger(self, x, n):
        for c in self.cuts:
            k = n - c
            if -6 <= k <= 6:
                if k <= 0: pos = ease((k + 7) / 7.0) * self.umax; m = (self.u <= pos); edge = self.u - pos
                else: pos = ease(k / 7.0) * self.umax; m = (self.u >= pos); edge = pos - self.u
                m2 = (self.u <= pos - 170) if k <= 0 else (self.u >= pos + 170)
                mh = m.to(DT)[None]; m2h = m2.to(DT)[None]
                x = x * (1 - mh * 0.0)
                stripes = (0.93 + 0.07 * torch.sin(yy_ * 0.07 + xx_ * 0.03)).to(DT)[None]
                x = x * (1 - mh) + (self.dkred * (1 - m2h) + self.redt * m2h) * stripes * mh
                ed = (torch.exp(-(edge / 7.0) ** 2) * 0.9).to(DT)[None] * (edge.abs() < 40).to(DT)[None]
                x = x + ed
                x = rgb_split(x, 10 * (1 - abs(k) / 7.0))
        return x

    # ---- fotogramas
    def src_frame(self, n, it, src, dx=0.0, dy=0.0):
        c = self.c; t = n / FPS
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        z = self.zoom(n, it, t)
        return warp_src(src, c.cam.theta(f, z, 540.0, 880.0, ext_y=260.0), ext_bg=self.navyt.expand(3, H, W), dx=dx, dy=dy, fade=(0.90, 0.14))

    def hook_frame(self, n, it, src):
        c = self.c; t = n / FPS
        dx, dy = shake(n, 3.0)
        x = to_bw(self.src_frame(n, it, src, dx, dy), n) * self.vig
        x = x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.03
        sc_ = ((torch.sin(yy_ * 1.3) * 0.5 + 0.5) * 0.06).to(DT)[None]
        x = x * (1 - sc_)                                                   # líneas de barrido
        blend(x, self.vf, 0, 0, 0.9)
        if int(t * 2.4) % 2 == 0: blend(x, self.rec, 76 + 26, 300 + 96)
        if self.hook_t:
            s0, e0 = 0.35, c.hook_end - 0.25
            if s0 <= t < e0 + 0.3:
                spr = self.banner
                if t < s0 + 0.28: spr = wipe_gpu(spr, ease((t - s0) / 0.28), "in")
                elif t >= e0: spr = wipe_gpu(spr, ease((t - e0) / 0.28), "out")
                blend(x, spr, 495 - spr.shape[2] / 2, 1230 - spr.shape[1] / 2)
        g = max(0.0, 1 - t / 0.35)                                          # glitch de entrada
        if g > 0: x = rgb_split(x, 14 * g) + g * 0.18
        return x.clamp(0, 1)

    def main_frame(self, n, it, src):
        t = n / FPS
        h, a = self.hit_state(t)
        dx = dy = 0.0
        if h is not None and a < 0.22:
            amp = 16 * (1 - a / 0.22)
            dx, dy = amp * math.sin(a * 140), amp * 0.7 * math.cos(a * 170)
        x = grade_color(self.src_frame(n, it, src, dx, dy), 1.09, 1.12) * self.vig
        x = x * (1 - self.top) + self.navyt * self.top
        x = x * (1 - self.shade) + self.navyt * self.shade
        x = x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.005
        if h is not None and a < 0.18: x = x + (1 - a / 0.18) * 0.22 * tcolor((255, 120, 110))     # destello rojo
        return x.clamp(0, 1)

    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
        if t < c.hook_end: x = self.hook_frame(n, it, src)
        else:
            x = self.main_frame(n, it, src)
            self.draw_embers(x, t)
            blend(x, self.wmark, SAFE["right"] - self.wmark.shape[2], 276, ease((t - c.hook_end - 0.3) / 0.4))
            self.draw_captions(x, t)
            self.draw_l3(x, t)
            self.draw_hit(x, t)
            h, a = self.hit_state(t)
            if h is not None and a < 0.25: x = rgb_split(x, 12 * (1 - a / 0.25))          # aberración cromática del golpe
        x = self.stinger(x, n)
        return exit_to_white(x, c.END0 - n)

    def whips(self): return []

    def cues(self):
        c = self.c; out = [(0.02, "boom", 0.24), (0.05, "click", 0.45)]
        for cut in self.cuts: out.append((cut / FPS - 0.20, "whoosh", 0.50))
        for h in self.hits: out.append((h["s"] + 0.02, "boom", 0.34)); out.append((h["s"], "swish", 0.26))
        out.append((self.l3_t, "click", 0.26)); out.append((self.l3_t, "swish", 0.24))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
