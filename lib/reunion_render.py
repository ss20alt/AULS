# Render del FORMATO REUNIÓN (lo usa reunion.py edit). Panel 4:5 a ancho completo (≈1.25–1.4× de ampliación, casi la calidad
# original), fondo = la misma imagen desenfocada, titular ABAJO (carril de los micrófonos), placa con el nombre de cada persona la primera vez que habla,
# subtítulos de un solo estilo, cierre de la ficha del cliente. Cámara estática: estabilización (vidstab) + recorte anclado a la cara.
import os, sys, json, subprocess, wave, time, re
from concurrent.futures import ThreadPoolExecutor
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import signal
from scipy.ndimage import gaussian_filter1d

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(STUDIO, "assets", "fonts")
FPS, W, H = 30, 1080, 1920
PANEL_Y, PANEL_H = 286, 1350
# carriles de gráficos (zona segura 9:16 = y 270–1440): titular abajo, a la altura de los micrófonos (pedido del usuario);
# subtítulos encima del titular; placa de nombre encima de los subtítulos
TITLE_Y, CAP_Y, NAME_Y = 1288, 1196, 1018
TM = ("zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=300,format=gbrpf32le,zscale=p=bt709,"
      "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv:d=error_diffusion,format=yuv420p")
CROP_MIN, CROP_MAX = 860.0, 1080.0          # alto del recorte en la fuente: nunca más de ~1.57× de ampliación
K_FACE = 3.25                               # alto del recorte ≈ 3.25 × tamaño de la cara


def jload(p): return json.load(open(p, encoding="utf-8"))
def jsave(o, p): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def RS(name, *p): return os.path.join(STUDIO, "sources", name, "reunion", *p)
def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


def font(w, s):
    p = os.path.join(FONTS, f"Montserrat-{w}.ttf")
    if not os.path.exists(p): p = os.path.join(FONTS, "Montserrat-Bold.ttf")
    return ImageFont.truetype(p, s)


