# Estilo nuevo 5 — LA CITA: gancho con la frase en grande (Georgia) sobre la imagen desenfocada, que aparece palabra por palabra al
# ritmo de la voz; después video limpio con subtítulos y, en cada idea, una tarjeta de CITA TEXTUAL (palabras reales de ella, entre
# comillas, firmada "— Lilian Samaniego"). Las citas salen de la transcripción, nunca se inventan ni se resumen.
from styles.base import *

INKN = (10, 16, 36)
CREAM = (248, 242, 230)


class Style(Base):
    hook_y = 560                                  # centro del texto del gancho (arriba de la cara; el control plantado lo baja a la cara)

    def init(self):
        c = self.c
        self.hook_words = [w for w in c.WORDS if w["sc"] == 0]
        self.hook_rep = self.scene_spk.get(0) == "R"
        self.hook_sprites = {}
        self.quote_cards = []
        for b in self.beats:
            if b["anchor_t"] is None or b["o0"] < self.first_a - 0.01 and b["role"] == "H" and b["o1"] <= self.first_a + 0.05: continue
            q = self.quote_for(b)
            if not q: continue
            q, t_anchor = q
            t0 = max(t_anchor - 0.3, b["o0"] + 0.4, self.first_a + 3.7)            # cuando ELLA dice la palabra (no el periodista)
            if t0 + 3.6 > c.END0 / FPS - 0.3 or t0 + 2.0 > b["o1"]: continue      # la cita aparece mientras esa idea todavía suena
            if self.quote_cards and t0 < self.quote_cards[-1][0] + 4.6: continue
            self.quote_cards.append((t0, spr_t(self.quote_sprite(q))))

    def quote_for(self, b):
        """frase TEXTUAL alrededor de la palabra ancla: empieza al inicio de una cláusula, termina en puntuación o antes de un
        conector (que, porque, y…); 3–10 palabras; si dos cláusulas cortas van juntas ("están garantizados, están protegidos") se unen"""
        ws = [w for w in self.c.WORDS if b["o0"] - 0.01 <= w["s"] < b["o1"] and self.scene_spk.get(w["sc"]) == "L"]
        idx = next((i for i, w in enumerate(ws) if P.norm(w["t"].strip("¿?¡!.,;:")).startswith(P.norm(b["anchor"])[:5])), None)
        if idx is None: return None
        CONN = {"que", "porque", "y", "a", "de", "en", "para", "como", "cuando", "pero", "si"}
        best = None
        for a in range(max(0, idx - 10), idx + 1):
            start_ok = a == 0 or ws[a - 1]["t"][-1] in ".?!,;"
            for z in range(idx, min(len(ws), a + 12)):
                n = z - a + 1
                if n < 3: continue
                last = ws[z]["t"][-1]
                nxt = P.norm(ws[z + 1]["t"]) if z + 1 < len(ws) else ""
                if P.norm(ws[z]["t"].strip(".,;?!")) in CONN: continue           # nunca termina en un conector
                end = 3.0 if last in ".?!" else 2.2 if last in ",;" else 1.2 if (nxt in CONN or not nxt) else 0.0
                sc = end + (2.0 if start_ok else 0.0) - 0.12 * abs(n - 6)
                if best is None or sc > best[0]: best = (sc, a, z, start_ok)
        if best is None: return None
        _, a, z, start_ok = best
        q = " ".join(w["t"] for w in ws[a:z + 1]).strip(" ,;")
        q = q[0].upper() + q[1:]
        if not start_ok: q = "…" + q[0].lower() + q[1:]
        if q[-1] not in ".?!": q += "…"
        return q, ws[idx]["s"]

    def quote_sprite(self, q):
        f = wfont("georgiaz", 46); fs = font("SemiBold", 24)
        lines = wrap("“" + q + "”", f, 660)
        lh = 58
        Wc = 800; Hc = 40 + lh * len(lines) + 56
        im = rgba(Wc, Hc); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, Wc - 1, Hc - 1), radius=22, fill=INKN + (232,))
        d.rectangle((0, 18, 8, Hc - 18), fill=RED + (255,))
        for i, ln in enumerate(lines): d.text((40, 30 + i * lh), ln, font=f, fill=CREAM + (255,))
        tag = "— " + self.B.NAME
        d.text((42, 30 + lh * len(lines) + 10), tag, font=fs, fill=GOLD + (255,))
        return np_(shadowed(im, blur=14, dy=6, alpha=0.5, pad=18))

    def hook_sprite(self, k):
        """frase del gancho hasta la palabra k (las siguientes en transparente para que el bloque no salte)"""
        ws = [w["t"] for w in self.hook_words]
        f = wfont("georgiab", 70)
        lines = wrap(" ".join(ws), f, 820)
        lh = 88
        im = rgba(900, lh * len(lines) + 160); d = ImageDraw.Draw(im)
        d.text((10, -10), "“", font=wfont("georgiab", 150), fill=RED + (255,))
        n = 0
        for i, ln in enumerate(lines):
            x = 30
            for wd in ln.split():
                a = 255 if n <= k else 40
                d.text((x, 120 + i * lh), wd, font=f, fill=CREAM + (a,)); x += f.getlength(wd + " "); n += 1
        lab = "LA PREGUNTA" if self.hook_rep else self.B.NAME.upper()
        fl = font("ExtraBold", 26)
        d.text((32, 120 + lh * len(lines) + 4), lab, font=fl, fill=GOLD + (255,))
        return np_(shadowed(im, blur=14, dy=5, alpha=0.6, pad=0))

    def decorate(self, x, n, it, t):
        c = self.c
        if t < c.hook_end + 0.10:                                          # gancho: cita en grande sobre la imagen desenfocada
            fade = 1 - ease((t - c.hook_end + 0.30) / 0.36) if t > c.hook_end - 0.30 else 1.0     # se va antes de que vuelva la cara
            bl = gblur(x[None], 22)[0] * 0.42
            x = x * (1 - fade) + bl * fade
            k = sum(1 for w in self.hook_words if w["s"] <= t + 0.05) - 1
            if k not in self.hook_sprites: self.hook_sprites[k] = spr_t(self.hook_sprite(k))
            spr = self.hook_sprites[k]
            blend(x, spr, 80, self.hook_y - spr.shape[1] / 2 + 40, fade * ease(t / 0.3))
            return x
        self.draw_wmark(x, t)
        card = next(((t0, spr) for t0, spr in self.quote_cards if t0 <= t < t0 + 3.9), None)
        self.cap_y = 1170 if card is None else min(1170, 1438 - card[1].shape[1] - 46)   # el subtítulo sube por encima de la cita
        self.draw_captions(x, t)
        self.draw_name(x, t)
        if card:                                                           # tarjeta de cita textual (3.6 s), apoyada en el borde de la zona segura
            t0, spr = card
            p_in = easeo((t - t0) / 0.45); p_out = ease((t - t0 - 3.5) / 0.35)
            blend(x, spr, SAFE["left"] - 18, 1452 - spr.shape[1] + 50 * (1 - p_in) + 40 * p_out, (1 - p_out) * min(1.0, (t - t0) / 0.15))
        return x

    def cues(self):
        c = self.c; out = [(0.02, "swish", 0.22)]
        for t0, _ in self.quote_cards: out.append((t0 - 0.02, "swish", 0.24))
        out.append((c.hook_end - 0.05, "whoosh", 0.26))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
