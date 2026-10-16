# Estilo nuevo 4 — LAS CLAVES: el video como lista numerada. Arriba a la izquierda "N CLAVES" con puntos de progreso (el actual
# en rojo con su número, los pasados con ✓); al empezar cada idea entra por el carril inferior una tarjeta grande con el número y
# el titular; el cierre blanco repasa las claves con ✓ encima de los íconos. Subtítulos clásicos (blanco + claves en dorado).
from styles.base import *

NAVY2 = (12, 26, 64)


class KeysEnd(Endcard):
    """cierre blanco + repaso de las claves"""
    def __init__(self, titles):
        super().__init__()
        self.rh = 76 if len(titles) <= 6 else 52                          # filas más bajas si hay muchas claves (todo dentro de la zona segura)
        big = len(titles) <= 6
        f = font("ExtraBold", 40 if big else 30); fh = font("Black", 30)
        self.head = spr_t(self.label("LO QUE DIJO", fh, RED))
        self.rows = []
        for i, t in enumerate(titles):
            hh = 64 if big else 46; r_ = hh - 12
            im = rgba(800, hh); d = ImageDraw.Draw(im)
            d.ellipse((0, 6, r_, 6 + r_), fill=RED + (255,))
            cx, cy = r_ / 2, 6 + r_ / 2
            d.line((cx - 12 * r_ / 52, cy, cx - 3 * r_ / 52, cy + 10 * r_ / 52), fill=(255, 255, 255, 255), width=5)
            d.line((cx - 3 * r_ / 52, cy + 10 * r_ / 52, cx + 13 * r_ / 52, cy - 12 * r_ / 52), fill=(255, 255, 255, 255), width=5)
            px0 = 40 if big else 30; px = px0; f = font("ExtraBold", px)
            while f.getlength(t) > 700 and px > 22: px -= 2; f = font("ExtraBold", px)
            d.text((r_ + 20, hh / 2), t, font=f, fill=NAVY2 + (255,), anchor="lm")
            self.rows.append(spr_t(np_(im)))

    @staticmethod
    def label(t, f, col):
        w = int(sum(f.getlength(ch) + 4 for ch in t)) + 8
        im = rgba(w, 44); d = ImageDraw.Draw(im); x = 4
        for ch in t: d.text((x, 22), ch, font=f, fill=col + (255,), anchor="lm"); x += f.getlength(ch) + 4
        return np_(im)

    def frame(self, t):
        fr = super().frame(t)
        n = len(self.rows)
        y0 = max(290, 830 - self.rh * n - 70)
        blend(fr, self.head, 120, y0, ease(t / 0.25))
        for i, r in enumerate(self.rows):
            a = ease((t - 0.10 - 0.12 * i) / 0.25)
            blend(fr, r, 120 - 30 * (1 - a), y0 + 62 + self.rh * i, a)
        return fr


