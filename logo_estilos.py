# ESTILOS NUEVOS de logos animados de CAUSA REPUBLICANA para redes (manual de marca oct. 2025: Montserrat, rojo #C8102E, blanco,
# logotipo / isologotipo / eslogan originales). Todos sobrios e institucionales, sin letras de fantasía. Usa las piezas en alta
# de marca_causa.py y las funciones de logo_animado.py.
#   python logo_estilos.py todo     -> assets/marca_causa/animados/estilos/  (9:16 con sonido + versiones transparentes)
#   python logo_estilos.py cuadros  -> hoja de fotogramas de cada estilo (para revisar)
import os, sys, math
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logo_animado as LA
from logo_animado import place, ease, easeo, easeb, ROJO, BLANCO

OUT = os.path.join(LA.OUT, "estilos")
ROJO_OSC = ROJO * 0.72


def _logo(P, a, cx, cy, w, alpha=1.0, letras_t=None):
    """logotipo completo centrado en (cx, cy) con ancho w; letras_t = avance 0..1 de CAUSA/REPUBLICANA letra por letra"""
    s = w / P.lw; h = P.lh * s; x0, y0 = cx - w / 2, cy - h / 2
    if letras_t is None:
        place(a, P.logo, x0, y0, w, h, alpha); return x0, y0, h
    bx0, by0, bx1, by1 = P.icon_box
    ic = P.logo[by0:by1, bx0:bx1]; place(a, ic, x0 + bx0 * s, y0 + by0 * s, (bx1 - bx0) * s, (by1 - by0) * s, alpha)
    letras = [(p, P.causa) for p in P.letras_causa] + [(p, P.repu) for p in P.letras_repu]
    for i, (p, m) in enumerate(letras):
        pl = easeo(letras_t * len(letras) * 0.55 - i * 0.55 + 0.6)
        if pl <= 0: continue
        crop = m[p["y"]:p["y"] + p["h"], p["x"]:p["x"] + p["w"]]
        place(a, crop, x0 + p["x"] * s, y0 + p["y"] * s + (1 - pl) * 14, p["w"] * s, p["h"] * s, pl * alpha)
    return x0, y0, h


def _iso(P, a, cx, cy, w, alpha=1.0, giro=0.0, escala=1.0):
    """isologotipo CR completo (marco + C + R con la estrella calada), con giro y escala"""
    m = np.maximum(np.maximum(P.marco, P.c), P.r)
    if giro or escala != 1.0:
        M = cv2.getRotationMatrix2D((P.iso_w / 2, P.iso_h / 2), giro, escala)
        m = cv2.warpAffine(m, M, (P.iso_w, P.iso_h), flags=cv2.INTER_LINEAR)
    h = w * P.iso_h / P.iso_w
    place(a, m, cx - w / 2, cy - h / 2, w, h, alpha)


def _eslogan(P, rgb, alpha, x, y, w, u):
    """eslogan oficial (arte a color) con barrido de izquierda a derecha, u = 0..1"""
    if u <= 0: return
    e = cv2.resize(P.eslogan, (int(w), int(w * P.eslogan.shape[0] / P.eslogan.shape[1])), interpolation=cv2.INTER_AREA).copy()
    e[:, int(e.shape[1] * u):, 3] = 0
    x, y = int(x), int(y); h, ww = e.shape[:2]; H, W = rgb.shape[:2]
    if x < 0 or y < 0 or x + ww > W or y + h > H: return
    ea = e[..., 3:4]
    rgb[y:y + h, x:x + ww] = rgb[y:y + h, x:x + ww] * (1 - ea) + e[..., :3] * ea
    if alpha is not None: alpha[y:y + h, x:x + ww] = np.maximum(alpha[y:y + h, x:x + ww], ea[..., 0])


def _compose(bg, a, col, transparente):
    if transparente: return np.ones(a.shape + (3,), np.float32) * col, a.copy()
    return bg * (1 - a[..., None]) + col * a[..., None], None


