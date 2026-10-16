# Base de los estilos nuevos (ronda de 1 minuto): video con la cara anclada, subtítulos, placa de nombre, sello de redes,
# línea de tiempo de ideas (cfg["beats"]) y cierre blanco. Cada estilo hereda y redefine solo su "look".
import os
from styles.common import *
import plan as P
from PIL import ImageFont

import plataforma as PL
_fc = {}


def wfont(name, px):
    """fuente del sistema por su nombre de Windows (georgia, georgiab, georgiai, georgiaz, impact…); en Mac, la misma familia (plataforma.py)"""
    k = (name, px)
    if k not in _fc: _fc[k] = ImageFont.truetype(PL.sysfont(name), px)
    return _fc[k]


def text_sprite(lines, f, fill=WHITE, stroke=0, stroke_fill=(8, 10, 14), shadow=0.0, align="center", lh=1.18, pad=24, tracking=0.0):
    """bloque de texto multilínea -> sprite RGBA (con contorno/sombra opcional)"""
    if isinstance(lines, str): lines = [lines]
    widths = [sum(f.getlength(c) + tracking for c in ln) - tracking for ln in lines]
    asc, desc = f.getmetrics()
    lhp = int((asc + desc) * lh)
    W_ = int(max(widths)) + 2 * pad + 2 * stroke; H_ = lhp * len(lines) + 2 * pad
    im = Image.new("RGBA", (W_, H_), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        x = pad + stroke + ((max(widths) - widths[i]) / 2 if align == "center" else (max(widths) - widths[i]) if align == "right" else 0)
        y = pad + i * lhp
        for ch in ln:
            d.text((x, y), ch, font=f, fill=tuple(fill) + (255,), stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,)); x += f.getlength(ch) + tracking
    if shadow > 0: return np_(shadowed(im, blur=10, dy=5, alpha=shadow, pad=0))
    return np_(im)


