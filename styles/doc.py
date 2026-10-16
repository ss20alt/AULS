# Estilo nuevo 2 — DOCUMENTAL: franjas negras de cine, gradación de película (negros levantados, sombras frías, luces cálidas,
# grano y viñeta), acercamientos lentos sin golpes, subtítulos en Georgia itálica, rótulos de capítulo con numeral romano
# arriba a la izquierda (sobre la cabeza nunca), placa de nombre editorial y fundido a negro breve entre ideas.
from styles.base import *

TOP, BOT = 372, 1560                    # área de imagen; los rótulos y el sello van DENTRO de la franja superior (y 276–366, zona segura)
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"]
CREAM = (246, 238, 222)


class Style(Base):
    anchor = (540.0, 800.0)
    cap_x, cap_y = 495, 1400
    grain = 0.0

    def init(self):
        c = self.c
        self.bars = torch.ones(1, H, 1, device=dev, dtype=DT)
        self.bars[:, :TOP] = 0; self.bars[:, BOT:] = 0
        self.vig2 = make_vignette(0.55)
        self.lowshade = (0.78 * sm(1200.0, BOT, yy_)).expand(H, W)[None].to(DT)      # pie de imagen oscuro para el subtítulo (contraste ≥ 3:1)
        self.cache = {}
        # rótulos de capítulo (desde la segunda idea): numeral + título
        self.chap, self.chap_titles = [], []
        n = 0
        for b in self.beats:
            if not b["title"] or (b["role"] == "H" and b["o1"] <= self.first_a + 0.05): continue   # el gancho solo no cuenta como capítulo
            n += 1
            if b["o0"] <= self.first_a + 0.05: continue                     # la primera idea lleva la placa de nombre
            self.chap.append((b["o0"] + 0.35, spr_t(self.chapter_sprite(ROMAN[min(n - 1, len(ROMAN) - 1)], b["title"]))))
            self.chap_titles.append((b["o0"] + 0.35, b["title"]))
        self.name_s = spr_t(self.name_sprite())

    def qa_titles(self):
        return list(self.chap_titles)

    def chapter_sprite(self, num, title):
        """rótulo de capítulo en la franja negra: numeral dorado + título espaciado (como créditos de cine)"""
        f1, f2 = wfont("georgiab", 34), wfont("georgia", 36)
        tr = 5.0
        t = title.upper().strip("¿?")
        while sum(f2.getlength(ch) + tr for ch in t) > 470 and tr > 1.5: tr -= 0.5
        w = int(f1.getlength(num) + 30 + sum(f2.getlength(ch) + tr for ch in t)) + 12
        im = rgba(w, 60); d = ImageDraw.Draw(im)
        d.text((2, 8), num, font=f1, fill=GOLD + (255,))
        x = f1.getlength(num) + 16
        d.line((x, 30, x + 10, 30), fill=GOLD + (255,), width=2); x += 22
        for ch in t:
            d.text((x, 10), ch, font=f2, fill=CREAM + (255,)); x += f2.getlength(ch) + tr
        return np_(im)

    def name_sprite(self):
        f1, f2 = wfont("georgiab", 36), wfont("georgiai", 26)
        w = int(f1.getlength(self.B.NAME) + 24 + f2.getlength(self.B.ROLE)) + 12
        im = rgba(w, 60); d = ImageDraw.Draw(im)
        d.text((2, 8), self.B.NAME, font=f1, fill=CREAM + (255,))
        x = f1.getlength(self.B.NAME) + 12
        d.line((x, 18, x, 50), fill=GOLD + (255,), width=2)
        d.text((x + 12, 16), self.B.ROLE, font=f2, fill=(214, 204, 184, 255))
        if w > 560: return np_(im.resize((560, int(60 * 560 / w)), Image.LANCZOS))
        return np_(im)

    def zoom(self, n, it, t):
        c = self.c
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        base = 1.13 if it["shot"] % 2 == 0 else 1.19
        return base * (1 + 0.010 * tt)                                       # acercamiento lento y continuo, sin golpes

    def look(self, x, n, t):
        g = x.mean(0, keepdim=True)
        x = g + (x - g) * 0.82                                               # menos saturación
        x = (x - 0.5) * 1.10 + 0.5
        lum = g.clamp(0, 1)
        x = torch.cat([x[0:1] + 0.035 * lum - 0.012, x[1:2] + 0.008 * lum, x[2:3] + 0.030 * (1 - lum) - 0.020 * lum], 0)
        x = 0.045 + x * 0.94                                                 # negros levantados (película)
        if self.c.SC[0]["role"] == "H" and t < self.c.hook_end: x = to_bw(x, n, 1.15)
        x = x * self.vig2
        x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * 0.024).clamp(0, 1)
        return x

    def cap_sprite(self, k):
        if self.scene_spk.get(k["sc"]) == "R": return self.rep_sprite(k, f=wfont("georgiai", 44), fill=(214, 226, 246))
        f = wfont("georgiaz", 52)
        txt = " ".join(k["words"])
        return text_sprite([txt], f, fill=CREAM, stroke=3, stroke_fill=(18, 12, 6), shadow=0.85, pad=18)

    def draw_captions(self, fr, t):
        ci, k = self.chunk_at(t)
        if k is None: return
        if ci not in self.chunk_cache: self.chunk_cache[ci] = spr_t(self.cap_sprite(k))
        spr = self.chunk_cache[ci]; age = (t - k["s"]) * FPS
        a = min(1.0, (age + 1) / 5)
        s2 = spr if spr.shape[2] <= 900 else scaled(spr, 900 / spr.shape[2])
        blend(fr, s2, self.cap_x - s2.shape[2] / 2, self.cap_y - s2.shape[1] / 2, a)

    def decorate(self, x, n, it, t):
        c = self.c
        for s0 in self.beat_starts:                                          # fundido a negro breve entre ideas
            k = n - s0
            if -5 <= k < 6: x = x * (1 - 0.85 * (1 - abs(k + 0.5) / 5.5))
        x = x * (1 - self.lowshade)
        x = x * self.bars
        self.draw_wmark(x, t, y=280)
        self.draw_captions(x, t)
        la = self.first_a + 0.5
        if la <= t < la + 3.4:                                               # placa de nombre editorial (arriba a la izquierda)
            a = ease((t - la) / 0.5) * (1 - ease((t - la - 2.9) / 0.5))
            blend(x, self.name_s, SAFE["left"], 296 + 8 * (1 - ease((t - la) / 0.6)), a)
        for t0, spr in self.chap:
            if t0 <= t < t0 + 2.6:
                a = ease((t - t0) / 0.45) * (1 - ease((t - t0 - 2.1) / 0.5))
                blend(x, spr, SAFE["left"], 296 + 8 * (1 - ease((t - t0) / 0.6)), a)
        return x

    def cues(self):
        c = self.c; out = []
        for b in self.beats[1:]: out.append((b["o0"] - 0.05, "swish", 0.12))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.26)); out.append((c.END0 / FPS + 0.28, "chime", 0.30))
        return out
