# v13 — gráficos de la pantalla dividida (referencia ref01): banda blanca de subtítulos, chips, fotos del banco, logo, cierre.
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx5 as G
import gfx6 as X
from gfx5 import font, np_, shadowed

W, H = 1080, 1920
CX = 490
NAVY, RED, INK, WHITE = (8, 18, 44), (226, 35, 48), (13, 15, 22), (252, 252, 254)
TOP_H, BAND_Y, BAND_H = 926, 926, 88
BR_Y = BAND_Y + BAND_H                    # 1014: inicio de las tomas inferiores
BR_H = H - BR_Y                           # 906
FOTOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "material", "bcp", "fotos")   # material del tema BCP


def tlen(text, f, tr=0.0): return sum(f.getlength(c) + tr for c in text) - tr


# ------------------------------------------------------------------ subtítulos sobre la banda blanca
def caption_sprite(words, active, px=57, seed=0):
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    pad = 12
    iw, ih = int(total) + 2 * pad, int(px * 1.3) + 2 * pad
    im = Image.new("RGBA", (iw, ih), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = pad
    for i, wd in enumerate(words):
        d.text((x, ih / 2 + 2), wd, font=f, fill=(RED if i == active else INK) + (255,), anchor="lm")
        x += ws[i] + sp
    return np_(im)


# ------------------------------------------------------------------ chip (tarjeta azul con barra roja, estilo de las cards aprobadas)
def chip_sprite(text, maxw=830):
    px = 40
    while px > 26 and tlen(text, font("ExtraBold", px), 1.2) > maxw - 90: px -= 2
    f = font("ExtraBold", px)
    w = int(tlen(text, f, 1.2)) + 76; h = 74
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=18, fill=NAVY + (236,))
    d.rounded_rectangle((0, 0, 14, h - 1), radius=7, fill=RED + (255,)); d.rectangle((8, 0, 14, h - 1), fill=RED + (255,))
    x = 38
    for c in text:
        d.text((x, h / 2 + 1), c, font=f, fill=WHITE + (255,), anchor="lm"); x += f.getlength(c) + 1.2
    return np_(shadowed(im, blur=10, dy=6, alpha=0.55, pad=18)), 18


# ------------------------------------------------------------------ fotos
def load_photo(name, kind):
    im = Image.open(os.path.join(FOTOS, name)).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    if kind == "hazy":                                           # foto lavada: estira niveles y añade color
        lo, hi = np.percentile(a, 1.0), np.percentile(a, 99.4)
        a = np.clip((a - lo) / (hi - lo), 0, 1) * 255
        g = a.mean(2, keepdims=True); a = np.clip(g + (a - g) * 1.22, 0, 255)
    a = a.astype(np.uint8)
    h, w = a.shape[:2]
    up = cv2.resize(a, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up, (0, 0), 1.6)
    up = cv2.addWeighted(up, 1.55, blur, -0.55, 0)                # máscara de enfoque suave
    return up, (w, h)


def logo_canvas():
    """logo BCP sobre su azul; devuelve (logo RGBA a 2x, color de fondo)"""
    im = Image.open(os.path.join(FOTOS, "logo_bcp.png")).convert("RGB")
    a = np.asarray(im)
    bg = tuple(int(v) for v in np.median(np.concatenate([a[:6, :6].reshape(-1, 3), a[-6:, -6:].reshape(-1, 3)]), axis=0))
    up = cv2.resize(a, (a.shape[1] * 2, a.shape[0] * 2), interpolation=cv2.INTER_LANCZOS4)
    return up, bg


# ------------------------------------------------------------------ cierre
def end_role():
    f = font("SemiBold", 31)
    t = "SENADORA DE LA NACIÓN"
    w = int(tlen(t, f, 7)) + 40
    im = Image.new("RGBA", (w, 56), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 20
    for c in t:
        d.text((x, 28), c, font=f, fill=(24, 28, 40, 235), anchor="lm"); x += f.getlength(c) + 7
    return np_(im)
