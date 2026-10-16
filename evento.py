# Estudio de edición — formato EVENTO / RECORRIDA: varias tomas sueltas de un acto, una visita o un cumpleaños (saludos, público,
# mesa principal, fotos) -> video vertical con música, al ritmo, con título manuscrito, la voz de Lilian (con subtítulo) cuando
# habla, barridos entre tomas y la tarjeta final de la casa. Como las referencias T08/T09/T18 (peluquería, Caacupé, misa).
#   python evento.py <carpeta|videos…> --titulo "CUMPLEAÑOS DE ARNALDO" [--sub "7 de febrero"] [--length 40] [--name x]
#                    [--grupo N] [--no-render] [--no-deliver]
#   (con una carpeta, --grupo N elige el N-ésimo evento de entender.py: tomas del mismo día y a < 4 h)
# Qué elige: momentos NÍTIDOS, con cámara quieta, con caras (y Lilian, por huella de cara) y, sobre todo, cuando ELLA habla
# (frases completas, con su audio y subtítulo). Nada de barridos de cámara, nada oscuro ni movido. Cortes en el pulso de la música.
import os, sys, json, subprocess, math, time, re, argparse, shutil, datetime
import numpy as np, cv2

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO)
from core import *                                                  # noqa  (torch, W, H, FPS, SR, SPF, blend, spr_t, warp_src…)
import plataforma as PL
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PROJECTS = os.path.join(STUDIO, "projects")
DELIVER = [os.path.join(os.path.expanduser("~"), "Downloads"), os.path.join(os.path.expanduser("~"), "Documents", "videosclaudesubir")]
BPM = 104
BEAT = 60.0 / BPM
AF = 10                                                             # cuadros por segundo del análisis
log = lambda *a: print("[evento]", *a, flush=True)


# ================================================================== 1. tomas normalizadas (9:16, 30 fps, SDR, píxeles cuadrados)
def prepare(paths, pd):
    import ingest as IG
    os.makedirs(os.path.join(pd, "clips"), exist_ok=True)
    out = []
    for k, p in enumerate(paths):
        v, a = os.path.join(pd, "clips", f"c{k}.mp4"), os.path.join(pd, "clips", f"c{k}.wav")
        info = IG.probe(p)
        if not os.path.exists(v):
            cx = IG.landscape_face_x(info) if info["width"] > info["height"] else None
            IG.make_work(info, v, cx)
        if not os.path.exists(a):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-vn", "-ac", "2", "-ar", str(SR), a])
            if not os.path.exists(a): write_wav(a, np.zeros((int(info["duration"] * SR), 2), np.float32))
        dur_v = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v], capture_output=True, text=True).stdout
        n = int(round(float((re.findall(r"[\d.]+", dur_v) or ["0"])[0]) * FPS))   # el clip ya está a 30 cps constantes (algunos DJI listan 2 pistas)
        out.append(dict(k=k, path=p, file=os.path.basename(p), video=v, audio=a, frames=n, dur=n / FPS))
        log(f"toma {k}: {os.path.basename(p)} · {n / FPS:.1f} s")
    return out