# =========================================================================================== preparar cada bloque
def prepare(name, pd):
    """por bloque: tramo SDR a 30 fps con márgenes (color = hable npl300), estabilización suave y la cara de quien habla cuadro a cuadro"""
    E = jload(os.path.join(pd, "edl.json")); meta = jload(RS(name, "meta.json")); W_ = jload(RS(name, "face_windows.json"))
    wk = os.path.join(pd, "blocks"); os.makedirs(wk, exist_ok=True)
    import plataforma as PL
    jobs = []
    for bid, spk, st, en in E["blocks"]:
        segs = [s for s in E["segments"] if s["block"] == bid]
        f0 = max(0, min(s["fs"] for s in segs) - 15); f1 = max(s["fe"] for s in segs) + E["tail"] + E["xf"] + 21
        jobs.append((bid, spk, f0, f1))

    def one(j):
        bid, spk, f0, f1 = j
        mz, sz = os.path.join(wk, f"mz_{bid}.mp4"), os.path.join(wk, f"sz_{bid}.mp4")
        vf = "fps=30," + (TM if meta.get("hdr") else "format=yuv420p")
        enc = ["-c:v", "h264_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", "14", "-b:v", "40M"] if PL.ENCODER == "nvenc" else ["-c:v", "libx264", "-preset", "fast", "-crf", "14"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{f0 / 30:.5f}", "-i", meta["path"], "-t", f"{(f1 - f0) / 30:.5f}", "-an", "-vf", vf,
                        *enc, "-g", "30", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", mz], check=True)
        trf = os.path.join(wk, f"st_{bid}.trf").replace("\\", "/").replace(":", "\\:")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mz, "-vf", f"vidstabdetect=shakiness=6:accuracy=15:stepsize=4:mincontrast=0.2:result='{trf}'", "-f", "null", "-"], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mz, "-vf", f"vidstabtransform=input='{trf}':smoothing=75:optalgo=gauss:optzoom=0:zoom=0:crop=black:interpol=bicubic",
                        *enc, "-g", "30", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", sz], check=True)
        n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", sz],
                               capture_output=True, text=True).stdout.strip().strip(","))
        return bid, dict(f0=f0, frames=n, expected=f1 - f0)

    with ThreadPoolExecutor(3) as ex: res = dict(ex.map(one, jobs))
    for bid, r in res.items():
        if r["frames"] < r["expected"] - 2: raise RuntimeError(f"bloque {bid}: {r['frames']} cuadros de {r['expected']}")
    jsave(res, os.path.join(wk, "mz.json"))
    # cara de quien habla: semilla = ventana de "qué cara habla" más cercana al centro del bloque
    det = cv2.FaceDetectorYN.create(os.path.join(STUDIO, "models", "yunet.onnx"), "", (960, 540), 0.55, 0.3, 50)
    for bid, spk, st, en in E["blocks"]:
        cand = [w for w in W_ if w["spk"] == spk and w["e"] > st and w["s"] < en] or [w for w in W_ if w["spk"] == spk]
        mid = (st + en) / 2
        seed = min(cand, key=lambda w: abs((w["s"] + w["e"]) / 2 - mid))
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", os.path.join(wk, f"sz_{bid}.mp4"), "-vf", "scale=960:540", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        faces = []
        while True:
            b = p.stdout.read(960 * 540 * 3)
            if len(b) < 960 * 540 * 3: break
            _, f = det.detect(np.frombuffer(b, np.uint8).reshape(540, 960, 3))
            faces.append([] if f is None else [((x + fw / 2) * 2, (y + fh / 2) * 2, max(fw, fh) * 2) for x, y, fw, fh in f[:, :4]])
        n = len(faces); f0 = res[bid]["f0"]
        imid = min(max(int(round((seed["s"] + seed["e"]) / 2 * FPS)) - f0, 0), n - 1)
        tr = np.full((n, 3), np.nan)

        def pick(i, ref):
            best = None
            for c in faces[i]:
                d = np.hypot(c[0] - ref[0], c[1] - ref[1])
                if d < max(140, 0.9 * ref[2]) and (best is None or d < best[0]): best = (d, c)
            return None if best is None else best[1]

        s0 = None
        for k in range(0, 60):
            for i in (imid + k, imid - k):
                if s0 is None and 0 <= i < n:
                    c = pick(i, (seed["cx"], seed["cy"], max(seed["size"], 160)))
                    if c: s0 = (i, c)
        if s0 is None: raise RuntimeError(f"bloque {bid}: no encontré la cara de {spk}")
        tr[s0[0]] = s0[1]
        for dr in (1, -1):
            ref, i = s0[1], s0[0] + dr
            while 0 <= i < n:
                c = pick(i, ref)
                if c: tr[i] = c; ref = c
                i += dr
        ok = ~np.isnan(tr[:, 0])
        for k in range(3): tr[:, k] = np.interp(np.arange(n), np.where(ok)[0], tr[ok, k])
        tr[:, 0] = gaussian_filter1d(tr[:, 0], 40); tr[:, 1] = gaussian_filter1d(tr[:, 1], 40); tr[:, 2] = gaussian_filter1d(tr[:, 2], 60)
        np.save(os.path.join(wk, f"face_{bid}.npy"), tr)
        print(f"[reunión] bloque {bid} ({spk}): cara detectada en {ok.mean() * 100:.0f}% de {n} cuadros", flush=True)


# =========================================================================================== encuadre (render + control final)
def encuadre(E, MZ, FACES):
    """recorte 4:5 del panel en la fuente para (segmento si, cuadro local lf) -> (x0, y0, alto del recorte). Lo usan render() y el
       control final (reunion.qa_formato: dónde queda la cara en el cuadro terminado). Devuelve (crop_for, segmentos de cada bloque)."""
    SEGS = E["segments"]
    order, BR, prev, r = {}, {}, None, 0
    for i, s in enumerate(SEGS): order.setdefault(s["block"], []).append(i)
    for bid, spk, *_ in E["blocks"]:
        r = r + 1 if spk == prev else 0; BR[bid] = r; prev = spk

    def crop_for(si, lf):
        s = SEGS[si]; b = s["block"]
        fx, fy, fs = FACES[b][min(max(lf, 0), len(FACES[b]) - 1)]
        ch = min(CROP_MAX, max(CROP_MIN, K_FACE * fs))
        if (BR[b] + order[b].index(si)) % 2 == 1: ch = max(760.0, ch / 1.15)      # cambio de encuadre en cada unión / corte interno
        L = s["fe"] - s["fs"]
        if L > 12 * FPS: ch /= 1 + 0.06 * ease((lf - (s["fs"] - MZ[b]["f0"])) / L)  # toma larga: acercamiento imperceptible
        cw = ch * W / PANEL_H
        fyr = 0.33 if fs > 200 else 0.30
        x0 = min(max(0.0, fx - cw / 2), 1920 - cw); y0 = min(max(0.0, fy - fyr * ch), 1080 - ch)
        return x0, y0, ch
    return crop_for, order


