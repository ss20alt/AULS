# Gráficos del video v5 (sprites RGBA con PIL). Todo respeta la ZONA SEGURA de Reels / TikTok / Shorts:
#   superior 270 px · inferior 480 px (contenido hasta y=1440) · derecha 190 px (contenido hasta x=890) · izquierda 60 px.
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
SAFE = dict(top=270, bottom=1440, left=60, right=890)       # límites de contenido (px)
STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))         # lib/ está dentro del estudio
FONTS = os.path.join(STUDIO_DIR, "assets", "fonts")
RED, NAVY, YELLOW, WHITE = (226, 35, 48), (10, 17, 32), (255, 216, 59), (255, 255, 255)

_f = {}


def font(weight, px):
    k = (weight, px)
    if k not in _f: _f[k] = ImageFont.truetype(os.path.join(FONTS, f"Montserrat-{weight}.ttf"), px)
    return _f[k]


def rgba(w, h): return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def shadowed(img, blur=10, dy=6, alpha=0.55, pad=24):
    """devuelve img con sombra suave debajo, con margen"""
    out = rgba(img.width + 2 * pad, img.height + 2 * pad)
    sh = rgba(out.width, out.height)
    a = img.split()[3].point(lambda v: int(v * alpha))
    blk = Image.new("RGBA", img.size, (0, 0, 0, 255)); blk.putalpha(a)
    sh.paste(blk, (pad, pad + dy)); sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh); out.alpha_composite(img, (pad, pad))
    return out


def np_(img): return np.asarray(img).copy()


# ------------------------------------------------------------------ subtítulos (resaltado palabra a palabra)
def caption_sprite(words, active, px=62, maxw=700):
    """words: lista de str; active: índice resaltado (o -1). Hasta 2 líneas centradas, máx. maxw px de ancho."""
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    if total <= maxw: lines = [list(range(len(words)))]
    else:   # mejor corte en 2 líneas (equilibradas)
        best, bi = 1e9, 1
        for i in range(1, len(words)):
            a = sum(ws[:i]) + sp * (i - 1); b = sum(ws[i:]) + sp * (len(words) - i - 1)
            if max(a, b) < best: best, bi = max(a, b), i
        lines = [list(range(bi)), list(range(bi, len(words)))]
    pitch = int(px * 1.22)
    pad = 40
    lw = [sum(ws[i] for i in l) + sp * (len(l) - 1) for l in lines]
    iw, ih = int(max(lw)) + 2 * pad, pitch * len(lines) + 2 * pad
    img = rgba(iw, ih)
    d = ImageDraw.Draw(img)
    st = max(4, int(px * 0.105))
    for li, l in enumerate(lines):
        x = (iw - lw[li]) / 2
        y = pad + li * pitch
        for i in l:
            col = YELLOW if i == active else WHITE
            d.text((x, y), words[i], font=f, fill=col + (255,), stroke_width=st, stroke_fill=(8, 10, 18, 255))
            x += ws[i] + sp
    return np_(shadowed(img, blur=9, dy=5, alpha=0.6, pad=0))


# ------------------------------------------------------------------ chip de capítulo (esquina superior izquierda, dentro de zona segura)
def chip_sprite(num, title, sub):
    f1, f2, fn = font("ExtraBold", 31), font("SemiBold", 25), font("Black", 30)
    t1, t2 = title.upper(), sub
    w1, w2 = f1.getlength(t1), f2.getlength(t2)
    h = 92
    wtxt = max(w1, w2)
    w = int(24 + 56 + 18 + wtxt + 30)
    im = rgba(w, h); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=22, fill=NAVY + (222,))
    d.rounded_rectangle((0, 0, 11, h - 1), radius=6, fill=RED + (255,))
    cx, cy = 24 + 28, h // 2
    d.ellipse((cx - 28, cy - 28, cx + 28, cy + 28), fill=RED + (255,))
    n = f"{num:02d}"; bb = d.textbbox((0, 0), n, font=fn)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), n, font=fn, fill=WHITE + (255,))
    x0 = 24 + 56 + 18
    d.text((x0, 14), t1, font=f1, fill=WHITE + (255,))
    d.text((x0, 52), t2, font=f2, fill=(200, 208, 224, 255))
    return np_(shadowed(im, blur=12, dy=6, alpha=0.5, pad=20)), 20


