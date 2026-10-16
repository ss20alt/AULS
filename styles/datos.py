# Estilo DATOS — para fuentes en formato PANEL (TV horizontal en baja resolución, p. ej. Senado TV): la persona en un recuadro
# fijo (el encuadre ya viene armado desde ingest --layout panel, sin zoom que entre y salga), arriba el titular de cada idea,
# abajo los subtítulos, y DATOS ANIMADOS cuando ella los menciona: números que cuentan hasta la cifra, comparaciones con barras,
# lista, línea de tiempo y tarjeta de noticia. Paleta bordó (la de sus infografías). Color natural: sin gradación ni grano.
# Cuando la transmisión deja de mostrarla (proyecta sus láminas), el recuadro pasa a un fondo hecho con SUS láminas en alta
# calidad (material del tema) y los datos se muestran en grande, centrados.
#   sources/<fuente>/datos.json = {"datos": [ {kind, trigger: [palabras], ...} ], "fondos": [ {desde, hasta, img} ]}
from styles.base import *
import json, os
import plan as P

WINE = (110, 26, 58)          # bordó de las infografías
WINE_D = (58, 12, 30)
ROSE = (246, 232, 237)
ROSE_D = (214, 170, 186)
INK2 = (40, 12, 24)
ALERT = (226, 48, 64)
CW = 820                      # ancho de las tarjetas: dentro de la zona segura (x 60–890)
FONDOS = {"rosa": (254, 171, 173), "rosa_fuerte": (240, 110, 124), "bordo": (110, 26, 58), "azul": (14, 34, 78), "rojo": (210, 30, 44),
          "blanco": (246, 246, 248)}          # medidos en las referencias (T15 rosa claro, T16 rosa fuerte) + colores de la casa
CX = (SAFE["left"] + SAFE["right"]) / 2


def fmt(n):
    """37825 -> 37.825 (como se escribe en Paraguay)"""
    return f"{int(round(n)):,}".replace(",", ".")


def spaced(d, xy, text, f, fill, tr=2.0, anchor="l"):
    x, y = xy
    if anchor == "m": x -= (sum(f.getlength(c) + tr for c in text) - tr) / 2
    for ch in text: d.text((x, y), ch, font=f, fill=fill, anchor="lm"); x += f.getlength(ch) + tr
    return x


