# CIERRES, FONDOS EN LOOP y MOSCAS de cada estilo de logo animado de CAUSA REPUBLICANA (logo_estilos.py). Misma marca: Montserrat,
# rojo #C8102E, blanco, piezas originales del logo. Sobrio e institucional.
#   python logo_extras.py todo     -> assets/marca_causa/animados/estilos/extras/
#   python logo_extras.py hoja     -> hoja de fotogramas para revisar
#   · cierre_<estilo>: el logo entra con el movimiento de su estilo y abajo aparecen las redes + /somoscausapy con su acento
#   · fondo_<estilo>: fondo en LOOP perfecto (10 s, el último cuadro empalma con el primero) para transmisiones y vivos
#   · mosca_<estilo>: isologo de esquina transparente en loop (6 s), blanco o rojo
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logo_animado as LA
import logo_estilos as LE
from logo_animado import place, ease, easeo, easeb, ROJO, BLANCO

OUT = os.path.join(LE.OUT, "extras")
FONTS = os.path.join(LA.STUDIO, "assets", "fonts")
GLIFOS = ["", "", "", ""]                  # instagram, facebook, twitter (como el manual), tiktok
LOOP = 10.0


def _redes(rgb, W, H, t, t0, fondo, acento):
    """bloque de redes + /somoscausapy debajo del logo, con el acento de cada estilo"""
    U = LE._U(W, H); fg = BLANCO if fondo == "rojo" else ROJO; bgc = ROJO if fondo == "rojo" else BLANCO
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    cy = H * (0.76 if H > W * 1.2 else 0.80); R = U * 0.052; gap = U * 0.15
    F = lambda c: tuple(int(v * 255) for v in c)
    for i, g in enumerate(GLIFOS):
        p = (easeb if acento in ("estrella", "barrido") else easeo)((t - t0 - i * 0.10) / 0.35)
        if p <= 0: continue
        cx = W / 2 + (i - 1.5) * gap; r = R * (p if acento == "estrella" else 1.0)
        dy = 0 if acento in ("estrella", "barrido") else (1 - p) * U * 0.04
        d.ellipse((cx - r, cy - r + dy, cx + r, cy + r + dy), fill=F(fg) + (int(255 * min(1, p * 1.3)),))
        if p > 0.5:
            f2 = ImageFont.truetype(os.path.join(FONTS, "fa-brands-400.ttf"), max(8, int(R * 1.05 * min(1, p))))
            d.text((cx, cy + dy), g, font=f2, fill=F(bgc) + (255,), anchor="mm")
    ph = ease((t - t0 - 0.55) / 0.5)
    yh = cy + R + U * 0.075
    if ph > 0:
        f = ImageFont.truetype(os.path.join(FONTS, "Montserrat-ExtraBold.ttf"), int(U * 0.058))
        tw = f.getlength("/somoscausapy")
        tl = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(tl).text((W / 2, yh), "/somoscausapy", font=f, fill=F(fg) + (255,), anchor="mm")
        arr = np.asarray(tl).copy(); arr[:, int(W / 2 - tw / 2 - 6 + (tw + 12) * ph):, 3] = 0
        lay.alpha_composite(Image.fromarray(arr))
        # acentos de cada estilo
        ya = int(yh + U * 0.05)
        if acento == "linea":                                          # la línea se dibuja bajo el nombre desde el centro
            hw = tw * 0.55 * easeo((t - t0 - 0.7) / 0.5)
            if hw > 1: d.rectangle((W / 2 - hw, ya, W / 2 + hw, ya + max(2, U * 0.004)), fill=F(fg) + (255,))
        elif acento == "barrido":                                      # barra que cruza de izquierda a derecha y queda
            u = easeo((t - t0 - 0.7) / 0.45)
            if u > 0: d.rectangle((W / 2 - tw * 0.55, ya, W / 2 - tw * 0.55 + tw * 1.1 * u, ya + max(3, U * 0.007)), fill=F(fg) + (255,))
        elif acento == "franjas":                                      # dos franjas cortas en diagonal a los costados
            u = easeo((t - t0 - 0.7) / 0.45); L = U * 0.05 * u; e = U * 0.012
            for sx in (-1, 1):
                x = W / 2 + sx * (tw / 2 + U * 0.05)
                d.polygon([(x - L / 2, yh + L / 2), (x - L / 2 + e, yh + L / 2), (x + L / 2 + e, yh - L / 2), (x + L / 2, yh - L / 2)], fill=F(fg) + (255,))
        elif acento == "estrella":                                     # estrellita que gira y queda antes del nombre
            u = easeb((t - t0 - 0.7) / 0.5)
            if u > 0:
                rr = U * 0.022 * u; x = W / 2 - tw / 2 - U * 0.045; ang = (1 - u) * math.pi
                pts = [(x + (rr if k % 2 == 0 else rr * 0.42) * math.sin(ang + k * math.pi / 5),
                        yh - (rr if k % 2 == 0 else rr * 0.42) * math.cos(ang + k * math.pi / 5)) for k in range(10)]
                d.polygon(pts, fill=F(fg) + (255,))
    im.alpha_composite(lay)
    return np.asarray(im.convert("RGB"), np.float32) / 255


