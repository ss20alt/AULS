# Estilo 3 — REPORTAJE (referencias R2/R7): globo de cómic con la pregunta, cards de capítulo, recuadros con fotos del banco y logo centrado
# que cubren los cortes, barridos con destello entre escenas, subtítulos en barra azul con palabras clave en amarillo, sello de redes y cierre blanco.
import os, sys
from styles.common import *
import gfx18 as G18
import plan as P
from PIL import ImageFont

CAPX = 495
YEL = (255, 214, 64)
ZCYC = [1.08, 1.16, 1.11, 1.18, 1.13, 1.20, 1.09, 1.17]


def bar_sprite(words, flags, px=54):
    """subtítulo en barra azul marino translúcida; las palabras clave en amarillo"""
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    padx, pady = 34, 16
    w = int(total) + 2 * padx; h = int(px * 1.25) + 2 * pady
    m = 24
    im = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((m, m, m + w, m + h), radius=22, fill=(8, 16, 40, 214))
    d.rounded_rectangle((m, m + h - 7, m + w, m + h), radius=5, fill=RED + (255,)); d.rectangle((m, m + h - 7, m + w, m + h - 4), fill=(8, 16, 40, 214))
    x = m + padx
    for i, wd in enumerate(words):
        d.text((x, m + pady - 2), wd, font=f, fill=(YEL if flags[i] else WHITE) + (255,)); x += ws[i] + sp
    return np_(shadowed(im, blur=10, dy=6, alpha=0.5, pad=0))