def icon(kind, s, col=(255, 255, 255)):
    """íconos simples dibujados (sin archivos externos): lazo, alerta, documento, personas, calendario, mazo, noticia"""
    im = rgba(s, s); d = ImageDraw.Draw(im); c = tuple(col) + (255,); w = max(3, s // 14)
    if kind == "lazo":
        d.ellipse((s * .30, s * .06, s * .70, s * .50), outline=c, width=w * 2)
        d.line((s * .40, s * .44, s * .22, s * .94), fill=c, width=w * 2); d.line((s * .60, s * .44, s * .78, s * .94), fill=c, width=w * 2)
    elif kind == "alerta":
        d.polygon([(s * .5, s * .06), (s * .96, s * .90), (s * .04, s * .90)], outline=c, width=w)
        d.line((s * .5, s * .34, s * .5, s * .64), fill=c, width=w + 1); d.ellipse((s * .46, s * .72, s * .54, s * .80), fill=c)
    elif kind == "doc":
        d.rounded_rectangle((s * .18, s * .06, s * .82, s * .94), radius=s // 12, outline=c, width=w)
        for k in range(4): d.line((s * .30, s * (.28 + .16 * k), s * .70, s * (.28 + .16 * k)), fill=c, width=max(2, w - 1))
    elif kind == "personas":
        for cx, r, top in ((.34, .13, .14), (.68, .10, .30)):
            d.ellipse((s * (cx - r), s * top, s * (cx + r), s * (top + 2 * r)), fill=c)
            d.rounded_rectangle((s * (cx - r * 1.5), s * (top + 2 * r + .03), s * (cx + r * 1.5), s * .94), radius=s // 10, fill=c)
    elif kind == "calendario":
        d.rounded_rectangle((s * .08, s * .16, s * .92, s * .92), radius=s // 12, outline=c, width=w)
        d.line((s * .08, s * .36, s * .92, s * .36), fill=c, width=w)
        for i in range(3):
            for j in range(3): d.rectangle((s * (.2 + .22 * i), s * (.46 + .15 * j), s * (.32 + .22 * i), s * (.56 + .15 * j)), fill=c)
    elif kind == "mazo":
        d.polygon([(s * .52, s * .08), (s * .86, s * .42), (s * .70, s * .58), (s * .36, s * .24)], fill=c)
        d.line((s * .58, s * .46, s * .16, s * .88), fill=c, width=w * 2); d.rectangle((s * .10, s * .88, s * .62, s * .96), fill=c)
    return np_(im)


class Style(Base):
    grain = 0.0                                  # color natural y nítido (lo pidió el usuario)
    show_name = False
    cap_x, cap_y = CX, 1338

    # ---------------------------------------------------------------- preparación
    def init(self):
        c = self.c
        self.P = tuple(P.SRC.get("panel") or (0, 400, 1080, 840))
        px, py, pw, ph = self.P
        self.idt = torch.tensor([[1.0, 0, 0], [0, 1.0, 0]], device=dev).view(1, 2, 3)
        m = torch.ones(1, H, W, device=dev, dtype=DT); m[:, py:py + ph, px:px + pw] = 0          # fondo bordó con el hueco del recuadro
        gy = (yy_ / H).to(DT)[None]
        self.tint = (tcolor(WINE_D) * (1 - gy) + tcolor((20, 4, 12)) * gy) * m
        self.tint_a = (0.86 * m)
        fondo = c.cfg.get("fondo")                         # Senado sobre fondo LISO (referencias T15/T16: rosa en octubre)
        self.claro = False
        if fondo:
            col = FONDOS.get(str(fondo).lower()) or tuple(int(str(fondo).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
            self.tint = tcolor(col) * m; self.tint_a = 1.0 * m
            self.claro = (0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]) / 255 > 0.55       # fondo claro: los textos van oscuros
        line = rgba(W, 6); ImageDraw.Draw(line).rectangle((0, 0, W, 5), fill=ROSE_D + (255,))
        self.line = spr_t(np_(line))
        fade = np.zeros((90, W, 4), np.uint8); fade[..., :3] = WINE_D; fade[..., 3] = (np.linspace(0, 1, 90) ** 1.6 * 200).astype(np.uint8)[:, None]
        self.pfade = spr_t(fade)
        et = self.etiqueta()
        self.tag = spr_t(self.tag_sprite(et)) if et else None
        self.titles, self.cache, self.feet = {}, {}, {}
        spec = c.cfg.get("stats")
        if spec is None:                                   # los datos del tema viven con la fuente (sources/<fuente>/datos.json)
            pj = os.path.join(P.SRC["dir"], "datos.json")
            spec = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
        if isinstance(spec, list): spec = dict(datos=spec)
        if not spec.get("datos") and c.cfg.get("cifras", "auto") != "no":     # sin datos preparados (datos.json): las cifras de peso que
            spec = dict(spec, datos=self.cifras_auto(c.cfg.get("cifras", "auto")))   # ella dice, en la tarjeta de dato del estilo
        self.stats = self.resolve_stats(spec.get("datos", []))
        self.slides = self.resolve_slides(spec.get("fondos", []))
        self.qa_cover = [(s["t0"], s["t1"]) for s in self.stats if s["kind"] == "grande"] + [(a, b) for a, b, _ in self.slides]
        self.qa_decor = [self.tag] if self.tag is not None else []
        try:                                               # para el control final: tramos de láminas (sin cara, fondo casi quieto a propósito)
            declarar_tramos(c.dir, "laminas", [[a, b] for a, b, _ in self.slides], quietos=True)
            declarar_tramos(c.dir, "tv_sin_cara", self.tv_sin_cara(), quietos=True)   # la TV muestra una lámina fija (las cifras que ella pidió)
            tp = os.path.join(c.dir, "tramos_estilo.json"); te = json.load(open(tp))
            te["zona_imagen"] = [int(px), int(py), int(pw), int(ph)]            # el QA mide brillo/cara en el recuadro, no en el fondo bordó
            json.dump(te, open(tp, "w"), indent=1)
        except Exception as e: print("[datos] tramos:", e)

    def etiqueta(self):
        """placa de arriba: --etiqueta manda; si no, 'SENADO · SESIÓN dd/mm/aaaa' solo si es una sesión (ella habla a 'colegas',
        'senadores'…) y con la FECHA REAL de la toma (source.json); si no se sabe, sin fecha. Nunca una fecha fija."""
        et = self.c.cfg.get("etiqueta")
        if et is not None: return str(et).upper() or None
        f = P.SRC.get("fecha")
        fecha = f"{f[8:10]}/{f[5:7]}/{f[:4]}" if f and len(f) >= 10 else None
        txt = " ".join(w["t"] for w in self.c.WORDS).lower()
        pistas = sum(1 for k in ("senador", "senado", "colegas", "honorable", "bancada", "plenaria", "sesión", "cámara") if k in txt)
        if pistas >= 2: return "SENADO · SESIÓN " + fecha if fecha else "SENADO"
        return fecha

    def tv_sin_cara(self):
        """tramos en que la señal de TV no la muestra (panel.json: lámina, otra cámara), llevados al tiempo del video final.
        Es contenido (p. ej. la imagen de las cifras que ella pidió mostrar): el QA no lo cuenta como cara perdida ni congelado."""
        pj = os.path.join(P.SRC["dir"], "panel.json")
        sin = json.load(open(pj)).get("sin_cara", []) if os.path.exists(pj) else []
        out = []
        for a, b in sin:
            for it in self.c.SEGS:
                s0, s1 = it["fs"] / FPS, it["fe"] / FPS
                lo, hi = max(a, s0), min(b, s1)
                if hi - lo < 0.3: continue
                o = (it["out"] + it.get("pre", 0)) / FPS
                out.append([round(o + lo - s0, 2), round(o + hi - s0, 2)])
        return sorted(out)

    def cifras_auto(self, mode):
        """estadísticas que ella dice en el guion (cifras.py: con lo que cuentan; fechas, horas, edades, leyes y números chicos no),
        pocas y separadas, como tarjetas 'dato' sincronizadas con la palabra. Sin cifras de peso -> ninguna."""
        import cifras as CF
        W_ = self.c.WORDS
        hers = lambda sc: self.scene_spk.get(sc, "L") != "R"
        cands, vistas = [], set()
        for cd in CF.candidates(W_):
            if cd["pct"] or W_[cd["i0"]].get("sc") is None or not hers(W_[cd["i0"]]["sc"]): continue
            if len({W_[k].get("sc") for k in range(cd["i0"], min(cd["i1"], len(W_)))}) != 1: continue
            if (cd["value"], cd["label"]) in vistas: continue             # la misma cifra dos veces (gancho y después en contexto): una vez
            vistas.add((cd["value"], cd["label"])); cands.append(cd)
        sel = CF.pick(cands, lambda cd: cd["s"], dur=self.c.END0 / FPS, min_score=3.0 if mode == "mas" else 3.5, per_min=3.0 if mode == "mas" else 2.0)
        out = [dict(kind="dato", value=cd["value"], label=cd["label"], icon=cd.get("icon") or "documento", t0=W_[cd["i0"]]["s"], dur=4.6,
                    count_s=float(min(1.3, max(0.7, W_[cd["i0"]]["e"] - W_[cd["i0"]]["s"] + 0.45)))) for cd in sel]
        print("[datos] cifras automáticas:", [(fmt(x["value"]), x["label"], round(x["t0"], 1)) for x in out] or "ninguna")
        return out

    def qa_titles(self):
        return [(b.get("a0", b["o0"]), b["title"]) for b in self.beats if b.get("title")]

    # ---------------------------------------------------------------- en qué momento aparece cada dato (palabras del video)
    def resolve_stats(self, specs):
        norm = lambda s: P.norm(s)
        out, t_min = [], 0.0
        for sp in specs:
            trig = [norm(x) for x in sp.get("trigger", [])]
            t0 = sp["t0"] if "t0" in sp else next((w["s"] for w in self.c.WORDS if w["s"] + 1e-3 >= t_min and w.get("sc") is not None and norm(w["t"]) in trig), None)
            if t0 is None: print("[datos] sin momento para", sp.get("trigger")); continue
            t0 += sp.get("delay", 0.0)
            out.append(dict(sp, t0=t0, t1=t0 + sp.get("dur", 4.2))); t_min = t0 + 0.5
        out.sort(key=lambda s: s["t0"])
        ends = sorted(b["o0"] for b in self.beats) + [self.c.END0 / FPS]
        for s in out:                                        # cada dato termina con su idea (no se mete en la siguiente)
            nxt = next((e for e in ends if e > s["t0"] + 0.5), ends[-1])
            s["t1"] = min(s["t1"], nxt - 0.2)
        for a, b in zip(out, out[1:]):                       # nunca dos datos encimados
            if a["t1"] > b["t0"] - 0.15: a["t1"] = b["t0"] - 0.15
        print("[datos]", [(s["kind"], round(s["t0"], 1), round(s["t1"], 1)) for s in out])
        return out

    # ---------------------------------------------------------------- tramos en que la TV no la muestra -> fondo con sus láminas
    def resolve_slides(self, fondos):
        pj = os.path.join(P.SRC["dir"], "panel.json")
        sin = json.load(open(pj)).get("sin_cara", []) if os.path.exists(pj) else []
        px, py, pw, ph = self.P
        out, imgs = [], {}
        for a, b in sin:
            if b - a < 1.5: continue
            f = next((x for x in fondos if x["desde"] - 2 <= a <= x["hasta"]), None)
            if f is None: continue
            for it in self.c.SEGS:                          # fuente -> salida (por cada corte que toca el tramo)
                s0, s1 = it["fs"] / FPS, it["fe"] / FPS
                lo, hi = max(a, s0), min(b, s1)
                if hi - lo < 0.4: continue
                o = (it["out"] + it.get("pre", 0)) / FPS
                out.append([o + lo - s0, o + hi - s0, f["img"]])
            if f["img"] not in imgs:
                im = cv2.cvtColor(cv2.imread(os.path.join(P.SRC["dir"], f["img"])), cv2.COLOR_BGR2RGB)
                sc = max(pw / im.shape[1], ph / im.shape[0]); im = cv2.resize(im, (int(im.shape[1] * sc) + 1, int(im.shape[0] * sc) + 1), interpolation=cv2.INTER_AREA)
                oy = int(f.get("y", 0.5) * (im.shape[0] - ph)); ox = (im.shape[1] - pw) // 2
                im = cv2.GaussianBlur(im[oy:oy + ph, ox:ox + pw], (0, 0), f.get("blur", 5)).astype(np.float32) / 255
                tt = torch.from_numpy(im).to(dev).permute(2, 0, 1).to(DT)
                imgs[f["img"]] = tt * 0.30 + tcolor(WINE_D) * 0.70            # textura de sus láminas: que no compita con el dato animado
        out.sort()
        merged = []
        for s in out:                                       # cortes seguidos con la misma lámina: un solo tramo
            if merged and s[2] == merged[-1][2] and s[0] - merged[-1][1] < 0.6: merged[-1][1] = s[1]
            else: merged.append(s)
        self.bgimg = imgs
        print("[datos] láminas en", [(round(a, 1), round(b, 1), os.path.basename(i)) for a, b, i in merged])
        return merged

    def slide_at(self, t):
        for a, b, img in self.slides:
            if a - 0.3 <= t < b + 0.3:
                al = min(ease((t - a + 0.3) / 0.3), 1 - ease((t - b) / 0.3))
                return img, al, clamp01((t - a + 0.3) / max(1.0, b - a + 0.6))
        return None, 0.0, 0.0

    # ---------------------------------------------------------------- piezas
    def text_line(self, t, px, col, font_w="SemiBold"):
        if getattr(self, "claro", False): col = WINE_D                     # fuente de los datos: oscura sobre fondo claro
        f = font(font_w, px); w = int(f.getlength(t)) + 12
        im = rgba(w, int(px * 1.5)); ImageDraw.Draw(im).text((6, px * 0.75), t, font=f, fill=tuple(col) + (255,), anchor="lm")
        return np_(im)

    def tag_sprite(self, t):
        f = font("Bold", 24); w = int(sum(f.getlength(ch) + 2.5 for ch in t)) + 34
        im = rgba(w, 44); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, 43), radius=10, fill=WINE + (235,))
        spaced(d, (17, 22), t, f, (255, 255, 255, 255), tr=2.5)
        return np_(im)

    def title_sprite(self, title, kind):
        ft = font("Black", 50); fl = font("Bold", 22)
        lab = {"dato": "LOS DATOS", "denuncia": "LA DENUNCIA", "propuesta": "LA PROPUESTA", "mensaje": "EL MENSAJE", "cierre": "EL MENSAJE",
               "pregunta": "LA PREGUNTA", "ataque": "LA RESPUESTA", "logro": "LO LOGRADO"}.get(kind, "EL TEMA")
        title = title.upper(); px = 50
        while ft.getlength(title) > 760 and px > 30: px -= 2; ft = font("Black", px)
        w = int(max(ft.getlength(title), sum(fl.getlength(ch) + 3 for ch in lab))) + 60
        im = rgba(w, 118); d = ImageDraw.Draw(im)
        d.rectangle((0, 8, 8, 110), fill=ALERT + (255,))
        claro = getattr(self, "claro", False)
        spaced(d, (26, 22), lab, fl, (WINE if claro else ROSE_D) + (255,), tr=3)
        d.text((24, 76), title, font=ft, fill=(INK2 if claro else (255, 255, 255)) + (255,), anchor="lm")
        return np_(im) if claro else np_(shadowed(im, blur=10, dy=4, alpha=0.5, pad=12))

    def lab_col(self):
        return (255, 255, 255, 255) if getattr(self, "claro", False) else WINE + (255,)

    def card(self, h, fill=ROSE, alpha=246):
        im = rgba(CW, h); d = ImageDraw.Draw(im)
        if getattr(self, "claro", False) and tuple(fill) == ROSE:           # fondo claro: la tarjeta rosa pálida pasa a BLANCA con borde bordó
                                                                             # (las oscuras —cita en bordó— ya contrastan sobre el rosa)
            d.rounded_rectangle((0, 0, CW - 1, h - 1), radius=24, fill=(255, 255, 255, 255), outline=WINE + (255,), width=4)
            d.rounded_rectangle((0, 0, CW - 1, 56), radius=24, fill=WINE + (255,)); d.rectangle((0, 34, CW - 1, 56), fill=WINE + (255,))
            return im, d                                                    # encabezado bordó (como la tarjeta de noticia): el rótulo va en blanco
        d.rounded_rectangle((0, 0, CW - 1, h - 1), radius=24, fill=tuple(fill) + (alpha,))
        return im, d

    def done(self, key, im):
        out = spr_t(np_(shadowed(im, blur=16, dy=8, alpha=0.55, pad=20)))
        if len(self.cache) > 500: self.cache.clear()
        self.cache[key] = out
        return out

    def wrap2(self, text, f, maxw):
        lines, cur = [], ""
        for wd in text.split():
            tt = (cur + " " + wd).strip()
            if f.getlength(tt) <= maxw or not cur: cur = tt
            else: lines.append(cur); cur = wd
        return lines + [cur]

    def stat_sprite(self, s, prog):
        """tarjeta de dato: ícono + número que cuenta + etiqueta (+ detalle). prog 0..1 = avance del conteo"""
        key = ("dato", id(s), round(prog, 3))
        if key in self.cache: return self.cache[key]
        Hc = 176
        im, d = self.card(Hc)
        d.rounded_rectangle((0, 0, 150, Hc - 1), radius=24, fill=WINE + (255,)); d.rectangle((126, 0, 150, Hc - 1), fill=WINE + (255,))
        im.alpha_composite(Image.fromarray(icon(s.get("icon", "lazo"), 92)), (29, (Hc - 92) // 2))
        num = fmt(s["value"] * easeo(prog)) if prog < 1 else fmt(s["value"])
        fn = font("Black", 92); fl = font("ExtraBold", 34); fs = font("SemiBold", 25)
        x = 174
        d.text((x, 92), num, font=fn, fill=WINE + (255,), anchor="ls")
        xn = x + fn.getlength(fmt(s["value"])) + 18
        for i, ln in enumerate(self.wrap2(s.get("label", ""), fl, CW - xn - 22)[:2]): d.text((xn, 40 + 36 * i), ln, font=fl, fill=INK2 + (255,), anchor="lm")
        if s.get("detail"):
            d.line((x, 112, CW - 28, 112), fill=ROSE_D + (255,), width=3)
            while fs.getlength(s["detail"]) > CW - x - 30 and fs.size > 18: fs = font("SemiBold", fs.size - 1)
            d.text((x, 144), s["detail"], font=fs, fill=(92, 52, 68, 255), anchor="lm")
        return self.done(key, im)

    def compare_sprite(self, s, prog):
        """barras: año contra año que crecen hasta su valor (con una nota bajo cada año)"""
        key = ("cmp", id(s), round(prog, 3))
        if key in self.cache: return self.cache[key]
        Hc = 196
        im, d = self.card(Hc)
        fl = font("Black", 32); fn = font("Black", 50); ft = font("Bold", 22); fnote = font("SemiBold", 19)
        spaced(d, (28, 30), s.get("label", "").upper(), ft, WINE + (255,), tr=2)
        vmax = max(v for _, v, _ in s["bars"])
        for i, (lab, v, note) in enumerate(s["bars"]):
            y = 64 + i * 64
            d.text((28, y + 18), lab, font=fl, fill=INK2 + (255,), anchor="lm")
            if note: d.text((28, y + 46), note, font=fnote, fill=(120, 80, 96, 255), anchor="lm")
            p = easeo(clamp01(prog * 1.25 - 0.25 * i))
            bw = int((CW - 170 - 130) * v / vmax * p)
            d.rounded_rectangle((170, y + 4, 170 + max(14, bw), y + 48), radius=12, fill=(WINE if i == 0 else ALERT) + (255,))
            d.text((184 + max(14, bw), y + 27), fmt(v * p) if p < 1 else fmt(v), font=fn, fill=INK2 + (255,), anchor="lm")
        return self.done(key, im)

    def list_sprite(self, s, prog):
        """lista: los ítems se encienden uno por uno"""
        items = s["items"]; nk = len(items); k = min(nk, int(prog * nk + 0.5))
        key = ("lista", id(s), k)
        if key in self.cache: return self.cache[key]
        Hc = 196
        im, d = self.card(Hc)
        spaced(d, (28, 30), s.get("label", "").upper(), font("Bold", 22), self.lab_col(), tr=2)
        fi = font("ExtraBold", 32); cols = 2; cw = (CW - 56) // cols
        for i, it in enumerate(items):
            r, q = divmod(i, cols); x = 28 + q * cw; y = 64 + r * 62
            on = i < k
            if getattr(self, "claro", False) and not on:                    # apagado sobre tarjeta blanca: bordó tenue (blanco sobre rosa no se lee)
                d.rounded_rectangle((x, y, x + cw - 16, y + 50), radius=14, fill=(244, 232, 236, 255))
                d.text((x + 20, y + 25), it, font=fi, fill=WINE + (190,), anchor="lm"); continue
            d.rounded_rectangle((x, y, x + cw - 16, y + 50), radius=14, fill=(WINE if on else ROSE_D) + (255,))
            d.text((x + 20, y + 25), it, font=fi, fill=(255, 255, 255, 255 if on else 190), anchor="lm")
        return self.done(key, im)

    def timeline_sprite(self, s, prog):
        """línea de tiempo: los hitos se encienden uno por uno"""
        steps = s["steps"]; nk = len(steps); k = min(nk, int(prog * nk + 0.35))
        key = ("tl", id(s), k, round(min(1.0, prog * 1.3), 2))
        if key in self.cache: return self.cache[key]
        Hc = 210
        im, d = self.card(Hc)
        spaced(d, (28, 30), s.get("label", "").upper(), font("Bold", 22), self.lab_col(), tr=2)
        fy = font("Black", 34); fl = font("SemiBold", 19)
        x0, x1, yl = 74, CW - 74, 104
        d.line((x0, yl, x1, yl), fill=ROSE_D + (255,), width=6)
        d.line((x0, yl, x0 + (x1 - x0) * min(1.0, prog * 1.15), yl), fill=WINE + (255,), width=8)
        for i, (yr, txt, bad) in enumerate(steps):
            x = x0 + (x1 - x0) * i / max(1, nk - 1); on = i < k
            col = (ALERT if bad else WINE) if on else ROSE_D
            d.ellipse((x - 15, yl - 15, x + 15, yl + 15), fill=col + (255,))
            if on:
                d.text((x, yl - 36), yr, font=fy, fill=col + (255,), anchor="mm")
                for j, ln in enumerate(txt.split("|")): d.text((x, yl + 40 + 24 * j), ln, font=fl, fill=INK2 + (255,), anchor="mm")
        return self.done(key, im)

    def news_sprite(self, s):
        key = ("news", id(s))
        if key in self.cache: return self.cache[key]
        Hc = 196
        im, d = self.card(Hc, fill=(255, 255, 255))
        d.rounded_rectangle((0, 0, CW - 1, 56), radius=24, fill=ALERT + (255,)); d.rectangle((0, 36, CW - 1, 56), fill=(255, 255, 255, 255))
        spaced(d, (26, 22), s.get("kicker", "CASO").upper(), font("Black", 23), (255, 255, 255, 255), tr=3)
        fh = font("ExtraBold", 34)
        for i, ln in enumerate(self.wrap2(s["headline"], fh, CW - 56)[:3]): d.text((28, 76 + 40 * i), ln, font=fh, fill=INK2 + (255,), anchor="lm")
        if s.get("credit"): d.text((CW - 26, Hc - 18), s["credit"], font=font("SemiBold", 20), fill=(120, 96, 106, 255), anchor="rm")
        return self.done(key, im)

    def quote_sprite(self, s):
        """frase destacada (palabras textuales de ella)"""
        key = ("frase", id(s))
        if key in self.cache: return self.cache[key]
        fq = font("ExtraBold", 40); lines = self.wrap2("«" + s["text"] + "»", fq, CW - 90)
        while len(lines) > 3 and fq.size > 30: fq = font("ExtraBold", fq.size - 2); lines = self.wrap2("«" + s["text"] + "»", fq, CW - 90)
        Hc = 70 + 50 * len(lines)
        im, d = self.card(Hc, fill=WINE, alpha=240)
        d.rectangle((26, 26, 34, Hc - 26), fill=ALERT + (255,))
        for i, ln in enumerate(lines): d.text((56, 52 + 50 * i), ln, font=fq, fill=(255, 255, 255, 255), anchor="lm")
        return self.done(key, im)

    def big_sprite(self, s, prog):
        """dato grande (sobre el recuadro): ícono, número enorme que cuenta, etiqueta y detalle"""
        key = ("big", id(s), round(prog, 3))
        if key in self.cache: return self.cache[key]
        Wc, Hc = 860, 600
        im = rgba(Wc, Hc); d = ImageDraw.Draw(im)
        if s.get("icon"):
            ic = Image.fromarray(icon(s["icon"], 110, ROSE)); im.alpha_composite(ic, ((Wc - 110) // 2, 0))
        num = fmt(s["value"] * easeo(prog)) if prog < 1 else fmt(s["value"])
        fn = font("Black", 240); fl = font("Black", 60); fs = font("Bold", 32)
        d.text((Wc / 2, 350), num, font=fn, fill=(255, 255, 255, 255), anchor="ms", stroke_width=6, stroke_fill=WINE_D + (255,))
        lab = s.get("label", "").upper()
        while fl.getlength(lab) > Wc - 40 and fl.size > 34: fl = font("Black", fl.size - 2)
        d.text((Wc / 2, 420), lab, font=fl, fill=(255, 214, 224, 255), anchor="mm", stroke_width=4, stroke_fill=WINE_D + (255,))
        if s.get("detail"):
            while fs.getlength(s["detail"]) > Wc - 40 and fs.size > 22: fs = font("Bold", fs.size - 1)
            d.text((Wc / 2, 492), s["detail"], font=fs, fill=(255, 255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=WINE_D + (255,))
        out = spr_t(np_(im)); self.cache[key] = out
        return out

    # ---------------------------------------------------------------- cámara: el encuadre ya viene armado (sin zoom)
    def video(self, n, it, rd, z=None, anchor=None, fade=(0.985, 0.03)):
        return warp_src(self.src_frame(n, it, rd), self.idt, ext_bg=None, fade_top=False)

    def look(self, x, n, t):
        x = x * (1 - self.tint_a) + self.tint * self.tint_a
        img, al, u = self.slide_at(t)
        if img is not None and al > 0.003:
            px, py, pw, ph = self.P
            sc = 0.93 + 0.07 * u                                    # la lámina se aleja despacio (vida sin distraer)
            th = torch.tensor([[sc, 0, 0.02 * (1 - u)], [0, sc, -0.03 * (1 - u)]], device=dev, dtype=torch.float32).view(1, 2, 3)
            g = F.affine_grid(th, (1, 3, ph, pw), align_corners=False)
            bg = F.grid_sample(self.bgimg[img][None].float(), g, mode="bilinear", padding_mode="border", align_corners=False)[0].to(DT)
            x[:, py:py + ph, px:px + pw] = x[:, py:py + ph, px:px + pw] * (1 - al) + bg * al
        return x

    # ---------------------------------------------------------------- capas
    def stat_at(self, t):
        for s in self.stats:
            if s["t0"] - 0.05 <= t < s["t1"] + 0.4: return s
        return None

    def draw_stat(self, fr, s, t):
        px, py, pw, ph = self.P
        a = t - s["t0"]; dur = s["t1"] - s["t0"]
        p_in = easeo(a / 0.42); p_out = ease((a - dur) / 0.35) if a > dur else 0.0
        vis = min(1.0, a / 0.12) * (1 - p_out)
        prog = clamp01((a - 0.25) / s.get("count_s", 1.1))
        k = s["kind"]
        slide = self.slide_at(t)[0] is not None
        if k == "grande" or (k == "dato" and slide):                  # número enorme en el recuadro
            if not slide:
                dim = 0.62 * vis
                fr[:, py:py + ph, px:px + pw] = fr[:, py:py + ph, px:px + pw] * (1 - dim) + tcolor(WINE_D) * dim
            spr = self.big_sprite(s, prog)
            s2 = scaled(spr, 0.86 + 0.14 * easeb(clamp01(a / 0.5)))
            blend(fr, s2, CX - s2.shape[2] / 2, py + ph / 2 - s2.shape[1] / 2 + 10 + 30 * p_out, vis)
        else:
            spr = {"dato": lambda: self.stat_sprite(s, prog), "comparar": lambda: self.compare_sprite(s, prog),
                   "linea": lambda: self.timeline_sprite(s, prog), "noticia": lambda: self.news_sprite(s), "lista": lambda: self.list_sprite(s, prog),
                   "frase": lambda: self.quote_sprite(s)}[k]()
            if slide: y = py + ph / 2 - spr.shape[1] / 2 + 60 * (1 - p_in) + 40 * p_out           # sin ella en cuadro: al centro
            else: y = 1268 - spr.shape[1] + 20 + 90 * (1 - p_in) + 60 * p_out                      # con ella: abajo, sin tocarle la cara
            blend(fr, spr, CX - spr.shape[2] / 2, y, vis)
        ft = s.get("fuente")
        if ft:
            if ft not in self.feet: self.feet[ft] = spr_t(self.text_line(ft, 24, ROSE_D))
            blend(fr, self.feet[ft], SAFE["left"], 1430, vis)

    def draw_title(self, fr, t):
        b = self.beat_at(t)
        if b is None or not b.get("title"): return
        t0 = max(b.get("a0", b["o0"]), self.first_a)
        if t < t0: return
        k = (b["title"], b.get("kind"))
        if k not in self.titles: self.titles[k] = spr_t(self.title_sprite(b["title"], b.get("kind")))
        spr = self.titles[k]; a = ease((t - t0) / 0.4)
        blend(fr, spr, SAFE["left"] - 22 - 40 * (1 - a), 270, a)

    def decorate(self, x, n, it, t):
        px, py, pw, ph = self.P
        blend(x, self.pfade, 0, py + ph - 90)
        blend(x, self.line, 0, py - 3); blend(x, self.line, 0, py + ph - 3)
        self.draw_title(x, t)
        if self.tag is not None and t >= self.first_a + 0.2 and self.slide_at(t)[0] is None: blend(x, self.tag, SAFE["left"], py + 18, ease((t - self.first_a - 0.2) / 0.4))
        s = self.stat_at(t)
        if s is not None: self.draw_stat(x, s, t)
        elif t < self.first_a + 4.0: self.draw_name(x, t, y=py + ph - self.name.shape[1] - 24)
        self.draw_captions(x, t)
        if self.slide_at(t)[0] is None and t >= self.first_a + 0.2:                 # sello de redes: arriba a la derecha del recuadro (zona segura)
            blend(x, self.wmark, SAFE["right"] - self.wmark.shape[2], py + 14, ease((t - self.first_a - 0.2) / 0.4))
        return x

    def cues(self):
        c = self.c; out = []
        for s in self.stats:
            out.append((s["t0"] - 0.02, "swish", 0.16))
            if s["kind"] in ("dato", "grande", "comparar"): out.append((s["t0"] + 0.25 + s.get("count_s", 1.1), "click", 0.14))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.24)); out.append((c.END0 / FPS + 0.28, "chime", 0.26))
        return out
