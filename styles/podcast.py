# Estilo nuevo 8 — PODCAST / AUDIOGRAMA: el video a pantalla completa con un "reproductor" de vidrio oscuro en el carril inferior:
# micrófono, nombre, capítulo actual (titular de la idea), barras que se mueven con la VOZ REAL (energía del audio recortado),
# barra de progreso y tiempo. Arriba a la izquierda el título del episodio (la historia elegida del mapa de contenido).
from styles.base import *

PX0, PY0, PW_, PH_ = SAFE["left"], 1292, SAFE["right"] - SAFE["left"], 148


class Style(Base):
    cap_y = 1188
    grain = 0.003
    show_name = False

    def init(self):
        c = self.c
        v = c.voice
        if v.ndim > 1: v = v.mean(1)
        nfr = c.TOTAL
        env = np.array([float(np.sqrt(np.mean(v[i * SPF:(i + 1) * SPF] ** 2) + 1e-12)) if i * SPF < len(v) else 0.0 for i in range(nfr)])
        ref = np.percentile(env[env > 0], 95) if (env > 0).any() else 1.0
        self.env = np.clip(env / (ref + 1e-9), 0, 1.15)
        self.panel = spr_t(self.panel_sprite())
        import content as C
        title = C.STORIES.get(c.cfg.get("angle"), {}).get("title", "Conferencia de prensa")
        self.ep = spr_t(self.episode_sprite(title))
        self.chap = {}
        self.chapters = [(max(b["o0"], self.first_a), b["title"]) for b in self.beats if b["title"] and not (b["role"] == "H" and b["o1"] <= self.first_a + 0.05)]
        self.timecache = {}
        self.white = tcolor((255, 255, 255)); self.red = tcolor(RED)

    def qa_titles(self):
        return [(t0, t) for t0, t in self.chapters]

    def panel_sprite(self):
        im = rgba(PW_, PH_); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, PW_ - 1, PH_ - 1), radius=30, fill=(10, 12, 20, 168))
        cx, cy = 62, 58                                                        # micrófono dibujado
        d.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=RED + (255,))
        d.rounded_rectangle((cx - 11, cy - 26, cx + 11, cy + 8), radius=11, fill=(255, 255, 255, 255))
        d.arc((cx - 19, cy - 14, cx + 19, cy + 16), 0, 180, fill=(255, 255, 255, 255), width=4)
        d.line((cx, cy + 16, cx, cy + 25), fill=(255, 255, 255, 255), width=4)
        d.line((cx - 10, cy + 25, cx + 10, cy + 25), fill=(255, 255, 255, 255), width=4)
        d.text((122, 36), self.B.NAME, font=font("ExtraBold", 32), fill=(255, 255, 255, 255), anchor="lm")
        return np_(im)

    def episode_sprite(self, title):
        f1, f2 = font("ExtraBold", 20), font("Black", 30)
        lab = "EPISODIO"
        w = int(max(sum(f1.getlength(ch) + 3 for ch in lab), f2.getlength(title))) + 60
        im = rgba(w, 92); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, 91), radius=18, fill=(10, 12, 20, 170))
        d.ellipse((20, 16, 34, 30), fill=RED + (255,))
        x = 44
        for ch in lab: d.text((x, 23), ch, font=f1, fill=(255, 196, 196, 255), anchor="lm"); x += f1.getlength(ch) + 3
        d.text((20, 62), title, font=f2, fill=(255, 255, 255, 255), anchor="lm")
        return np_(shadowed(im, blur=8, dy=3, alpha=0.4, pad=10))

    def chap_sprite(self, i, title):
        f = font("SemiBold", 24)
        t = f"Cap. {i + 1} · {title[:1] + title[1:].lower()}"
        im = rgba(560, 34); d = ImageDraw.Draw(im)
        d.text((0, 17), t, font=f, fill=(206, 210, 226, 255), anchor="lm")
        return np_(im)

    def time_sprite(self, s):
        f = font("Bold", 22)
        tot = int(round(self.c.END0 / FPS))
        t = f"{s // 60}:{s % 60:02d} / {tot // 60}:{tot % 60:02d}"
        im = rgba(150, 30); d = ImageDraw.Draw(im)
        d.text((150, 15), t, font=f, fill=(206, 210, 226, 255), anchor="rm")
        return np_(im)

    def draw_player(self, x, n, t):
        blend(x, self.panel, PX0, PY0, ease(t / 0.3))
        k = max((i for i, (t0, _) in enumerate(self.chapters) if t0 <= t), default=None)
        if k is not None:
            if k not in self.chap: self.chap[k] = spr_t(self.chap_sprite(k, self.chapters[k][1]))
            blend(x, self.chap[k], PX0 + 122, PY0 + 56, ease((t - self.chapters[k][0]) / 0.3))
        # barras de voz (historia de la energía real, desplazándose)
        nb, bw, gap = 18, 9, 6                                               # a la derecha del nombre (nunca encima del texto)
        bx0 = PX0 + PW_ - nb * (bw + gap) - 22
        for j in range(nb):
            idx = n - (nb - 1 - j) * 2
            e = self.env[idx] if 0 <= idx < len(self.env) else 0.0
            h = int(6 + 46 * min(1.0, e))
            y0 = PY0 + 40 - h // 2
            col = self.red if j >= nb - 3 else self.white
            x[:, y0:y0 + h, bx0 + j * (bw + gap):bx0 + j * (bw + gap) + bw] = col * 0.95 + x[:, y0:y0 + h, bx0 + j * (bw + gap):bx0 + j * (bw + gap) + bw] * 0.05
        # progreso + tiempo
        p = min(1.0, n / max(1, self.end0))
        y = PY0 + PH_ - 30
        x0b, x1b = PX0 + 122, PX0 + PW_ - 190
        x[:, y:y + 6, x0b:x1b] = x[:, y:y + 6, x0b:x1b] * 0.4 + 0.6 * 0.45
        xe = x0b + int((x1b - x0b) * p)
        x[:, y:y + 6, x0b:xe] = self.red
        x[:, y - 5:y + 11, max(x0b, xe - 8):xe + 8] = self.white
        s = int(t)
        if s not in self.timecache: self.timecache[s] = spr_t(self.time_sprite(s))
        blend(x, self.timecache[s], PX0 + PW_ - 170, y - 12)

    def decorate(self, x, n, it, t):
        self.draw_wmark(x, t)
        blend(x, self.ep, SAFE["left"] - 10, 266, ease(t / 0.4))
        self.draw_captions(x, t)
        self.draw_player(x, n, t)
        return x

    def cues(self):
        c = self.c; out = [(0.02, "click", 0.20)]
        for t0, _ in self.chapters[1:]: out.append((t0 - 0.02, "click", 0.16))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.30)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