# ---------------- dónde queda cada texto YA ASENTADO (sin la animación de entrada); misma geometría que header()/name_card()/caption()
#                  de render(): si cambia el dibujo de una pieza, cambiar acá también (tests/pruebas_reunion.py lo compara con el video)
def cajas_titular(titulo):
    """rectángulos (x0, y0, x1, y1) en el cuadro 1080x1920 de la placa del titular: línea 1 (marino) y chip rojo de la línea 2"""
    l1, l2 = ((titulo or "").split("|") + [""])[:2]
    f1 = font("ExtraBold", 46)
    while f1.getlength(l1) > W - 150: f1 = font("ExtraBold", f1.size - 2)
    f2 = font("ExtraBold", 34)
    while f2.getlength(l2) > W - 190: f2 = font("ExtraBold", f2.size - 2)
    w1, h1 = f1.getlength(l1) + 64, 80
    out = [((W - w1) / 2, TITLE_Y + 8, (W + w1) / 2, TITLE_Y + 8 + h1)]
    if l2:
        w2 = f2.getlength(l2) + 46; out.append(((W - w2) / 2, TITLE_Y + h1 - 2, (W + w2) / 2, TITLE_Y + h1 + 56))
    return out


def caja_placa(nm, role):
    """rectángulo de la placa con el nombre (recuadro marino con la franja roja), apoyada en x=40 sobre el carril NAME_Y"""
    fn, fr_ = font("ExtraBold", 40), font("SemiBold", 27)
    wv = int(max(fn.getlength(nm), fr_.getlength(role))) + 70
    return (40, NAME_Y + 4, 40 + wv, NAME_Y + 120)


def mascara_subtitulo(text):
    """tinta del subtítulo (letra + contorno, sin la sombra suave) -> (máscara 0–255, x, y de la esquina en el cuadro)"""
    f = font("ExtraBold", 52); lh = int(52 * 1.22)
    wv = int(f.getlength(text)) + 40
    im = Image.new("L", (wv, lh + 30), 0)
    ImageDraw.Draw(im).text((20, 10), text, font=f, fill=255, stroke_width=5, stroke_fill=255)
    return np.asarray(im), int(round((W - wv) / 2)), int(round(CAP_Y - (lh + 30) / 2))


