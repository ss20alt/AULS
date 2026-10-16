# Estilo 2 — TIKTOK TINTA (referencias R1/R6): gancho B/N con visor + lente curva y título en tinta, entrevista con la cara anclada y zoom de énfasis,
# frases clave en cajas de tinta negra, barridos con destello entre escenas, momento rojo, placa de nombre, final B/N con barras y cierre blanco.
import os, sys
from styles.common import *
import gfx18 as G18
import plan as P

ZCYC = [1.12, 1.20, 1.15, 1.24, 1.17, 1.22, 1.13, 1.21]
REDT = torch.tensor([1.12, 0.40, 0.45], device=dev).view(3, 1, 1).to(DT)


def barrel(x, k=0.13, zin=0.93):
    """lente curva del gancho (R6): el cuadro se abomba y los bordes quedan negros y curvos"""
    gy, gx = torch.meshgrid(torch.linspace(-1, 1, H, device=dev), torch.linspace(-1, 1, W, device=dev), indexing="ij")
    r2 = (gx * (W / H)) ** 2 + gy ** 2
    f = zin * (1 + k * r2 * 2.2)
    grid = torch.stack([gx * f, gy * f], -1)[None]
    out = F.grid_sample(x[None].float(), grid, mode="bilinear", padding_mode="zeros", align_corners=False)[0].to(DT)
    return out


