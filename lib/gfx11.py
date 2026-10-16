# v11 — "Preguntas de la prensa": gráficos (PIL → sprites RGBA uint8).
# Paleta: petróleo + amarillo marcador + blanco/negro. Tipografía: Bahnschrift Bold Condensed (títulos/chips) + Montserrat (subtítulos).
# Zona segura: contenido entre y=270..1440, x=60..890 (centro x=475). Las cards del usuario (placa blanca, globo) vienen de gfx6.
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx5 as G
import gfx6 as X
from gfx5 import font, rgba, np_, shadowed

W, H = 1080, 1920
CX = 475
PET_D, PET, PET_L = (3, 24, 30), (7, 52, 62), (14, 84, 96)
YEL, WHITE, BLACK, RED = (255, 201, 60), (250, 250, 252), (8, 10, 14), (226, 35, 48)
WIN_H = 1180                                       # y donde empieza el panel inferior (v1: 960)
PANEL_B = 1440                                     # y donde termina (v3: franja de ~260 px = 13.5 % de la pantalla; el video sigue debajo)
_bf = {}


def bfont(px, wght=700, wdth=75):
    k = (px, wght, wdth)
    if k not in _bf:
        import plataforma as PL
        f = ImageFont.truetype(PL.sysfont("bahnschrift"), px)           # en Mac: DIN Alternate (Bahnschrift es de Windows)
        try: f.set_variation_by_axes([wght, wdth])
        except Exception: pass
        _bf[k] = f
    return _bf[k]


def tlen(text, f, tr=0.0): return sum(f.getlength(c) + tr for c in text) - tr


