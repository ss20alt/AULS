# v18 — "Síntesis": gráficos propios del video de 2 minutos (el resto viene de gfx5/gfx6/gfx11/gfx13, ya aprobados).
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx5 as G
import gfx6 as X
import gfx11 as G11
import gfx13 as G13
from gfx5 import font, np_, shadowed, rgba

W, H = 1080, 1920
CX = 540
INK, WHITE, RED, NAVY = (12, 12, 16), (252, 252, 254), (226, 35, 48), (8, 18, 44)
WINW, WINH, WINCX, WINCY = 1000, 700, 540, 728          # recuadro de las fotos del banco (centrado en el cuadro)
WIN_R, WIN_B = 34, 10
FOTOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "material", "bcp", "fotos")   # material del tema BCP


def tlen(text, f, tr=0.0): return sum(f.getlength(c) + tr for c in text) - tr


# ------------------------------------------------------------------ título del gancho: caja de tinta negra con texto blanco (la palabra final en rojo)
def banner_ink(text, maxw=840, seed=7):
    words = text.split()
    px = 92
    while px > 40 and tlen(text, G11.bfont(px), 1.5) > maxw - 100: px -= 4
    f = G11.bfont(px)
    w = int(tlen(text, f, 1.5)) + 100; h = int(px * 1.2) + 46
    im = Image.fromarray(G11.ink_bg(w, h, seed, INK, pad=14, amp=5.0)); d = ImageDraw.Draw(im)
    x = 14 + 50
    for i, wd in enumerate(words):
        col = RED if i == len(words) - 1 else WHITE
        for c in wd:
            d.text((x, 14 + 19), c, font=f, fill=col + (255,)); x += f.getlength(c) + 1.5
        x += f.getlength(" ") + 1.5
    return np_(im)


# ------------------------------------------------------------------ subtítulos: blanco con contorno; frases clave en caja de tinta negra
def sub_sprite(words, key=False, px=62, seed=11):
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    if key:
        padx, pady = 30, 13
        w = int(total) + 2 * padx; h = int(px * 1.22) + 2 * pady
        im = Image.fromarray(G11.ink_bg(w, h, seed, INK, pad=12, amp=3.6)); d = ImageDraw.Draw(im)
        x = 12 + padx
        for i, wd in enumerate(words):
            d.text((x, 12 + pady - 3), wd, font=f, fill=WHITE + (255,)); x += ws[i] + sp
        return np_(im)
    pad = 36
    iw, ih = int(total) + 2 * pad, int(px * 1.25) + 2 * pad
    txt = Image.new("RGBA", (iw, ih), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    st = max(5, int(px * 0.10))
    x = pad
    for i, wd in enumerate(words):
        d.text((x, pad), wd, font=f, fill=WHITE + (255,), stroke_width=st, stroke_fill=(8, 10, 14, 255)); x += ws[i] + sp
    return np_(shadowed(txt, blur=8, dy=5, alpha=0.55, pad=0))


# ------------------------------------------------------------------ recuadro de las fotos (marco blanco redondeado + sombra)
def window_frame():
    pad = 70
    im = Image.new("RGBA", (WINW + 2 * pad, WINH + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 22, pad + WINW, pad + WINH + 22), radius=WIN_R, fill=170)
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    blk = Image.new("RGBA", im.size, (0, 0, 10, 255)); blk.putalpha(sh)
    im.alpha_composite(blk)
    ImageDraw.Draw(im).rounded_rectangle((pad - WIN_B, pad - WIN_B, pad + WINW + WIN_B, pad + WINH + WIN_B), radius=WIN_R + WIN_B, fill=(255, 255, 255, 255))
    a = np.asarray(im).copy()
    hole = np.zeros(a.shape[:2], np.float32)
    S = 3
    m = Image.new("L", (WINW * S, WINH * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, WINW * S - 1, WINH * S - 1), radius=WIN_R * S, fill=255)
    hole[pad:pad + WINH, pad:pad + WINW] = np.asarray(m.resize((WINW, WINH), Image.LANCZOS)) / 255.0
    a[..., 3] = (a[..., 3] * (1 - hole)).astype(np.uint8)
    mask = np.zeros(a.shape[:2], np.float32); mask[pad:pad + WINH, pad:pad + WINW] = hole[pad:pad + WINH, pad:pad + WINW]
    return a, pad, mask


def window_tag(text):
    """etiqueta blanca bajo el recuadro (p. ej. 'Banco Central del Paraguay')"""
    f = font("ExtraBold", 27)
    w = int(tlen(text.upper(), f, 3)) + 44; h = 52
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=NAVY + (240,))
    d.rounded_rectangle((0, 0, 11, h - 1), radius=6, fill=RED + (255,)); d.rectangle((6, 0, 11, h - 1), fill=RED + (255,))
    x = 28
    for c in text.upper():
        d.text((x, h / 2 + 1), c, font=f, fill=WHITE + (255,), anchor="lm"); x += f.getlength(c) + 3
    return np_(shadowed(im, blur=9, dy=5, alpha=0.5, pad=14)), 14


# ------------------------------------------------------------------ fotos y logo
def load_photo(name, kind):
    """foto del banco: niveles + balance de blancos suave (la fachada lavada tiraba a rosado) + ampliado 2x con enfoque"""
    im = Image.open(os.path.join(FOTOS, name)).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    if kind == "hazy":
        lo, hi = np.percentile(a, 1.0), np.percentile(a, 99.4)
        a = np.clip((a - lo) / (hi - lo), 0, 1) * 255
        m = a.reshape(-1, 3).mean(0); gain = m.mean() / m                     # gray-world al 75 %
        a = np.clip(a * (1 + 0.75 * (gain - 1)), 0, 255)
        g = a.mean(2, keepdims=True); a = np.clip(g + (a - g) * 1.12, 0, 255)
    a = a.astype(np.uint8)
    h, w = a.shape[:2]
    up = cv2.resize(a, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(up, (0, 0), 1.6)
    up = cv2.addWeighted(up, 1.55, blur, -0.55, 0)
    return up, (w, h)


def logo_canvas():
    return G13.logo_canvas()


def end_role():
    return G13.end_role()
