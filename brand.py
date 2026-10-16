# Estudio de edición — MARCA DEL CLIENTE (punto 3): nombre, cargo, @ y redes salen de clients/<cliente>.json, no del código.
# Versiones parametrizadas de las piezas aprobadas (placa de nombre, sello de redes, cierre blanco, cabecera de llamada).
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import plan as P
import gfx5 as G
import gfx6 as X
import gfx11 as G11
from gfx5 import font, np_, rgba, shadowed

C = P.CLIENT
NAME = C.get("name", "Lilian Samaniego")
ROLE = C.get("role", "Senadora de la Nación")
HANDLE = C.get("handle", "/LILIANSAMANIEGOPY")
ICONS = {"facebook": "", "instagram": "", "x": "", "tiktok": "", "whatsapp": "", "youtube": ""}
NETS = [ICONS[n] for n in C.get("networks", ["facebook", "instagram", "x", "tiktok", "whatsapp"]) if n in ICONS]
RED, WHITE = tuple(C.get("colors", {}).get("accent", G.RED)), (255, 255, 255)


def name_card():
    return X.name_card(NAME, ROLE)


def watermark():
    """sello de redes arriba a la derecha (como en las referencias)"""
    fa = ImageFont.truetype(os.path.join(G.FONTS, "fa-brands-400.ttf"), 24)
    f = G11.bfont(26, 700, 85)
    n = len(NETS)
    w = max(int(n * 40 + 6), int(G11.tlen(HANDLE, f, 1.2)) + 8) + 28; h = 82
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(0, 0, 0, 105))
    x0 = (w - (n * 40 - 8)) / 2
    for i, g in enumerate(NETS):
        x = x0 + i * 40
        d.rounded_rectangle((x, 9, x + 32, 41), radius=9, fill=RED + (255,))
        bb = d.textbbox((0, 0), g, font=fa)
        d.text((x + 16 - (bb[2] - bb[0]) / 2 - bb[0], 25 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=WHITE + (255,))
    xx = (w - G11.tlen(HANDLE, f, 1.2)) / 2
    for c in HANDLE:
        d.text((xx, 62), c, font=f, fill=WHITE + (255,), anchor="lm"); xx += f.getlength(c) + 1.2
    return np_(im)


def endcard_layers():
    """cierre blanco: íconos de redes en rojo + @ (devuelve [(sprite, x, y, retardo)])"""
    fa = X.font_fa(60)
    out = []
    size, gap = 116, 26
    total = len(NETS) * size + (len(NETS) - 1) * gap
    x0 = (G.W - total) // 2 - 6
    for i, g in enumerate(NETS):
        im = rgba(size + 40, size + 40); d = ImageDraw.Draw(im)
        d.rounded_rectangle((20, 20, 20 + size, 20 + size), radius=30, fill=RED + (255,))
        bb = d.textbbox((0, 0), g, font=fa)
        d.text((20 + size / 2 - (bb[2] - bb[0]) / 2 - bb[0], 20 + size / 2 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=WHITE + (255,))
        out.append((np_(im), x0 + i * (size + gap) - 20 + 6, 870, 0.30 + 0.07 * i))
    f3 = font("Black", 50)
    bb = ImageDraw.Draw(rgba(10, 10)).textbbox((0, 0), HANDLE, font=f3)
    im = rgba(bb[2] - bb[0] + 60, bb[3] - bb[1] + 60); ImageDraw.Draw(im).text((30 - bb[0], 30 - bb[1]), HANDLE, font=f3, fill=RED + (255,))
    out.append((np_(im), (G.W - im.width) // 2, 1030, 0.75))
    return out


def end_role():
    f = font("SemiBold", 31)
    t = ROLE.upper()
    w = int(G11.tlen(t, f, 7)) + 40
    im = Image.new("RGBA", (w, 56), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 20
    for c in t:
        d.text((x, 28), c, font=f, fill=(24, 28, 40, 235), anchor="lm"); x += f.getlength(c) + 7
    return np_(im)


def call_header(PW, HDR_H, TXT_X, NAVY):
    im = Image.new("RGBA", (PW, HDR_H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((TXT_X + 70, 29), NAME, font=font("ExtraBold", 31), fill=NAVY + (255,), anchor="lm")
    d.text((TXT_X + 70, 58), f"En llamada · {ROLE}", font=font("SemiBold", 21), fill=(98, 108, 138, 255), anchor="lm")
    return np_(im)