# ------------------------------------------------------------------ fondos
def panel_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.clip((yy - WIN_H) / (PANEL_B - WIN_H), 0, 1)
    c0 = np.array(PET, np.float32); c1 = np.array(PET_D, np.float32)
    img = c0[None, None] * (1 - t[..., None]) + c1[None, None] * t[..., None]
    glow = np.exp(-(((xx - 700) / 520) ** 2 + ((yy - (WIN_H + 130)) / 160) ** 2))[..., None]
    img += glow * np.array([6, 38, 44], np.float32)
    hatch = (((xx + yy) % 46) < 2).astype(np.float32)[..., None] * 3.0                # tramado diagonal muy tenue
    img += hatch
    img += np.random.default_rng(5).normal(0, 1.1, (H, W, 1)).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def ext_bg():
    """fondo petróleo liso con tramado: rellena fuera del cuadro del video (arriba/costados)"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.broadcast_to(np.array(PET, np.float32), (H, W, 3)).copy()
    img += (((xx + yy) % 46) < 2).astype(np.float32)[..., None] * 3.0
    img += np.random.default_rng(6).normal(0, 1.1, (H, W, 1)).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def bottom_line():
    im = np.zeros((4, W, 4), np.uint8); im[..., :3] = YEL; im[..., 3] = 255
    return im


def seam_sprite():
    h = 46
    im = np.zeros((h, W, 4), np.uint8)
    a = (np.linspace(1, 0, h) ** 1.8 * 150).astype(np.uint8)
    im[..., :3] = 0; im[..., 3] = a[:, None]
    im[:4, :, :3] = YEL; im[:4, :, 3] = 255
    return im


# ------------------------------------------------------------------ tinta amarilla (bordes rotos)
def ink_bg(w, h, seed, color, pad=14, amp=4.0, alpha=250):
    r = np.random.default_rng(seed)
    Hh, Ww = h + 2 * pad, w + 2 * pad

    def nz(n, a):
        s = gaussian_filter1d(r.normal(0, 1, n), 1.0) * 1.8 + gaussian_filter1d(r.normal(0, 1, n), 7) * 1.6
        s = s + gaussian_filter1d((r.random(n) < 0.012) * r.normal(0, 3, n), 0.8) * 2
        return s / (np.abs(s).max() + 1e-6) * a

    top = pad + nz(Ww, amp); bot = pad + h + nz(Ww, amp)
    left = pad + nz(Hh, amp * 1.8); right = pad + w + nz(Hh, amp * 1.8)
    yy = np.arange(Hh)[:, None]; xx = np.arange(Ww)[None, :]
    m = ((yy >= top[None, :]) & (yy <= bot[None, :]) & (xx >= left[:, None]) & (xx <= right[:, None])).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 0.8)
    out = np.zeros((Hh, Ww, 4), np.uint8)
    out[..., :3] = color; out[..., 3] = (m * alpha).astype(np.uint8)
    return out


def banner_sprite(text, maxw=800, seed=7):
    """banner de pincel amarillo con texto negro (gancho)"""
    px = 96
    while px > 40 and tlen(text, bfont(px), 1.5) > maxw - 90: px -= 4
    f = bfont(px)
    w = int(tlen(text, f, 1.5)) + 90; h = int(px * 1.18) + 40
    im = Image.fromarray(ink_bg(w, h, seed, YEL, pad=14, amp=5.0)); d = ImageDraw.Draw(im)
    x = 14 + 45
    for c in text:
        d.text((x, 14 + 16), c, font=f, fill=BLACK + (255,)); x += f.getlength(c) + 1.5
    return np_(im)


def sub_sprite(words, key=False, px=60, seed=11):
    """subtítulo de 2-3 palabras: blanco con contorno negro; si key → caja de marcador amarilla con texto negro"""
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    if key:
        padx, pady = 30, 12
        w = int(total) + 2 * padx; h = int(px * 1.22) + 2 * pady
        im = Image.fromarray(ink_bg(w, h, seed, YEL, pad=12, amp=3.6)); d = ImageDraw.Draw(im)
        x = 12 + padx
        for i, wd in enumerate(words):
            d.text((x, 12 + pady - 3), wd, font=f, fill=BLACK + (255,)); x += ws[i] + sp
        return np_(im)
    pad = 36
    iw, ih = int(total) + 2 * pad, int(px * 1.25) + 2 * pad
    txt = Image.new("RGBA", (iw, ih), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
    st = max(5, int(px * 0.10))
    x = pad
    for i, wd in enumerate(words):
        d.text((x, pad), wd, font=f, fill=WHITE + (255,), stroke_width=st, stroke_fill=BLACK + (255,)); x += ws[i] + sp
    return np_(shadowed(txt, blur=8, dy=5, alpha=0.55, pad=0))


# ------------------------------------------------------------------ panel
def header_chip(num, topic, maxw=820):
    f1, px = bfont(42), 38
    while px > 26 and tlen(topic.upper(), bfont(px), 1.0) > maxw - 150: px -= 2
    f2 = bfont(px)
    tw = tlen(topic.upper(), f2, 1.0)
    w = int(78 + tw + 30); h = 58
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(255, 255, 255, 28), outline=(255, 255, 255, 70), width=2)
    d.rounded_rectangle((0, 0, 66, h - 1), radius=14, fill=YEL + (255,))
    d.rectangle((36, 0, 66, h - 1), fill=YEL + (255,))
    if num is None:
        pts = []
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5; rr = 22 if k % 2 == 0 else 9
            pts.append((33 + rr * math.cos(ang), h / 2 + 1 + rr * math.sin(ang)))
        d.polygon(pts, fill=BLACK + (255,))
    else:
        bb = d.textbbox((0, 0), f"{num:02d}", font=f1)
        d.text((33 - (bb[2] - bb[0]) / 2 - bb[0], h / 2 - (bb[3] - bb[1]) / 2 - bb[1] - 1), f"{num:02d}", font=f1, fill=BLACK + (255,))
    x = 82
    for c in topic.upper():
        d.text((x, h / 2 - 1), c, font=f2, fill=WHITE + (255,), anchor="lm"); x += f2.getlength(c) + 1.0
    return np_(im)


def status_sprite(text, color):
    f = bfont(30, 700, 80)
    w = int(tlen(text, f, 4)) + 46; h = 40
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((4, h / 2 - 7, 18, h / 2 + 7), fill=color + (255,))
    x = 30
    for c in text:
        d.text((x, h / 2 - 1), c, font=f, fill=color + (255,), anchor="lm"); x += f.getlength(c) + 4
    return np_(im)


def kw_chip(text, maxw=830):
    px = 42
    while px > 24 and tlen(text, bfont(px, 700, 78), 1.0) > maxw - 70: px -= 2
    f = bfont(px, 700, 78)
    w = int(tlen(text, f, 1.0)) + 56; h = 52
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=12, fill=(250, 250, 252, 255))
    d.rounded_rectangle((0, 0, 12, h - 1), radius=6, fill=YEL + (255,)); d.rectangle((7, 0, 12, h - 1), fill=YEL + (255,))
    x = 28
    for c in text:
        d.text((x, h / 2 - 1), c, font=f, fill=PET_D + (255,), anchor="lm"); x += f.getlength(c) + 1.0
    return np_(shadowed(im, blur=9, dy=6, alpha=0.5, pad=14)), 14


def mic_sprite(size=120):
    S = 3
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = size * S / 2
    d.rounded_rectangle((c - 34 * S / 1.6, c - 62 * S / 1.6, c + 34 * S / 1.6, c + 18 * S / 1.6), radius=int(34 * S / 1.6), fill=WHITE + (255,))
    d.arc((c - 54 * S / 1.6, c - 36 * S / 1.6, c + 54 * S / 1.6, c + 52 * S / 1.6), 20, 160, fill=WHITE + (255,), width=int(9 * S / 1.6))
    d.rectangle((c - 5 * S / 1.6, c + 50 * S / 1.6, c + 5 * S / 1.6, c + 78 * S / 1.6), fill=WHITE + (255,))
    d.rounded_rectangle((c - 34 * S / 1.6, c + 74 * S / 1.6, c + 34 * S / 1.6, c + 86 * S / 1.6), radius=int(6 * S / 1.6), fill=WHITE + (255,))
    for k in range(5):                                                         # rejilla del micrófono
        y = c - 46 * S / 1.6 + k * 12 * S / 1.6
        d.line((c - 24 * S / 1.6, y, c + 24 * S / 1.6, y), fill=PET + (200,), width=int(3 * S / 1.6))
    return np_(im.resize((size, size), Image.LANCZOS))


def ring_sprite(rad, wd=5, color=YEL, alpha=255):
    d = rad * 2 + 20
    im = Image.new("RGBA", (d * 2, d * 2), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse((d - rad * 2, d - rad * 2, d + rad * 2, d + rad * 2), outline=color + (alpha,), width=wd * 2)
    return np_(im.resize((d, d), Image.LANCZOS))


def dots_sprite(n, cur):
    w = n * 34 + 6; h = 22
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i in range(n):
        x = 3 + i * 34
        d.rounded_rectangle((x, 4, x + 26, 16), radius=6, fill=(YEL if i == cur else (255, 255, 255)) + ((255,) if i == cur else (60,)))
    return np_(im)


# ------------------------------------------------------------------ sello de redes (arriba a la derecha, como en las referencias)
def watermark():
    fa = ImageFont.truetype(os.path.join(G.FONTS, "fa-brands-400.ttf"), 24)
    icons = ["\uf09a", "\uf16d", "\ue61b", "\ue07b", "\uf232"]
    f = bfont(26, 700, 85)
    handle = "/LILIANSAMANIEGOPY"
    w = max(int(5 * 40 + 6), int(tlen(handle, f, 1.2)) + 8) + 28; h = 82
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=14, fill=(0, 0, 0, 105))
    x0 = (w - (5 * 40 - 8)) / 2
    for i, g in enumerate(icons):
        x = x0 + i * 40
        d.rounded_rectangle((x, 9, x + 32, 41), radius=9, fill=RED + (255,))
        bb = d.textbbox((0, 0), g, font=fa)
        d.text((x + 16 - (bb[2] - bb[0]) / 2 - bb[0], 25 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=WHITE + (255,))
    xx = (w - tlen(handle, f, 1.2)) / 2
    for c in handle:
        d.text((xx, 62), c, font=f, fill=WHITE + (255,), anchor="lm"); xx += f.getlength(c) + 1.2
    return np_(im)


# ------------------------------------------------------------------ gancho: visor B/N
def viewfinder():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x0, x1, y0, y1, L, t = 76, 874, 300, 1420, 78, 6
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line((cx, cy, cx + sx * L, cy), fill=(245, 245, 245, 255), width=t)
        d.line((cx, cy, cx, cy + sy * L), fill=(245, 245, 245, 255), width=t)
    cxm, cym = (x0 + x1) // 2, (y0 + y1) // 2 + 20
    d.line((cxm - 34, cym, cxm + 34, cym), fill=(245, 245, 245, 235), width=3)
    d.line((cxm, cym - 34, cxm, cym + 34), fill=(245, 245, 245, 235), width=3)
    f = bfont(34, 700, 85)
    d.text((x0 + 26, y0 + 30), "CONFERENCIA DE PRENSA", font=f, fill=(245, 245, 245, 235))
    return np_(im)


def rec_dot():
    im = Image.new("RGBA", (130, 52), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((4, 12, 30, 38), fill=RED + (255,))
    d.text((42, 25), "REC", font=bfont(36, 700, 85), fill=(245, 245, 245, 255), anchor="lm")
    return np_(im)


def dust_layers(n=8):
    out = []
    for k in range(n):
        r = np.random.default_rng(100 + k)
        im = np.zeros((H, W, 4), np.uint8)
        for _ in range(26):
            cv2.circle(im, (int(r.integers(30, W - 30)), int(r.integers(30, H - 30))), int(r.integers(1, 3)), (235, 235, 235, 230), -1, cv2.LINE_AA)
        for _ in range(3):
            x0, y0 = int(r.integers(60, W - 60)), int(r.integers(60, H - 300)); L = int(r.integers(30, 120))
            cv2.line(im, (x0, y0), (x0 + int(r.integers(-6, 7)), y0 + L), (225, 225, 225, 200), 1, cv2.LINE_AA)
        out.append(im)
    return out


# ------------------------------------------------------------------ cierre amarillo
def end_sprites():
    out = {}
    fa = ImageFont.truetype(os.path.join(G.FONTS, "fa-brands-400.ttf"), 58)
    icons = ["\uf09a", "\uf16d", "\ue61b", "\ue07b", "\uf232"]
    size, gap = 100, 12
    sprites = []
    for g in icons:
        im = Image.new("RGBA", (size + 40, size + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle((20, 20, 20 + size, 20 + size), radius=32, fill=BLACK + (255,))
        bb = d.textbbox((0, 0), g, font=fa)
        d.text((20 + size / 2 - (bb[2] - bb[0]) / 2 - bb[0], 20 + size / 2 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=YEL + (255,))
        sprites.append(np_(im))
    out["icons"] = sprites
    out["isize"], out["igap"] = size + 40, gap
    f = bfont(76, 700, 80)
    t = "/LILIANSAMANIEGOPY"
    im = Image.new("RGBA", (int(tlen(t, f, 2)) + 40, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 20
    for c in t:
        d.text((x, 60), c, font=f, fill=BLACK + (255,), anchor="lm"); x += f.getlength(c) + 2
    out["handle"] = np_(im)
    f2 = bfont(36, 600, 85)
    t2 = "SENADORA DE LA NACIÓN"
    im = Image.new("RGBA", (int(tlen(t2, f2, 7)) + 40, 64), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 20
    for c in t2:
        d.text((x, 32), c, font=f2, fill=(8, 10, 14, 230), anchor="lm"); x += f2.getlength(c) + 7
    out["role"] = np_(im)
    return out