# ---------------------------------------------------------------- 1. BARRIDO: panel rojo que cruza y deja el logo
def barrido(P, W, H, t, transparente=False):
    """sobre blanco, un panel rojo entra en diagonal desde la izquierda, se planta, el logo blanco aparece adentro; sale al final"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    diag = xx + (yy - H / 2) * 0.25
    span = W * 1.4
    u_in, u_out = easeo(t / 0.55), ease((t - 3.0) / 0.5)
    frente = -W * 0.2 + span * u_in; cola = -W * 0.2 + span * u_out
    panel = np.clip((frente - diag) / 3, 0, 1) * np.clip((diag - cola) / 3, 0, 1) if t >= 3.0 else np.clip((frente - diag) / 3, 0, 1)
    rgb = BLANCO * (1 - panel[..., None]) + ROJO * panel[..., None]
    alpha = panel.copy() if transparente else None
    a = np.zeros((H, W), np.float32)
    pl = easeo((t - 0.45) / 0.5)
    if pl > 0: _logo(P, a, W / 2, H * 0.47, W * 0.80 * (0.94 + 0.06 * pl), pl * (1 - u_out), letras_t=None)
    a *= panel
    rgb = rgb * (1 - a[..., None]) + BLANCO * a[..., None]
    if alpha is not None: alpha = np.maximum(alpha, a)
    _eslogan(P, rgb, alpha, W * 0.16, H * 0.47 + W * 0.17, W * 0.68, ease((t - 1.3) / 0.5) * (1 - u_out))
    return np.clip(rgb, 0, 1), alpha


# ---------------------------------------------------------------- 2. ESTRELLA: la estrella gira, crece y abre el isologo
def estrella(P, W, H, t, transparente=False):
    """sobre rojo: la estrella blanca gira y crece al centro, se abre en el isologo CR, que sube y deja paso al logotipo"""
    a = np.zeros((H, W), np.float32)
    ps = easeb(t / 0.7)
    st = P.estrella; ys, xs = np.where(st > 0.5)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = st[y0:y1 + 1, x0:x1 + 1]
    if t < 1.1:
        ang = (1 - ps) * 220; sz = W * (0.05 + 0.20 * ps) * (1 - ease((t - 0.85) / 0.25) * 0.6)
        M = cv2.getRotationMatrix2D((crop.shape[1] / 2, crop.shape[0] / 2), ang, 1.0)
        c2 = cv2.warpAffine(crop, M, (crop.shape[1], crop.shape[0]), flags=cv2.INTER_LINEAR)
        place(a, c2, W / 2 - sz / 2, H * 0.45 - sz / 2, sz, sz * crop.shape[0] / crop.shape[1], ps)
    pi = easeo((t - 0.85) / 0.5)
    if pi > 0:
        sube = easeo((t - 1.6) / 0.6)
        _iso(P, a, W / 2, H * 0.45 - sube * H * 0.12, W * (0.30 + 0.14 * pi - 0.12 * sube), min(1, pi * 1.3), escala=0.85 + 0.15 * pi)
    pl = ease((t - 1.9) / 0.9)
    if pl > 0:
        s = W * 0.80 / P.lw; bx0, by0, bx1, by1 = P.icon_box
        letras = np.zeros_like(a)
        for grupo, m in ((P.letras_causa, P.causa), (P.letras_repu, P.repu)):
            for p in grupo:
                crop2 = m[p["y"]:p["y"] + p["h"], p["x"]:p["x"] + p["w"]]
                place(letras, crop2, W * 0.5 - (p["x"] - bx1) * 0 + (p["x"] - (bx1 + P.lw) / 2) * s, H * 0.53 + (p["y"] - P.lh / 2) * s,
                      p["w"] * s, p["h"] * s, pl)
        a = np.maximum(a, letras)
    rgb, alpha = _compose(ROJO, a, BLANCO, transparente)
    _eslogan(P, rgb, alpha, W * 0.18, H * 0.66, W * 0.64, ease((t - 2.6) / 0.5))
    return np.clip(rgb, 0, 1), alpha


# ---------------------------------------------------------------- 3. FRANJAS: bandas de la marca que se cruzan
def franjas(P, W, H, t, transparente=False):
    """tres franjas rojas en diagonal entran escalonadas sobre blanco, se abren al centro y el logo rojo entra con un leve impacto"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = (xx * 0.8 - yy * 0.6)
    cob = np.zeros((H, W), np.float32)
    for i, (c, ancho) in enumerate(((-H * 0.18, H * 0.07), (0.0, H * 0.035), (H * 0.18, H * 0.07))):
        u = easeo((t - i * 0.12) / 0.5); salida = ease((t - 1.05) / 0.45)
        frente = -W * 1.2 + (W * 2.4) * u
        dist = np.abs((xx * 0.6 + yy * 0.8) - (W * 0.6 * 0.5 + H * 0.8 * 0.5) - c)
        banda = np.clip((ancho * (1 - salida) - dist) / 2, 0, 1) * np.clip((frente - d) / 4, 0, 1)
        cob = np.maximum(cob, banda)
    a = np.zeros((H, W), np.float32)
    pl = easeb((t - 1.15) / 0.45)
    if pl > 0: _logo(P, a, W / 2, H * 0.46, W * 0.82 * (1.12 - 0.12 * pl), min(1, pl * 1.5))
    if transparente:
        rgb = np.ones((H, W, 3), np.float32) * ROJO; alpha = np.maximum(cob, a)
    else:
        rgb = BLANCO * (1 - cob[..., None]) + ROJO * cob[..., None]
        rgb = rgb * (1 - a[..., None]) + ROJO * a[..., None]; alpha = None
    _eslogan(P, rgb, alpha, W * 0.16, H * 0.46 + W * 0.18, W * 0.68, ease((t - 1.9) / 0.5))
    return np.clip(rgb, 0, 1), alpha


