# LOGOS ANIMADOS de CAUSA REPUBLICANA para redes — siguiendo el manual de marca (oct. 2025): solo Montserrat, rojo #C8102E y
# blanco, logotipo / isologotipo / eslogan / /somoscausapy originales (redibujados en alta por marca_causa.py). Movimiento sobrio
# e institucional: el marco se dibuja, la C y la R entran, la estrella se marca, el isologo se ubica y aparecen CAUSA y
# REPUBLICANA letra por letra; el eslogan entra con un barrido. Nada de letras de fantasía ni efectos de caricatura.
#   python logo_animado.py todo        -> assets/marca_causa/animados/: intro 9:16 · 1:1 · 16:9 (fondo rojo y fondo blanco),
#                                         intro transparente (.mov ProRes 4444, para poner encima de un video), cierre 9:16 con
#                                         /somoscausapy y redes, mosca (isologo chico en bucle, transparente)
import os, sys, json, math, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO)
PZ = os.path.join(STUDIO, "assets", "marca_causa", "piezas")
OUT = os.path.join(STUDIO, "assets", "marca_causa", "animados")
FPS = 30
ROJO = np.array([200, 16, 46], np.float32) / 255
BLANCO = np.array([1, 1, 1], np.float32)
ease = lambda x: (lambda v: v * v * (3 - 2 * v))(min(1.0, max(0.0, x)))
easeo = lambda x: 1 - (1 - min(1.0, max(0.0, x))) ** 3
easeb = lambda x: (lambda v: 1 + 2.2 * (v - 1) ** 3 + 1.2 * (v - 1) ** 2)(min(1.0, max(0.0, x)))   # salida con un leve rebote


def mask(name):
    return np.asarray(Image.open(os.path.join(PZ, name)).convert("L"), np.float32) / 255


class Piezas:
    def __init__(self):
        J = json.load(open(os.path.join(PZ, "piezas.json"), encoding="utf-8"))
        self.marco, self.c, self.r, self.estrella = (mask(f) for f in ("iso_marco.png", "iso_c.png", "iso_r.png", "iso_estrella.png"))
        self.iso_h, self.iso_w = self.marco.shape
        self.causa, self.repu = mask("causa.png"), mask("republicana.png")
        self.logo = mask("logotipo.png"); self.lh, self.lw = self.logo.shape
        ic = J["logotipo_icono"]["partes"]
        x0 = min(p["x"] for p in ic); y0 = min(p["y"] for p in ic); x1 = max(p["x"] + p["w"] for p in ic); y1 = max(p["y"] + p["h"] for p in ic)
        self.icon_box = (x0, y0, x1, y1)                                    # dónde va el isologo dentro del logotipo
        self.letras_causa = sorted(J["causa_letras"]["partes"], key=lambda p: p["x"])
        self.letras_repu = sorted(J["republicana_letras"]["partes"], key=lambda p: p["x"])
        e = Image.open(os.path.join(PZ, "eslogan.png")).convert("RGBA")
        self.eslogan = np.asarray(e, np.float32) / 255
        r_relleno = np.maximum(self.r, self.estrella)                     # la R con la estrella tapada (para "marcar" la estrella)
        self.r_lleno = r_relleno


def place(canvas_a, m, x, y, w, h, alpha=1.0):
    """pone la máscara m escalada a (w, h) con su esquina en (x, y) — resolución subpíxel — sumando cobertura en canvas_a"""
    if w < 2 or h < 2 or alpha <= 0: return
    wi, hi = int(math.ceil(w)) + 2, int(math.ceil(h)) + 2
    sm = cv2.resize(m, (max(2, int(round(w))), max(2, int(round(h)))), interpolation=cv2.INTER_AREA if w < m.shape[1] else cv2.INTER_CUBIC)
    fx, fy = x - math.floor(x), y - math.floor(y)
    M = np.float32([[1, 0, fx], [0, 1, fy]])
    sm = cv2.warpAffine(sm, M, (wi, hi), flags=cv2.INTER_LINEAR, borderValue=0)
    X, Y = int(math.floor(x)), int(math.floor(y))
    H, W = canvas_a.shape
    xa, ya, xb, yb = max(0, X), max(0, Y), min(W, X + wi), min(H, Y + hi)
    if xb <= xa or yb <= ya: return
    sub = sm[ya - Y:yb - Y, xa - X:xb - X] * alpha
    canvas_a[ya:yb, xa:xb] = np.maximum(canvas_a[ya:yb, xa:xb], np.clip(sub, 0, 1))


