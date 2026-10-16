# v6 — gráficos al estilo de las referencias del canal: cajas de tinta con barrido, globo de cómic, franjas de frase clave,
# cierre blanco. Todo el contenido queda dentro de la ZONA SEGURA (y 270–1440, x 60–890); las tarjetas viven en el
# "carril inferior" (y 1290–1420), a la altura de los micrófonos.
import os
import numpy as np, cv2
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter1d
import gfx5 as G
from gfx5 import W, H, SAFE, RED, YELLOW, WHITE, font, np_, rgba, shadowed

INK = (11, 12, 16)
LANE_Y = 1296                      # borde superior del carril de tarjetas (a la altura de los micrófonos)


# ------------------------------------------------------------------ tinta: fondo con bordes rotos
def ink_bg(w, h, seed, pad=16, amp=4.5):
    r = np.random.default_rng(seed)
    Hh, Ww = h + 2 * pad, w + 2 * pad

    def nz(n, a):
        s = gaussian_filter1d(r.normal(0, 1, n), 1.0) * 1.8 + gaussian_filter1d(r.normal(0, 1, n), 7) * 1.6
        sp = (r.random(n) < 0.012) * r.normal(0, 3, n)
        s = s + gaussian_filter1d(sp, 0.8) * 2
        return s / (np.abs(s).max() + 1e-6) * a

    top = pad + nz(Ww, amp); bot = pad + h + nz(Ww, amp)
    left = pad + nz(Hh, amp * 1.8); right = pad + w + nz(Hh, amp * 1.8)
    yy = np.arange(Hh)[:, None]; xx = np.arange(Ww)[None, :]
    m = ((yy >= top[None, :]) & (yy <= bot[None, :]) & (xx >= left[:, None]) & (xx <= right[:, None])).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 0.8)
    out = np.zeros((Hh, Ww, 4), np.uint8)
    out[..., :3] = INK; out[..., 3] = (m * 246).astype(np.uint8)
    return out


def _txt(img, xy, s, f, col, anchor="la"):
    ImageDraw.Draw(img).text(xy, s, font=f, fill=col + (255,), anchor=anchor)


def ink_title(num, title, sub, seed=3):
    """caja de tinta de capítulo: '01 · TÍTULO' + subtítulo"""
    f1, f2 = font("ExtraBold", 40), font("SemiBold", 27)
    t = f"{num:02d}  {title.upper()}"
    w = int(max(f1.getlength(t), f2.getlength(sub)) + 76); h = 112
    bg = ink_bg(w, h, seed); im = Image.fromarray(bg); pad = 16
    d = ImageDraw.Draw(im)
    nlen = f1.getlength(f"{num:02d}  ")
    d.text((pad + 38, pad + 16), f"{num:02d}", font=f1, fill=RED + (255,))
    d.text((pad + 38 + nlen, pad + 16), title.upper(), font=f1, fill=WHITE + (255,))
    d.text((pad + 38, pad + 66), sub, font=f2, fill=(205, 212, 226, 255))
    return np_(im), pad


def ink_name(name, role, seed=5):
    f1, f2 = font("ExtraBold", 44), font("SemiBold", 28)
    w = int(max(f1.getlength(name.upper()), f2.getlength(role)) + 76); h = 114
    bg = ink_bg(w, h, seed); im = Image.fromarray(bg); pad = 16
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad + 20, pad + 22, pad + 27, pad + h - 22), radius=3, fill=RED + (255,))
    d.text((pad + 44, pad + 14), name.upper(), font=f1, fill=WHITE + (255,))
    d.text((pad + 44, pad + 66), role, font=f2, fill=(205, 212, 226, 255))
    return np_(im), pad


def wipe(spr, p, mode):
    """barrido horizontal de izquierda a derecha con borde irregular. mode 'in' (revela) | 'out' (oculta). p 0..1"""
    h, w = spr.shape[:2]
    jag = np.sin(np.arange(h) * 0.9) * 9 + np.sin(np.arange(h) * 0.23 + 1.0) * 16
    edge = -50 + (w + 100) * p
    xx = np.arange(w)[None, :]
    vis = (xx < (edge + jag)[:, None]) if mode == "in" else (xx >= (edge + jag)[:, None])
    out = spr.copy()
    out[..., 3] = (out[..., 3] * vis).astype(np.uint8)
    return out


