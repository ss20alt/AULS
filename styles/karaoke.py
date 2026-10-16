# Estilo nuevo 1 — KARAOKE DINÁMICO: subtítulo grande en mayúsculas (2-4 palabras) donde la palabra que se está diciendo va
# dentro de una caja roja que salta de palabra en palabra; claves en amarillo; zoom que alterna fuerte en cada toma, golpe de zoom
# en las claves, destello + sacudida al cambiar de idea y barra de progreso arriba. Ritmo de TikTok, la cara siempre libre.
from styles.base import *

CAP_F = 80


class Style(Base):
    zcyc = [1.08, 1.24, 1.12, 1.27, 1.10, 1.22]
    cap_y = 1165
    grain = 0.004

    def init(self):
        self.kcache = {}
        self.bar_bg = tcolor((255, 255, 255))

    def zoom(self, n, it, t):
        c = self.c
        if t < c.hook_end: return 1.20 * (1 + 0.03 * (t / max(1e-3, c.hook_end)))
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        z = self.zcyc[it["shot"] % len(self.zcyc)] * (1 + 0.010 * tt)
        return z * self.punch(t, 0.10)

    def word_sprite(self, k, active, reporter):
        """todas las palabras del fragmento; la activa dentro de una caja roja"""
        f = font("Black", CAP_F if not reporter else 62)
        words = [w.upper() for w in k["words"]]
        sp = f.getlength(" ") * 0.9
        ws = [f.getlength(w) for w in words]
        padx, pady = 22, 12
        total = sum(ws) + sp * (len(words) - 1) + 2 * padx
        asc, desc = f.getmetrics(); hh = asc + desc
        im = Image.new("RGBA", (int(total) + 60, hh + 2 * pady + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x = 30 + padx
        for i, w in enumerate(words):
            if i == active:
                d.rounded_rectangle((x - padx * 0.7, 20 + pady * 0.2, x + ws[i] + padx * 0.7, 20 + hh + pady * 1.2), radius=16,
                                    fill=((40, 120, 220) if reporter else GOLD) + (255,))          # amarillo: se lee sobre el saco rojo
                d.text((x, 20 + pady), w, font=f, fill=((255, 255, 255) if reporter else (12, 12, 16)) + (255,))
            else:
                col = (255, 214, 90) if (k.get("flags") or [False] * len(words))[i] and not reporter else (255, 255, 255)
                d.text((x, 20 + pady), w, font=f, fill=col + (255,), stroke_width=8, stroke_fill=(10, 10, 14, 255))
            x += ws[i] + sp
        return np_(shadowed(im, blur=10, dy=6, alpha=0.55, pad=0))

    def draw_captions(self, fr, t):
        ci, k = self.chunk_at(t)
        hold = False
        if k is None:                                                      # pausa corta dentro de la frase: el texto se queda (sin palabra activa)
            CH = self.c.CHUNKS
            prev = max((i for i, x in enumerate(CH) if x["e"] <= t), default=None, key=lambda i: CH[i]["e"])
            if prev is None: return
            nxt = prev + 1 if prev + 1 < len(CH) else None
            if t - CH[prev]["e"] > 0.7 or nxt is None or CH[nxt]["sc"] != CH[prev]["sc"] or CH[nxt]["s"] - CH[prev]["e"] > 0.9: return
            ci, k, hold = prev, CH[prev], True
        ts = k.get("ts") or [k["s"]]
        act = -1 if hold else max(0, sum(1 for x in ts if x <= t + 0.03) - 1)
        rep = self.scene_spk.get(k["sc"]) == "R"
        key = (ci, -2 if rep else act)
        if key not in self.kcache: self.kcache[key] = spr_t(self.rep_sprite(k, px=50) if rep else self.word_sprite(k, act, rep))
        spr = self.kcache[key]
        age = (t - k["s"]) * FPS
        sc = 0.80 + 0.20 * easeb(age / 5)
        if hold: age = 99
        mw = 940 / spr.shape[2]                                            # nunca más ancho que la pantalla útil
        s2 = scaled(spr, min(sc, sc * mw))
        y = self.cap_y if not rep else self.cap_y + 10
        blend(fr, s2, self.cap_x - s2.shape[2] / 2, y - s2.shape[1] / 2, min(1.0, (age + 1) / 2))

    def decorate(self, x, n, it, t):
        c = self.c
        for s0 in self.beat_starts:                                        # cambio de idea: destello + sacudida
            k = n - s0
            if 0 <= k < 3: x = (x + (1 - k / 3) * 0.35).clamp(0, 1)
        self.draw_wmark(x, t)
        self.draw_captions(x, t)
        self.draw_name(x, t)
        p = min(1.0, n / max(1, self.end0))                                # barra de progreso arriba
        x[:, 252:260, 0:W] = x[:, 252:260, 0:W] * 0.55 + 0.45 * 0.12
        x[:, 252:260, 0:int(W * p)] = tcolor(RED)
        return x

    def video(self, n, it, rd, **kw):
        out = super().video(n, it, rd, **kw)
        for s0 in self.beat_starts:
            k = n - s0
            if 0 <= k < 5:
                dx, dy = shake(n, 9 * (1 - k / 5))
                out = torch.roll(out, shifts=(int(dy), int(dx)), dims=(1, 2))
        return out

    def cues(self):
        c = self.c; out = []
        for b in self.beats[1:]: out.append((b["o0"] - 0.03, "boom", 0.16)); out.append((b["o0"] - 0.10, "whoosh", 0.22))
        out.append((self.first_a + 0.55, "swish", 0.30))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
