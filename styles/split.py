# Estilo 7 — PANTALLA DIVIDIDA: la entrevista (cara anclada) arriba con subtítulos y, abajo, un panel azul (≈36 %) con barra de progreso roja,
# título del tema, y una ventana redondeada con tomas del edificio / fotos del Banco Central / escudo centrado.
import os, sys
from styles.common import *
from PIL import ImageFilter
from styles.call import Style as CallStyle, ClipPlayer, BR_H
import plan as P

CAPX = 495
SPLIT_Y = 1230
WIN_X, WIN_Y, WIN_W, WIN_H = 60, 1500, 960, 330


def window_sprite():
    pad = 30
    im = Image.new("RGBA", (WIN_W + 2 * pad, WIN_H + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sh = Image.new("L", im.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 10, pad + WIN_W, pad + WIN_H + 10), radius=30, fill=170)
    sh = np.asarray(sh.filter(ImageFilter.GaussianBlur(14))).astype(np.uint8)
    out = np.zeros((WIN_H + 2 * pad, WIN_W + 2 * pad, 4), np.uint8); out[..., 3] = sh
    S = 3
    m = Image.new("L", ((WIN_W + 12) * S, (WIN_H + 12) * S), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, (WIN_W + 12) * S - 1, (WIN_H + 12) * S - 1), radius=36 * S, fill=255)
    m = np.asarray(m.resize((WIN_W + 12, WIN_H + 12), Image.LANCZOS))
    out[pad - 6:pad - 6 + WIN_H + 12, pad - 6:pad - 6 + WIN_W + 12, :3] = 255
    out[pad - 6:pad - 6 + WIN_H + 12, pad - 6:pad - 6 + WIN_W + 12, 3] = np.maximum(out[pad - 6:pad - 6 + WIN_H + 12, pad - 6:pad - 6 + WIN_W + 12, 3], m)
    hole = Image.new("L", (WIN_W * S, WIN_H * S), 0); ImageDraw.Draw(hole).rounded_rectangle((0, 0, WIN_W * S - 1, WIN_H * S - 1), radius=30 * S, fill=255)
    hole = np.asarray(hole.resize((WIN_W, WIN_H), Image.LANCZOS)).astype(np.float32) / 255
    mask = np.zeros(out.shape[:2], np.float32); mask[pad:pad + WIN_H, pad:pad + WIN_W] = hole
    out[..., 3] = (out[..., 3] * (1 - mask)).astype(np.uint8)
    return out, pad, mask


def title_sprite(num, title, sub, maxw=900):
    px = 70
    while px > 40 and tlen(title.upper(), font("Black", px), 1) > maxw: px -= 4
    f = font("Black", px); f2 = font("Bold", 30); fn = font("Black", 30)
    w = int(max(tlen(title.upper(), f, 1), tlen(sub, f2, 0))) + 40; h = int(px * 1.2) + 96
    im = Image.new("RGBA", (w + 40, h + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 8, 74, 50), radius=12, fill=RED + (255,)); d.text((37, 29), f"{num:02d}", font=fn, fill=WHITE + (255,), anchor="mm")
    d.text((92, 29), "TEMA", font=font("Bold", 24), fill=(255, 150, 158, 255), anchor="lm")
    x = 0
    for c in title.upper():
        d.text((x, 62), c, font=f, fill=WHITE + (255,)); x += f.getlength(c) + 1
    d.text((0, 62 + int(px * 1.18)), sub, font=f2, fill=GOLD + (255,))
    return np_(im)