# ================================================================== 2. mirar cada toma
def analyze(c, pd):
    jp = os.path.join(pd, "clips", f"c{c['k']}.json")
    if os.path.exists(jp): return json.load(open(jp, encoding="utf-8"))
    w, h = 270, 480
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", c["video"], "-vf", f"fps={AF},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    det = cv2.FaceDetectorYN.create(os.path.join(STUDIO, "models", "yunet.onnx"), "", (540, 960), 0.6, 0.3, 50)
    rec = cv2.FaceRecognizerSF.create(os.path.join(STUDIO, "models", "sface.onnx"), "")
    fp = np.load(os.path.join(STUDIO, "clients", "lilian_faceprint.npy")).astype(np.float32).ravel(); fp /= np.linalg.norm(fp)
    sharp, mot, bri, nf, fsz, lil, fcx, fcy = [], [], [], [], [], [], [], []
    prev, i = None, 0
    big = subprocess.Popen(["ffmpeg", "-v", "error", "-i", c["video"], "-vf", f"fps={AF / 2},scale=540:960", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    while True:
        b = pr.stdout.read(w * h * 3)
        if len(b) < w * h * 3: break
        fr = np.frombuffer(b, np.uint8).reshape(h, w, 3); g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        sharp.append(float(np.log(cv2.Laplacian(g, cv2.CV_32F).var() + 1.0))); bri.append(float(g.mean()))
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(np.float32(prev), np.float32(g)); mot.append(float(np.hypot(dx, dy)))
        else: mot.append(0.0)
        prev = g
        if i % 2 == 0:                                                  # caras a la mitad de cadencia y en 540×960
            bb = big.stdout.read(540 * 960 * 3)
            if len(bb) == 540 * 960 * 3:
                F = np.frombuffer(bb, np.uint8).reshape(960, 540, 3)
                _, f = det.detect(F)
                f = [] if f is None else [r for r in f if r[2] > 22]
                best_l, cx, cy, mx = 0.0, None, None, 0.0
                for r in sorted(f, key=lambda r: -r[2] * r[3])[:4]:
                    try:
                        e = rec.feature(rec.alignCrop(F, r)).ravel(); e /= np.linalg.norm(e) + 1e-9; s = float(e @ fp)
                    except cv2.error: s = 0.0
                    if s > best_l: best_l = s
                    if r[3] / 960 > mx: mx = r[3] / 960; cx, cy = (r[0] + r[2] / 2) * 2, (r[1] + r[3] / 2) * 2
                last = (len(f), mx, best_l, cx, cy)
            else: last = (0, 0.0, 0.0, None, None)
        nf.append(last[0]); fsz.append(last[1]); lil.append(last[2]); fcx.append(last[3]); fcy.append(last[4])
        i += 1
    big.kill()
    # voz: dónde habla ella (huella de voz, umbral flexible: en actos su voz suena distinta) y qué dice (whisper, palabra por palabra)
    import speakers as SPK
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    a16 = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", c["audio"], "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                                       capture_output=True).stdout, np.int16).astype(np.float32) / 32768
    vad = [(v["start"] / 16000, v["end"] / 16000) for v in get_speech_timestamps(a16, VadOptions(threshold=0.5, min_silence_duration_ms=250, speech_pad_ms=60))] if len(a16) > 16000 else []
    vp = np.load(os.path.join(STUDIO, "clients", "lilian_voiceprint.npy")); thr = json.load(open(os.path.join(STUDIO, "clients", "lilian_voiceprint.json")))["threshold"]
    her = []
    for s, e in vad:
        if e - s < 0.8: continue
        sims = [float(SPK.embed(a16, x, y) @ vp) for x, y in SPK.chunks(s, e, 3.0)]
        if np.median(sims) >= thr - 0.07: her.append((s, e))
    words = []
    ya = transcripcion_ingresada(c["path"])                         # el mismo video ya pasó por ingest: su transcripción es mejor
    if her and ya is not None:                                      # (con guía, alineada palabra por palabra, bien puntuada)
        words = [w for w in ya if any(s - 0.2 <= (w["s"] + w["e"]) / 2 <= e + 0.2 for s, e in her)]
        her = her if words else her
    elif her:
        import plataforma as PL2
        m = PL2.whisper_model("large-v3")
        segs, _ = m.transcribe(a16, language="es", beam_size=5, word_timestamps=True, vad_filter=True, condition_on_previous_text=False,
                               initial_prompt=("Palabras de la senadora Lilian Samaniego en un acto. Frases completas, con puntos y comas. "
                                               + os.environ.get("EVENTO_TEMA", "")).strip())   # sin guía no puntúa; el tema ayuda con los nombres
        for sg in segs:
            for wd in (sg.words or []):
                mid = (wd.start + wd.end) / 2
                if any(s - 0.2 <= mid <= e + 0.2 for s, e in her) and wd.word.strip(): words.append(dict(t=wd.word.strip(), s=round(wd.start, 2), e=round(wd.end, 2)))
    r = dict(sharp=sharp, mot=mot, bri=bri, nf=nf, fsz=fsz, lil=lil, fcx=fcx, fcy=fcy, her=her, words=words)
    json.dump(r, open(jp + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, default=float); os.replace(jp + ".tmp", jp)
    return r


def transcripcion_ingresada(path):
    """palabras (alineadas) de una fuente ya ingresada a partir de ESTE mismo archivo (sources/*/source.json "original"), o None"""
    ap = os.path.normcase(os.path.abspath(path))
    sd = os.path.join(STUDIO, "sources")
    for d in os.listdir(sd):
        sj = os.path.join(sd, d, "source.json")
        if not os.path.exists(sj): continue
        try: src = json.load(open(sj, encoding="utf-8"))
        except Exception: continue
        if os.path.normcase(os.path.abspath(src.get("original", "") or "")) != ap: continue
        for f in ("transcript_aligned.json", "transcript.json"):
            tp = os.path.join(sd, d, f)
            if os.path.exists(tp):
                segs = json.load(open(tp, encoding="utf-8"))
                out = [dict(t=w["w"].strip(), s=round(w["s"], 2), e=round(w["e"], 2)) for g in segs for w in g.get("words", []) if w["w"].strip()]
                if out: log(f"transcripción reutilizada de sources/{d}/{f}"); return out
    return None


# ================================================================== 3. qué momentos entran
def sentences(words, max_len=9.0, min_gap=0.28):
    """frases por puntuación; si whisper no puntuó (acto con ruido: 14–19 s sin un punto), se parten en sus PAUSAS reales hasta
    trozos ≤ max_len. Cada frase sabe si arranca y termina en pausa (pre/post) para saber si se entiende sola."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if w["t"][-1:] in ".?!": out.append(cur); cur = []
    if cur: out.append(cur)
    def split(x):
        if x[-1]["e"] - x[0]["s"] <= max_len or len(x) < 4: return [x]
        gaps = [(x[i]["s"] - x[i - 1]["e"], i) for i in range(2, len(x) - 1)
                if x[i]["s"] - x[0]["s"] >= 1.5 and x[-1]["e"] - x[i - 1]["e"] >= 1.5]
        g, i = max(gaps, default=(0, None))
        if i is None or g < min_gap: return [x]
        return split(x[:i]) + split(x[i:])
    pieces = [q for x in out for q in split(x)]
    merged = []                                                           # un trozo que termina en coma (o sin cierre) no está completo:
    for q in pieces:                                                      # se une con el siguiente ("Yo tengo, tenía un," + "hice un compromiso…")
        if merged and merged[-1][-1]["t"][-1:] not in ".?!" and q[0]["s"] - merged[-1][-1]["e"] < 2.5 and q[-1]["e"] - merged[-1][0]["s"] <= 16.0:
            merged[-1] = merged[-1] + q
        else: merged.append(q)
    pieces = merged
    res = []
    for k, x in enumerate(pieces):
        pre = x[0]["s"] - pieces[k - 1][-1]["e"] if k else x[0]["s"]
        post = pieces[k + 1][0]["s"] - x[-1]["e"] if k + 1 < len(pieces) else 9.0
        nxt_low = k + 1 < len(pieces) and pieces[k + 1][0]["t"][:1].islower()       # lo que sigue empieza en minúscula: es la misma frase
        res.append(dict(s=x[0]["s"], e=x[-1]["e"], text=" ".join(w["t"] for w in x), words=x, pre=pre, post=post, nxt_low=nxt_low))
    return res


# "esta parte no se va a grabar. Vamos a apagar todo." -> desde ahí, nada de esa toma (ni su voz ni su imagen)
OFFREC = re.compile(r"no se (va a |vaya a )?grab|no (lo |la |me )?graben|apag(ar|uen|á|a)\b.{0,12}(todo|c[aá]mara|eso)|esto no (se )?(sale|publica|sube)"
                    r"|fuera de (c[aá]mara|micr[oó]fono)|\bcorten\b|off the record", re.I)
COLGADAS = {"y", "e", "o", "u", "de", "del", "a", "al", "la", "el", "los", "las", "que", "en", "con", "para", "por", "un", "una", "su", "sus",
            "mi", "como", "pero", "sin", "porque", "cuando", "donde", "nuestro", "nuestra", "este", "esta", "ese", "esa"}
SUELTA = re.compile(r"^(pero|porque|entonces|y eso|eso|así que|o sea|que)\b", re.I)   # arranca colgada de algo anterior


def off_record(A):
    """segundo desde el que la toma NO se usa (ella pidió no grabar), o None"""
    for st in sentences(A["words"]):
        if OFFREC.search(st["text"]): return max(0.0, st["s"] - 0.3)
    return None


def candidates(c, A):
    sh = np.array(A["sharp"]); mot = np.array(A["mot"]); bri = np.array(A["bri"]); n = len(sh)
    if n < AF: return []
    cut = off_record(A)
    if cut is not None:
        log(f"toma {c['k']}: pide no grabar desde {cut:.1f} s -> se usa solo lo anterior")
        n = min(n, int(cut * AF))
    shz = (sh - np.median(sh)) / (np.std(sh) + 1e-6)
    jit = np.abs(mot - np.convolve(mot, np.ones(5) / 5, "same"))                # temblor = movimiento que no es paneo suave
    nf = np.array(A["nf"]); lil = np.array(A["lil"]); fsz = np.array(A["fsz"])
    out = []
    # (a) cuando ella habla: frases completas de 1.2–9 s, con su audio y subtítulo (lo más valioso del evento)
    for st in sentences(A["words"]):
        d = st["e"] - st["s"]
        if not 1.2 <= d <= 16.0: continue
        if cut is not None and st["e"] > cut: continue
        txt = st["text"].strip()
        if st["s"] < 0.3 or st["e"] > c["dur"] - 0.5: continue                              # la cámara la cortó al empezar o al terminar
        if SUELTA.match(txt) or len(txt.split()) < 4: continue                              # tiene que entenderse sola
        if txt[:1].islower() and st["pre"] < 0.28: continue                                 # sigue una frase anterior sin pausa
        if txt[-1:] not in ".?!" and (st["post"] < 0.28 or st["nxt_low"]): continue       # sin punto: cierra en pausa real y lo que sigue no la continúa
        ult = re.sub(r"[^\wáéíóúñü]", "", st["words"][-1]["t"].lower())
        if ult in COLGADAS: continue                                                        # "…lo que me había pedido y": frase colgada
        st = dict(st, text=txt[:1].upper() + txt[1:], words=[dict(st["words"][0], t=st["words"][0]["t"][:1].upper() + st["words"][0]["t"][1:])] + st["words"][1:])
        a, b = max(0.0, st["s"] - 0.15), min(c["dur"] - 0.05, st["e"] + 0.30)
        i0, i1 = int(a * AF), max(int(a * AF) + 1, int(b * AF))
        out.append(dict(k=c["k"], a=a, b=b, kind="habla", text=st["text"], words=st["words"],
                        score=4.0 + float(np.mean(shz[i0:i1])) + 1.5 * float(np.mean(lil[i0:i1] >= 0.38)) - 0.08 * float(np.mean(mot[i0:i1]))))
    # (b) tomas de ambiente: ventanas de 4–8 pulsos (2.3–4.6 s): las referencias de recorridas cortan 10–16 veces por minuto
    for nb in (8, 6, 5, 4):
        L = nb * BEAT
        for a in np.arange(0.2, min(c["dur"], n / AF) - L - 0.1, 0.4):
            i0, i1 = int(a * AF), int((a + L) * AF)
            if i1 > n: break
            m_ = mot[i0 + 1:i1]
            if len(m_) == 0: continue
            if m_.max() > 22 or bri[i0:i1].mean() < 45: continue        # barrido de cámara o muy oscuro: nunca
            sc = (1.0 * float(np.mean(shz[i0:i1])) - 0.22 * float(np.mean(jit[i0:i1])) - 0.05 * float(np.mean(m_))
                  + 1.0 * float(np.mean(nf[i0:i1] >= 1)) + 0.6 * float(np.mean(nf[i0:i1] >= 2)) + 1.6 * float(np.mean(lil[i0:i1] >= 0.38))
                  + 2.0 * min(0.25, float(np.median(fsz[i0:i1]))) + 0.10 * nb)          # a igual calidad, tomas más largas
            out.append(dict(k=c["k"], a=float(a), b=float(a + L), kind="ambiente", score=sc, beats=nb))
    return out


def select(clips, cands, length):
    chosen = []
    used = {c["k"]: [] for c in clips}
    def free(x): return all(x["b"] + 0.5 <= a or x["a"] >= b + 0.5 for a, b in used[x["k"]])
    total = lambda: sum(x["b"] - x["a"] for x in chosen)
    share = {c["k"]: c["dur"] / max(1e-6, sum(cc["dur"] for cc in clips)) for c in clips}
    cap = {k: max(1, int(math.ceil(share[k] * length / (4 * BEAT))) + 1) for k in share}
    # 1) lo que dice ella primero (si entra), 2) la mejor toma de cada video, 3) el resto por puntaje
    for x in sorted([x for x in cands if x["kind"] == "habla"], key=lambda x: -x["score"]):
        if total() + (x["b"] - x["a"]) <= length * 0.6 and free(x): chosen.append(x); used[x["k"]].append((x["a"], x["b"]))
    for c in clips:
        if any(x["k"] == c["k"] for x in chosen): continue
        best = max([x for x in cands if x["k"] == c["k"] and x["kind"] == "ambiente" and free(x)], key=lambda x: x["score"], default=None)
        if best and best["score"] > -1.5 and total() + best["b"] - best["a"] <= length: chosen.append(best); used[best["k"]].append((best["a"], best["b"]))
    for x in sorted([x for x in cands if x["kind"] == "ambiente"], key=lambda x: -x["score"]):
        if total() >= length - 1.2: break
        if x["score"] < -1.0 or not free(x) or sum(1 for y in chosen if y["k"] == x["k"]) >= cap[x["k"]]: continue
        if total() + (x["b"] - x["a"]) > length + 0.6: continue
        chosen.append(x); used[x["k"]].append((x["a"], x["b"]))
    order = {c["k"]: i for i, c in enumerate(clips)}
    chosen.sort(key=lambda x: (order[x["k"]], x["a"]))                   # orden real: toma por toma, en su tiempo
    return chosen


# ================================================================== 4. gráficos
def title_sprite(titulo, sub, accent=None):
    """título INSTITUCIONAL (manual de marca: Montserrat Black/ExtraBold, rojo y blanco): bloque rojo con el título en blanco y
    la fecha en una placa blanca con letras rojas. NUNCA letra manuscrita ni contorno tipo caricatura (pedido del usuario)."""
    if accent is None:
        try: accent = tuple(json.load(open(os.path.join(STUDIO, "clients", "lilian.json"), encoding="utf-8"))["colors"]["accent"])
        except Exception: accent = (200, 16, 46)
    F = lambda w, px: ImageFont.truetype(os.path.join(STUDIO, "assets", "fonts", f"Montserrat-{w}.ttf"), px)
    lines = [l.strip() for l in titulo.upper().split("|") if l.strip()]
    if len(lines) == 1 and len(lines[0]) > 18 and " " in lines[0]:   # largo: dos líneas parejas
        ws = lines[0].split(); j = min(range(1, len(ws)), key=lambda j: abs(len(" ".join(ws[:j])) - len(" ".join(ws[j:]))))
        lines = [" ".join(ws[:j]), " ".join(ws[j:])]
    px = 76; f = F("Black", px)
    while max(f.getlength(l) for l in lines) > 820 and px > 44: px -= 2; f = F("Black", px)
    lh = int(px * 1.12); padx, pady = 40, 26
    bw = int(max(f.getlength(l) for l in lines)) + 2 * padx; bh = lh * len(lines) + 2 * pady - int(px * 0.12)
    fs = F("ExtraBold", 36); st = sub.upper() if sub else ""
    sw = int(fs.getlength(st)) + 44 if st else 0
    Wc = max(bw, sw) + 40; Hc = bh + (70 if st else 0) + 40
    im = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x0 = (Wc - bw) // 2; y0 = 16
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=18, fill=tuple(accent) + (255,))
    for i, l in enumerate(lines):
        d.text((Wc / 2, y0 + pady + i * lh), l, font=f, fill=(255, 255, 255, 255), anchor="ma")
    if st:
        sx = (Wc - sw) // 2; sy = y0 + bh + 14
        d.rounded_rectangle((sx, sy, sx + sw, sy + 52), radius=12, fill=(255, 255, 255, 255))
        d.text((Wc / 2, sy + 26), st, font=fs, fill=tuple(accent) + (255,), anchor="mm")
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(im.split()[3].point(lambda v: int(v * 0.35)))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)), (0, 8)); out.alpha_composite(im)
    full = Image.new("RGBA", (W, Hc), (0, 0, 0, 0)); full.alpha_composite(out, ((W - Wc) // 2, 0))
    return np.asarray(full).copy()


def cap_chunks(words, max_chars=20):
    out, cur = [], []
    for w in words:
        if cur and len(" ".join(x["t"] for x in cur + [w])) > max_chars: out.append(cur); cur = []
        cur.append(w)
        if w["t"][-1:] in ".?!,": out.append(cur); cur = []
    if cur: out.append(cur)
    return [dict(s=x[0]["s"], e=x[-1]["e"], text=" ".join(w["t"] for w in x)) for x in out]


# ================================================================== 5. armar y renderizar
def build(clips, chosen, pd, titulo, sub, name):
    from styles.common import Endcard, sub_sprite, exit_to_white
    # línea de tiempo
    tl, t = [], 0.0
    for x in chosen:
        d = x["b"] - x["a"]; tl.append(dict(x, o0=t, o1=t + d)); t += d
    main = t; END = 3.0; total = main + END; NF = int(round(total * FPS))
    whips = [int(round(s["o0"] * FPS)) for i, s in enumerate(tl) if i and s["k"] != tl[i - 1]["k"]]       # barrido al cambiar de toma
    # audio: voz de ella a pleno + ambiente bajo (−14 dB) + música al pulso (baja cuando ella habla)
    N = NF * SPF
    voice = np.zeros((N, 2), np.float32); amb = np.zeros((N, 2), np.float32); mask = []
    for s in tl:
        a = read_wav(clips[s["k"]]["audio"])
        if a.shape[1] == 1: a = np.repeat(a, 2, 1)
        i0, i1 = int(s["a"] * SR), int(s["b"] * SR); seg = a[i0:i1]
        o = int(s["o0"] * SR); seg = seg[:max(0, min(len(seg), N - o))]
        fl = min(int(0.03 * SR), len(seg) // 2)
        if fl > 0: seg = seg.copy(); seg[:fl] *= np.linspace(0, 1, fl)[:, None]; seg[-fl:] *= np.linspace(1, 0, fl)[:, None]
        if s["kind"] == "habla": voice[o:o + len(seg)] += seg; mask.append(np.arange(o, o + len(seg)))
        else: amb[o:o + len(seg)] += seg * 10 ** (-14 / 20)
    mix_p = os.path.join(pd, "mix.wav")
    info = mix_audio(voice * 0.5, NF, whips, [(main - 0.12, "whoosh", 0.12), (main + 0.28, "chime", 0.13)], mix_p, music_db=-20.0, bpm=BPM,
                     speech_mask=np.concatenate(mask) if mask else None, seed=53)          # todo a media escala: el pico no recorta
    m = read_wav(mix_p); m[:len(amb)] += amb[:len(m)] * 0.5                               # (el volumen final lo fija loudnorm a −14 LUFS)
    pk = float(np.abs(m).max()); m = m * (0.89 / pk if pk > 0.89 else 1.0); write_wav(mix_p, m)
    info["pico_mezcla"] = round(20 * np.log10(max(pk, 1e-9)), 1)
    log("audio", info)
    # gráficos
    T_spr = spr_t(title_sprite(titulo, sub)) if titulo else None
    caps = []
    for s in tl:
        if s["kind"] != "habla": continue
        for ch in cap_chunks(s["words"]):
            caps.append(dict(s=s["o0"] + ch["s"] - s["a"], e=s["o0"] + ch["e"] - s["a"] + 0.15, spr=spr_t(sub_sprite(ch["text"].split(), px=54))))
    end = Endcard()
    # el título no tapa caras: arriba (centro y=330) salvo que en los primeros 3 s haya caras en esa franja -> abajo (y=1180)
    ty = 330
    if T_spr is not None:
        th_ = T_spr.shape[1]; top, bot = 330 - th_ / 2, 330 + th_ / 2
        Af = json.load(open(os.path.join(pd, "clips", f"c{tl[0]['k']}.json"), encoding="utf-8"))
        hits = 0; tot = 0
        for j in range(int(tl[0]["a"] * AF), int(min(tl[0]["b"], tl[0]["a"] + 3.0) * AF)):
            if j >= len(Af["fcy"]): break
            tot += 1
            if Af["fcy"][j] is not None and Af["fsz"][j] > 0:
                fy, fh = Af["fcy"][j], Af["fsz"][j] * H
                if fy - fh * 0.8 < bot and fy + fh * 0.6 > top: hits += 1
        if tot and hits / tot > 0.2: ty = 1180
        log(f"título en y={ty}" + (" (arriba había caras)" if ty != 330 else ""))
    out = os.path.join(pd, f"{name}.mp4")
    enc = start_encoder(out, mix_p, total)
    rd, cur = None, None
    A = {c["k"]: json.load(open(os.path.join(pd, "clips", f"c{c['k']}.json"), encoding="utf-8")) for c in clips}
    t0 = time.time()
    for n in range(NF):
        t = n / FPS
        if t >= main:
            fr = end.frame(t - main)
        else:
            si = next(i for i, s in enumerate(tl) if s["o0"] - 1e-6 <= t < s["o1"] + 1e-6 or i == len(tl) - 1)
            s = tl[si]
            if cur != si:
                if rd: rd.close()
                rd = Reader(clips[s["k"]]["video"], int(round(s["a"] * FPS))); cur = si
            src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
            # encuadre: empuje lento hacia la cara principal (o el centro), alternando entra/sale por toma
            u = (t - s["o0"]) / max(1e-3, s["o1"] - s["o0"])
            z = 1.04 + 0.05 * (u if si % 2 == 0 else 1 - u)
            ai = min(len(A[s["k"]]["fcx"]) - 1, int((s["a"] + t - s["o0"]) * AF))
            fx = next((A[s["k"]]["fcx"][j] for j in range(ai, max(-1, ai - 20), -1) if A[s["k"]]["fcx"][j] is not None), W / 2)
            fy = next((A[s["k"]]["fcy"][j] for j in range(ai, max(-1, ai - 20), -1) if A[s["k"]]["fcy"][j] is not None), H * 0.42)
            cx = W / 2 + 0.35 * (fx - W / 2); cy = H * 0.45 + 0.25 * (fy - H * 0.45)
            cw, ch = W / z, H / z
            x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
            th = torch.tensor([[cw / W, 0, 2 * (x0 + cw / 2) / W - 1], [0, ch / H, 2 * (y0 + ch / 2) / H - 1]], dtype=torch.float32, device=dev).view(1, 2, 3)
            fr = warp_src(src, th, ext_bg=None, fade_top=False)
            fr = grade_color(fr, contrast=1.04, sat=1.06)
            if T_spr is not None and t < 3.4:                              # entra con un barrido de izquierda a derecha y sale con fundido
                if t < 2.9:
                    u = ease((t - 0.2) / 0.5)
                    if u > 0.01:
                        s2 = T_spr.clone(); cut = int(s2.shape[2] * u); s2[:, :, cut:] = 0
                        blend(fr, s2, 0, ty - s2.shape[1] / 2, 1.0)
                else:
                    blend(fr, T_spr, 0, ty - T_spr.shape[1] / 2, 1 - ease((t - 2.9) / 0.5))
            for c_ in caps:
                if c_["s"] <= t < c_["e"]:
                    blend(fr, c_["spr"], W / 2 - c_["spr"].shape[2] / 2, 1231 - c_["spr"].shape[1] / 2)
            k, off = whip_k(n, whips)
            fr = whip_filter(fr, k, off)
            fr = exit_to_white(fr, int(round(main * FPS)) - n)
        enc.stdin.write(to_np(fr).tobytes())
        if n % 300 == 0: log(f"render {n}/{NF} ({n / max(1e-3, time.time() - t0):.0f} fps)")
    if rd: rd.close()
    enc.stdin.close(); enc.wait()
    make_lite(out, os.path.join(pd, f"{name}_liviano.mp4"))
    json.dump(dict(timeline=[{k: v for k, v in s.items() if k not in ("words",)} for s in tl], total=total, audio=info),
              open(os.path.join(pd, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return out


def qa(out, total):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out, "-vf", "blackdetect=d=0.15:pix_th=0.06", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    blacks = re.findall(r"black_start:([\d.]+)", r); I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip() or 0)
    F = []
    if blacks: F.append(f"negro en {blacks[:3]}")
    if I and not -16.5 <= float(I[-1]) <= -11.5: F.append(f"volumen {I[-1]} LUFS")
    if abs(dur - total) > 0.3: F.append(f"duración {dur:.1f} vs {total:.1f}")
    return dict(ok=not F, findings=F, lufs=float(I[-1]) if I else None, dur=dur)


# ================================================================== principal
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+"); ap.add_argument("--titulo", default=""); ap.add_argument("--sub", default="")
    ap.add_argument("--length", type=float, default=0); ap.add_argument("--name"); ap.add_argument("--grupo", type=int)
    ap.add_argument("--no-render", action="store_true"); ap.add_argument("--no-deliver", action="store_true")
    ap.add_argument("--tema", default="", help="nombres propios y temas (mejoran la transcripción de lo que ella dice)")
    a = ap.parse_args()
    if a.tema: os.environ["EVENTO_TEMA"] = a.tema
    paths = []
    for x in a.inputs:
        if os.path.isdir(x):
            import entender as EN
            rs = [EN.entender(os.path.join(x, f)) for f in sorted(os.listdir(x)) if f.lower().endswith((".mp4", ".mov", ".m4v"))]
            gs = EN.grupos(rs)
            for i, g in enumerate(gs): log(f"grupo {i}: {g[0]['fecha'][:16]} · " + ", ".join(r["file"] for r in g))
            g = gs[a.grupo if a.grupo is not None else 0]
            paths += [r["path"] for r in g]
        else: paths.append(x)
    seen, uniq = set(), []                                                  # sin copias repetidas del mismo archivo
    for p in paths:
        key = (os.path.getsize(p), open(p, "rb").read(1 << 20))
        if key not in seen: seen.add(key); uniq.append(p)
    name = a.name or re.sub(r"[^a-z0-9]+", "_", (a.titulo or "evento").lower()).strip("_")[:30]
    pd = os.path.join(PROJECTS, name); os.makedirs(pd, exist_ok=True)
    t0 = time.time()
    clips = prepare(uniq, pd)
    A = {c["k"]: analyze(c, pd) for c in clips}
    cands = [x for c in clips for x in candidates(c, A[c["k"]])]
    good = sum(c["dur"] for c in clips)
    length = a.length or float(np.clip(0.45 * good, 12.0, 45.0))
    chosen = select(clips, cands, length)
    log(f"elegidas {len(chosen)} tomas · {sum(x['b'] - x['a'] for x in chosen):.1f} s (pedido {length:.0f} s) de {good:.0f} s de material")
    for x in chosen:
        log(f"  {clips[x['k']]['file'][:28]:28s} {x['a']:6.1f}-{x['b']:6.1f}  {x['kind']:8s} {x['score']:5.2f}  {x.get('text', '')[:70]}")
    json.dump(dict(chosen=[{k: v for k, v in x.items() if k != 'words'} for x in chosen], clips=clips), open(os.path.join(pd, "plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    if a.no_render: return
    out = build(clips, chosen, pd, a.titulo, a.sub, name)
    q = qa(out, sum(x["b"] - x["a"] for x in chosen) + 3.0)
    log(f"QA: {'OK' if q['ok'] else 'HALLAZGOS ' + str(q['findings'])} · {q['dur']:.1f} s · {q['lufs']} LUFS · {time.time() - t0:.0f} s")
    if q["ok"] and not a.no_deliver:
        for d in DELIVER:
            if os.path.isdir(d):
                shutil.copy(out, os.path.join(d, os.path.basename(out)))
                shutil.copy(os.path.join(pd, f"{name}_liviano.mp4"), os.path.join(d, f"{name}_liviano.mp4"))
                log("entregado en", d)


if __name__ == "__main__":
    main()