# ---------------------------------------------------------------- 4. LÍNEA: una línea dibuja y revela el nombre
def linea(P, W, H, t, transparente=False):
    """sobre rojo: una línea blanca se dibuja de centro a los lados; el isologo aparece arriba y CAUSA REPUBLICANA sube desde la línea"""
    a = np.zeros((H, W), np.float32)
    ul = easeo(t / 0.6); cy = int(H * 0.50); half = W * 0.40 * ul
    if half > 1: a[cy - 2:cy + 2, int(W / 2 - half):int(W / 2 + half)] = 1.0
    _iso(P, a, W / 2, H * 0.38, W * 0.26, ease((t - 0.45) / 0.45))
    # nombre: sube desde abajo de la línea (máscara: solo se ve por debajo de la línea)
    pn = easeo((t - 0.8) / 0.7)
    if pn > 0:
        nm = np.zeros_like(a); s = W * 1.0 / P.lw
        todas = P.letras_causa + P.letras_repu
        xa, xb = min(p["x"] for p in todas), max(p["x"] + p["w"] for p in todas); ya = min(p["y"] for p in todas)
        for grupo, m in ((P.letras_causa, P.causa), (P.letras_repu, P.repu)):
            for p in grupo:
                crop = m[p["y"]:p["y"] + p["h"], p["x"]:p["x"] + p["w"]]
                place(nm, crop, W / 2 + (p["x"] - (xa + xb) / 2) * s, cy + 30 + (p["y"] - ya) * s + (1 - pn) * 120, p["w"] * s, p["h"] * s)
        nm[:cy + 6] = 0
        a = np.maximum(a, nm)
    rgb, alpha = _compose(ROJO, a, BLANCO, transparente)
    _eslogan(P, rgb, alpha, W * 0.20, H * 0.64, W * 0.60, ease((t - 1.8) / 0.5))
    return np.clip(rgb, 0, 1), alpha