def cierre(nombre, P, W, H, t, fondo=None):
    """cierre propio del estilo: su animación (más rápida y un poco más arriba) y abajo las redes con su acento"""
    fn, dur = LE.ESTILOS[nombre]
    base = LE.FONDO[nombre]; fondo = fondo or base
    tt = min(t * 1.8, dur - 0.7)                                       # queda antes de la salida del estilo (barrido se va a blanco)
    rgb = fn(P, W, H, tt)[0]
    sube = int(H * 0.10 * easeo((t - 1.1) / 0.6)) if H > W * 1.2 else int(H * 0.08 * easeo((t - 1.1) / 0.6))
    if sube:                                                           # el logo sube para hacer lugar a las redes
        bgc = ROJO if base == "rojo" else BLANCO
        rgb = np.concatenate([rgb[sube:], np.ones((sube, W, 3), np.float32) * bgc], 0)
    if fondo != base: rgb = LE.invertir(rgb)
    return _redes(rgb, W, H, t, 1.4, fondo, nombre), None


# ---------------------------------------------------------------- fondos en loop (10 s, empalme perfecto)
def fondo(nombre, P, W, H, t, color="rojo"):
    """fondo para transmisiones/vivos: movimiento lento y periódico (periodo = LOOP) + isologo grande de agua + logo chico abajo"""
    ph = (t % LOOP) / LOOP; two = 2 * math.pi
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = ROJO if color == "rojo" else BLANCO; tono = (ROJO * 0.80) if color == "rojo" else np.array([0.93, 0.88, 0.89], np.float32)
    m = np.zeros((H, W), np.float32)
    if nombre == "franjas":                                            # franjas diagonales que avanzan exactamente un período por vuelta
        per = 0.22 * max(W, H); d = (xx * 0.8 - yy * 0.6) - ph * per
        m = (np.mod(d, per) < per * 0.32).astype(np.float32) * 0.55
        m = cv2.GaussianBlur(m, (0, 0), 2)
    elif nombre == "barrido":                                          # luz diagonal suave que cruza una vez por vuelta
        d = (xx + yy * 0.4) / (W + H * 0.4); c = ph * 1.6 - 0.3
        m = np.exp(-((d - c) / 0.12) ** 2) * 0.7 + np.exp(-((d - c + 1.6) / 0.12) ** 2) * 0.7
    elif nombre == "linea":                                            # líneas horizontales finas que bajan un paso por vuelta
        per = H / 6; d = np.mod(yy - ph * per, per)
        m = np.exp(-(d / 2.0) ** 2) * 0.8
    elif nombre == "estrella":                                         # estrellas tenues que suben y vuelven (posición periódica)
        rng = np.random.RandomState(7); im = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(im)
        for k in range(36):
            x0, y0, s, sp = rng.rand() * W, rng.rand() * H, (6 + rng.rand() * 18) * max(W, H) / 1920, 1 + rng.randint(0, 2)
            y = (y0 - ph * sp * H) % (H + 80) - 40; x = x0 + 12 * math.sin(two * (ph + k / 36))
            pts = [(x + (s if j % 2 == 0 else s * 0.42) * math.sin(j * math.pi / 5), y - (s if j % 2 == 0 else s * 0.42) * math.cos(j * math.pi / 5)) for j in range(10)]
            dr.polygon(pts, fill=int(110 + 100 * (0.5 + 0.5 * math.sin(two * ph + k))))
        m = np.asarray(im, np.float32) / 255 * 0.6
    rgb = base * (1 - m[..., None]) + tono * m[..., None]
    a = np.zeros((H, W), np.float32)
    U = LE._U(W, H); giro = 4 * math.sin(two * ph)                      # isologo de agua que respira (periódico)
    LE._iso(P, a, W * (0.72 if W > H else 0.5), H * (0.45 if W > H else 0.42), U * 0.62, 0.08, giro=giro)
    fg = BLANCO if color == "rojo" else ROJO
    rgb = rgb * (1 - a[..., None]) + fg * a[..., None]
    b = np.zeros((H, W), np.float32)
    lw = U * 0.34; place(b, P.logo, W * 0.05, H - U * 0.05 - lw * P.lh / P.lw, lw, lw * P.lh / P.lw, 0.95)
    rgb = rgb * (1 - b[..., None]) + fg * b[..., None]
    return np.clip(rgb, 0, 1), None