class Style(Base):
    def init(self):
        c = self.c
        self.keys = []
        for b in self.beats:
            if not b["title"]: continue
            t0 = (self.first_a + 0.25) if b["o0"] <= self.first_a + 0.05 else b.get("a0", b["o0"]) + 0.2   # la clave entra cuando ella responde
            if b["role"] == "H" and b["o1"] <= self.first_a + 0.05: continue
            self.keys.append(dict(t0=t0, o0=b["o0"], title=b["title"].strip(), sub=b["sub"]))
        self.keys = self.keys[:10]
        N = len(self.keys)
        self.end = KeysEnd([k["title"] for k in self.keys])
        self.head = spr_t(self.head_sprite(N))
        self.cards = [spr_t(self.card_sprite(i + 1, k["title"], k["sub"])) for i, k in enumerate(self.keys)]
        self.dots = {}

    def qa_titles(self):
        return [(k["t0"], k["title"]) for k in self.keys]

    def head_sprite(self, N):
        f = font("Black", 30)
        t = f"{N} CLAVES"
        w = int(sum(f.getlength(ch) + 3 for ch in t)) + 36
        im = rgba(w, 52); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, 51), radius=12, fill=NAVY2 + (235,))
        x = 18
        for ch in t: d.text((x, 26), ch, font=f, fill=(255, 255, 255, 255), anchor="lm"); x += f.getlength(ch) + 3
        return np_(shadowed(im, blur=8, dy=3, alpha=0.4, pad=10))

    def dots_sprite(self, cur):
        N = len(self.keys); r = 22; gap = 14
        im = rgba(N * (2 * r + gap) + 10, 2 * r + 10); d = ImageDraw.Draw(im)
        fn = font("Black", 24)
        for i in range(N):
            x = 5 + i * (2 * r + gap)
            if i < cur:
                d.ellipse((x, 5, x + 2 * r, 5 + 2 * r), fill=(255, 255, 255, 240))
                d.line((x + 12, 5 + r, x + 19, 5 + r + 8), fill=RED + (255,), width=5); d.line((x + 19, 5 + r + 8, x + 32, 5 + r - 8), fill=RED + (255,), width=5)
            elif i == cur:
                d.ellipse((x - 3, 2, x + 2 * r + 3, 8 + 2 * r), fill=RED + (255,))
                d.text((x + r, 5 + r), str(i + 1), font=fn, fill=(255, 255, 255, 255), anchor="mm")
            else:
                d.ellipse((x, 5, x + 2 * r, 5 + 2 * r), outline=(255, 255, 255, 220), width=3, fill=(0, 0, 0, 90))
                d.text((x + r, 5 + r), str(i + 1), font=fn, fill=(255, 255, 255, 230), anchor="mm")
        return np_(shadowed(im, blur=6, dy=2, alpha=0.45, pad=8))

    def card_sprite(self, num, title, sub):
        fn, ft, fs = font("Black", 104), font("Black", 46), font("SemiBold", 28)
        Wc, Hc = 820, 150
        im = rgba(Wc, Hc); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, 150, Hc - 1), radius=22, fill=RED + (255,)); d.rectangle((130, 0, 150, Hc - 1), fill=RED + (255,))
        d.text((75, Hc / 2 + 4), str(num), font=fn, fill=(255, 255, 255, 255), anchor="mm")
        d.rounded_rectangle((150, 0, Wc - 1, Hc - 1), radius=22, fill=(252, 252, 254, 250)); d.rectangle((150, 0, 175, Hc - 1), fill=(252, 252, 254, 250))
        px = 46
        while ft.getlength(title) > Wc - 210 and px > 28: px -= 2; ft = font("Black", px)
        d.text((180, 58 if sub else Hc / 2), title, font=ft, fill=NAVY2 + (255,), anchor="lm")
        if sub: d.text((182, 108), sub, font=fs, fill=(96, 104, 128, 255), anchor="lm")
        return np_(shadowed(im, blur=14, dy=6, alpha=0.5, pad=18))

    def cur_key(self, t):
        k = -1
        for i, kk in enumerate(self.keys):
            if kk["t0"] <= t: k = i
        return k

    def decorate(self, x, n, it, t):
        c = self.c
        self.draw_wmark(x, t)
        k = self.cur_key(t)
        if t >= self.first_a:                                              # cabecera + puntos de progreso
            a = ease((t - self.first_a) / 0.4)
            blend(x, self.head, SAFE["left"] - 10, 266, a)
            if k not in self.dots: self.dots[k] = spr_t(self.dots_sprite(k))
            blend(x, self.dots[k], SAFE["left"] - 8, 336, a)
        self.draw_captions(x, t)
        la = 0.5 if self.first_a >= 2.5 else self.first_a + 0.55              # placa de nombre durante la pregunta (antes de la 1.ª clave)
        if la <= t < la + 3.2 and (not self.keys or t < self.keys[0]["t0"] - 0.05):
            p_in = easeo((t - la) / 0.45); p_out = ease((t - min(la + 2.8, self.keys[0]["t0"] - 0.35 if self.keys else la + 2.8)) / 0.30)
            blend(x, self.name, SAFE["left"] - 20, X.LANE_Y - 20 + 90 * (1 - p_in) + 90 * p_out, (1 - p_out) * min(1.0, (t - la) / 0.15))
        if k >= 0:                                                         # tarjeta grande de la clave (3.4 s)
            t0 = self.keys[k]["t0"]
            if t0 <= t < t0 + 3.8:
                p_in = easeo((t - t0) / 0.45); p_out = ease((t - t0 - 3.4) / 0.35)
                spr = self.cards[k]
                blend(x, spr, SAFE["left"] - 18 - 120 * (1 - p_in), X.LANE_Y - 22 + 60 * p_out, (1 - p_out) * min(1.0, (t - t0) / 0.12))
        return x

    def cues(self):
        c = self.c; out = []
        for kk in self.keys: out.append((kk["t0"] - 0.02, "swish", 0.26)); out.append((kk["t0"] + 0.30, "click", 0.18))
        out.append((self.first_a + 0.55, "swish", 0.26))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
