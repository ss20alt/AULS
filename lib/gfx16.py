# v16 — panel de LLAMADA con letra (sin avatar), fondo claro, ubicado en la franja verde del boceto del usuario:
# y=862..1196, ancho casi total. Estilo de la letra de Spotify: líneas dichas en gris, línea activa oscura; la palabra en curso en rojo.
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx13 as G13
from gfx5 import font, np_

W, H = 1080, 1920
PANEL_BG, PANEL_BG2 = (250, 250, 253), (240, 242, 249)
NAVY, GRAY, RED, GREEN = (9, 18, 52), (143, 151, 176), (226, 35, 48), (46, 190, 106)
PX0, PX1 = 24, 1056
PW = PX1 - PX0
PANEL_Y0, PANEL_Y1 = 862, 1206
PH = PANEL_Y1 - PANEL_Y0                                   # 334
HDR_H = 74
ROW_H = 60
NROWS = 4
LIN_Y0 = HDR_H + 14
TXT_PX = 40
TXT_X = 48                                                 # margen izquierdo del texto dentro del panel (x=72 en pantalla)
RIGHT = 866                                                # borde derecho de la cabecera dentro del panel (x=890: zona segura)
MAXW = 800


def tlen(text, f, tr=0.0): return sum(f.getlength(c) + tr for c in text) - tr


def _balance(ws, f, sp):
    n = len(ws)
    wl = [f.getlength(w["t"]) for w in ws]
    pre = np.concatenate([[0.0], np.cumsum(wl)]) + np.arange(n + 1) * sp

    def width(i, j): return pre[j] - pre[i] - sp
    INF = 1e18
    best = [INF] * (n + 1); prv = [0] * (n + 1); best[0] = 0.0
    for j in range(1, n + 1):
        for i in range(j):
            if best[i] >= INF: continue
            wd = width(i, j)
            if wd > MAXW and j - i > 1: continue
            last = j == n
            slack = max(0.0, MAXW - wd) / MAXW
            c = slack ** 2 * (0.5 if last else 1.0)
            if last and j - i == 1 and n > 3: c += 0.7
            if (not last) and ws[j - 1]["t"][-1] == ",": c -= 0.12
            v = best[i] + c + 0.05
            if v < best[j]: best[j] = v; prv[j] = i
    cuts, j = [], n
    while j > 0: cuts.append((prv[j], j)); j = prv[j]
    return [ws[i:j] for i, j in cuts[::-1]]


def build_lines(words):
    f = font("ExtraBold", TXT_PX)
    sp = f.getlength(" ")
    sents, cur = [], []
    for w in words:
        cur.append(w)
        if w["t"][-1] in ".?!": sents.append(cur); cur = []
    if cur: sents.append(cur)
    out = []
    for sn in sents:
        for ln in _balance(sn, f, sp):
            x = 0.0; x0s = []
            for wd in ln:
                x0s.append(x); x += f.getlength(wd["t"]) + sp
            out.append(dict(words=ln, x0=x0s, w=x - sp, t0=ln[0]["s"], t1=ln[-1]["e"]))
    return out


def line_sprite(ln, nspoken, mode):
    """'past': gris · 'future': gris tenue · 'active': dicho = azul oscuro, palabra en curso = rojo, lo que falta = gris"""
    f = font("ExtraBold", TXT_PX)
    pad = 10
    w = int(ln["w"]) + 2 * pad + 6; h = ROW_H
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, (wd, x0) in enumerate(zip(ln["words"], ln["x0"])):
        if mode == "past": col, a = GRAY, 255
        elif mode == "future": col, a = GRAY, 150
        else:
            if i < nspoken - 1: col, a = NAVY, 255
            elif i == nspoken - 1: col, a = RED, 255
            else: col, a = GRAY, 190
        d.text((pad + x0, h / 2 + 2), wd["t"], font=f, fill=col + (a,), anchor="lm")
    return np_(im), pad


# ------------------------------------------------------------------ panel claro
def panel_bg():
    S = 3
    t = np.linspace(0, 1, PH, dtype=np.float32)[:, None, None]
    a = np.array(PANEL_BG, np.float32)[None, None, :]; b = np.array(PANEL_BG2, np.float32)[None, None, :]
    img = np.broadcast_to(a * (1 - t) + b * t, (PH, PW, 3)).copy().astype(np.uint8)
    m = Image.new("L", (PW * S, PH * S), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, PW * S - 1, PH * S - 1), radius=30 * S, fill=255)
    mask = np.asarray(m.resize((PW, PH), Image.LANCZOS))
    rgba = np.dstack([img, mask])
    rgba[HDR_H:HDR_H + 2, 36:PW - 36, :3] = (214, 218, 232)
    rgba[0:5, 60:PW - 60, :3] = RED                                      # filo rojo de marca en el borde superior
    rgba[0:5, 60:PW - 60, 3] = np.minimum(rgba[0:5, 60:PW - 60, 3], 255)
    return rgba


def panel_shadow():
    pad = 60
    im = Image.new("L", (PW + 2 * pad, PH + 2 * pad), 0)
    ImageDraw.Draw(im).rounded_rectangle((pad, pad + 14, pad + PW, pad + PH + 14), radius=30, fill=150)
    sh = im.filter(ImageFilter.GaussianBlur(24))
    out = np.zeros((PH + 2 * pad, PW + 2 * pad, 4), np.uint8); out[..., 3] = np.asarray(sh)
    return out, pad


# ------------------------------------------------------------------ cabecera de llamada (sin avatar)
def handset_icon(size=52):
    """círculo verde con el auricular de la fuente del sistema (Segoe UI Symbol, U+1F4DE)"""
    S = 4
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size * S - 1, size * S - 1), fill=GREEN + (255,))
    import plataforma as PL
    f = ImageFont.truetype(PL.sysfont("seguisym"), int(size * S * 0.62))
    if PL.has_font("seguisym") and f.getmask("📞").getbbox():
        d.text((size * S / 2, size * S / 2 + 2), "📞", font=f, fill=(255, 255, 255, 255), anchor="mm")
    else:                                                                  # sin el glifo (Mac): auricular dibujado
        c, r = size * S / 2, size * S * 0.30
        d.rounded_rectangle((c - r, c - r * 0.25, c + r, c + r * 0.25), radius=int(r * 0.25), fill=(255, 255, 255, 255))
        for sx in (-1, 1): d.ellipse((c + sx * r * 0.62 - r * 0.38, c - r * 0.05, c + sx * r * 0.62 + r * 0.38, c + r * 0.62), fill=(255, 255, 255, 255))
    return np_(im.resize((size, size), Image.LANCZOS))


def header_static():
    im = Image.new("RGBA", (PW, HDR_H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((TXT_X + 70, 29), "Lilian Samaniego", font=font("ExtraBold", 31), fill=NAVY + (255,), anchor="lm")
    d.text((TXT_X + 70, 58), "En llamada · Senadora de la Nación", font=font("SemiBold", 21), fill=(98, 108, 138, 255), anchor="lm")
    return np_(im)


def timecodes(total=60):
    f = font("SemiBold", 28)
    out = []
    for s in range(total + 1):
        t = f"{s // 60:02d}:{s % 60:02d}"
        w = int(tlen(t, f, 1)) + 8
        im = Image.new("RGBA", (w, 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x = 4
        for c in t:
            d.text((x, 20), c, font=f, fill=NAVY + (255,), anchor="lm"); x += f.getlength(c) + 1
        out.append(np_(im))
    return out
