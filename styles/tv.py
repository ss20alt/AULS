# Estilo nuevo 3 — TV NOTICIAS: gráfica de canal de noticias. Mosca "CONFERENCIA DE PRENSA" arriba a la izquierda, zócalo de dos
# pisos en el carril de las tarjetas (etiqueta roja + titular de cada idea que cambia con un giro), cinta inferior con los titulares
# corriendo, subtítulos encima del zócalo. El primer zócalo presenta a la senadora (nombre + cargo), como un súper de TV.
from styles.base import *

BX, BY = SAFE["left"], 1298            # zócalo
BW = 830
NAVY2 = (12, 26, 64)


class Style(Base):
    cap_y = 1196
    grain = 0.0
    show_name = False

    def init(self):
        c = self.c
        self.bug = spr_t(self.bug_sprite())
        self.items = []                                                    # (t0, etiqueta, titular)
        self.items.append((0.0, "EN CONFERENCIA", f"{self.B.NAME.upper()} RESPONDE"))
        self.items.append((self.first_a, self.B.ROLE.upper(), self.B.NAME.upper()))
        t_name_end = self.first_a + 3.6
        for b in self.beats:
            if not b["title"]: continue
            a0 = b.get("a0", b["o0"])                                         # el titular cambia cuando ella responde
            if b["kind"] == "pregunta" and a0 - b["o0"] > 1.0 and b["o0"] > t_name_end:   # mientras pregunta el periodista: zócalo neutro
                self.items.append((b["o0"] + 0.15, "PREGUNTA", "LA PRENSA CONSULTA"))
            t0 = max(a0 + 0.25, t_name_end) if a0 < t_name_end else a0 + 0.25
            lab = {"pregunta": "RESPONDE", "ataque": "DURO MENSAJE", "denuncia": "DENUNCIA", "dato": "DATO", "mensaje": "MENSAJE",
                   "cierre": "MENSAJE", "logro": "SU TRABAJO", "propuesta": "PROPUESTA"}.get(b["kind"], "DECLARACIÓN")
            if t0 < c.END0 / FPS - 1.5: self.items.append((t0, lab, b["title"].strip()))
        self.items.sort(key=lambda x: x[0])
        self.spr = [spr_t(self.banner_sprite(lab, txt)) for _, lab, txt in self.items]
        heads = [txt for _, lab, txt in self.items[2:] if lab != "PREGUNTA"] or [self.B.ROLE.upper()]
        self.ticker = spr_t(self.ticker_sprite("   •   ".join(heads + [self.B.HANDLE])))

    def qa_titles(self):
        return [(t0, txt) for t0, lab, txt in self.items[2:] if lab != "PREGUNTA"]

    # ---------------------------------------------------------------- piezas
    def bug_sprite(self):
        f = font("ExtraBold", 24)
        t = "CONFERENCIA DE PRENSA"
        w = int(sum(f.getlength(ch) + 2 for ch in t)) + 64
        im = rgba(w, 50); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, 49), radius=10, fill=RED + (245,))
        d.ellipse((18, 18, 32, 32), fill=(255, 255, 255, 255))
        x = 44
        for ch in t: d.text((x, 25), ch, font=f, fill=(255, 255, 255, 255), anchor="lm"); x += f.getlength(ch) + 2
        return np_(shadowed(im, blur=8, dy=3, alpha=0.45, pad=10))

    def banner_sprite(self, label, text):
        fl, fh = font("ExtraBold", 24), font("Black", 44)
        lw = int(sum(fl.getlength(ch) + 2 for ch in label)) + 34
        im = rgba(BW + 20, 150); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, lw, 40), fill=RED + (255,))                       # piso 1: etiqueta roja
        x = 17
        for ch in label: d.text((x, 21), ch, font=fl, fill=(255, 255, 255, 255), anchor="lm"); x += fl.getlength(ch) + 2
        d.rectangle((0, 40, BW, 112), fill=(250, 250, 252, 250))            # piso 2: titular
        d.rectangle((0, 40, 10, 112), fill=NAVY2 + (255,))
        t = text
        px = 44
        while fh.getlength(t) > BW - 50 and px > 28: px -= 2; fh = font("Black", px)
        d.text((28, 77), t, font=fh, fill=NAVY2 + (255,), anchor="lm")
        return np_(shadowed(im, blur=10, dy=4, alpha=0.40, pad=12))

    def ticker_sprite(self, text):
        f = font("Bold", 26)
        w = int(f.getlength(text + "   •   ")) + 2
        im = rgba(w, 36); d = ImageDraw.Draw(im)
        d.text((0, 18), text + "   •   ", font=f, fill=(255, 255, 255, 255), anchor="lm")
        return np_(im)

    # ---------------------------------------------------------------- dibujo
    def draw_banner(self, fr, t):
        k = max((i for i, it in enumerate(self.items) if it[0] <= t), default=None)
        if k is None: return
        t0 = self.items[k][0]
        p = easeo((t - t0) / 0.32)
        spr = self.spr[k]
        if p < 1 and k > 0:                                                  # giro: el anterior se pliega, el nuevo se despliega
            prev = self.spr[k - 1]
            if p < 0.5:
                h = max(1, int(prev.shape[1] * (1 - 2 * p)))
                blend(fr, F.interpolate(prev[None].float(), size=(h, prev.shape[2]), mode="bilinear")[0].to(DT), BX - 12, BY - 12 + (prev.shape[1] - h) / 2)
                return
            h = max(1, int(spr.shape[1] * (2 * p - 1)))
            blend(fr, F.interpolate(spr[None].float(), size=(h, spr.shape[2]), mode="bilinear")[0].to(DT), BX - 12, BY - 12 + (spr.shape[1] - h) / 2)
            return
        a = ease(t / 0.3) if k == 0 else 1.0
        blend(fr, spr, BX - 12 - 40 * (1 - a), BY - 12, a)

    def draw_ticker(self, fr, t):
        y0, y1 = BY + 116, BY + 148
        fr[:, y0:y1, BX:BX + BW] = fr[:, y0:y1, BX:BX + BW] * 0.12 + tcolor(NAVY2) * 0.88
        tw = self.ticker.shape[2]
        off = (t * 110) % tw
        for rep in range(3):
            x = BX + 12 - off + rep * tw
            if x > BX + BW: break
            sub_ = self.ticker[:, 2:34, :]
            # recorte a la caja del ticker
            xa, xb = max(int(x), BX + 8), min(int(x) + tw, BX + BW - 8)
            if xb <= xa: continue
            seg = sub_[:, :, xa - int(x):xb - int(x)]
            a = seg[3:4]
            fr[:, y0:y0 + 32, xa:xb] = fr[:, y0:y0 + 32, xa:xb] * (1 - a) + seg[:3] * a

    def decorate(self, x, n, it, t):
        c = self.c
        blend(x, self.bug, SAFE["left"] - 10, 266, ease(t / 0.4))
        self.draw_wmark(x, t)
        self.draw_captions(x, t)
        self.draw_banner(x, t)
        if t > 0.3: self.draw_ticker(x, t)
        for s0 in self.beat_starts:                                          # destello de canal al cambiar de tema
            k = n - s0
            if 0 <= k < 4: x = (x + (1 - k / 4) * 0.12).clamp(0, 1)
        return x

    def cues(self):
        c = self.c; out = [(0.05, "swish", 0.24)]
        for t0, lab, txt in self.items[1:]: out.append((t0 - 0.03, "whoosh", 0.20))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