# ---------------------------------------------------------------- moscas (esquina, transparentes, loop 6 s)
def _r_con_estrella(P, ang):
    """R con su estrella calada girada ang grados (para la mosca de la estrella)"""
    st = P.estrella; ys, xs = np.where(st > 0.5)
    M = cv2.getRotationMatrix2D((float(xs.mean()), float(ys.mean())), ang, 1.0)
    st2 = cv2.warpAffine(st, M, (P.iso_w, P.iso_h), flags=cv2.INTER_LINEAR)
    return np.clip(P.r_lleno - st2, 0, 1)


def mosca(nombre, P, S, t, color="blanco", dur=6.0):
    ph = (t % dur) / dur; a = np.zeros((S, S), np.float32)
    w = S * 0.70; h = w * P.iso_h / P.iso_w; x = (S - w) / 2; y = (S - h) / 2
    if nombre == "estrella":                                           # la estrella da una vuelta completa por loop
        ang = 360 * easeo(min(1, ph / 0.35)) if ph < 0.35 else 0
        place(a, P.marco, x, y, w, h); place(a, P.c, x, y, w, h); place(a, _r_con_estrella(P, ang), x, y, w, h)
    else:
        LE._iso(P, a, S / 2, S / 2, w)
    acc = np.zeros_like(a)
    if nombre == "barrido":                                            # brillo diagonal que cruza el isologo
        yy, xx = np.mgrid[0:S, 0:S].astype(np.float32); g = (ph - 0.5) / 0.3
        if 0 <= g <= 1: band = np.exp(-((xx + yy * 0.4 - (g * S * 1.6 - S * 0.2)) / (S * 0.07)) ** 2); a = a * (1 - 0.45 * band)
    elif nombre == "franjas":                                          # tres franjitas que pasan por detrás y se van
        u = ease(min(1, ph / 0.3)) * (1 - ease(max(0, ph - 0.55) / 0.3))
        for i, dy in enumerate((-0.18, 0, 0.18)):
            L = S * 0.95 * ease(min(1, max(0, u * 1.4 - i * 0.15)))
            if L > 2:
                im = Image.new("L", (S, S), 0); ImageDraw.Draw(im).line([(S / 2 - L / 2, S * (0.5 + dy) + L * 0.25), (S / 2 + L / 2, S * (0.5 + dy) - L * 0.25)],
                                                                        fill=255, width=int(S * 0.035))
                acc = np.maximum(acc, np.asarray(im, np.float32) / 255 * 0.55)
        acc = acc * (1 - (a > 0.3))                                     # por detrás del isologo
    elif nombre == "linea":                                            # línea que se dibuja debajo y se retira
        u = easeo(min(1, ph / 0.3)) if ph < 0.6 else 1 - ease((ph - 0.6) / 0.3)
        hw = S * 0.38 * max(0, u)
        if hw > 1: acc[int(y + h + S * 0.05):int(y + h + S * 0.05) + max(2, int(S * 0.012)), int(S / 2 - hw):int(S / 2 + hw)] = 1
    al = np.maximum(a * 0.95, acc)
    col = BLANCO if color == "blanco" else ROJO
    return np.ones((S, S, 3), np.float32) * col, al