# =========================================================================================== render
def render(name, pd, titulo=None):
    E = jload(os.path.join(pd, "edl.json")); wk = os.path.join(pd, "blocks"); MZ = jload(os.path.join(wk, "mz.json"))
    src = jload(RS(name, "source.json")); ppl = jload(RS(name, "people.json"))["people"]
    client = jload(os.path.join(STUDIO, "clients", src["client"] + ".json"))
    S = jload(RS(name, "sentences.json")); B = jload(os.path.join(pd, "blocks.json"))["blocks"]
    SEGS, FR = E["segments"], E["frames"]; MAIN_END, TOTAL = E["main_end"], E["total"]
    FACES = {bid: np.load(os.path.join(wk, f"face_{bid}.npy")) for bid, *_ in E["blocks"]}
    RED = tuple(client.get("colors", {}).get("accent", (210, 30, 44))); NAVY = tuple(client.get("colors", {}).get("navy", (11, 19, 34)))
    titulo = titulo or src.get("titulo") or src.get("tema", "").upper()
    crop_for, order = encuadre(E, MZ, FACES)                          # recorte del panel (el control final de reunion.py usa el mismo)
    LAST = {b: order[b][-1] for b in order}

    def panel(src_, si, lf):
        x0, y0, ch = crop_for(si, lf); z = PANEL_H / ch
        return cv2.warpAffine(src_, np.array([[z, 0, -x0 * z], [0, z, -y0 * z]], np.float32), (W, PANEL_H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

    def background(pan):
        sm = cv2.GaussianBlur(cv2.resize(pan, (108, 135), interpolation=cv2.INTER_AREA), (0, 0), 6)
        big = cv2.resize(sm, (int(W * 1920 / PANEL_H * 0.76), 1920), interpolation=cv2.INTER_LINEAR)
        x = (big.shape[1] - W) // 2
        return (big[:, x:x + W].astype(np.float32) * 0.38).astype(np.uint8)

    def bgra(im): return np.asarray(im.convert("RGBA"))[..., [2, 1, 0, 3]].copy()

    def blend(fr, spr, x, y, a=1.0):
        h, w = spr.shape[:2]; x, y = int(round(x)), int(round(y))
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0 or a <= 0: return
        s_ = spr[y0 - y:y1 - y, x0 - x:x1 - x]; al = s_[..., 3:4].astype(np.float32) * (a / 255)
        roi = fr[y0:y1, x0:x1]; roi[:] = (roi * (1 - al) + s_[..., :3] * al).astype(np.uint8)

    # ---------------- piezas gráficas
    def header():                                                   # titular: placa marina + chip rojo, centrado, sobre la mesa
        l1, l2 = (titulo.split("|") + [""])[:2]
        f1 = font("ExtraBold", 46)
        while f1.getlength(l1) > W - 150: f1 = font("ExtraBold", f1.size - 2)
        f2 = font("ExtraBold", 34)
        while f2.getlength(l2) > W - 190: f2 = font("ExtraBold", f2.size - 2)
        w1, h1 = f1.getlength(l1) + 64, 80
        w2 = f2.getlength(l2) + 46
        im = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
        ds.rounded_rectangle(((W - w1) / 2 + 4, 14, (W + w1) / 2 + 4, 14 + h1), radius=14, fill=(0, 0, 0, 120))
        if l2: ds.rounded_rectangle(((W - w2) / 2 + 4, h1 + 4, (W + w2) / 2 + 4, h1 + 64), radius=10, fill=(0, 0, 0, 110))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9))); d = ImageDraw.Draw(im)
        d.rounded_rectangle(((W - w1) / 2, 8, (W + w1) / 2, 8 + h1), radius=14, fill=NAVY + (238,))
        bb = d.textbbox((0, 0), l1, font=f1)
        d.text(((W - f1.getlength(l1)) / 2, 8 + (h1 - (bb[3] - bb[1])) / 2 - bb[1] - (6 if l2 else 0)), l1, font=f1, fill=(255, 255, 255, 255))
        if l2:
            d.rounded_rectangle(((W - w2) / 2, h1 - 2, (W + w2) / 2, h1 + 56), radius=10, fill=RED + (255,))
            bb = d.textbbox((0, 0), l2, font=f2)
            d.text(((W - f2.getlength(l2)) / 2, h1 - 2 + (58 - (bb[3] - bb[1])) / 2 - bb[1]), l2, font=f2, fill=(255, 255, 255, 255))
        return bgra(im)

    def name_card(nm, role):
        fn, fr_ = font("ExtraBold", 40), font("SemiBold", 27)
        wv = int(max(fn.getlength(nm), fr_.getlength(role))) + 70
        im = Image.new("RGBA", (wv + 30, 140), (0, 0, 0, 0))
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((6, 12, wv, 128), radius=12, fill=(0, 0, 0, 110))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8))); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 4, wv, 120), radius=12, fill=NAVY + (232,)); d.rectangle((0, 4, 9, 120), fill=RED + (255,))
        d.text((32, 16), nm, font=fn, fill=(255, 255, 255, 255)); d.text((32, 70), role, font=fr_, fill=(205, 212, 226, 255))
        return bgra(im)

    def caption(text):
        f = font("ExtraBold", 52); lh = int(52 * 1.22)
        wv = int(f.getlength(text)) + 40
        im = Image.new("RGBA", (wv, lh + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.text((20, 10), text, font=f, fill=(255, 255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))
        a = im.split()[3].point(lambda v: int(v * 0.5)); sh = Image.new("RGBA", im.size, (0, 0, 0, 255)); sh.putalpha(a)
        sh = sh.transform(sh.size, Image.AFFINE, (1, 0, 0, 0, 1, -3)).filter(ImageFilter.GaussianBlur(5))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.alpha_composite(sh); out.alpha_composite(im)
        return bgra(out)

    def endcard():
        im = Image.new("RGBA", (W, H), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
        icons = {"facebook": "", "instagram": "", "x": "", "tiktok": "", "whatsapp": "", "youtube": ""}
        nets = [icons[n] for n in client.get("networks", list(icons)[:5]) if n in icons]
        fa = ImageFont.truetype(os.path.join(FONTS, "fa-brands-400.ttf"), 66)
        for i, g in enumerate(nets):
            cx = W / 2 + (i - (len(nets) - 1) / 2) * 158
            d.rounded_rectangle((cx - 66, 814, cx + 66, 946), radius=34, fill=(228, 36, 48, 255))
            bb = d.textbbox((0, 0), g, font=fa)
            d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], 880 - (bb[3] - bb[1]) / 2 - bb[1]), g, font=fa, fill=(255, 255, 255, 255))
        f = font("Black", 50); t = client.get("handle", "")
        x = (W - sum(f.getlength(c) + 5 for c in t)) / 2
        for c in t: d.text((x, 990), c, font=f, fill=(228, 36, 48, 255)); x += f.getlength(c) + 5
        return np.asarray(im.convert("RGB"))[..., ::-1].copy()

    HEADER, END = header(), endcard()
    TOPSH = np.clip(1 - np.arange(PANEL_Y) / PANEL_Y, 0, 1)[:, None, None] * 0.35

    # ---------------- subtítulos (texto de la transcripción + glosario de la FUENTE)
    gl = {"exdiputado": "ex diputado", "Exdiputado": "Ex diputado", "exdiputada": "ex diputada", "Exdiputada": "Ex diputada",
          "exsenador": "ex senador", "exsenadora": "ex senadora", "expresidente": "ex presidente", "exministro": "ex ministro"}
    gl.update(src.get("glossary", {}))
    def fix(t):
        for a, b in gl.items():
            if " " in a: t = re.sub(r"\b" + re.escape(a) + r"\b", b, t)
        core = t.rstrip(".,;:?!")
        return gl.get(core, core) + t[len(core):] if core in gl else t
    ow = []
    for bi, b in enumerate(B):
        ss = [s for s in SEGS if s["block"] == f"b{bi}"]
        for k, si in enumerate(b["sents"]):
            for j, w in enumerate(S[si]["words"]):
                if b.get("upto") is not None and si == b["sents"][-1] and j >= b["upto"]: break   # bloque que termina en una pausa adentro de la frase
                m = (w["s"] + w["e"]) / 2 * FPS
                seg = next((s for s in ss if s["fs"] <= m < s["fe"]), None)
                # la 1.ª palabra del bloque siempre va (el borde verificado la incluye aunque whisper la ubique antes: "Muy" 0.0–0.62)
                if seg is None and k == 0 and j == 0 and ss and w["e"] * FPS > ss[0]["fs"] - 3: seg = ss[0]
                if seg is None: continue
                t0 = (seg["out"] + max(w["s"] * FPS, seg["fs"]) - seg["fs"]) / FPS
                t1 = (seg["out"] + min(w["e"] * FPS, seg["fe"] - 0.01) - seg["fs"]) / FPS
                ow.append(dict(t=w["w"], s=t0, e=t1, blk=bi))
    txt_all = " ".join(x["t"] for x in ow)
    for a, b_ in gl.items():
        if " " in a and a in txt_all:                       # reemplazos de varias palabras (p. ej. "Aarón Luis Díaz" -> "Aarón Ruiz Díaz")
            aw, bw = a.split(), b_.split()
            for i in range(len(ow) - len(aw) + 1):
                if [norm_(ow[i + k]["t"]) for k in range(len(aw))] == [norm_(x) for x in aw] and len(aw) == len(bw):
                    for k in range(len(aw)): ow[i + k]["t"] = bw[k] + ow[i + k]["t"][len(ow[i + k]["t"].rstrip(".,;:?!")):]
    for x in ow:
        core = x["t"].rstrip(".,;:?!")
        if core in gl and " " not in core: x["t"] = gl[core] + x["t"][len(core):]
    FUNC = ("a", "de", "del", "la", "el", "los", "las", "y", "que", "en", "con", "por", "para", "un", "una", "se", "nos", "lo")
    caps, cur = [], []
    for i, x in enumerate(ow):
        nb = ow[i + 1]["blk"] if i + 1 < len(ow) else None
        cur.append(x); tx = " ".join(y["t"] for y in cur); endS = x["t"][-1] in ".?!"
        if endS or (x["t"][-1] in ",;:" and len(tx) >= 14) or len(tx) >= 20 or nb != x["blk"]:
            if not endS and x["t"].lower() in FUNC and nb == x["blk"] and len(tx) < 26: continue
            caps.append(cur); cur = []
    if cur: caps.append(cur)
    CAPS = [dict(s=c[0]["s"], e=c[-1]["e"], t=" ".join(y["t"] for y in c)) for c in caps]
    for i, c in enumerate(CAPS[:-1]): c["e"] = min(max(c["e"] + 0.15, c["s"] + 0.6), CAPS[i + 1]["s"])
    CAPS[-1]["e"] = min(CAPS[-1]["e"] + 0.3, MAIN_END / FPS)
    jsave(CAPS, os.path.join(pd, "captions.json"))
    capspr = {}
    LT, seen = [], set()
    for s in SEGS:
        if s["speaker"] in seen or s["speaker"] not in ppl: continue
        seen.add(s["speaker"]); t0 = s["out"] / FPS + 0.6
        LT.append((t0, t0 + 4.2, name_card(ppl[s["speaker"]]["name"], ppl[s["speaker"]].get("role", ""))))

    def compose(pan, t):
        fr = background(pan)
        fr[:PANEL_Y] = (fr[:PANEL_Y] * (1 - TOPSH)).astype(np.uint8)
        fr[PANEL_Y:PANEL_Y + PANEL_H] = pan
        k = ease((t - 0.25) / 0.5)                                    # el titular sube desde abajo al empezar
        blend(fr, HEADER, 0, TITLE_Y + (1 - k) * 40, k)
        for a, b_, spr in LT:
            if a <= t < b_:
                k = ease((t - a) / 0.35) * ease((b_ - t) / 0.3); blend(fr, spr, 40 - (1 - k) * 60, NAME_Y, k)
        for c in CAPS:
            if c["s"] <= t < c["e"]:
                if c["t"] not in capspr: capspr[c["t"]] = caption(c["t"])
                spr = capspr[c["t"]]; blend(fr, spr, (W - spr.shape[1]) / 2, CAP_Y - spr.shape[0] / 2, min(1.0, (t - c["s"]) / 0.08))
        return fr

    class Reader:
        def __init__(self, bid, start):
            self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", os.path.join(wk, f"sz_{bid}.mp4"), "-vf", f"select=gte(n\\,{start})", "-fps_mode", "passthrough",
                                       "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, bufsize=1920 * 1080 * 6)
            self.n = start; self.buf = None
        def get(self, n):
            while self.n <= n:
                b = self.p.stdout.read(1920 * 1080 * 3)
                if len(b) < 1920 * 1080 * 3: break
                self.buf = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3); self.n += 1
            return self.buf
        def close(self): self.p.kill()

    def frame_panel(n, rd):
        bid, sf, si, xf = FR[n]; si = si if si >= 0 else LAST[bid]
        lf = sf - MZ[bid]["f0"]; pan = panel(rd[bid].get(lf), si, lf)
        if xf:
            pb, psf, wg = xf; plf = psf - MZ[pb]["f0"]
            prev_ = panel(rd[pb].get(plf), LAST[pb], plf)
            pan = (prev_.astype(np.float32) * (1 - wg) + pan.astype(np.float32) * wg).astype(np.uint8)
        return pan

    # ---------------- audio
    mixp = os.path.join(pd, "mix.wav"); _audio(name, pd, E, mixp)
    import plataforma as PL
    venc = ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "16M", "-maxrate", "24M", "-bufsize", "48M", "-profile:v", "high"] \
        if PL.ENCODER == "nvenc" else ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-maxrate", "24M", "-bufsize", "48M"]
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", mixp,
                            "-map", "0:v", "-map", "1:a", *venc, "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                            "-c:a", "aac", "-b:a", "320k", "-shortest", "-movflags", "+faststart", os.path.join(pd, "video.mp4")], stdin=subprocess.PIPE)
    rd = {bid: Reader(bid, SEGS[order[bid][0]]["fs"] - MZ[bid]["f0"]) for bid in order}
    t0, last = time.time(), None
    for n in range(TOTAL):
        if n < MAIN_END: fr = compose(frame_panel(n, rd), n / FPS); last = fr
        else:
            a = ease((n - MAIN_END) / 14); fr = (last.astype(np.float32) * (1 - a) + END.astype(np.float32) * a).astype(np.uint8)
        enc.stdin.write(fr.tobytes())
        if n % 600 == 0: print(f"[reunión] render {n}/{TOTAL} ({n / max(1e-6, time.time() - t0):.1f} fps)", flush=True)
    enc.stdin.close(); enc.wait()
    for x in rd.values(): x.close()