def sweep(m, u, cx=None, cy=None):
    """revela la máscara con un barrido angular (el marco "se dibuja" en sentido horario desde arriba)"""
    if u >= 1: return m
    h, w = m.shape
    cx = w / 2 if cx is None else cx; cy = h / 2 if cy is None else cy
    yy, xx = np.mgrid[0:h, 0:w]
    ang = (np.arctan2(xx - cx, -(yy - cy)) + 2 * np.pi) % (2 * np.pi) / (2 * np.pi)
    soft = np.clip((u - ang) / 0.03, 0, 1)
    return m * soft


class Anim:
    """intro: isologo que se arma al centro -> se ubica en el logotipo -> CAUSA / REPUBLICANA letra por letra -> eslogan"""
    def __init__(self, P, W, H, fondo="rojo", dur=3.8):
        self.P, self.W, self.H, self.fondo, self.dur = P, W, H, fondo, dur
        horiz = W > H
        self.logo_w = min(W * (0.62 if horiz else 0.84), 1180)
        self.logo_h = self.logo_w * P.lh / P.lw
        self.lx = (W - self.logo_w) / 2
        self.ly = H * (0.45 if not horiz else 0.40) - self.logo_h / 2       # el conjunto (logo + eslogan) queda centrado
        s = self.logo_w / P.lw
        x0, y0, x1, y1 = P.icon_box
        self.icon_final = (self.lx + x0 * s, self.ly + y0 * s, (x1 - x0) * s, (y1 - y0) * s)
        big = min(W, H) * 0.42
        self.icon_big = (W / 2 - big / 2, H * (0.47 if not horiz else 0.47) - big / 2, big, big * P.iso_h / P.iso_w)
        self.esl_w = self.logo_w * 0.86; self.esl_h = self.esl_w * P.eslogan.shape[0] / P.eslogan.shape[1]
        self.esl_x = (W - self.esl_w) / 2; self.esl_y = self.ly + self.logo_h + self.logo_h * 0.42

    def coverage(self, t):
        P = self.P; a = np.zeros((self.H, self.W), np.float32)
        # 1) isologo al centro, grande (0–1.15 s); 2) se achica y va a su lugar en el logotipo (1.15–1.75 s)
        u = easeo((t - 1.15) / 0.6)
        bx, by, bw, bh = self.icon_big; fx, fy, fw, fh = self.icon_final
        X, Y, Wd = bx + (fx - bx) * u, by + (fy - by) * u, bw + (fw - bw) * u
        k = Wd / P.iso_w; Hd = P.iso_h * k
        place(a, sweep(P.marco, ease(t / 0.55)), X, Y, Wd, Hd)
        pc = easeb((t - 0.30) / 0.42)                                          # la C crece desde su centro
        if pc > 0:
            sc = 0.55 + 0.45 * pc; cw, ch = P.iso_w * k * sc, P.iso_h * k * sc
            place(a, P.c, X + (Wd - cw) / 2, Y + (Hd - ch) / 2, cw, ch, min(1.0, pc * 1.4))
        pr = easeo((t - 0.48) / 0.40)                                          # la R sube
        if pr > 0:
            place(a, P.r_lleno if t < 0.82 else P.r, X, Y + (1 - pr) * Hd * 0.14, Wd, Hd, min(1.0, pr * 1.3))
        if 0.82 <= t:                                                          # la estrella se "marca" (hueco que crece girando)
            ps = easeb((t - 0.82) / 0.30)
            st = P.estrella
            if ps < 1:
                ang = (1 - ps) * 72; sc = max(0.02, ps)
                M = cv2.getRotationMatrix2D((P.iso_w * 0.5, P.iso_h * 0.5), 0, 1)
                ys, xs = np.where(st > 0.5); cxs, cys = xs.mean(), ys.mean()
                M = cv2.getRotationMatrix2D((float(cxs), float(cys)), ang, sc)
                st = cv2.warpAffine(st, M, (P.iso_w, P.iso_h), flags=cv2.INTER_LINEAR)
            hole = np.zeros_like(a); place(hole, st, X, Y, Wd, Hd)
            r_area = np.zeros_like(a); place(r_area, P.r_lleno, X, Y + 0, Wd, Hd)
            a = np.where(r_area > 0, np.maximum(a - hole * (r_area > 0.5), 0), a)
        # 3) CAUSA y REPUBLICANA letra por letra (desde 1.35 s), cada letra sube 18 px y aparece
        s = self.logo_w / P.lw
        for grupo, m, t0, gap in ((P.letras_causa, P.causa, 1.35, 0.045), (P.letras_repu, P.repu, 1.55, 0.035)):
            for i, p in enumerate(grupo):
                pl = easeo((t - t0 - i * gap) / 0.32)
                if pl <= 0: continue
                crop = m[p["y"]:p["y"] + p["h"], p["x"]:p["x"] + p["w"]]
                place(a, crop, self.lx + p["x"] * s, self.ly + p["y"] * s + (1 - pl) * 18, p["w"] * s, p["h"] * s, pl)
        return np.clip(a, 0, 1)

    def frame(self, t, transparente=False):
        a = self.coverage(t)
        logo_col = BLANCO if self.fondo == "rojo" else ROJO
        bg = ROJO if self.fondo == "rojo" else BLANCO
        if transparente:
            rgb = np.ones((self.H, self.W, 3), np.float32) * logo_col; alpha = a.copy()
        else:
            rgb = bg * (1 - a[..., None]) + logo_col * a[..., None]; alpha = None
        # eslogan (arte oficial a color) con barrido de izquierda a derecha desde 2.05 s
        pe = ease((t - 2.05) / 0.45)
        if pe > 0:
            P = self.P
            e = cv2.resize(P.eslogan, (int(self.esl_w), int(self.esl_h)), interpolation=cv2.INTER_AREA)
            cut = int(e.shape[1] * pe); e = e.copy(); e[:, cut:, 3] = 0
            x, y = int(self.esl_x), int(self.esl_y)
            h, w = e.shape[:2]; ea = e[..., 3:4]
            if transparente:
                rgb[y:y + h, x:x + w] = rgb[y:y + h, x:x + w] * (1 - ea) + e[..., :3] * ea
                alpha[y:y + h, x:x + w] = np.maximum(alpha[y:y + h, x:x + w], ea[..., 0])
            else:
                rgb[y:y + h, x:x + w] = rgb[y:y + h, x:x + w] * (1 - ea) + e[..., :3] * ea
        # brillo sutil que cruza el logo (2.7–3.3 s)
        g = (t - 2.7) / 0.6
        if 0 <= g <= 1:
            xx = np.arange(self.W, dtype=np.float32)[None, :] - (self.lx - 200 + g * (self.logo_w + 400))
            yy = np.arange(self.H, dtype=np.float32)[:, None]
            band = np.exp(-((xx + (yy - self.ly) * 0.35) / 60.0) ** 2) * 0.35
            m = band * a
            rgb = rgb + (1 - rgb) * m[..., None] if self.fondo == "rojo" or transparente else rgb * (1 - 0.4 * m[..., None]) + ROJO * 0.0
        return np.clip(rgb, 0, 1), alpha


