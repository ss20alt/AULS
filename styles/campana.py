# Estilo nuevo 7 — CAMPAÑA: sobrio, azul marino y dorado. Marco dorado fino alrededor de la imagen, degradado marino abajo,
# subtítulos en Georgia (claves en dorado), "actos" con numeral romano en una placa marina con filo dorado arriba a la izquierda,
# placa de nombre institucional y un barrido de luz dorada al cambiar de idea. Pensado para un candidato: claro, calmo, serio.
from styles.base import *

NAVY3 = (10, 20, 46)
GOLD2 = (222, 178, 92)
CREAM = (250, 244, 230)
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"]


class Style(Base):
    ext_color = NAVY3
    cap_y = 1262
    grain = 0.003
    show_name = False

    def init(self):
        c = self.c
        self.navy = tcolor(NAVY3)
        self.grad = (0.80 * sm(1030.0, 1460.0, yy_) + 0.15 * sm(1460.0, 1920.0, yy_)).clamp(0, 0.92).expand(H, W)[None].to(DT)
        fr = torch.zeros(1, H, W, device=dev)
        i0 = 30                                                              # marco dorado fino (inset)
        fr[:, i0:i0 + 3, i0:W - i0] = 1; fr[:, H - i0 - 3:H - i0, i0:W - i0] = 1
        fr[:, i0:H - i0, i0:i0 + 3] = 1; fr[:, i0:H - i0, W - i0 - 3:W - i0] = 1
        self.frame_m = (fr * 0.85).to(DT)
        self.gold = tcolor(GOLD2)
        self.acts, self.act_titles = [], []
        n = 0
        for b in self.beats:
            if not b["title"] or (b["role"] == "H" and b["o1"] <= self.first_a + 0.05): continue
            n += 1
            t0 = max(b.get("a0", b["o0"]), self.first_a) + 0.3                  # con la respuesta de ella; arriba: no choca con la placa (abajo)
            self.acts.append((t0, spr_t(self.act_sprite(ROMAN[min(n - 1, len(ROMAN) - 1)], b["title"]))))
            self.act_titles.append((t0, b["title"]))
        self.name_s = spr_t(self.name_sprite())
        self.sweeps = [int(round(b["o0"] * FPS)) for b in self.beats[1:]]

    def qa_titles(self):
        return list(self.act_titles)

    def act_sprite(self, num, title):
        fn, ft = wfont("georgiab", 30), wfont("georgiab", 40)
        t = title.strip()
        t = t[:1] + t[1:].lower() if not any(ch.isdigit() for ch in t) else t.title()
        px = 40
        while ft.getlength(t) > 470 and px > 26: px -= 2; ft = wfont("georgiab", px)
        w = int(ft.getlength(t)) + 130
        im = rgba(w, 76); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, 75), radius=14, fill=NAVY3 + (232,), outline=GOLD2 + (255,), width=2)
        d.ellipse((14, 14, 62, 62), outline=GOLD2 + (255,), width=2)
        d.text((38, 39), num, font=fn, fill=GOLD2 + (255,), anchor="mm")
        d.text((80, 39), t, font=ft, fill=CREAM + (255,), anchor="lm")
        return np_(shadowed(im, blur=10, dy=4, alpha=0.45, pad=12))

    def name_sprite(self):
        f1, f2 = font("Black", 40), wfont("georgiai", 30)
        n = self.B.NAME.upper()
        w1 = sum(f1.getlength(ch) + 4 for ch in n)
        w = int(max(w1, f2.getlength(self.B.ROLE))) + 40
        im = rgba(w, 120); d = ImageDraw.Draw(im)
        d.line((4, 4, 120, 4), fill=GOLD2 + (255,), width=4)
        x = 4
        for ch in n: d.text((x, 20), ch, font=f1, fill=CREAM + (255,)); x += f1.getlength(ch) + 4
        d.text((6, 74), self.B.ROLE, font=f2, fill=GOLD2 + (255,))
        return np_(shadowed(im, blur=10, dy=4, alpha=0.55, pad=12))

    def cap_sprite(self, k):
        rep = self.scene_spk.get(k["sc"]) == "R"
        if rep: return self.rep_sprite(k, f=wfont("georgiai", 46), fill=(206, 220, 244))
        f = wfont("georgiai", 50) if rep else wfont("georgiab", 54)
        words = k["words"]; flags = k.get("flags") or [False] * len(words)
        sp = f.getlength(" ")
        tw = sum(f.getlength(w) for w in words) + sp * (len(words) - 1)
        im = rgba(int(tw) + 60, 110); d = ImageDraw.Draw(im); x = 30
        for w, fl in zip(words, flags):
            col = (200, 214, 240) if rep else (GOLD2 if fl else CREAM)
            d.text((x, 22), w, font=f, fill=col + (255,), stroke_width=2, stroke_fill=(6, 10, 24, 255))
            x += f.getlength(w) + sp
        return np_(shadowed(im, blur=10, dy=4, alpha=0.75, pad=0))

    def look(self, x, n, t):
        x = grade_color(x, 1.03, 0.96)
        x = (x * 0.96 + 0.025).clamp(0, 1)                                   # luces suaves
        return x * self.vig

    def decorate(self, x, n, it, t):
        c = self.c
        x = x * (1 - self.grad) + self.navy * self.grad
        for s0 in self.sweeps:                                               # barrido de luz dorada (diagonal) al cambiar de idea
            k = n - s0
            if 0 <= k < 14:
                pos = -400 + (W + 1600) * (k / 14)
                band = torch.exp(-(((xx_ + 0.45 * yy_) - pos) / 140.0) ** 2)[None].to(DT) * 0.22 * (1 - k / 14)
                x = (x + self.gold * band).clamp(0, 1)
        x = x * (1 - self.frame_m) + self.gold * self.frame_m
        self.draw_wmark(x, t)
        self.draw_captions(x, t)
        la = self.first_a + 0.5
        if la <= t < la + 3.3:
            a = ease((t - la) / 0.5) * (1 - ease((t - la - 2.9) / 0.4))
            blend(x, self.name_s, SAFE["left"] - 8, 1312 + 20 * (1 - ease((t - la) / 0.6)), a)
        for t0, spr in self.acts:
            if t0 <= t < t0 + 3.0:
                a = ease((t - t0) / 0.4) * (1 - ease((t - t0 - 2.6) / 0.4))
                blend(x, spr, SAFE["left"] - 10 - 40 * (1 - ease((t - t0) / 0.5)), 380, a)
        return x

    def cues(self):
        c = self.c; out = []
        for s0 in self.sweeps: out.append((s0 / FPS - 0.05, "swish", 0.16))
        for t0, _ in self.acts: out.append((t0, "chime", 0.10))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.28)); out.append((c.END0 / FPS + 0.28, "chime", 0.30))
        return out