# ------------------------------------------------------------------ globo de cómic (pregunta de la prensa)
def bubble_sprite(text, nvis, maxw=640, px=37):
    """globo blanco con cola abajo-izquierda; solo se dibujan las primeras nvis palabras. devuelve (sprite, tipx, tipy)"""
    S = 2
    f = font("ExtraBold", px * S)
    words = text.split(); lines, cur = [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if f.getlength(t) <= maxw * S: cur = t
        else: lines.append(cur); cur = w_
    lines.append(cur)
    padx, pady, pitch = 38 * S, 26 * S, int(px * 1.22) * S
    bw = int(max(f.getlength(l) for l in lines)) + 2 * padx
    bh = pitch * len(lines) + 2 * pady
    tail = 56 * S; m = 10 * S
    iw, ih = bw + 2 * m, bh + tail + 2 * m
    body = Image.new("L", (iw, ih), 0); d = ImageDraw.Draw(body)
    d.rounded_rectangle((m, m, m + bw, m + bh), radius=44 * S, fill=255)
    d.polygon([(m + 62 * S, m + bh - 6 * S), (m + 124 * S, m + bh - 6 * S), (m + 18 * S, m + bh + tail)], fill=255)
    b = np.asarray(body).astype(np.float32) / 255
    outline = cv2.dilate(b, np.ones((3 * S + 1, 3 * S + 1), np.uint8))
    img = np.zeros((ih, iw, 4), np.float32)
    img[..., :3] = 16; img[..., 3] = outline * 255
    img[..., :3] = img[..., :3] * (1 - b[..., None]) + 255 * b[..., None]
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    k = 0
    for li, l in enumerate(lines):
        x = m + padx
        for w_ in l.split():
            if k < nvis: d.text((x, m + pady + li * pitch), w_, font=f, fill=(14, 14, 18, 255))
            x += f.getlength(w_ + " "); k += 1
    im = im.resize((iw // S, ih // S), Image.LANCZOS)
    sp = shadowed(im, blur=9, dy=6, alpha=0.45, pad=18)
    tip = (18 + (m + 18 * S) / S, 18 + (m + bh + tail) / S)
    return np_(sp), tip[0], tip[1], len(words)


# ------------------------------------------------------------------ subtítulo con franja de tinta (frases clave)
def caption_ink_sprite(words, active, px=62, maxw=700, seed=11):
    f = font("ExtraBold", px)
    sp = f.getlength(" ")
    ws = [f.getlength(w) for w in words]
    total = sum(ws) + sp * (len(words) - 1)
    if total > maxw: raise ValueError("franja: texto demasiado ancho")
    padx, pady = 34, 14
    w, h = int(total) + 2 * padx, int(px * 1.22) + 2 * pady
    bg = ink_bg(w, h, seed, pad=12, amp=3.8); im = Image.fromarray(bg); d = ImageDraw.Draw(im)
    x = 12 + padx
    for i, wd in enumerate(words):
        d.text((x, 12 + pady - 2), wd, font=f, fill=(YELLOW if i == active else WHITE) + (255,))
        x += ws[i] + sp
    return np_(im)


# ------------------------------------------------------------------ cierre blanco con íconos rojos (como las referencias)
def endcard_white():
    """devuelve (fondo_RGB, [(sprite,x,y,delay)])"""
    fa = font_fa(60)
    icons = ["", "", "", "", ""]       # facebook, instagram, X, tiktok, whatsapp
    out = []
    size, gap = 116, 26
    total = 5 * size + 4 * gap
    x0 = (W - total) // 2 - 6
    for i, g in enumerate(icons):
        im = rgba(size + 40, size + 40); d = ImageDraw.Draw(im)
        d.rounded_rectangle((20, 20, 20 + size, 20 + size), radius=30, fill=RED + (255,))
        bb = d.textbbox((0, 0), g, font=fa)
        d.text((20 + size / 2 - (bb[2] - bb[0]) / 2 - bb[0], 20 + size / 2 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=WHITE + (255,))
        out.append((np_(im), x0 + i * (size + gap) - 20 + 6, 870, 0.30 + 0.07 * i))
    f3 = font("Black", 50)
    t = "/LILIANSAMANIEGOPY"; bb = ImageDraw.Draw(rgba(10, 10)).textbbox((0, 0), t, font=f3)
    im = rgba(bb[2] - bb[0] + 60, bb[3] - bb[1] + 60); ImageDraw.Draw(im).text((30 - bb[0], 30 - bb[1]), t, font=f3, fill=RED + (255,))
    out.append((np_(im), (W - im.width) // 2, 1030, 0.75))
    return out


def font_fa(px):
    from PIL import ImageFont
    return ImageFont.truetype(os.path.join(G.FONTS, "fa-brands-400.ttf"), px)


# ------------------------------------------------------------------ placa de nombre: tarjeta blanca (distinta de las navy de capítulo)
def name_card(name, role):
    f1, f2 = font("ExtraBold", 44), font("Bold", 25)
    r = role.upper()
    spc = 2.2
    rw = sum(f2.getlength(ch) + spc for ch in r)
    w = int(max(f1.getlength(name), rw) + 44 + 52); h = 116
    im = rgba(w, h); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=20, fill=(250, 250, 253, 246))
    d.rounded_rectangle((0, 0, 24, h - 1), radius=12, fill=RED + (255,))
    d.rectangle((14, 0, 24, h - 1), fill=RED + (255,))
    d.text((44 + 8, 14), name, font=f1, fill=(10, 17, 32, 255))
    x = 44 + 8
    for ch in r:
        d.text((x, 72), ch, font=f2, fill=RED + (255,)); x += f2.getlength(ch) + spc
    return np_(shadowed(im, blur=12, dy=7, alpha=0.5, pad=20)), 20