def wrap(text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


class Base:
    ext_color = NAVY
    anchor = (540.0, 700.0)              # dónde queda la cara en pantalla
    zcyc = [1.10, 1.17, 1.12, 1.19, 1.14, 1.21, 1.11, 1.18]
    cap_x, cap_y = 495, 1170
    grain = 0.005                        # grano suave (con 0.010 se comía la tasa de datos y el video se veía más blando)
    show_name = True
    ext_x = 0.0                          # sin relleno por reflejo en X (200 px dejaba ver el saco duplicado)

    def __init__(self, ctx):
        self.c = ctx

    # ---------------------------------------------------------------- preparación
    def setup(self):
        c = self.c
        self.end = Endcard()
        self.vig = make_vignette(0.34)
        self.ext_t = tcolor(self.ext_color)
        self.ext = self.ext_t.expand(3, H, W) * (0.75 + 0.55 * (yy_ / 420.0).clamp(0, 1))[None].to(DT)
        import brand as B
        self.B = B
        self.wmark = spr_t(B.watermark())
        self.name = spr_t(B.name_card()[0])
        self.beats = c.cfg.get("beats", [])
        self.chunk_cache = {}
        self.keys_range = [(k["s"], k["e"]) for k in c.CHUNKS if k["key"] and k["e"] - k["s"] >= 0.45]
        self.scene_starts = [int(round(v["o0"] * FPS)) for k, v in c.SC.items() if k >= 1]
        self.beat_starts = [int(round(b["o0"] * FPS)) for b in self.beats[1:]]
        self.end0 = c.END0
        import content as C
        def _spk(sid):                                                     # quién habla en la escena (el gancho puede ser de ella)
            try: return C.SENT[int(str(sid).rsplit("_", 1)[1])]["spk"]
            except Exception: return "L"
        self.scene_spk = dict(c.SPK) if hasattr(c, "SPK") else {k: ("R" if v["role"] == "Q" else _spk(v["sid"])) for k, v in c.SC.items()}
        self.first_a = next((v["o0"] for k, v in sorted(c.SC.items()) if self.scene_spk[k] == "L"), 0.0)   # primera vez que habla ella
        self.init()

    def init(self): pass

    def beat_at(self, t):
        cur = None
        for b in self.beats:
            if b["o0"] - 1e-3 <= t: cur = b
        return cur

    # ---------------------------------------------------------------- cámara
    def punch(self, t, amt=0.07):
        a = 0.0
        for s, e in self.keys_range:
            if s <= t < e: a = max(a, amt)
            elif e <= t < e + 0.15: a = max(a, amt * (1 - ease((t - e) / 0.15)))
        return 1 + a

    def zoom(self, n, it, t):
        c = self.c
        if t < c.hook_end: return 1.16 * (1 + 0.02 * (t / max(1e-3, c.hook_end)))
        t0 = c.shot_start(it); tt = (n - t0) / FPS
        z = self.zcyc[it["shot"] % len(self.zcyc)] * (1 + 0.012 * tt) * ((1 + 0.04 * (1 - ease(tt / 0.35))) if n - t0 < 12 else 1.0)
        return z * self.punch(t)

    def src_frame(self, n, it, rd):
        return (T(rd.get()).permute(2, 0, 1).float() / 255)[None]

    def video(self, n, it, rd, z=None, anchor=None, fade=(0.985, 0.03)):
        c = self.c; t = n / FPS
        src = self.src_frame(n, it, rd)
        z = self.zoom(n, it, t) if z is None else z
        ax, ay = anchor or self.anchor
        f = it["fs"] + max(0, n - it["out"] - it.get("pre", 0))
        return warp_src(src, c.cam.theta(f, z, ax, ay, ext_x=self.ext_x, ext_y=0.0), ext_bg=self.ext, fade=fade)

    def look(self, x, n, t):
        """gradación de color por defecto"""
        return grade_color(x) * self.vig

    # ---------------------------------------------------------------- capas comunes
    def chunk_at(self, t):
        for ci, k in enumerate(self.c.CHUNKS):
            if k["s"] <= t < k["e"]: return ci, k
        return None, None

    def cap_sprite(self, k):
        if self.scene_spk.get(k["sc"]) == "R":                             # la voz del periodista se distingue (tono azulado, más chico, frase entera)
            return self.rep_sprite(k)
        return sub_sprite(k["words"], key_color=GOLD if k["key"] else None, flags=k.get("flags"))

    def rep_sprite(self, k, px=46, fill=(206, 222, 250), f=None):
        f = f or font("ExtraBold", px)
        lines = wrap(" ".join(k["words"]), f, 800)
        return text_sprite(lines, f, fill=fill, stroke=max(4, px // 10), stroke_fill=(8, 10, 14), shadow=0.5, lh=1.12, pad=26)

    def draw_hold(self, fr, t, y_ans):
        """la pregunta recién terminada sigue visible (más chica, arriba) mientras arranca la respuesta"""
        for ci, k in enumerate(self.c.CHUNKS):
            if k.get("hold") and k["e"] <= t < k["e"] + k["hold"]:
                if ci not in self.chunk_cache: self.chunk_cache[ci] = spr_t(self.cap_sprite(k))
                s2 = scaled(self.chunk_cache[ci], 0.78)
                a = 0.92 * (1 - ease((t - k["e"] - k["hold"] + 0.25) / 0.25))
                blend(fr, s2, self.cap_x - s2.shape[2] / 2, y_ans - 70 - s2.shape[1], a)

    def draw_captions(self, fr, t):
        self.draw_hold(fr, t, self.cap_y)
        ci, k = self.chunk_at(t)
        if k is None: return
        if ci not in self.chunk_cache: self.chunk_cache[ci] = spr_t(self.cap_sprite(k))
        spr = self.chunk_cache[ci]; age = (t - k["s"]) * FPS
        s2 = scaled(spr, (0.92 + 0.08 * ease(age / 4)) * (1.0 + (0.05 * ease(age / 6) if k["key"] else 0)))
        blend(fr, s2, self.cap_x - s2.shape[2] / 2, self.cap_y - s2.shape[1] / 2, min(1.0, (age + 1) / 3))

    def draw_name(self, fr, t, y=None):
        la = self.first_a + 0.55; le = la + 2.8
        if la <= t < le + 0.4:
            p_in = easeo((t - la) / 0.45); p_out = ease((t - le) / 0.30) if t >= le else 0.0
            off = 90 * (1 - p_in) + 90 * p_out
            blend(fr, self.name, SAFE["left"] - 20, (y or X.LANE_Y - 20) + off, (1 - p_out) * min(1.0, (t - la) / 0.15))

    def draw_wmark(self, fr, t, y=276):
        t0 = self.first_a + 0.2
        if t >= t0: blend(fr, self.wmark, SAFE["right"] - self.wmark.shape[2], y, ease((t - t0) / 0.4))

    def decorate(self, x, n, it, t):
        """capas propias del estilo (por defecto: sello + subtítulos + placa)"""
        self.draw_wmark(x, t)
        self.draw_captions(x, t)
        if self.show_name: self.draw_name(x, t)
        return x

    # ---------------------------------------------------------------- fotograma
    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        x = self.video(n, it, rd)
        x = self.look(x, n, t)
        if self.grain: x = (x + torch.randn(1, H, W, device=dev, dtype=DT) * self.grain).clamp(0, 1)
        x = self.decorate(x, n, it, t)
        return exit_to_white(x, self.end0 - n)

    def whips(self): return []

    def cues(self):
        c = self.c; out = []
        for b in self.beats[1:]: out.append((b["o0"] - 0.02, "click", 0.20))
        out.append((self.first_a + 0.55, "swish", 0.30))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out


def declarar_tramos(cdir, capa, spans, quietos=False):
    """cada capa declara SUS tramos sin cara / imagen quieta (se reemplazan, no se acumulan entre corridas) y el total para el QA"""
    import json, os
    tp = os.path.join(cdir, "tramos_estilo.json")
    try: te = json.load(open(tp)) if os.path.exists(tp) else {}
    except Exception: te = {}
    capas = te.get("capas", {})
    capas[capa] = dict(sin_cara=[list(x) for x in spans], quietos=[list(x) for x in spans] if quietos else [])
    te["capas"] = capas
    te["sin_cara"] = [x for c in capas.values() for x in c["sin_cara"]]
    te["quietos"] = [x for c in capas.values() for x in c["quietos"]]
    json.dump(te, open(tp, "w"), indent=1)