def cierre_frame(P, W, H, t):
    """cierre 9:16 como la última página del manual: fondo rojo, logotipo blanco al centro, redes + /somoscausapy abajo"""
    rgb = np.ones((H, W, 3), np.float32) * ROJO
    a = np.zeros((H, W), np.float32)
    lw = W * 0.82; lh = lw * P.lh / P.lw; lx = (W - lw) / 2; ly = H * 0.40 - lh / 2
    pl = easeo(t / 0.6); sc = 0.9 + 0.1 * pl
    place(a, P.logo, lx + lw * (1 - sc) / 2, ly + lh * (1 - sc) / 2, lw * sc, lh * sc, pl)
    rgb = rgb * (1 - a[..., None]) + BLANCO * a[..., None]
    im = Image.fromarray((rgb * 255).astype(np.uint8)); d = ImageDraw.Draw(im)
    fa = ImageFont.truetype(os.path.join(STUDIO, "assets", "fonts", "fa-brands-400.ttf"), 64)
    glyphs = ["", "", "", ""]                      # instagram, facebook, twitter (como el manual), tiktok
    R_ = 64; gapx = 150; cy = int(H * 0.80)
    for i, gch in enumerate(glyphs):
        p = easeb((t - 0.7 - i * 0.12) / 0.35)
        if p <= 0: continue
        cx = W / 2 + (i - 1.5) * gapx; r = R_ * p
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255))
        if p > 0.6:
            f2 = ImageFont.truetype(os.path.join(STUDIO, "assets", "fonts", "fa-brands-400.ttf"), int(64 * min(1.0, p)))
            d.text((cx, cy), gch, font=f2, fill=tuple(int(v * 255) for v in ROJO), anchor="mm")
    ph = ease((t - 1.3) / 0.5)
    if ph > 0:
        f = ImageFont.truetype(os.path.join(STUDIO, "assets", "fonts", "Montserrat-ExtraBold.ttf"), 64)
        txt = "/somoscausapy"; tw = f.getlength(txt)
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(layer)
        dl.text((W / 2, cy + 130), txt, font=f, fill=(255, 255, 255, 255), anchor="mm")
        lm = np.asarray(layer).copy(); x0 = int(W / 2 - tw / 2 - 10); cut = int(x0 + (tw + 20) * ph); lm[:, cut:, 3] = 0
        im.alpha_composite(Image.fromarray(lm)) if im.mode == "RGBA" else im.paste(Image.fromarray(lm), (0, 0), Image.fromarray(lm))
    return np.asarray(im.convert("RGB"), np.float32) / 255


