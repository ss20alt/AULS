# Piezas compartidas por los estilos: cierre blanco, subtítulos base, tarjetas aprobadas (placa blanca, globo, sello de redes).
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw
from core import *
import gfx5 as G
import gfx6 as X
import gfx11 as G11
import gfx13 as G13
from gfx5 import font, np_, shadowed, rgba

NAVY = (8, 18, 44)
RED = (226, 35, 48)
GOLD = (255, 201, 60)
WHITE = (252, 252, 254)
INK = (12, 12, 16)


def tlen(text, f, tr=0.0): return sum(f.getlength(c) + tr for c in text) - tr


class Endcard:
    """cierre blanco con íconos rojos y @ (referencias R1/R4/R5/R6/R7)"""
    def __init__(self):
        import brand as B
        self.layers = [(spr_t(s), x, y, d) for s, x, y, d in B.endcard_layers()]
        self.role = spr_t(B.end_role())

    def frame(self, t):
        fr = torch.ones(3, H, W, device=dev, dtype=DT)
        for spr, x, y, d in self.layers:
            a = ease((t - d) / 0.28)
            if a <= 0: continue
            sc = 0.7 + 0.3 * easeb((t - d) / 0.35)
            s2 = scaled(spr, sc); h, w = s2.shape[1:]; oh, ow = spr.shape[1:]
            blend(fr, s2, x + (ow - w) / 2, y + (oh - h) / 2, a)
        blend(fr, self.role, W / 2 - self.role.shape[2] / 2, 1118, ease((t - 0.85) / 0.3))
        return fr


def exit_to_white(out, kk):
    """últimos fotogramas antes del cierre: desenfoque + fundido a blanco"""
    if 1 <= kk <= 4:
        a = (5 - kk) / 5.0
        out = gblur_h(out, 1 + 2 * int(round(a * 40))) * (1 - 0.8 * a) + 0.8 * a
    return out