class Style(CallStyle):
    uses_video = True

    def setup(self):
        c = self.c; cfg = c.cfg
        self.end = Endcard(); self.cp = ClipPlayer()
        self.setup_broll(sorted({k["s"] for k in c.CHUNKS}))
        self.vig = make_vignette(0.34)
        self.navyt = tcolor(NAVY)
        self.ext = self.navyt.expand(3, H, W) * (0.75 + 0.55 * (yy_ / 420.0).clamp(0, 1))[None].to(DT)
        yy2 = torch.arange(H - SPLIT_Y, device=dev, dtype=torch.float32)[:, None]
        g = (yy2 / (H - SPLIT_Y))
        self.panel = (tcolor((10, 26, 62)) * (1 - g * 0.55)[None].to(DT).expand(3, -1, W)).clone() if False else (torch.tensor([10, 26, 62], device=dev).view(3, 1, 1).to(DT) / 255 * (1 - 0.55 * g).to(DT)[None]).expand(3, H - SPLIT_Y, W).clone()
        stripes = (((torch.arange(W, device=dev, dtype=torch.float32)[None, :] + yy2) % 56) < 3).to(DT)[None] * 0.025
        self.panel = self.panel + stripes
        self.shade_v = (0.30 * sm(900.0, SPLIT_Y, yy_)).expand(H, W)[None].to(DT)
        ws, self.wpad, wm = window_sprite(); self.wspr = spr_t(ws); self.wmask = T(wm).to(DT)[None]
        import brand as B; self.wmark = spr_t(B.watermark())
        self.titles = {}
        for sid, (num, title, sub) in cfg.get("titles", {}).items():
            sc = c.scene_of(sid)[0]; self.titles[sc] = spr_t(title_sprite(num, title, sub))
        self.chunk_cache = {}
        self.keys_range = [(k["s"], k["e"]) for k in c.CHUNKS if k["key"] and k["e"] - k["s"] >= 0.45]
        self.whips_f = [int(round(c.SC[k]["o0"] * FPS)) for k in c.SC if k >= 1]
        self.end0 = c.END0
        self.chips = []

    def scene_info(self, t):
        c = self.c
        cur = max([k for k in c.SC if c.SC[k]["o0"] <= t + 1e-6] or [0])
        return cur, c.SC[cur]["o0"], c.SC[cur]["o1"]

    def punch(self, t):
        a = 0.0
        for s, e in self.keys_range:
            if s <= t < e: a = max(a, 0.06)
            elif e <= t < e + 0.15: a = max(a, 0.06 * (1 - ease((t - e) / 0.15)))
        return 1 + a

    def chunk_spr(self, ci):
        if ci not in self.chunk_cache:
            k = self.c.CHUNKS[ci]; self.chunk_cache[ci] = spr_t(sub_sprite(k["words"], key_color=GOLD if k["key"] else None, flags=k.get("flags")))
        return self.chunk_cache[ci]

    def draw_captions(self, fr, t):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]:
                spr = self.chunk_spr(ci); age = (t - k["s"]) * FPS
                s2 = scaled(spr, 0.93 + 0.07 * ease(age / 4))
                blend(fr, s2, CAPX - s2.shape[2] / 2, 1105 - s2.shape[1] / 2, min(1.0, (age + 1) / 3))
                break

    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        z = (1.10 + 0.05 * math.sin(it["shot"] * 1.9) ** 2) * (1 + 0.012 * tt) * ((1 + 0.04 * (1 - ease(tt / 0.35))) if n - t0 < 12 else 1.0) * self.punch(t)
        x = warp_src(src, c.cam.theta(f, z, 540.0, 610.0, ext_y=0.0), ext_bg=self.ext, fade=(0.985, 0.03))
        x = grade_color(x) * self.vig
        x = x * (1 - self.shade_v) + self.navyt * self.shade_v
        x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.005).clamp(0, 1)
        # panel inferior
        x[:, SPLIT_Y:] = self.panel
        x[:, SPLIT_Y - 3:SPLIT_Y + 3] = tcolor(RED)                                             # filo rojo
        frac = clamp01(t / max(1e-6, c.END0 / FPS - 0.2))
        x[:, SPLIT_Y + 3:SPLIT_Y + 11, :int(W * frac)] = tcolor((255, 120, 128))             # progreso
        sc, a, b = self.scene_info(t)
        if sc in self.titles:
            spr = self.titles[sc]; p = (t - a - 0.10) / 0.45
            if p > 0:
                s2 = wipe_gpu(spr, ease(p), "in") if p < 1 else spr
                blend(x, s2, WIN_X - 20 + 24 * (1 - easeo(p)), 1258, min(1.0, p * 3))
        # ventana con tomas del banco
        br = self.broll(n)
        for cf in self.shot_f[1:-1]:
            sw = {-1: 0.45, 0: 1.0, 1: 0.40}.get(n - cf)
            if sw: br = gblur_h(br, 1 + 2 * int(round(sw * 44)))
        crop = br[:, 186:186 + WIN_H, 60:60 + WIN_W]
        P_ = self.wpad
        hp = torch.zeros(3, WIN_H + 2 * P_, WIN_W + 2 * P_, device=dev, dtype=DT); hp[:, P_:P_ + WIN_H, P_:P_ + WIN_W] = crop
        m = self.wmask
        rgb = hp * m + self.wspr[:3] * (1 - m); al = m + self.wspr[3:4] * (1 - m)
        blend(x, torch.cat([rgb, al], 0), WIN_X - P_, WIN_Y - P_, ease((t - 0.2) / 0.4))
        blend(x, self.wmark, SAFE["right"] - self.wmark.shape[2], 276, ease((t - 0.3) / 0.4))
        self.draw_captions(x, t)
        k, off = whip_k(n, self.whips_f)
        x = whip_filter(x, k, off)
        return exit_to_white(x, c.END0 - n)

    def whips(self): return self.whips_f

    def cues(self):
        c = self.c; out = [(0.10, "click", 0.4)]
        for f in self.whips_f: out.append((f / FPS - 0.14, "whoosh", 0.38))
        for cf in self.shot_f[1:-1]: out.append((cf / FPS - 0.10, "swish", 0.22))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