# ---------------------------------------------------------------- 5. TERCIO INFERIOR: placa de marca para poner sobre un video
def tercio(P, W, H, t, transparente=True, dur=5.0):
    """placa abajo (zona segura): barra roja que entra desde la izquierda con el isologo, CAUSA REPUBLICANA y #GanarParaServir;
    queda y sale. Transparente: se pone encima de cualquier video en CapCut"""
    rgb = np.zeros((H, W, 3), np.float32); alpha = np.zeros((H, W), np.float32)
    ui, uo = easeo(t / 0.5), ease((t - (dur - 0.6)) / 0.5)
    bh = int(H * 0.085); by = int(H * 0.70); bw = W * 0.86 * ui * (1 - uo); bx = W * 0.07
    if bw > 2:
        x1 = int(bx + bw); rgb[by:by + bh, int(bx):x1] = ROJO; alpha[by:by + bh, int(bx):x1] = 1
        acc = int(bh * 0.08); rgb[by + bh:by + bh + acc, int(bx):x1] = BLANCO; alpha[by + bh:by + bh + acc, int(bx):x1] = 1
    a = np.zeros((H, W), np.float32)
    vis = ease((t - 0.35) / 0.3) * (1 - ease((t - (dur - 0.75)) / 0.3))
    if vis > 0:
        _iso(P, a, bx + bh * 0.62, by + bh / 2, bh * 0.82, vis)
        s = (bh * 0.62) / P.lh; bx1 = P.icon_box[2]
        nm = np.zeros_like(a)
        place(nm, P.logo[:, bx1 + 10:], bx + bh * 1.25, by + bh * 0.19, (P.lw - bx1 - 10) * s, P.lh * s, vis)
        a = np.maximum(a, nm)
    a *= alpha > 0
    rgb = rgb * (1 - a[..., None]) + BLANCO * a[..., None]
    _eslogan(P, rgb, alpha, bx + bh * 0.2, by + bh * 1.25, W * 0.46, ease((t - 0.7) / 0.5) * (1 - uo))
    if not transparente:
        base = np.ones((H, W, 3), np.float32) * 0.18
        return np.clip(base * (1 - alpha[..., None]) + rgb * alpha[..., None], 0, 1), None
    return np.clip(rgb, 0, 1), alpha


ESTILOS = {"barrido": (barrido, 3.6), "estrella": (estrella, 3.8), "franjas": (franjas, 3.4), "linea": (linea, 3.4)}


def todo():
    P = LA.Piezas(); os.makedirs(OUT, exist_ok=True); outs = []
    LA.OUT, prev = OUT, LA.OUT
    for nombre, (fn, dur) in ESTILOS.items():
        au = os.path.join(OUT, f"_{nombre}.wav"); LA.audio_intro(au, dur)
        for tag, (W, H) in (("9x16", (1080, 1920)), ("1x1", (1080, 1080))):
            outs.append(LA.render(f"CausaRepublicana_{nombre}_{tag}", W, H, lambda t, fn=fn, W=W, H=H: fn(P, W, H, t), dur, audio=au))
        outs.append(LA.render(f"CausaRepublicana_{nombre}_9x16_TRANSPARENTE", 1080, 1920,
                              lambda t, fn=fn: fn(P, 1080, 1920, t, transparente=True), dur, transparente=True))
    outs.append(LA.render("CausaRepublicana_placa_inferior_9x16_TRANSPARENTE", 1080, 1920, lambda t: tercio(P, 1080, 1920, t, True), 5.0,
                          transparente=True))
    outs.append(LA.render("CausaRepublicana_placa_inferior_9x16_muestra", 1080, 1920, lambda t: tercio(P, 1080, 1920, t, False), 5.0))
    LA.OUT = prev
    return outs


def cuadros():
    P = LA.Piezas(); os.makedirs(OUT, exist_ok=True); filas = []
    todos = dict(ESTILOS, placa=(lambda P, W, H, t, transparente=False: tercio(P, W, H, t, False), 5.0))
    for nombre, (fn, dur) in todos.items():
        ts = np.linspace(0.15, dur - 0.1, 8)
        filas.append(np.hstack([cv2.resize((fn(P, 1080, 1920, float(t))[0] * 255).astype(np.uint8), (180, 320)) for t in ts]))
    cv2.imwrite(os.path.join(OUT, "_cuadros_estilos.png"), cv2.cvtColor(np.vstack(filas), cv2.COLOR_RGB2BGR))
    print("ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"todo": todo, "cuadros": cuadros}[sys.argv[1]]()