class Style:
    def __init__(self, ctx):
        self.c = ctx

    def setup(self):
        c = self.c; cfg = c.cfg
        self.end = Endcard()
        self.vig = make_vignette(0.40)
        self.navyt = tcolor(NAVY)
        self.shade = (0.42 * sm(1000.0, 1500.0, yy_) + 0.26 * sm(1500.0, 1920.0, yy_)).expand(H, W)[None].to(DT)
        import brand as B; self.wmark = spr_t(B.watermark())
        import brand as B; self.name = spr_t(B.name_card()[0])
        self.vf = spr_t(G11.viewfinder()); self.rec = spr_t(G11.rec_dot())
        self.dust = [spr_t(d) for d in G11.dust_layers(8)]
        self.banner = spr_t(G18.banner_ink(cfg["hook_text"]))
        self.last = max(c.SC)
        # final B/N solo en la última frase completa (como R6), no en todo el bloque de cierre
        lw = [w for w in c.WORDS if w["sc"] == self.last]
        starts = [lw[i]["s"] for i in range(1, len(lw)) if lw[i - 1]["t"][-1] in ".?!" and lw[i]["s"] <= c.END0 / FPS - 4.0]
        self.fin_t = (starts[-1] - 0.25) if starts else c.SC[self.last]["o0"] + 0.05
        self.whips_f = [int(round(c.SC[k]["o0"] * FPS)) for k in c.SC if k >= 1]
        if int(round(self.fin_t * FPS)) not in self.whips_f: self.whips_f.append(int(round(self.fin_t * FPS)))
        self.chunk_cache = {}
        self.keys_range = [(k["s"], k["e"]) for k in c.CHUNKS if k["key"] and k["e"] - k["s"] >= 0.45 and k["s"] < self.fin_t]
        # momento rojo en la palabra elegida
        self.red0 = None
        for sc in sorted(c.SC):
            ws = [w for w in c.WORDS if w["sc"] == sc and P.norm(w["t"]) == P.norm(cfg.get("red_word", "irresponsable"))]
            if ws and self.red0 is None and sc != self.last: self.red0 = ws[0]["s"] - 0.06
        self.red1 = (self.red0 or 0) + 1.45
        self.end0 = c.END0

    # ---- cámara
    def punch(self, t):
        a = 0.0
        for s, e in self.keys_range:
            if s <= t < e: a = max(a, 0.12)
            elif e <= t < e + 0.15: a = max(a, 0.12 * (1 - ease((t - e) / 0.15)))
        return 1 + a

    def zoom(self, n, it, t, mode):
        c = self.c
        if mode == "hook": return 1.22 * (1 + 0.025 * (t / max(1e-3, c.hook_end)))
        if mode == "finale": return 1.16 * (1 + 0.018 * (t - self.fin_t) / 6.0)
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        return ZCYC[it["shot"] % len(ZCYC)] * (1 + 0.012 * tt) * ((1 + 0.04 * (1 - ease(tt / 0.35))) if n - t0 < 12 else 1.0) * self.punch(t)

    def src_frame(self, n, it, src, mode, dx=0.0, dy=0.0):
        c = self.c; t = n / FPS
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        z = self.zoom(n, it, t, mode)
        return warp_src(src, c.cam.theta(f, z, 540.0, 690.0, ext_y=0.0), ext_bg=self.navyt.expand(3, H, W), dx=dx, dy=dy, fade=(0.985, 0.03))

    # ---- capas
    def chunk_spr(self, ci, force_key=None):
        k = (ci, force_key)
        if k not in self.chunk_cache:
            ch = self.c.CHUNKS[ci]; key = ch["key"] if force_key is None else force_key
            self.chunk_cache[k] = spr_t(two_rows(lambda ws, j0: sub_sprite(ws, ink_box=key, seed=ci + 3 + j0), ch["words"]))
        return self.chunk_cache[k]

    def draw_captions(self, fr, t, finale):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]:
                if finale != (t >= self.fin_t - 0.05): continue
                spr = self.chunk_spr(ci, True if finale else None)
                age = (t - k["s"]) * FPS; cy = 1250 if finale else 1170
                key = finale or k["key"]
                if key:
                    if age < 4: spr = wipe_gpu(spr, ease((age + 0.5) / 4.5), "in")
                    blend(fr, spr, CAPX - spr.shape[2] / 2, cy - spr.shape[1] / 2)
                else:
                    s2 = scaled(spr, 0.92 + 0.08 * ease(age / 4))
                    blend(fr, s2, CAPX - s2.shape[2] / 2, cy - s2.shape[1] / 2, min(1.0, (age + 1) / 3))
                break

    def draw_name(self, fr, t):
        c = self.c
        la = c.SC[1]["o0"] + 0.55; le = la + 2.8
        if la <= t < le + 0.4:
            p_in = easeo((t - la) / 0.45); p_out = ease((t - le) / 0.30) if t >= le else 0.0
            off = 90 * (1 - p_in) + 90 * p_out
            blend(fr, self.name, SAFE["left"] - 20, X.LANE_Y - 20 + off, (1 - p_out) * min(1.0, (t - la) / 0.15))

    # ---- tipos de fotograma
    def hook_frame(self, n, it, src):
        c = self.c; t = n / FPS
        dx, dy = shake(n, 2.2)
        x = self.src_frame(n, it, src, "hook", dx, dy)
        x = to_bw(x, n) * self.vig
        x = x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.028
        blend(x, self.dust[(n // 2) % len(self.dust)], 0, 0, 0.9)
        blend(x, self.vf, 0, 0, 0.95)
        if int(t * 2.2) % 2 == 0: blend(x, self.rec, 76 + 26, 300 + 96)
        s0, e0 = 0.30, c.hook_end - 0.20
        if s0 <= t < e0 + 0.30:
            spr = self.banner
            if t < s0 + 0.28: spr = wipe_gpu(spr, ease((t - s0) / 0.28), "in")
            elif t >= e0: spr = wipe_gpu(spr, ease((t - e0) / 0.28), "out")
            blend(x, spr, CX - spr.shape[2] / 2, 1175 - spr.shape[1] / 2)
        x = x.clamp(0, 1)
        return barrel(x)

    def finale_frame(self, n, it, src):
        t = n / FPS
        dx, dy = shake(n, 2.4)
        x = self.src_frame(n, it, src, "finale", dx, dy)
        x = to_bw(x, n, 1.26) * self.vig
        x = x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.03
        x[:, :300] = 0; x[:, 1400:] = 0
        blend(x, self.dust[(n // 2) % len(self.dust)], 0, 0, 0.6)
        return x.clamp(0, 1)

    def main_frame(self, n, it, src):
        c = self.c; t = n / FPS
        x = grade_color(self.src_frame(n, it, src, "main")) * self.vig
        x = x * (1 - self.shade) + self.navyt * self.shade
        x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.005).clamp(0, 1)
        if self.red0 is not None and self.red0 <= t < self.red1:             # momento rojo (referencia R6)
            k = min(ease((t - self.red0) / 0.10), 1 - ease((t - (self.red1 - 0.2)) / 0.2))
            g = (0.299 * x[0:1] + 0.587 * x[1:2] + 0.114 * x[2:3])
            red = (g * REDT + torch.tensor([14 / 255, 0, 4 / 255], device=dev).view(3, 1, 1).to(DT)).clamp(0, 1)
            x = x * (1 - k) + red * k
            if t - self.red0 < 0.10: x = x + (1 - (t - self.red0) / 0.10) * 0.30
        return x

    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
        if t < c.hook_end: out = self.hook_frame(n, it, src)
        elif t >= self.fin_t:
            out = self.finale_frame(n, it, src); self.draw_captions(out, t, True)
        else:
            out = self.main_frame(n, it, src)
            if t >= c.SC[1]["o0"] + 0.2: blend(out, self.wmark, SAFE["right"] - self.wmark.shape[2], 276, ease((t - c.SC[1]["o0"] - 0.2) / 0.4))
            self.draw_captions(out, t, False)
            self.draw_name(out, t)
        k, off = whip_k(n, self.whips_f)
        out = whip_filter(out, k, off)
        return exit_to_white(out, c.END0 - n)

    def whips(self): return self.whips_f

    def cues(self):
        c = self.c; out = [(0.02, "boom", 0.22), (0.06, "click", 0.50), (0.30, "swish", 0.28)]
        for f in self.whips_f: out.append((f / FPS - 0.14, "whoosh", 0.40))
        out.append((c.SC[1]["o0"] + 0.55, "swish", 0.30))
        if self.red0: out.append((self.red0, "boom", 0.26))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out


CAPX = 495