class Style:
    def __init__(self, ctx):
        self.c = ctx

    def setup(self):
        c = self.c; cfg = c.cfg
        self.end = Endcard()
        self.vig = make_vignette(0.34)
        self.navyt = tcolor(NAVY)
        self.shade = (0.40 * sm(1000.0, 1500.0, yy_) + 0.24 * sm(1500.0, 1920.0, yy_)).expand(H, W)[None].to(DT)
        import brand as B; self.wmark = spr_t(B.watermark())
        import brand as B; self.name = spr_t(B.name_card()[0])
        # globo de la pregunta
        hook = [w["t"] for w in c.WORDS if w["sc"] == 0]
        self.bub_txt = " ".join(hook)
        self.bubs = {k: (lambda v: (spr_t(v[0]), v[1], v[2]))(X.bubble_sprite(self.bub_txt, k)) for k in range(len(self.bub_txt.split()) + 1)}
        self.bub_tip = (84, 1420)
        self.hook_words = [w for w in c.WORDS if w["sc"] == 0]
        # fotos y recuadro
        self.photos = {}
        for nm, fl, kind in (("p1", "banco1.webp", "normal"), ("p2", "banco2.webp", "hazy")):
            up, (w, h) = G18.load_photo(fl, kind)
            self.photos[nm] = dict(t=T(up).permute(2, 0, 1).to(DT)[None] / 255, w=w, h=h)
        logo, bg = G18.logo_canvas()
        self.logo = T(logo).permute(2, 0, 1).to(DT)[None] / 255
        self.logo_bg = torch.tensor(bg, device=dev).view(3, 1, 1).to(DT) / 255
        wf, self.wpad, wm = G18.window_frame()
        self.wframe = spr_t(wf); self.wmask = T(wm).to(DT)[None]
        self.WINW, self.WINH = G18.WINW, G18.WINH
        xw = torch.arange(self.WINW, device=dev, dtype=torch.float32)[None, :]; yw = torch.arange(self.WINH, device=dev, dtype=torch.float32)[:, None]
        self.xw, self.yw = xw, yw
        self.vig_win = (1 - 0.28 * ((((xw - self.WINW / 2) / (self.WINW * 0.78)) ** 2 + ((yw - self.WINH / 2) / (self.WINH * 0.78)) ** 2) - 0.30).clamp(0, 1).pow(1.4))[None].to(DT)
        self.dist_logo = torch.sqrt((xw - self.WINW / 2) ** 2 + (yw - self.WINH / 2) ** 2)[None].to(DT)
        self.tags = {}
        self.cuts = []
        for sid, tok, nth, off, dur, typ, r0, r1, grade, tag in cfg["cutaways"]:
            sc = c.scene_of(sid)[0]
            s = c.w_(sc, tok, nth) + off
            self.cuts.append(dict(s=s, e=s + dur, typ=typ, r0=r0, r1=r1, grade=grade, tag=tag, sc=sc))
        for i in range(len(self.cuts) - 1): assert self.cuts[i]["e"] <= self.cuts[i + 1]["s"] - 0.3, ("cutaways muy juntos", i, self.cuts[i], self.cuts[i + 1])
        # capítulos
        self.chapters = []
        for i, (sid, title, sub) in enumerate(cfg["chapters"]):
            sc = c.scene_of(sid)[0]
            a = c.SC[sc]["o0"]
            nxt = [c.SC[k]["o0"] for k in sorted(c.SC) if k > sc]
            b = nxt[0] if nxt else c.END0 / FPS
            self.chapters.append((i + 1, title, sub, a, b))
        self.chap_spr = {i: (lambda v: (spr_t(v[0]), v[1]))(G.chip_sprite(n, t, s)) for i, (n, t, s, a, b) in enumerate(self.chapters)}
        self.last = max(c.SC)
        self.whips_f = [int(round(c.SC[k]["o0"] * FPS)) for k in c.SC if k >= 2]
        self.chunk_cache = {}
        self.keys_range = [(k["s"], k["e"]) for k in c.CHUNKS if k["key"] and k["e"] - k["s"] >= 0.45]
        self.end0 = c.END0

    # ---- cámara
    def punch(self, t):
        a = 0.0
        for s, e in self.keys_range:
            if s <= t < e: a = max(a, 0.08)
            elif e <= t < e + 0.15: a = max(a, 0.08 * (1 - ease((t - e) / 0.15)))
        return 1 + a

    def zoom(self, n, it, t):
        c = self.c
        if t < c.hook_end: return 1.0 * (1 + 0.012 * (t / max(1e-3, c.hook_end))) * 1.12
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        return ZCYC[it["shot"] % len(ZCYC)] * (1 + 0.012 * tt) * ((1 + 0.04 * (1 - ease(tt / 0.35))) if n - t0 < 12 else 1.0) * self.punch(t)

    # ---- recuadro de fotos
    def photo_content(self, name, r0, r1, u):
        p = self.photos[name]
        cx = r0[0] + (r1[0] - r0[0]) * u; top = r0[1] + (r1[1] - r0[1]) * u; w = r0[2] + (r1[2] - r0[2]) * u
        h = w * self.WINH / self.WINW
        cx = min(max(cx, w / 2), p["w"] - w / 2); top = min(max(top, 0), p["h"] - h)
        cy = top + h / 2
        th = torch.tensor([[w / p["w"], 0, 2 * cx / p["w"] - 1], [0, h / p["h"], 2 * cy / p["h"] - 1]], dtype=torch.float32, device=dev).view(1, 2, 3)
        grid = F.affine_grid(th, (1, 3, self.WINH, self.WINW), align_corners=False)
        return F.grid_sample(p["t"].float(), grid, mode="bilinear", padding_mode="border", align_corners=False).to(DT)[0]

    def logo_content(self, u, t):
        z = 1.0 + 0.08 * u
        lw, lh = self.logo.shape[3], self.logo.shape[2]
        sc = 470.0 / lw * z
        sx, sy = self.WINW / (lw * sc), self.WINH / (lh * sc)
        th = torch.tensor([[sx, 0, 0], [0, sy, 0]], dtype=torch.float32, device=dev).view(1, 2, 3)
        grid = F.affine_grid(th, (1, 3, self.WINH, self.WINW), align_corners=False)
        out = F.grid_sample(self.logo.float(), grid, mode="bilinear", padding_mode="border", align_corners=False).to(DT)[0]
        inside = ((grid[0, ..., 0].abs() <= 1) & (grid[0, ..., 1].abs() <= 1)).to(DT)[None]
        gl = torch.exp(-((((self.xw - self.WINW / 2) / 440) ** 2) + (((self.yw - self.WINH / 2) / 300) ** 2)))[None].to(DT)
        img = (out * inside + self.logo_bg * (1 - inside)) * (1 + 0.20 * gl)
        for k in range(3):
            ph = (t * 0.45 + k / 3) % 1.0
            r = 300 * 0.82 + 300 * ph
            img = img + torch.exp(-((self.dist_logo - r) / 2.6) ** 2) * (1 - ph) * 0.20
        return img.clamp(0, 1)

    def grade_photo(self, x, mode):
        g = x.mean(0, keepdim=True)
        if mode == "gloom":
            y = g + (x - g) * 0.48
            y = y * torch.tensor([0.92, 0.97, 1.06], device=dev).view(3, 1, 1).to(DT) * 0.90
            y = (y - 0.5) * 1.10 + 0.5
        else:
            y = (x - 0.5) * 1.07 + 0.5
            y = g + (y - g) * 1.10
        return (y * self.vig_win).clamp(0, 1)

    def tag_spr(self, text):
        if text not in self.tags:
            sp, pad = G18.window_tag(text); self.tags[text] = (spr_t(sp), pad)
        return self.tags[text]

    def draw_cutaway(self, base, cu, t):
        a = t - cu["s"]; dur = cu["e"] - cu["s"]
        pout = ease((a - (dur - 0.26)) / 0.26)
        vis = min(1.0, a / 0.16) * (1 - pout)
        sc = (0.86 + 0.14 * min(1.0, easeb(a / 0.36))) * (1 - 0.05 * pout)
        bg = gblur(base[None], 26)[0] * 0.42 + self.navyt * 0.58
        out = base * (1 - vis) + bg * vis
        u = ease(a / dur)
        cont = self.logo_content(u, t) if cu["typ"] == "logo" else self.grade_photo(self.photo_content(cu["typ"], cu["r0"], cu["r1"], u), cu["grade"])
        if cu["tag"]:
            ts, tpad = self.tag_spr(cu["tag"])
            cont = cont.clone()
            ta = easeo((a - 0.35) / 0.3)
            blend(cont, ts, 24 - tpad + 28 * (1 - ta), self.WINH - 52 - 24 - tpad, ta)
        WP = self.wpad
        hp = torch.zeros(3, self.WINH + 2 * WP, self.WINW + 2 * WP, device=dev, dtype=DT)
        hp[:, WP:WP + self.WINH, WP:WP + self.WINW] = cont
        m = self.wmask
        rgb = hp * m + self.wframe[:3] * (1 - m)
        al = m + self.wframe[3:4] * (1 - m)
        spr = scaled(torch.cat([rgb, al], 0), sc)
        h, w = spr.shape[1:]
        blend(out, spr, G18.WINCX - w / 2, G18.WINCY - h / 2, vis)
        return out

    def cutaway_at(self, t):
        for cu in self.cuts:
            if cu["s"] <= t < cu["e"] + 0.02: return cu
        return None

    # ---- cards
    def chapter_bar(self, w, idx, frac):
        n = len(self.chapters); gap = 8; sw = (w - gap * (n - 1)) / n
        im = Image.new("RGBA", (w, 12), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for i in range(n):
            x0 = i * (sw + gap)
            d.rounded_rectangle((x0, 2, x0 + sw, 9), radius=3, fill=(255, 255, 255, 95))
            f_ = 1.0 if i < idx else (min(1.0, frac) if i == idx else 0.0)
            if f_ > 0: d.rounded_rectangle((x0, 2, x0 + max(7, sw * f_), 9), radius=3, fill=G.RED + (255,))
        return spr_t(np.asarray(im).copy())

    def draw_cards(self, fr, t):
        for i, (num, title, sub, a, b) in enumerate(self.chapters):
            s_, e_ = a + 0.12, a + 2.45
            if not (s_ <= t < e_ + 0.34): continue
            spr, pad = self.chap_spr[i]; w = spr.shape[2]
            if t < e_: off = -(w + 40) * (1 - easeb((t - s_) / 0.40)); al = min(1.0, (t - s_) / 0.12)
            else: p = ease((t - e_) / 0.30); off = -(w + 40) * p; al = 1 - p
            x = SAFE["left"] - pad + off
            blend(fr, spr, x, X.LANE_Y - pad, al)
            blend(fr, self.chapter_bar(w - 2 * pad, i, (t - a) / max(1e-6, b - a)), x + pad, X.LANE_Y - 22, al)
        sc1 = self.c.SC[1]["o0"]
        la, le = sc1 + 0.55 + 2.7, sc1 + 0.55 + 5.2                        # placa blanca de nombre, después del primer capítulo
        if la <= t < le + 0.4:
            p_in = easeo((t - la) / 0.45); p_out = ease((t - le) / 0.30) if t >= le else 0.0
            blend(fr, self.name, SAFE["left"] - 20, X.LANE_Y - 20 + 90 * (1 - p_in) + 90 * p_out, (1 - p_out) * min(1.0, (t - la) / 0.15))

    def draw_bubble(self, fr, t):
        c = self.c
        a0, a1 = 0.10, c.hook_end - 0.08
        if not (a0 <= t < a1 + 0.22): return
        pop = easeb((t - a0) / 0.30); out = 1 - ease((t - a1) / 0.22) if t >= a1 else 1.0
        s_ = max(0.0, pop * out)
        nvis = sum(1 for w in self.hook_words if t >= w["s"] - 0.02)
        spr, tx, ty = self.bubs[min(nvis, len(self.bubs) - 1)]
        if s_ > 0.02: blend(fr, scaled(spr, s_), self.bub_tip[0] - tx * s_, self.bub_tip[1] - ty * s_, min(1.0, (t - a0) / 0.08))

    def chunk_spr(self, ci):
        if ci not in self.chunk_cache:
            k = self.c.CHUNKS[ci]; fl = k["flags"]
            self.chunk_cache[ci] = spr_t(two_rows(lambda ws, j0: bar_sprite(ws, fl[j0:j0 + len(ws)]), k["words"]))
        return self.chunk_cache[ci]

    def draw_captions(self, fr, t):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]:
                spr = self.chunk_spr(ci); age = (t - k["s"]) * FPS
                s2 = scaled(spr, 0.94 + 0.06 * ease(age / 4))
                blend(fr, s2, CAPX - s2.shape[2] / 2, 1190 - s2.shape[1] / 2, min(1.0, (age + 1) / 3))
                break

    # ---- fotograma
    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        z = self.zoom(n, it, t)
        x = warp_src(src, c.cam.theta(f, z, 540.0, 700.0, ext_y=0.0), ext_bg=self.navyt.expand(3, H, W), fade=(0.985, 0.03))
        x = grade_color(x) * self.vig
        x = x * (1 - self.shade) + self.navyt * self.shade
        x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.005).clamp(0, 1)
        cu = self.cutaway_at(t)
        if cu is not None: x = self.draw_cutaway(x, cu, t)
        if t >= c.SC[1]["o0"] + 0.2: blend(x, self.wmark, SAFE["right"] - self.wmark.shape[2], 276, ease((t - c.SC[1]["o0"] - 0.2) / 0.4))
        if t < c.hook_end: self.draw_bubble(x, t)
        else: self.draw_captions(x, t)
        self.draw_cards(x, t)
        k, off = whip_k(n, self.whips_f)
        x = whip_filter(x, k, off)
        return exit_to_white(x, c.END0 - n)

    def whips(self): return self.whips_f

    def cues(self):
        c = self.c; out = [(0.10, "click", 0.40), (0.14, "swish", 0.26)]
        for f in self.whips_f: out.append((f / FPS - 0.14, "whoosh", 0.40))
        for cu in self.cuts: out.append((cu["s"] - 0.02, "swish", 0.30))
        for (num, title, sub, a, b) in self.chapters: out.append((a + 0.12, "click", 0.22))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
