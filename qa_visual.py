# Estudio de edición — QA VISUAL automático: lo que antes se veía "a ojo".
# Recompone fotogramas de muestra con el estilo real, registrando cada pieza gráfica que se dibuja (subtítulos, tarjetas, rótulos),
# y mide sobre el fotograma final:
#   CONTRAST    texto que no se lee contra lo que tiene detrás (contraste WCAG < 3:1; p. ej. crema sobre el escudo dorado)
#   CARD_BLEND  tarjeta o caja del mismo color que lo que tapa (p. ej. caja roja sobre el saco rojo)
#   TEXT_ON_FACE texto o tarjeta encima de la cara
#   MIRROR      borde de imagen espejada (relleno por reflejo visible)
#   SAFE_ZONE   texto en zonas que tapa la app (arriba, abajo, columna de íconos a la derecha)
#   python qa_visual.py <proyecto> [cada_n_fotogramas]
import os as _os; _os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # Mac: operaciones sin MPS caen al procesador
import os, sys, json, importlib
import numpy as np, cv2, torch

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO)
FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _lin(c):
    c = c.float()
    return torch.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lum(x):
    """luminancia relativa (WCAG) de un tensor (3, …) en 0–1"""
    l = _lin(x)
    return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]


def ratio(a, b):
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


class Recorder:
    def __init__(self, blend):
        self.blend, self.items, self.skip = blend, [], set()

    def __call__(self, fr, spr, x, y, alpha=1.0):
        if fr.shape[0] == 3 and fr.shape[1] == 1920 and id(spr) not in self.skip:
            self.items.append((spr, int(round(x)), int(round(y)), float(alpha)))
        return self.blend(fr, spr, x, y, alpha)


def mirror_cols(theta, dx=0.0, W=1080):
    """columnas de la salida que caen FUERA del video original (se rellenan por reflejo): cálculo exacto con la cámara"""
    th00, th02 = float(theta[0, 0, 0]), float(theta[0, 0, 2]) + float(theta[0, 0, 0]) * 2 * dx / W
    xn = (2 * np.arange(W) + 1) / W - 1
    gx = th00 * xn + th02
    return int((np.abs(gx) > 1.0 + 1e-4).sum())


