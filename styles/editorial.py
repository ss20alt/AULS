# Estilo nuevo 6 — EDITORIAL: papel crema de revista; el video es una tarjeta grande de bordes redondeados con sombra (la cara en el
# centro de la tarjeta); arriba, la sección ("EL DATO", "LA PREGUNTA"…) y el titular de cada idea en Georgia con un resaltador
# amarillo que lo barre; contador de página "02 / 05"; cambio de idea = la tarjeta entra deslizándose como una página nueva.
from styles.base import *

PAPER = (244, 239, 229)
INKN = (14, 22, 48)
CX0, CY0, CW, CH = 60, 430, 960, 990          # tarjeta de video (y 430–1420, dentro de la zona segura)
KIND_LAB = {"pregunta": "LA PREGUNTA", "dato": "EL DATO", "mensaje": "EL MENSAJE", "cierre": "EL MENSAJE", "ataque": "LA RESPUESTA",
            "denuncia": "LA DENUNCIA", "logro": "SU TRABAJO", "propuesta": "LA PROPUESTA"}


class Style(Base):
    anchor = (540.0, 800.0)
    zcyc = [1.22, 1.30, 1.25, 1.33]
    cap_x, cap_y = 540, 1330
    grain = 0.0
    show_name = False

    def init(self):
        c = self.c
        g = torch.Generator(device="cpu").manual_seed(3)
        tex = (torch.rand(1, H // 4, W // 4, generator=g) - 0.5).to(dev)
        tex = F.interpolate(tex[None], size=(H, W), mode="bilinear")[0].to(DT) * 0.035
        self.paper = (tcolor(PAPER).expand(3, H, W) + tex).clamp(0, 1)
        m = torch.zeros(1, H, W, device=dev)
        m[:, CY0:CY0 + CH, CX0:CX0 + CW] = 1
        r = 34                                                               # esquinas redondeadas
        for (cx, cy) in ((CX0 + r, CY0 + r), (CX0 + CW - r, CY0 + r), (CX0 + r, CY0 + CH - r), (CX0 + CW - r, CY0 + CH - r)):
            box = (slice(None), slice(cy - r if cy < CY0 + CH / 2 else cy, cy if cy < CY0 + CH / 2 else cy + r),
                   slice(cx - r if cx < CX0 + CW / 2 else cx, cx if cx < CX0 + CW / 2 else cx + r))
            yy = torch.arange(H, device=dev)[box[1]][:, None].float(); xx = torch.arange(W, device=dev)[box[2]][None, :].float()
            m[box] = ((((yy - cy) ** 2 + (xx - cx) ** 2).sqrt() <= r).float())[None]
        self.mask = m.to(DT)
        self.shadow = (gblur(torch.roll(m, shifts=(18, 0), dims=(1, 2))[None].to(DT), 22)[0] * 0.30)
        self.bottom = (0.55 * sm(1180.0, 1420.0, yy_)).expand(H, W)[None].to(DT)     # pie de tarjeta oscuro para el subtítulo
        ff = font("SemiBold", 22); im = rgba(960, 40); d = ImageDraw.Draw(im)       # pie de página de revista (decorativo)
        d.line((0, 6, 960, 6), fill=(196, 188, 172, 255), width=2)
        d.text((0, 26), "CONFERENCIA DE PRENSA", font=ff, fill=(150, 142, 128, 255), anchor="lm")
        d.text((960, 26), self.B.HANDLE, font=ff, fill=(150, 142, 128, 255), anchor="rm")
        self.footer = spr_t(np_(im))
        self.qa_decor = [self.footer]                                         # pie decorativo: fuera de la zona segura a propósito
        # titulares por idea
        acr = {w["t"].strip(".,¿?¡!") for w in c.WORDS if w["t"].strip(".,¿?¡!").isupper() and len(w["t"].strip(".,¿?¡!")) >= 2}
        self.pages = [(0.0, "LA SENADORA", self.B.NAME)]
        slides = []
        for b in self.beats:
            if not b["title"]: continue
            if b["role"] == "H" and b["o1"] <= self.first_a + 0.05: continue      # gancho del periodista: sin página propia
            t0 = max(b.get("a0", b["o0"]), self.first_a + 3.0)                     # la página cambia cuando ella responde
            self.pages.append((t0, KIND_LAB.get(b["kind"], "LA DECLARACIÓN"), self.sentence_case(b["title"], acr)))
            slides.append(max(b["o0"], self.first_a + 3.0))                         # la página (tarjeta) cambia con el tema; el titular, con la respuesta
        self.n_pages = len(self.pages) - 1
        self.spr = [self.head_sprites(i, lab, tt) for i, (t0, lab, tt) in enumerate(self.pages)]
        self.slide_at = [int(round(t0 * FPS)) for t0 in slides[1:]]

    def qa_titles(self):
        return [(t0, tt) for t0, lab, tt in self.pages[1:]]

    @staticmethod
    def sentence_case(t, acr):
        out = []
        for i, w in enumerate(t.split()):
            core = w.strip(".,¿?¡!")
            if core in acr: out.append(w)
            else:
                lw = w.lower()
                if i == 0: j = next((k for k, ch in enumerate(lw) if ch.isalpha()), 0); lw = lw[:j] + lw[j].upper() + lw[j + 1:]
                out.append(lw)
        return " ".join(out)

    def head_sprites(self, i, lab, title):
        fl, ft, fp = font("ExtraBold", 22), wfont("georgiab", 56), font("Bold", 22)
        px = 56
        while ft.getlength(title) > 900 and px > 34: px -= 2; ft = wfont("georgiab", px)
        im = rgba(980, 150); d = ImageDraw.Draw(im)
        x = 4
        for ch in lab: d.text((x, 14), ch, font=fl, fill=RED + (255,), anchor="lm"); x += fl.getlength(ch) + 4
        if i > 0:
            pg = f"{i:02d} / {self.n_pages:02d}"
            d.text((960, 14), pg, font=fp, fill=(110, 116, 136, 255), anchor="rm")
        lab_s = np_(im)
        tw = int(ft.getlength(title)) + 16
        im2 = rgba(tw + 20, 96); d2 = ImageDraw.Draw(im2)
        d2.text((10, 48), title, font=ft, fill=INKN + (255,), anchor="lm")
        hl = rgba(tw + 20, 96); dh = ImageDraw.Draw(hl)
        dh.rectangle((2, 50, tw + 12, 84), fill=(255, 214, 90, 235))           # resaltador (barrido en el tiempo)
        return spr_t(lab_s), spr_t(np_(im2)), spr_t(np_(hl))

    def page_at(self, t):
        k = 0
        for i, (t0, _, _) in enumerate(self.pages):
            if t0 <= t: k = i
        return k

    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        v = self.video(n, it, rd)
        v = grade_color(v, 1.05, 1.06)
        v = v * (1 - self.bottom)
        dx = 0
        for s0 in self.slide_at:                                            # página nueva: la tarjeta entra deslizándose
            k = n - s0
            if 0 <= k < 10: dx = int(1100 * (1 - easeo(k / 10)))
        shd = self.shadow
        if dx: shd = torch.roll(shd, shifts=dx, dims=2); shd[:, :, :dx] = 0          # sin "vuelta" de la sombra por el borde
        out = self.paper * (1 - shd)
        mk = self.mask
        layer = v
        if dx:
            mk = torch.roll(mk, shifts=dx, dims=2); mk[:, :, :dx] = 0
            layer = torch.roll(v, shifts=dx, dims=2)
        out = out * (1 - mk) + layer * mk
        # watermark dentro de la tarjeta (arriba a la derecha) + subtítulos dentro de la tarjeta
        if not dx:
            t0w = self.first_a + 0.2
            if t >= t0w: blend(out, self.wmark, CX0 + CW - self.wmark.shape[2] - 24 - 130, CY0 + 22, ease((t - t0w) / 0.4))
            self.draw_captions(out, t)
        blend(out, self.footer, CX0, CY0 + CH + 40)
        # cabecera editorial
        k = self.page_at(t)
        lab, tit, hl = self.spr[k]
        t0 = self.pages[k][0]
        a = ease((t - t0) / 0.35) if k > 0 or t > 0.05 else 1.0
        blend(out, lab, CX0 - 4, 268, a)
        p = easeo((t - t0 - 0.15) / 0.55)
        if p > 0:
            w = int(hl.shape[2] * p)
            if w > 2: blend(out, hl[:, :, :w], CX0 - 14, 308, a)
        blend(out, tit, CX0 - 14, 308 - 8 * (1 - a), a)
        return exit_to_white(out, self.end0 - n)

    def cues(self):
        c = self.c; out = []
        for s0 in self.slide_at: out.append((s0 / FPS - 0.05, "swish", 0.30))
        for t0, _, _ in self.pages[1:2]: out.append((t0 + 0.1, "click", 0.18))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