def mosca_frame(P, S, t, dur):
    """isologo chico (mosca) para una esquina, en bucle: aparece, queda, un brillo cada vuelta. Transparente."""
    a = np.zeros((S, S), np.float32)
    w = S * 0.86; h = w * P.iso_h / P.iso_w; x = (S - w) / 2; y = (S - h) / 2
    place(a, P.marco, x, y, w, h); place(a, P.c, x, y, w, h)
    rr = np.zeros_like(a); place(rr, P.r, x, y, w, h); a = np.maximum(a, rr)
    rgb = np.ones((S, S, 3), np.float32)
    g = ((t % dur) / dur - 0.55) / 0.25
    if 0 <= g <= 1:
        xx = np.arange(S, dtype=np.float32)[None, :] - (g * S * 1.6 - S * 0.3); yy = np.arange(S, dtype=np.float32)[:, None]
        band = np.exp(-((xx + yy * 0.4 - S * 0.2) / (S * 0.08)) ** 2)
        rgb = rgb * (1 - 0.25 * band[..., None]) + np.array([1, 0.85, 0.85], np.float32) * 0.25 * band[..., None]
    return rgb, a * 0.92


def audio_intro(path, dur):
    import core
    N = int(dur * core.SR); mix = np.zeros((N, 2), np.float32)
    for t0, name, vol in ((0.0, "whoosh", 0.35), (0.82, "click", 0.45), (1.3, "swish", 0.30), (2.05, "swish", 0.22), (dur - 0.9, "chime", 0.30)):
        x = core.sfx(name); x = x if x.ndim == 2 else np.repeat(x[:, None], 2, 1)
        o = int(t0 * core.SR); k = min(len(x), N - o)
        if k > 0: mix[o:o + k] += x[:k] * vol
    mix[-int(0.4 * core.SR):] *= np.linspace(1, 0, int(0.4 * core.SR))[:, None]
    core.write_wav(path, mix)


def render(nombre, W, H, gen, dur, transparente=False, audio=None):
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, nombre + (".mov" if transparente else ".mp4"))
    if transparente:
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", out]
    else:
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"] + \
              (["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"] if audio else []) + \
              ["-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(int(round(dur * FPS))):
        rgb, alpha = gen(n / FPS)
        if transparente:
            buf = np.dstack([rgb, alpha[..., None]]) if alpha is not None else np.dstack([rgb, np.ones(rgb.shape[:2] + (1,), np.float32)])
            p.stdin.write((np.clip(buf, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        else:
            p.stdin.write((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    print("listo", os.path.basename(out), flush=True)
    return out


def todo():
    P = Piezas(); dur = 3.8
    os.makedirs(OUT, exist_ok=True)
    au = os.path.join(OUT, "_intro.wav"); audio_intro(au, dur)
    outs = []
    for tag, (W, H) in (("9x16", (1080, 1920)), ("1x1", (1080, 1080)), ("16x9", (1920, 1080))):
        for fondo in ("rojo", "blanco"):
            A = Anim(P, W, H, fondo, dur)
            outs.append(render(f"CausaRepublicana_intro_{tag}_fondo_{fondo}", W, H, lambda t, A=A: A.frame(t), dur, audio=au))
    A = Anim(P, 1080, 1920, "rojo", dur)
    outs.append(render("CausaRepublicana_intro_9x16_TRANSPARENTE", 1080, 1920, lambda t: A.frame(t, transparente=True), dur, transparente=True))
    outs.append(render("CausaRepublicana_cierre_9x16", 1080, 1920, lambda t: (cierre_frame(P, 1080, 1920, t), None), 3.5, audio=au))
    outs.append(render("CausaRepublicana_mosca_TRANSPARENTE", 400, 400, lambda t: mosca_frame(P, 400, t, 6.0), 6.0, transparente=True))
    return outs


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "todo": todo()
    elif sys.argv[1] == "cuadros":                                        # fotogramas de prueba
        P = Piezas(); A = Anim(P, 1080, 1920, sys.argv[2] if len(sys.argv) > 2 else "rojo")
        ts = [0.2, 0.45, 0.7, 0.9, 1.1, 1.4, 1.7, 2.2, 3.0, 3.7]
        ims = [cv2.resize((A.frame(t)[0] * 255).astype(np.uint8), (216, 384)) for t in ts]
        cv2.imwrite(os.path.join(STUDIO, "assets", "marca_causa", "cuadros_intro.png"), cv2.cvtColor(np.hstack(ims), cv2.COLOR_RGB2BGR))
        print("ok")