def faces(bg):
    im = (bg.clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous().cpu().numpy()
    g = cv2.cvtColor(cv2.resize(im, (540, 960)), cv2.COLOR_RGB2GRAY)
    fc = [(2 * x, 2 * y, 2 * w, 2 * h) for x, y, w, h in FACE.detectMultiScale(g, 1.1, 5, minSize=(60, 60))]
    fc = [f for f in fc if f[3] >= 150 and f[1] + f[3] / 2 < 1100]          # su cara: grande y en la mitad de arriba (no "caras" en los micrófonos)
    return [max(fc, key=lambda f: f[2] * f[3])] if fc else []


def run(name, step=10, log=print, cfg=None, firmar=False):
    import build
    cfg = cfg or build.get_cfg(name)
    pdir = os.path.join(STUDIO, "projects", name)
    ctx = build.Ctx(cfg, pdir)
    ctx.cam.zoom_mul = cfg.get("zoom_mul", 1.0)
    mod = importlib.import_module("styles." + cfg["style"])
    import core
    mods = [m for m in (mod, sys.modules.get("styles.common"), sys.modules.get("styles.base"), core) if m is not None]
    rec = Recorder(core.blend)
    last_bg = {}
    orig_warp = core.warp_src

    def warp_rec(*a, **k):
        out = orig_warp(*a, **k)
        if out.shape[-2:] == (1920, 1080):
            last_bg["x"] = out
            last_bg["mir"] = max(last_bg.get("mir", 0), mirror_cols(a[1] if len(a) > 1 else k["theta"], k.get("dx", a[3] if len(a) > 3 else 0.0)))
        return out
    saved = [(m, getattr(m, "blend", None), getattr(m, "warp_src", None)) for m in mods]
    for m in mods:
        if hasattr(m, "blend"): m.blend = rec
        if hasattr(m, "warp_src"): m.warp_src = warp_rec
    try:
        S = mod.Style(ctx); S.setup()
        for t_ in getattr(S, "qa_decor", []): rec.skip.add(id(t_))                 # piezas decorativas declaradas por el estilo
        hidden = cfg.get("face_hidden_s", 0.0)
        # tramos donde el estilo tapa la cara A PROPÓSITO (recuadros de fotos del reportaje, etc.)
        cover = list(getattr(S, "qa_cover", [])) + [(c_["s"], c_["e"]) for c_ in getattr(S, "cuts", []) if isinstance(c_, dict) and "s" in c_]
        # el cuadro n del video es el cuadro n de selects.mp4 (el habla va seguida desde 0): se leen SOLO los cuadros que se revisan
        rstep = step if all(s["out"] == ctx.SEL0[i] for i, s in enumerate(ctx.SEGS)) else 1
        rd = core.Reader(ctx.selects, step=rstep) if getattr(S, "uses_video", True) else None
        # transiciones (barridos, desenfoques de costura): la legibilidad se juzga en fotogramas estables, no en los 0.2–0.4 s del cambio
        trans = sorted({int(round(v["o0"] * core.FPS)) for v in ctx.SC.values()} | {int(f) for f in (S.whips() if hasattr(S, "whips") else [])})
        near_trans = lambda n: any(abs(n - f) <= 7 for f in trans)
        F = {"CONTRAST": [], "CARD_BLEND": [], "TEXT_ON_FACE": [], "MIRROR": [], "SAFE_ZONE": [], "CLIPPED": []}
        n_checked = 0
        for n in range(ctx.TOTAL):
            it = ctx.item_at(n)
            sample = (n % step == 0) and it["kind"] == "speech" and n < ctx.END0 - 6 and not near_trans(n)   # sin el fundido final ni transiciones
            if not sample:
                if it["kind"] == "speech" and rd is not None and n % rstep == 0: rd.get()
                continue
            rec.items = []; last_bg.clear()
            fr = S.compose(n, it, rd if it["kind"] == "speech" else None)
            n_checked += 1
            t = n / core.FPS
            bg = last_bg.get("x")
            if last_bg.get("mir", 0) > 12: F["MIRROR"].append((round(t, 1), last_bg["mir"]))      # > 12 px de imagen espejada
            fbox = faces(bg) if (bg is not None and t >= hidden) else []
            Y = lum(fr)
            for spr, x, y, a in rec.items:
                if a < 0.9: continue                                              # solo piezas ya asentadas (no animaciones de entrada/salida)
                h, w = spr.shape[1:]
                if h >= 1500 or (w >= 1000 and h >= 600): continue                 # capa de pantalla completa (partículas, barridos): no es texto
                x0, y0, x1, y1 = max(0, x), max(0, y), min(1080, x + w), min(1920, y + h)
                if x1 - x0 < 20 or y1 - y0 < 20: continue                          # líneas y barras finas: no es texto
                full_ink = int((spr[3].float() * a > 0.85).sum())                  # texto que se sale del cuadro (cortado por el borde)
                if full_ink > 400:
                    inside = int((spr[3, y0 - y:y1 - y, x0 - x:x1 - x].float() * a > 0.85).sum())
                    if (full_ink - inside) / full_ink > 0.03: F["CLIPPED"].append((round(t, 1), (x, y, w, h)))
                al = spr[3, y0 - y:y1 - y, x0 - x:x1 - x].float() * a
                ink = al > 0.85
                n_ink = int(ink.sum())
                if n_ink < 400: continue
                yy = Y[y0:y1, x0:x1]
                vals = yy[ink]
                p10, p90 = float(torch.quantile(vals, 0.10)), float(torch.quantile(vals, 0.90))
                # ¿el texto se lee? contraste interno (letra con contorno o sobre su propia tarjeta) o contra lo que tiene alrededor
                if ratio(p10, p90) < 3.0:
                    pad = 8
                    xa, ya, xb, yb = max(0, x0 - pad), max(0, y0 - pad), min(1080, x1 + pad), min(1920, y1 + pad)
                    full = torch.zeros(yb - ya, xb - xa, device=Y.device)
                    full[y0 - ya:y1 - ya, x0 - xa:x1 - xa] = al
                    ring = full < 0.05
                    if int(ring.sum()) > 200:
                        sur = float(Y[ya:yb, xa:xb][ring].median()); inkm = float(vals.median())
                        r = ratio(inkm, sur)
                        if r < 3.0: F["CONTRAST"].append((round(t, 1), (x0, y0, x1 - x0, y1 - y0), round(r, 2)))
                # tarjeta o caja del mismo color que lo que tiene detrás
                rgb = fr[:, y0:y1, x0:x1][:, ink].float()
                dom = rgb.median(1).values
                share = float(((rgb - dom[:, None]).abs().max(0).values < 0.06).float().mean())
                if share > 0.45 and n_ink > 3000:
                    pad = 10
                    xa, ya, xb, yb = max(0, x0 - pad), max(0, y0 - pad), min(1080, x1 + pad), min(1920, y1 + pad)
                    full = torch.zeros(yb - ya, xb - xa, device=Y.device)
                    full[y0 - ya:y1 - ya, x0 - xa:x1 - xa] = al
                    ring = full < 0.05
                    if int(ring.sum()) > 200:
                        sur = fr[:, ya:yb, xa:xb][:, ring].float().median(1).values
                        if float((dom - sur).abs().max()) < 0.10: F["CARD_BLEND"].append((round(t, 1), (x0, y0, x1 - x0, y1 - y0)))
                # sobre la cara (zona de ojos y boca)
                for fx, fy, fw, fh in ([] if any(a_ <= t < b_ for a_, b_ in cover) else fbox):
                    cx0, cy0, cx1, cy1 = fx + 0.15 * fw, fy + 0.2 * fh, fx + 0.85 * fw, fy + 0.95 * fh
                    ix0, iy0, ix1, iy1 = int(max(cx0, x0)), int(max(cy0, y0)), int(min(cx1, x1)), int(min(cy1, y1))
                    if ix1 > ix0 and iy1 > iy0:
                        cov = float((al[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] > 0.5).float().sum()) / ((cx1 - cx0) * (cy1 - cy0))
                        if cov > 0.08: F["TEXT_ON_FACE"].append((round(t, 1), round(cov, 2)))
                # zona segura: arriba (<250), abajo (>1460) y columna de íconos de la app (x>900, y 800–1460)
                ys = torch.arange(y0, y1, device=Y.device)[:, None].expand(y1 - y0, x1 - x0)
                xs = torch.arange(x0, x1, device=Y.device)[None, :].expand(y1 - y0, x1 - x0)
                bad = ((ys < 250) | (ys > 1460) | ((xs > 900) & (ys > 800) & (ys < 1460))) & ink
                if float(bad.sum()) / n_ink > 0.25: F["SAFE_ZONE"].append((round(t, 1), (x0, y0, x1 - x0, y1 - y0)))
        if rd is not None: rd.close()
    finally:
        for m, b, w in saved:
            if b is not None: m.blend = b
            if w is not None: m.warp_src = w
    findings = []
    SEV = {"CONTRAST": "media", "TEXT_ON_FACE": "media", "MIRROR": "media", "CARD_BLEND": "baja", "SAFE_ZONE": "baja", "CLIPPED": "media"}
    TXT = {"CONTRAST": "texto con poco contraste", "TEXT_ON_FACE": "texto/tarjeta sobre la cara", "MIRROR": "borde de imagen espejada",
           "CARD_BLEND": "tarjeta del mismo color que el fondo", "SAFE_ZONE": "texto en zona que tapa la app", "CLIPPED": "texto cortado por el borde del cuadro"}
    for k, v in F.items():
        if len({e[0] for e in v}) >= 2:                                           # al menos dos muestras: no un fotograma suelto
            ts = sorted({e[0] for e in v})
            findings.append((SEV[k], k, f"{TXT[k]} en {len(ts)} de {n_checked} muestras (ej. {ts[:5]} s)", "ver qa_visual.json"))
    out = dict(checked=n_checked, step=step, detail={k: v[:40] for k, v in F.items()})
    if firmar: out.update(firma=firma(name, cfg), hallazgos=findings)          # el control final puede reutilizarlo si nada cambió
    json.dump(out, open(os.path.join(pdir, "qa_visual.json"), "w"), indent=1)
    log(f"[qa visual] {name}: {n_checked} fotogramas · " + (", ".join(f"{k}×{len(v)}" for k, v in F.items() if v) or "sin problemas"))
    return findings


def firma(name, cfg):
    """huella de todo lo que define los cuadros del video: configuración, EDL, palabras, escenas, selects y el código que dibuja"""
    import hashlib, glob
    pdir = os.path.join(STUDIO, "projects", name)
    h = hashlib.sha1(json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    for f in ("edl.json", "words.json", "scenes.json"):
        p = os.path.join(pdir, f)
        h.update(open(p, "rb").read() if os.path.exists(p) else b"-")
    files = [os.path.join(pdir, "selects.mp4")] + sorted(glob.glob(os.path.join(STUDIO, "styles", "*.py")) + glob.glob(os.path.join(STUDIO, "lib", "*.py"))
                                                          + glob.glob(os.path.join(STUDIO, "clients", "*.json")) + glob.glob(os.path.join(STUDIO, "*.py")))
    for p in files:
        if os.path.exists(p):
            st = os.stat(p); h.update(f"{os.path.basename(p)}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


def reutilizable(name, cfg, step):
    """hallazgos de la verificación previa si revisó los MISMOS cuadros con al menos esta densidad; si no, None"""
    p = os.path.join(STUDIO, "projects", name, "qa_visual.json")
    try:
        d = json.load(open(p))
        if d.get("firma") and d.get("step", 10 ** 9) <= step and d["firma"] == firma(name, cfg): return [tuple(f) for f in d["hallazgos"]]
    except Exception: pass
    return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for f in run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10): print(" ", f)