# ------------------------------------------------------------------ tarjeta de pregunta (gancho)
def question_sprite(tag, text, maxw=770):
    ft, fq = font("ExtraBold", 25), font("Bold", 40)
    words = text.split(); lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if fq.getlength(t) <= maxw - 64: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    h = 36 + 54 + 52 * len(lines) + 24
    im = rgba(maxw, h); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, maxw - 1, h - 1), radius=24, fill=NAVY + (226,))
    d.rounded_rectangle((0, 0, 11, h - 1), radius=6, fill=RED + (255,))
    tw = ft.getlength(tag) + 40
    d.rounded_rectangle((32, 24, 32 + tw, 24 + 44), radius=22, fill=RED + (255,))
    d.text((52, 24 + 22), tag, font=ft, fill=WHITE + (255,), anchor="lm")
    for i, ln in enumerate(lines):
        d.text((32, 24 + 44 + 26 + i * 52), ln, font=fq, fill=WHITE + (255,))
    return np_(shadowed(im, blur=12, dy=6, alpha=0.5, pad=20)), 20


# ------------------------------------------------------------------ placa de nombre (tercio inferior, sobre y=1440)
def nameplate_sprite(name, role):
    f1, f2 = font("ExtraBold", 44), font("SemiBold", 28)
    w = int(max(f1.getlength(name), f2.getlength(role)) + 80)
    h = 112
    im = rgba(w, h); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=20, fill=NAVY + (230,))
    d.rounded_rectangle((0, 0, 11, h - 1), radius=6, fill=RED + (255,))
    d.text((40, 18), name, font=f1, fill=WHITE + (255,))
    d.text((40, 70), role, font=f2, fill=(200, 208, 224, 255))
    return np_(shadowed(im, blur=12, dy=6, alpha=0.5, pad=20)), 20


# ------------------------------------------------------------------ viñeta + degradado inferior (legibilidad de subtítulos)
def vignette_layer():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W * 0.70)) ** 2 + ((yy - H * 0.46) / (H * 0.62)) ** 2)
    v = 1 - np.clip(r - 0.55, 0, 1) ** 1.6 * 0.42
    g = np.clip((yy - 1000) / 520, 0, 1) ** 1.4 * 0.30          # oscurece el tercio inferior
    t = np.clip((300 - yy) / 300, 0, 1) ** 1.3 * 0.18            # y un poco la parte superior
    return (v * (1 - g) * (1 - t)).astype(np.float32)[..., None]


# ------------------------------------------------------------------ tarjeta final
def endcard_layers():
    """devuelve [(sprite, x, y)] para el cierre (centrado dentro de la zona segura)."""
    out = []
    f1, f2, f3 = font("Black", 64), font("SemiBold", 32), font("Black", 42)
    def txt(s, f, col, spacing=0):
        bb = ImageDraw.Draw(rgba(10, 10)).textbbox((0, 0), s, font=f)
        im = rgba(bb[2] - bb[0] + 60, bb[3] - bb[1] + 60); d = ImageDraw.Draw(im)
        d.text((30 - bb[0], 30 - bb[1]), s, font=f, fill=col + (255,)); return im
    a = shadowed(txt("LILIAN SAMANIEGO", f1, WHITE), blur=10, dy=5, alpha=0.6, pad=0)
    out.append((np_(a), (W - a.width) // 2, 700))
    b = txt("SENADORA DE LA NACIÓN", f2, (214, 222, 238)); out.append((np_(b), (W - b.width) // 2, 830))
    bar = rgba(160, 10); ImageDraw.Draw(bar).rounded_rectangle((0, 0, 159, 9), radius=5, fill=RED + (255,))
    out.append((np_(bar), (W - 160) // 2, 800))
    fa = ImageFont.truetype(os.path.join(FONTS, "fa-brands-400.ttf"), 54)
    icons = ["", "", "", "", ""]
    row = rgba(5 * 112 + 4 * 22, 112); d = ImageDraw.Draw(row)
    for i, g in enumerate(icons):
        x = i * 134
        d.rounded_rectangle((x, 0, x + 111, 111), radius=30, fill=RED + (255,))
        bb = d.textbbox((0, 0), g, font=fa)
        d.text((x + 56 - (bb[2] - bb[0]) / 2 - bb[0], 56 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=WHITE + (255,))
    r = shadowed(row, blur=10, dy=6, alpha=0.5, pad=20)
    out.append((np_(r), (W - r.width) // 2, 920))
    h = txt("/LILIANSAMANIEGOPY", f3, (255, 255, 255))
    out.append((np_(h), (W - h.width) // 2, 1090))
    return out
