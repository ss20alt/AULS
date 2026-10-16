# Marca CAUSA REPUBLICANA (manual oct. 2025: Montserrat Medium/ExtraBold/Black · rojo HEX #C8102E (Pantone 186C) · blanco ·
# logotipo, isologotipo "CR" con estrella, eslogan #GanarParaServir, /somoscausapy). Los logos del PDF son MÁSCARAS (la forma)
# en baja resolución; acá se redibujan en alta desde sus contornos (vectorizado) y se separan en piezas para animarlas.
#   python marca_causa.py extraer   -> assets/marca_causa/piezas/*.png (máscaras en alta) + piezas.json
import os, sys, json
import numpy as np, cv2
from PIL import Image

STUDIO = os.path.dirname(os.path.abspath(__file__))
M = os.path.join(STUDIO, "assets", "marca_causa")
OUT = os.path.join(M, "piezas")
ROJO = (200, 16, 46)            # HEX #C8102E (texto del manual) — el dibujo del PDF se ve como #ED1C24 (conversión CMYK)
ROJO_PDF = (237, 28, 36)
BLANCO = (255, 255, 255)
MANUAL = r"C:\Users\acer\Downloads\MANUAL DE MARCA CAUSA REPUBLICANA.pdf"


def _mask(name):
    return np.array(Image.open(os.path.join(M, name)).convert("L"))


def vectorizar(mask, escala):
    """máscara chica -> máscara grande con bordes limpios: contornos subpíxel (agrandado suave + umbral) y relleno antialias"""
    big = cv2.resize(mask, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), escala * 0.35)
    _, b = cv2.threshold(big, 127, 255, cv2.THRESH_BINARY)
    cs, hier = cv2.findContours(b, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    ss = 4                                                              # relleno a 4× y reducción: borde antialias
    canvas = np.zeros((b.shape[0] * ss, b.shape[1] * ss), np.uint8)
    smooth = [cv2.approxPolyDP(c, 0.6, True) * ss for c in cs]
    cv2.drawContours(canvas, smooth, -1, 255, thickness=cv2.FILLED, hierarchy=hier, lineType=cv2.LINE_8)
    return cv2.resize(canvas, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_AREA)


def componentes(mask, min_area=30):
    n, lab, st, cen = cv2.connectedComponentsWithStats((mask > 127).astype(np.uint8), 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a >= min_area: out.append(dict(i=i, x=int(x), y=int(y), w=int(w), h=int(h), area=int(a), cx=float(cen[i][0]), cy=float(cen[i][1])))
    return out, lab


def extraer():
    os.makedirs(OUT, exist_ok=True)
    piezas = {}
    # --- logotipo completo (ícono + CAUSA + REPUBLICANA), 1531×268 -> ×3
    lg = vectorizar(_mask("mask_p2_x33.png"), 3.0)
    Image.fromarray(lg).save(os.path.join(OUT, "logotipo.png"))
    comps, lab = componentes(lg, 400)
    H = lg.shape[0]
    icon_w = int(0.18 * lg.shape[1])
    icono = [c for c in comps if c["x"] + c["w"] <= icon_w + 20]
    causa = sorted([c for c in comps if c not in icono and c["cy"] < H * 0.5], key=lambda c: c["x"])
    repub = sorted([c for c in comps if c not in icono and c["cy"] >= H * 0.5], key=lambda c: c["x"])
    def guardar(nombre, grupo):
        m = np.isin(lab, [c["i"] for c in grupo]).astype(np.uint8) * lg
        Image.fromarray(m).save(os.path.join(OUT, nombre + ".png"))
        return dict(archivo=nombre + ".png", partes=[{k: c[k] for k in ("x", "y", "w", "h")} for c in grupo])
    piezas["logotipo_icono"] = guardar("logotipo_icono", icono)
    piezas["causa_letras"] = guardar("causa", causa)
    piezas["republicana_letras"] = guardar("republicana", repub)
    piezas["logotipo"] = dict(archivo="logotipo.png", w=lg.shape[1], h=lg.shape[0], icono_w=icon_w)
    # --- isologotipo "CR" con estrella (263×264 -> ×6 ≈ 1580 px): marco, C, R, estrella
    iso = vectorizar(_mask("mask_p2_x35.png"), 6.0)
    Image.fromarray(iso).save(os.path.join(OUT, "isologo.png"))
    comps, lab = componentes(iso, 200)
    comps = sorted(comps, key=lambda c: -c["area"])
    marco = max(comps, key=lambda c: c["w"] * c["h"])                    # el que abarca todo
    letras = sorted([c for c in comps if c is not marco], key=lambda c: c["x"])  # C (izquierda) y R (derecha)
    def guardar_iso(nombre, m):
        Image.fromarray(m).save(os.path.join(OUT, nombre + ".png"))
        ys, xs = np.where(m > 127)
        return dict(archivo=nombre + ".png", x=int(xs.min()), y=int(ys.min()), w=int(xs.max() - xs.min()), h=int(ys.max() - ys.min()),
                    cx=float(xs.mean()), cy=float(ys.mean()))
    comp = lambda c: (lab == c["i"]).astype(np.uint8) * iso
    piezas["iso_marco"] = guardar_iso("iso_marco", comp(marco))
    if len(letras) >= 1: piezas["iso_c"] = guardar_iso("iso_c", comp(letras[0]))
    if len(letras) >= 2:
        r = comp(letras[1]); piezas["iso_r"] = guardar_iso("iso_r", r)
        # la estrella es un HUECO de la R: relleno de agujeros − R = estrella (para animarla aparte)
        b = (r > 127).astype(np.uint8); h_, w_ = b.shape
        flood = b.copy(); mask = np.zeros((h_ + 2, w_ + 2), np.uint8); cv2.floodFill(flood, mask, (0, 0), 1)
        hueco = ((flood == 0) & (b == 0)).astype(np.uint8) * 255
        hueco = cv2.GaussianBlur(hueco, (0, 0), 0.8)
        piezas["iso_estrella"] = guardar_iso("iso_estrella", hueco)
    piezas["isologo"] = dict(archivo="isologo.png", w=iso.shape[1], h=iso.shape[0], componentes=len(comps))
    # --- eslogan (arte oficial a color, 1712×196): se usa tal cual, con su transparencia
    g = np.array(Image.open(os.path.join(M, "img_p4_x44.png")).convert("RGB")); a = _mask("mask_p4_x44.png")
    Image.fromarray(np.dstack([g, a])).save(os.path.join(OUT, "eslogan.png"))
    piezas["eslogan"] = dict(archivo="eslogan.png", w=g.shape[1], h=g.shape[0])
    piezas["colores"] = dict(rojo=ROJO, rojo_pdf=ROJO_PDF, blanco=BLANCO)
    json.dump(piezas, open(os.path.join(OUT, "piezas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print({k: (v.get("partes") and len(v["partes"])) or v.get("w") for k, v in piezas.items() if isinstance(v, dict)})
    return piezas


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "extraer": extraer()