def sub_sprite(words, key_color=None, flags=None, px=58, stroke=None, fill=WHITE, ink_box=False, seed=11):
    """subtítulo de 2-3 palabras: relleno blanco (o de color si es clave) con contorno negro y sombra suave"""
    f = font("ExtraBold", px)
    wid = lambda ws_: sum(f.getlength(w) for w in ws_) + f.getlength(" ") * (len(ws_) - 1)
    if not ink_box and wid(words) > 840 and len(words) >= 4:              # texto largo (p. ej. una pregunta entera): dos líneas equilibradas
        best = min(range(1, len(words)), key=lambda j: max(wid(words[:j]), wid(words[j:])))
        rows = [words[:best], words[best:]]
        while px > 40 and max(wid(r) for r in rows) > 840: px -= 2; f = font("ExtraBold", px)
        sprs = [sub_sprite(r, key_color=key_color, flags=(flags[:best] if i == 0 else flags[best:]) if flags else None, px=px, stroke=stroke, fill=fill, seed=seed)
                for i, r in enumerate(rows)]
        w_ = max(s.shape[1] for s in sprs); h_ = sum(s.shape[0] for s in sprs) - 40
        out = np.zeros((h_, w_, 4), np.uint8); y_ = 0
        for s in sprs:
            x_ = (w_ - s.shape[1]) // 2
            region = out[y_:y_ + s.shape[0], x_:x_ + s.shape[1]]
            a_ = s[..., 3:4].astype(np.float32) / 255
            region[..., :3] = (s[..., :3] * a_ + region[..., :3] * (1 - a_)).astype(np.uint8)
            region[..., 3] = np.maximum(region[..., 3], s[..., 3])
            y_ += s.shape[0] - 40
        return out
    while px > 40 and wid(words) > 840:                                    # nunca más ancho que la zona segura
        px -= 2; f = font("ExtraBold", px); wid = lambda ws_: sum(f.getlength(w) for w in ws_) + f.getlength(" ") * (len(ws_) - 1)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    if ink_box:
        padx, pady = 30, 13
        w = int(total) + 2 * padx; h = int(px * 1.22) + 2 * pady
        im = Image.fromarray(G11.ink_bg(w, h, seed, INK, pad=12, amp=3.6)); d = ImageDraw.Draw(im)
        x = 12 + padx
        for i, wd in enumerate(words):
            d.text((x, 12 + pady - 3), wd, font=f, fill=fill + (255,)); x += ws[i] + sp
        return np_(im)
    pad = 36
    iw, ih = int(total) + 2 * pad, int(px * 1.25) + 2 * pad
    txt = Image.new("RGBA", (iw, ih), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    st = stroke or max(5, int(px * 0.10))
    x = pad
    for i, wd in enumerate(words):
        col = (key_color if (flags is None or flags[i]) else fill) if key_color else fill
        d.text((x, pad), wd, font=f, fill=col + (255,), stroke_width=st, stroke_fill=(8, 10, 14, 255)); x += ws[i] + sp
    return np_(shadowed(txt, blur=8, dy=5, alpha=0.55, pad=0))


def two_rows(build, words, maxw=860, overlap=None):
    """si el subtítulo hecho por `build(palabras, desde)` es más ancho que la zona segura, se arma en DOS filas equilibradas con el
    mismo diseño del estilo (caja de tinta, barra, karaoke…) y se apilan centradas. Nunca se sale del cuadro."""
    spr = build(words, 0)
    if spr.shape[1] <= maxw or len(words) < 4: return spr
    lens = [len(w) + 1 for w in words]; tot = sum(lens); acc, j = 0, 1
    for i, l in enumerate(lens):
        acc += l
        if acc >= tot / 2: j = max(1, min(len(words) - 1, i + 1)); break
    rows = [build(words[:j], 0), build(words[j:], j)]
    ov = rows[0].shape[0] // 4 if overlap is None else overlap
    w_ = max(r.shape[1] for r in rows); h_ = rows[0].shape[0] + rows[1].shape[0] - ov
    out = np.zeros((h_, w_, 4), np.uint8); y_ = 0
    for r in rows:
        x_ = (w_ - r.shape[1]) // 2
        reg = out[y_:y_ + r.shape[0], x_:x_ + r.shape[1]].astype(np.float32)
        a = r[..., 3:4].astype(np.float32) / 255
        reg[..., :3] = r[..., :3] * a + reg[..., :3] * (1 - a)
        reg[..., 3] = np.maximum(reg[..., 3], r[..., 3])
        out[y_:y_ + r.shape[0], x_:x_ + r.shape[1]] = reg.astype(np.uint8)
        y_ += r.shape[0] - ov
    if out.shape[1] > maxw:                                                # aun en dos filas no entra: se achica
        from PIL import Image as _I
        im = _I.fromarray(out); s_ = maxw / out.shape[1]
        out = np.array(im.resize((maxw, int(out.shape[0] * s_)), _I.LANCZOS))
    return out


def question_card(text, tag="PREGUNTA", maxw=800, px=44):
    """tarjeta blanca de pregunta (gancho): etiqueta roja + texto azul marino"""
    ft, fq = font("ExtraBold", 24), font("Bold", px)
    words = text.split(); lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fq.getlength(t) <= maxw - 100: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    lh = int(px * 1.28)
    h = 34 + 46 + 22 + lh * len(lines) + 30
    im = rgba(maxw, h); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, maxw - 1, h - 1), radius=26, fill=(250, 250, 253, 248))
    d.rounded_rectangle((0, 0, 22, h - 1), radius=11, fill=RED + (255,)); d.rectangle((12, 0, 22, h - 1), fill=RED + (255,))
    tw = sum(ft.getlength(c) + 3 for c in tag) + 38
    d.rounded_rectangle((52, 30, 52 + tw, 30 + 46), radius=23, fill=RED + (255,))
    x = 52 + 19
    for c in tag:
        d.text((x, 30 + 23), c, font=ft, fill=WHITE + (255,), anchor="lm"); x += ft.getlength(c) + 3
    for i, ln in enumerate(lines):
        d.text((54, 34 + 46 + 22 + i * lh), ln, font=fq, fill=NAVY + (255,))
    return np_(shadowed(im, blur=14, dy=8, alpha=0.5, pad=22)), 22