def norm_(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower()); t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", t)


def _audio(name, pd, E, out):
    SR = 48000; N = E["total"] * SR // FPS
    w = wave.open(RS(name, "a48.wav")); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    v = np.zeros(N, np.float32)
    for s in E["segments"]:
        x = a[s["fs"] * 1600:s["fe"] * 1600].copy()
        fi = int((0.06 if s["first"] else 0.015) * SR); fo = int((0.12 if s["last"] else 0.015) * SR)
        x[:fi] *= np.linspace(0, 1, fi); x[-fo:] *= np.linspace(1, 0, fo)
        v[s["out"] * 1600:s["out"] * 1600 + len(x)] += x
    tmp = os.path.join(pd, "voice_cut.wav"); ww = wave.open(tmp, "wb"); ww.setnchannels(1); ww.setsampwidth(2); ww.setframerate(SR)
    ww.writeframes((np.clip(v, -1, 1) * 32767).astype(np.int16).tobytes()); ww.close()
    cl = os.path.join(pd, "voice_clean.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", "highpass=f=80,afftdn=nr=8:nf=-45:tn=1,equalizer=f=250:t=q:w=1:g=-1.5,"
                    "equalizer=f=3000:t=q:w=1.2:g=2,acompressor=threshold=-24dB:ratio=2.5:attack=10:release=180:makeup=3,loudnorm=I=-16.5:LRA=8:TP=-2",
                    "-ar", str(SR), "-ac", "1", cl], check=True)
    w = wave.open(cl); v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; v = np.pad(v, (0, max(0, N - len(v))))[:N]
    t = np.arange(N) / SR
    def midi(m): return 440 * 2 ** ((m - 69) / 12)
    CH = [[52, 55, 59], [48, 52, 55], [43, 47, 50], [50, 54, 57]]; L = 4 * 60 / 72 * 2
    bed = np.zeros(N, np.float32)
    for ci in range(int(N / SR / L) + 2):
        s0 = max(0, int((ci * L - 0.6) * SR)); e0 = min(N, int(((ci + 1) * L + 0.6) * SR))
        if e0 <= s0: continue
        tt = t[s0:e0]; env = np.minimum(1, np.minimum((tt - ci * L + 0.6) / 1.2, ((ci + 1) * L + 0.6 - tt) / 1.2)).clip(0, 1)
        for m in CH[ci % 4]: bed[s0:e0] += (np.sin(2 * np.pi * midi(m) * tt) + 0.25 * np.sin(4 * np.pi * midi(m) * tt)) * env * 0.1
    bed = signal.sosfilt(signal.butter(4, 1500, "low", fs=SR, output="sos"), bed); bed /= np.sqrt(np.mean(bed ** 2)) + 1e-9
    me = E["main_end"] * 1600; vr = np.sqrt(np.mean(v[:me] ** 2)); r = int(0.8 * SR)
    g = np.full(N, vr * 10 ** (-24 / 20), np.float32)
    g[me - r:me] = np.linspace(g[0], vr * 10 ** (-14 / 20), r); g[me:] = vr * 10 ** (-14 / 20)
    g[:int(0.5 * SR)] *= np.linspace(0, 1, int(0.5 * SR)); g[-int(1.2 * SR):] *= np.linspace(1, 0, int(1.2 * SR)) ** 2
    mix = v + bed * g; mix = np.stack([mix, mix], 1); mix *= min(1.0, 0.89 / (np.abs(mix).max() + 1e-9))
    ww = wave.open(out, "wb"); ww.setnchannels(2); ww.setsampwidth(2); ww.setframerate(SR)
    ww.writeframes((mix * 32767).astype(np.int16).tobytes()); ww.close()