def todo():
    P = LA.Piezas(); os.makedirs(OUT, exist_ok=True); outs = []
    LA.OUT, prev = OUT, LA.OUT
    au = os.path.join(OUT, "_cierre.wav"); LA.audio_intro(au, 4.2)
    for n in LE.ESTILOS:
        otro = "blanco" if LE.FONDO[n] == "rojo" else "rojo"
        for tag in ("9x16", "4x5", "1x1", "16x9"):
            W, H = LE.FORMATOS[tag]
            for fo in (LE.FONDO[n], otro):
                outs.append(LA.render(f"CausaRepublicana_cierre_{n}_{tag}_fondo_{fo}", W, H, lambda t, n=n, W=W, H=H, fo=fo: cierre(n, P, W, H, t, fo),
                                      4.2, audio=au))
        for tag in ("16x9", "9x16"):
            W, H = LE.FORMATOS[tag]
            for c in ("rojo", "blanco"):
                outs.append(LA.render(f"CausaRepublicana_fondo_LOOP_{n}_{tag}_{c}", W, H, lambda t, n=n, W=W, H=H, c=c: fondo(n, P, W, H, t, c), LOOP))
        for c in ("blanco", "rojo"):
            outs.append(LA.render(f"CausaRepublicana_mosca_{n}_{c}_TRANSPARENTE", 400, 400, lambda t, n=n, c=c: mosca(n, P, 400, t, c), 6.0,
                                  transparente=True))
    LA.OUT = prev
    return outs


def hoja():
    P = LA.Piezas(); os.makedirs(OUT, exist_ok=True); filas = []
    for n in LE.ESTILOS:
        cel = [cv2.resize(cierre(n, P, 1080, 1920, t)[0], (180, 320)) for t in (0.6, 1.4, 2.0, 4.1)]
        cel += [cv2.resize(fondo(n, P, 1920, 1080, t)[0], (569, 320)) for t in (0.0, 5.0)]
        ms = []
        for t in (0.5, 1.5, 3.5):
            rgb, al = mosca(n, P, 400, t); g = np.ones((400, 400, 3), np.float32) * 0.25
            ms.append(cv2.resize(g * (1 - al[..., None]) + rgb * al[..., None], (160, 160)))
        cel.append(np.pad(np.vstack(ms[:2]), ((0, 0), (0, 0), (0, 0)))[:320])
        filas.append(np.hstack(cel))
    cv2.imwrite(os.path.join(OUT, "_hoja_extras.png"), cv2.cvtColor((np.clip(np.vstack(filas), 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    f0 = fondo("franjas", P, 1920, 1080, 0.0)[0]; f1 = fondo("franjas", P, 1920, 1080, LOOP)[0]
    print("empalme del loop (diferencia):", float(np.abs(f0 - f1).mean()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"todo": todo, "hoja": hoja}[sys.argv[1]]()
