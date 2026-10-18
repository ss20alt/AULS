# Estudio de edición — formato EVENTO / RECORRIDA: varias tomas sueltas de un acto, una visita o un cumpleaños (saludos, público,
# mesa principal, fotos) -> video vertical con música, al ritmo, con título INSTITUCIONAL (Montserrat, bloque rojo de la marca
# y fecha en placa blanca), la voz de Lilian (con subtítulo) cuando habla, barridos entre tomas y la tarjeta final de la casa.
# Como las referencias T08/T09/T18 (peluquería, Caacupé, misa).
#   python evento.py <carpeta|videos…> --titulo "CUMPLEAÑOS DE ARNALDO" [--sub "7 de febrero"] [--length 40] [--name x]
#                    [--grupo N] [--no-render] [--no-deliver]
#   python evento.py <proyecto> --qa [--titulo …]   -> solo los controles del montaje sobre un plan ya guardado (sin render)
#   (con una carpeta, --grupo N elige el N-ésimo evento de entender.py: tomas del mismo día y a < 4 h)
# Qué elige: momentos NÍTIDOS, con cámara quieta, con caras (y Lilian, por huella de cara) y, sobre todo, cuando ELLA habla
# (frases completas, con su audio y subtítulo). Nada de barridos de cámara, nada oscuro ni movido. Cortes en el pulso de la música.
# Las tomas de ambiente NUNCA llevan su voz y cortan en pausas (la voz de otros, si no hay pausa, entra y sale con fundido).
# Sus frases entran y salen ENTRE sus palabras (nunca dentro de una, ni de la frase vecina), en un silencio si lo hay.
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
VAD_OPT = dict(threshold=0.5, min_silence_duration_ms=250, speech_pad_ms=60)   # silero: el mismo en el análisis y en los análisis viejos
FUNDIDO_VOZ = 0.35                                                  # s: la voz de otros que no se pudo esquivar entra y sale así
TITULO_T = (0.2, 3.4)                                               # el título entra con barrido a los 0.2 s y se va con fundido hasta 3.4 s
SUB_Y = 1231                                                        # centro de los subtítulos (y)
log = lambda *a: print("[evento]", *a, flush=True)


# ================================================================== 1. tomas normalizadas (9:16, 30 fps, SDR, píxeles cuadrados)
ESTABILIZAR = os.environ.get("STUDIO_ESTABILIZAR", "1") != "0"


def estabilizar(v):
    """estabiliza una toma filmada en mano (pedido del usuario 2026-10-18: "los videos tiemblan mucho; solo los movimientos
    necesarios"): ffmpeg vidstab en dos pasadas. Se queda con los paneos lentos de quien filma y saca el pulso (suavizado de ~1 s,
    con el acercamiento justo para no mostrar bordes negros). Si algo falla, la toma queda como estaba"""
    import plataforma as PL
    d, b = os.path.dirname(v), os.path.basename(v)
    trf, tmp = b + ".trf", os.path.join(d, "estab_" + b)
    try:
        r1 = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", b, "-vf", f"vidstabdetect=shakiness=6:accuracy=12:result={trf}", "-f", "null", "-"],
                            cwd=d, capture_output=True, text=True)
        if r1.returncode or not os.path.exists(os.path.join(d, trf)): return False
        r2 = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", b, "-vf",
                             f"vidstabtransform=input={trf}:smoothing=30:optzoom=1:zoomspeed=0.2:interpol=bicubic,unsharp=5:5:0.5",
                             *PL.venc(16, "40M", "80M", 30, 0), "-pix_fmt", "yuv420p", "-an", os.path.basename(tmp)], cwd=d, capture_output=True, text=True)
        if r2.returncode or not os.path.exists(tmp): return False
        os.replace(tmp, v); log(f"toma estabilizada: {b}")
        return True
    except OSError: return False
    finally:
        for f in (os.path.join(d, trf), tmp):
            if os.path.exists(f): os.remove(f)


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
        if ESTABILIZAR and not os.path.exists(v + ".estab"):              # tomas en mano: se estabilizan una vez (y el análisis se rehace)
            if estabilizar(v):
                open(v + ".estab", "w").write("vidstab")
                jp = os.path.join(pd, "clips", f"c{k}.json")
                if os.path.exists(jp): os.remove(jp)
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
    vad = [(v["start"] / 16000, v["end"] / 16000) for v in get_speech_timestamps(a16, VadOptions(**VAD_OPT))] if len(a16) > 16000 else []
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
    r = dict(sharp=sharp, mot=mot, bri=bri, nf=nf, fsz=fsz, lil=lil, fcx=fcx, fcy=fcy, her=her, words=words,
             vad=[(round(s, 2), round(e, 2)) for s, e in vad])     # TODA la voz (de quien sea): las tomas de ambiente cortan fuera de ella
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


# ------------------------------------------------------------------ voz en cada toma (para que el ambiente no corte a nadie)
_VAD = {}


def vad_de(audio):
    """tramos con voz (de quien sea) del audio de una toma, en s. Para análisis anteriores que no guardaron el VAD: silero (el
    mismo del análisis, en el procesador: < 0.5 s por toma); sin silero, energía contra el piso de ruido de la sala"""
    if audio in _VAD: return _VAD[audio]
    a16 = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                                       capture_output=True).stdout, np.int16).astype(np.float32) / 32768
    try:
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        out = [(v["start"] / 16000, v["end"] / 16000) for v in get_speech_timestamps(a16, VadOptions(**VAD_OPT))] if len(a16) > 16000 else []
    except ImportError:                                               # respaldo: 20 ms con > 10 dB sobre el piso (p20), pausas < 0.25 s unidas
        hop = 320; nfr = len(a16) // hop
        db = 10 * np.log10(np.mean(a16[:nfr * hop].reshape(nfr, hop) ** 2, 1) + 1e-10) if nfr else np.zeros(0)
        on = db > np.percentile(db, 20) + 10 if nfr else np.zeros(0, bool)
        out = unir([(i * 0.02 - 0.06, (i + 1) * 0.02 + 0.06) for i in np.flatnonzero(on)], gap=0.25)
        out = [(max(0.0, s), e) for s, e in out if e - s >= 0.25]
    _VAD[audio] = out
    return out


def unir(iv, gap=0.0):
    """une tramos que se pisan (o separados por menos de gap s)"""
    out = []
    for s, e in sorted((float(s), float(e)) for s, e in iv if e > s):
        if out and s <= out[-1][1] + gap: out[-1][1] = max(out[-1][1], e)
        else: out.append([s, e])
    return [tuple(x) for x in out]


def voces(c, A):
    """(su voz, toda voz) de una toma, en s. Su voz = tramos con su huella de voz + cada palabra suya transcrita; toda voz = VAD
    (guardado en el análisis; si el análisis es anterior, se calcula ahora del audio de la toma) + lo de ella"""
    ella = unir([tuple(x) for x in A.get("her", [])] + [(w["s"], w["e"]) for w in A.get("words", [])])
    toda = A.get("vad")
    if toda is None: toda = vad_de(c["audio"]) if os.path.exists(c.get("audio", "") or "") else []
    return ella, unir([tuple(x) for x in toda] + ella)


def dentro(t, iv, m=0.05):
    """¿el instante t cae DENTRO de una voz (no en su borde)? -> cortar ahí corta una palabra"""
    return any(s + m < t < e - m for s, e in iv)


def pisa(a, b, iv):
    """segundos de voz entre a y b"""
    return sum(max(0.0, min(b, e) - max(a, s)) for s, e in iv)


def corte_libre(lo, hi, pref, voz, paso=0.01):
    """instante entre lo y hi, lo más cerca de pref, que NO cae dentro de una voz (VAD: un silencio); si en ese tramo no hay
    silencio, pref llevado al tramo -> s, o None si el tramo no existe (hi < lo)"""
    if hi < lo - 1e-9: return None
    for j in range(int(math.ceil(max(abs(pref - lo), abs(hi - pref)) / paso)) + 1):   # pref, pref−0.01, pref+0.01, pref−0.02…
        for t in ((round(pref - j * paso, 3), round(pref + j * paso, 3)) if j else (round(pref, 3),)):
            if lo <= t <= hi and not dentro(t, voz, 0.0): return float(t)
    return float(min(max(pref, lo), hi))


def bordes_habla(st, W, voz, fin):
    """dónde cortar una frase de ella (toma 'habla'): la entrada entre el fin de su palabra anterior (+0.02) y el inicio de la
    frase (−0.02), la salida entre el fin de la frase (+0.02) y su palabra siguiente (−0.02), en un silencio del VAD si hay uno
    (lo más cerca de s−0.15 / e+0.30, lo de antes) -> (a, b), o None si la frase está pegada a la anterior o a la siguiente
    (sin pausa entre las dos: cortar ahí es cortarla mientras habla). Antes era s−0.15 / e+0.30 a ciegas y en el Epi Centurión
    entregado la entrada caía dentro de «hacer.» y la salida dentro de «Entonces».
    Una palabra 'aplastada' por la alineación (dentro del tiempo de la anterior: «Y» 8.67–8.69 dentro de «hacer.» 8.41–8.69)
    no marca el borde: manda la primera palabra con tiempo propio (ahí «le», 9.31; el corte cae en la pausa 8.9–9.15 del VAD)."""
    try: i0, i1 = W.index(st["words"][0]), W.index(st["words"][-1])
    except ValueError: return None
    antes = max((w["e"] for w in W[:i0]), default=None)                             # fin de lo que dijo antes (de cualquier frase)
    ini = next((w["s"] for w in W[i0:i1 + 1] if antes is None or w["e"] > antes + 0.01), None)   # 1ra palabra con tiempo propio
    if ini is None: return None
    e = max(w["e"] for w in W[i0:i1 + 1])
    despues = next((w["s"] for w in W[i1 + 1:] if w["e"] > e + 0.01), None)        # lo próximo que dice (sin las aplastadas)
    a = corte_libre(max(0.0, ini - 0.6, antes + 0.02 if antes is not None else 0.0), ini - 0.02, ini - 0.15, voz)
    b = corte_libre(e + 0.02, min(fin, e + 0.6, despues - 0.02 if despues is not None else fin), e + 0.30, voz)
    return None if a is None or b is None else (a, b)


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
    ella, voz = voces(c, A)
    # (a) cuando ella habla: frases completas de 1.2–9 s, con su audio y subtítulo (lo más valioso del evento); los dos cortes
    #     ENTRE palabras suyas y, si se puede, en silencio (bordes_habla)
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
        ab = bordes_habla(st, A["words"], voz, min(c["dur"] - 0.05, cut if cut is not None else 1e9))   # (nada desde que pide no grabar)
        if ab is None: continue                                                             # pegada a otra frase suya: no hay dónde cortar
        a, b = ab
        st = dict(st, text=txt[:1].upper() + txt[1:], words=[dict(st["words"][0], t=st["words"][0]["t"][:1].upper() + st["words"][0]["t"][1:])] + st["words"][1:])
        i0, i1 = int(a * AF), max(int(a * AF) + 1, int(b * AF))
        if float(np.mean(lil[i0:i1] >= 0.38)) < 0.5: continue                              # SU cara en la mayoría del tramo: el umbral de voz
        #   (0.776) queda debajo del parecido mediano de otras voces con la suya (0.799): sin su cara, un animador saldría como ella
        #   (en las pruebas sus frases tenían su cara el 83–100 % del tiempo)
        out.append(dict(k=c["k"], a=a, b=b, kind="habla", text=st["text"], words=st["words"],
                        score=4.0 + float(np.mean(shz[i0:i1])) + 1.5 * float(np.mean(lil[i0:i1] >= 0.38)) - 0.08 * float(np.mean(mot[i0:i1]))))
    # (b) tomas de ambiente: ventanas de 4–8 pulsos (2.3–4.6 s): las referencias de recorridas cortan 10–16 veces por minuto.
    #     Van con su sonido bajo la música, así que NUNCA llevan la voz de ella (eso es 'habla', con subtítulo, o no entra: antes
    #     entraba cortada en "corazón", "le"…) y sus dos cortes caen en PAUSAS: la ventana se corre hasta ±0.3 s buscando silencio
    #     en los dos bordes; si no hay pausa cerca (una sala que no calla), la voz de otros entra y sale con fundido de 0.35 s y la
    #     ventana pierde puntaje (se prefieren tramos sin habla: −1.2 × la parte con voz, −0.6 si necesita fundido)
    lim = min(c["dur"], n / AF)
    vistas = set()
    for nb in (8, 6, 5, 4):
        L = nb * BEAT
        cabe = lambda a: 0.15 <= a and a + L <= lim - 0.1
        for a0 in np.arange(0.2, lim - L - 0.1, 0.4):
            a = next((float(a0 + d) for d in (0.0, -0.1, 0.1, -0.2, 0.2, -0.3, 0.3)
                      if cabe(a0 + d) and not dentro(a0 + d, voz) and not dentro(a0 + d + L, voz)), None)
            fa = fb = 0.03
            if a is None:                                               # sin pausa cerca: fundido largo en el borde con voz
                a = float(a0); fa = FUNDIDO_VOZ if dentro(a, voz) else 0.03; fb = FUNDIDO_VOZ if dentro(a + L, voz) else 0.03
            if pisa(a - 0.15, a + L + 0.15, ella) > 0: continue         # su voz (o su respiración antes de hablar): nunca de fondo
            if (nb, round(a * 20)) in vistas: continue                  # dos arranques que se corrieron al mismo silencio
            vistas.add((nb, round(a * 20)))
            i0, i1 = int(a * AF), int((a + L) * AF)
            if i1 > n: continue
            m_ = mot[i0 + 1:i1]
            if len(m_) == 0: continue
            if m_.max() > 22 or bri[i0:i1].mean() < 45: continue        # barrido de cámara o muy oscuro: nunca
            hv = pisa(a, a + L, voz) / L                                # parte de la ventana con voz (de otros)
            sc = (1.0 * float(np.mean(shz[i0:i1])) - 1.5 * float(np.mean(jit[i0:i1])) - 0.05 * float(np.mean(m_))   # pulso de la cámara:
                  - 0.15 * max(0.0, float(m_.max()) - 8.0)                     # se prefieren tomas quietas (pedido 2026-10-18: "tiemblan mucho")
                  + 1.0 * float(np.mean(nf[i0:i1] >= 1)) + 0.6 * float(np.mean(nf[i0:i1] >= 2)) + 1.6 * float(np.mean(lil[i0:i1] >= 0.38))
                  + 2.0 * min(0.25, float(np.median(fsz[i0:i1]))) + 0.10 * nb          # a igual calidad, tomas más largas
                  - 1.2 * hv - (0.6 if max(fa, fb) > 0.1 else 0.0))                    # y sin habla de fondo
            out.append(dict(k=c["k"], a=a, b=a + L, kind="ambiente", score=sc, beats=nb, fa=fa, fb=fb, voz=round(hv, 2)))
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


def linea_de_tiempo(chosen):
    """tomas elegidas -> línea de tiempo (o0/o1: dónde cae cada una en el video, sin la tarjeta final)"""
    tl, t = [], 0.0
    for x in chosen:
        d = x["b"] - x["a"]; tl.append(dict(x, o0=t, o1=t + d)); t += d
    return tl


def toma_en(tl, t):
    """índice de la toma que se ve en el segundo t del video"""
    return next(i for i, s in enumerate(tl) if s["o0"] - 1e-6 <= t < s["o1"] + 1e-6 or i == len(tl) - 1)


def encuadre(Ak, s, si, t):
    """cámara de una toma en el segundo t del video: empuje lento hacia la cara principal (o el centro), alternando entra/sale por
    toma -> (z, x0, y0, cw, ch): el recorte (x0, y0, cw×ch) del cuadro de la toma que llena la salida (salida = (p − x0)·z).
    Lo usan el render y los controles (así el QA mide exactamente lo que se ve)."""
    u = (t - s["o0"]) / max(1e-3, s["o1"] - s["o0"])
    z = 1.03 + 0.025 * u * u * (3 - 2 * u)                                 # acercamiento MUY lento y siempre hacia adentro (2026-10-18:
    i0 = max(0, int(s["a"] * AF)); i1 = max(i0 + 1, min(len(Ak["fcx"]), int(s["b"] * AF)))   # "solo los movimientos necesarios")
    xs = [v for v in Ak["fcx"][i0:i1] if v is not None]; ys = [v for v in Ak["fcy"][i0:i1] if v is not None]
    fx = float(np.median(xs)) if xs else W / 2                             # encuadre FIJO por toma (mediana de la cara en la toma):
    fy = float(np.median(ys)) if ys else H * 0.42                          # antes seguía la cara 10 veces por segundo y temblaba
    cx = W / 2 + 0.35 * (fx - W / 2); cy = H * 0.45 + 0.25 * (fy - H * 0.45)
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw); y0 = min(max(cy - ch / 2, 0), H - ch)
    return z, x0, y0, cw, ch


def palabras_de(s, A):
    """palabras de una frase de ella (las del plan; un plan viejo no las guardaba: se toman del análisis de la toma)"""
    if s.get("words"): return s["words"]
    ws = [dict(w) for w in A[s["k"]]["words"] if s["a"] - 0.05 <= w["s"] and w["e"] <= s["b"] + 0.05]
    if ws: ws[0]["t"] = ws[0]["t"][:1].upper() + ws[0]["t"][1:]
    return ws


def subtitulos(tl, A):
    """subtítulos de lo que ella dice: [{s, e, img (RGBA numpy), x, y (esquina donde se dibuja)}] en tiempo del video"""
    from styles.common import sub_sprite
    caps = []
    for s in tl:
        if s["kind"] != "habla": continue
        for ch in cap_chunks(palabras_de(s, A)):
            im = sub_sprite(ch["text"].split(), px=54)
            caps.append(dict(s=max(s["o0"], s["o0"] + ch["s"] - s["a"]), e=min(s["o1"], s["o0"] + ch["e"] - s["a"] + 0.15),   # dentro de SU toma
                             img=im, text=ch["text"], x=W / 2 - im.shape[1] / 2, y=SUB_Y - im.shape[0] / 2))   # (la salida puede ser e+0.02)
    for c1, c2 in zip(caps, caps[1:]): c1["e"] = min(c1["e"], max(c1["s"], c2["s"]))   # nunca dos a la vez en el mismo lugar (la cola
    return caps                                                                         # de +0.15 s pisaba 0.1 s al siguiente)


def tinta(img, thr=0.85):
    """caja (x0, y0, x1, y1) de lo que se ve de una pieza (alfa > thr), en coordenadas de la pieza"""
    ys, xs = np.where(img[..., 3] > thr * 255)
    return (0, 0, 0, 0) if not len(ys) else (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def titulo_y(tl, A, tit, caps=()):
    """centro (y) del título: ARRIBA con toda la tinta dentro de la zona segura (debajo de la barra de la app: y ≥ 270; antes un
    título de 2 líneas + fecha quedaba con el 28 % bajo esa barra), salvo que mientras está entero haya caras en esa franja ->
    ABAJO, si ahí tapa menos caras y no pisa los subtítulos de ella. Caras: la más grande de cada cuadro del análisis, llevada al
    cuadro de salida con el mismo encuadre del render (antes: solo la primera toma y sin el encuadre)."""
    Hc = tit.shape[0]; _, ty0, _, ty1 = tinta(tit)
    arriba = max(330.0, SAFE["top"] - ty0 + Hc / 2)
    abajo = 1180.0
    def caras(ty):
        top, bot = ty - Hc / 2 + ty0, ty - Hc / 2 + ty1
        hits = tot = 0
        for t in np.arange(TITULO_T[0] + 0.5, TITULO_T[1] - 0.5, 0.1):          # mientras está entero (sin la entrada ni la salida)
            si = toma_en(tl, t); s = tl[si]; Ak = A[s["k"]]
            j = int((s["a"] + t - s["o0"]) * AF)
            if j >= len(Ak["fcy"]): continue
            tot += 1
            if Ak["fcy"][j] is not None and Ak["fsz"][j] > 0:
                z, _, y0, _, _ = encuadre(Ak, s, si, t)
                fy, fh = (Ak["fcy"][j] - y0) * z, Ak["fsz"][j] * H * z
                if fy - fh * 0.8 < bot and fy + fh * 0.6 > top: hits += 1          # cara con pelo y mentón
        return hits / tot if tot else 0.0
    def pisa_subs(ty):
        top, bot = ty - Hc / 2 + ty0, ty - Hc / 2 + ty1
        return any(c["s"] < TITULO_T[1] and c["e"] > TITULO_T[0] and c["y"] + tinta(c["img"])[1] < bot and c["y"] + tinta(c["img"])[3] > top
                   for c in caps)
    ca = caras(arriba)
    if ca > 0.2 and not pisa_subs(abajo) and caras(abajo) < ca: return abajo
    return arriba


# ================================================================== 5. armar y renderizar
def build(clips, chosen, pd, titulo, sub, name):
    from styles.common import Endcard, exit_to_white
    # línea de tiempo
    tl = linea_de_tiempo(chosen)
    main = tl[-1]["o1"] if tl else 0.0; END = 3.0; total = main + END; NF = int(round(total * FPS))
    whips = ([int(round(s["o0"] * FPS)) for i, s in enumerate(tl) if i and s["k"] != tl[i - 1]["k"]]     # barrido al cambiar de toma:
             if os.environ.get("STUDIO_BARRIDOS") == "1" else [])          # apagado por defecto (cortes limpios, sin sacudón)
    # audio: voz de ella a pleno + ambiente bajo (−14 dB) + música al pulso (baja cuando ella habla)
    N = NF * SPF
    voice = np.zeros((N, 2), np.float32); amb = np.zeros((N, 2), np.float32); mask = []
    for s in tl:
        a = read_wav(clips[s["k"]]["audio"])
        if a.shape[1] == 1: a = np.repeat(a, 2, 1)
        i0, i1 = int(s["a"] * SR), int(s["b"] * SR); seg = a[i0:i1]
        o = int(s["o0"] * SR); seg = seg[:max(0, min(len(seg), N - o))].copy()
        amb_ = s["kind"] == "ambiente"                                  # ambiente con un borde en la voz de otro: fundido largo (candidates)
        fa = min(int((s.get("fa", 0.03) if amb_ else 0.03) * SR), len(seg) // 2)
        fb = min(int((s.get("fb", 0.03) if amb_ else 0.03) * SR), len(seg) // 2)
        if fa > 0: seg[:fa] *= np.linspace(0, 1, fa)[:, None]
        if fb > 0: seg[-fb:] *= np.linspace(1, 0, fb)[:, None]
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
    A = {c["k"]: json.load(open(os.path.join(pd, "clips", f"c{c['k']}.json"), encoding="utf-8")) for c in clips}
    tit = title_sprite(titulo, sub) if titulo else None
    T_spr = spr_t(tit) if tit is not None else None
    caps = subtitulos(tl, A)
    for c_ in caps: c_["spr"] = spr_t(c_["img"])
    end = Endcard()
    # el título no tapa caras: arriba (dentro de la zona segura) salvo que mientras está haya caras en esa franja -> abajo (y=1180)
    ty = titulo_y(tl, A, tit, caps) if tit is not None else 0.0
    if tit is not None: log(f"título en y={ty:.0f}" + (" (arriba había caras)" if ty >= 1000 else ""))
    out = os.path.join(pd, f"{name}.mp4")
    enc = start_encoder(out, mix_p, total)
    rd, cur = None, None
    t0 = time.time()
    for n in range(NF):
        t = n / FPS
        if t >= main:
            fr = end.frame(t - main)
        else:
            si = toma_en(tl, t)
            s = tl[si]
            if cur != si:
                if rd: rd.close()
                rd = Reader(clips[s["k"]]["video"], int(round(s["a"] * FPS))); cur = si
            src = (T(rd.get()).permute(2, 0, 1).float() / 255)[None]
            # encuadre: empuje lento hacia la cara principal (o el centro), alternando entra/sale por toma
            z, x0, y0, cw, ch = encuadre(A[s["k"]], s, si, t)
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
                    blend(fr, c_["spr"], c_["x"], c_["y"])                     # centrado en x, centro en y = SUB_Y
            k, off = whip_k(n, whips)
            fr = whip_filter(fr, k, off)
            fr = exit_to_white(fr, int(round(main * FPS)) - n)
        enc.stdin.write(to_np(fr).tobytes())
        if n % 300 == 0: log(f"render {n}/{NF} ({n / max(1e-3, time.time() - t0):.0f} fps)")
    if rd: rd.close()
    enc.stdin.close(); enc.wait()
    make_lite(out, os.path.join(pd, f"{name}_liviano.mp4"))
    json.dump(dict(timeline=[{k: v for k, v in s.items() if k not in ("words",)} for s in tl], total=total, audio=info,
                   titulo=titulo, sub=sub, ty=ty),                       # (el QA vuelve a medir con la misma altura del título)
              open(os.path.join(pd, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return out


def qa(out, total):
    """controles del archivo renderizado: cuadros negros, volumen y duración del archivo -> hallazgos (todos 'alta': no se entrega)"""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out, "-vf", "blackdetect=d=0.15:pix_th=0.06", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore").stderr
    blacks = re.findall(r"black_start:([\d.]+)", r); I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip() or 0)
    F = []
    if blacks: F.append(("alta", "BLACK", f"negro en {blacks[:3]}", ""))
    if I and not -16.5 <= float(I[-1]) <= -11.5: F.append(("alta", "LUFS", f"volumen {I[-1]} LUFS", ""))
    if abs(dur - total) > 0.3: F.append(("alta", "DUR", f"duración del archivo {dur:.1f} vs {total:.1f}", ""))
    return dict(ok=not F, findings=F, lufs=float(I[-1]) if I else None, dur=dur)


def cuadro(video, t, w=540, h=960):
    """un cuadro (BGR, w×h) de una toma en el segundo t, o None"""
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={w}:{h}",
                        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(b[:w * h * 3], np.uint8).reshape(h, w, 3) if len(b) >= w * h * 3 else None


def qa_montaje(pd, titulo=None, sub=None, ty=None, caras=True, plan=None, leer_cuadro=None):
    """controles del montaje SIN renderizar, con el plan (plan.json) y el análisis guardado de cada toma (clips/c*.json):
       DUR           lo armado vs lo pedido (corto = faltó material bueno)
       MIDSENTENCE   toma de ambiente que corta una palabra: su voz (alta: no se entrega) o la de otro sin fundido (media); su voz
                     entera bajo la música, sin subtítulo (media). Toma 'habla' (su frase) con la entrada o la salida DENTRO de una
                     palabra suya (alta: el Epi Centurión entregado entraba en «hacer.» y salía en «Entonces»)
       SAFE_ZONE     título o subtítulo en la zona que tapa la app (el criterio de qa_visual: > 25 % de la tinta)
       CLIPPED       título o subtítulo que se sale del cuadro (> 3 % de la tinta)
       SOLAPE        el título encima de los subtítulos
       TEXT_ON_FACE  el título tapa una cara: YuNet sobre los cuadros REALES de la toma mientras el título está entero, llevados al
                     cuadro de salida con el mismo encuadre del render (≈ 9 cuadros, procesador); cuenta con ≥ 2 muestras
    Las posiciones son las del render (título: titulo_y o la guardada en timeline.json; subtítulos: centro en SUB_Y).
    plan: otro plan (dict con chosen y clips) sobre el mismo análisis, en vez de pd/plan.json (para comparar selecciones).
    leer_cuadro(video, t) -> cuadro BGR 540×960 (por defecto cuadro(): ffmpeg sobre la toma; las pruebas pasan cuadros guardados).
    -> [(gravedad, código, texto, detalle)] como qa.json (alta = no se entrega; media/baja = aviso en el informe de auto.py)"""
    leer_cuadro = leer_cuadro or cuadro
    P = plan or json.load(open(os.path.join(pd, "plan.json"), encoding="utf-8"))
    tj = os.path.join(pd, "timeline.json")
    TL = json.load(open(tj, encoding="utf-8")) if os.path.exists(tj) and plan is None else {}    # (el render de ESE plan)
    clips = {c["k"]: c for c in P["clips"]}
    A = {k: json.load(open(os.path.join(pd, "clips", f"c{k}.json"), encoding="utf-8")) for k in clips}
    tl = linea_de_tiempo(P["chosen"])
    if not tl: return [("alta", "DUR", "no se eligió ninguna toma", "")]
    F = []
    # 1) duración: lo armado contra lo pedido
    armado = tl[-1]["o1"]; material = sum(c["dur"] for c in P["clips"])
    pedido = float(P.get("pedido") or np.clip(0.45 * material, 12.0, 45.0))          # plan viejo: el pedido por defecto de main()
    if armado < pedido - max(1.5, 0.08 * pedido):
        F.append(("media", "DUR", f"montaje de {armado:.1f} s para {pedido:.0f} s pedidos: con {material:.0f} s de material no alcanzaron las tomas buenas",
                  f"armado {armado:.1f} / pedido {pedido:.1f}"))
    elif armado > pedido + 1.5:
        F.append(("media", "DUR", f"montaje de {armado:.1f} s para {pedido:.0f} s pedidos", f"armado {armado:.1f} / pedido {pedido:.1f}"))
    # 2) ningún corte dentro de una palabra suya (tomas 'habla' y de ambiente) ni de otros (ambiente) y su voz nunca de fondo
    for i, s in enumerate(tl):
        nom = f"toma {i + 1} ({clips[s['k']]['file'][:26]} {s['a']:.1f}–{s['b']:.1f} s)"
        if s["kind"] == "habla":                                                    # su frase: los dos cortes ENTRE palabras suyas
            for x, borde in ((s["a"], "entrada"), (s["b"], "salida")):              # (±0.01: una intrusión de 0.02 s ya cuenta)
                w = next((w for w in A[s["k"]]["words"] if w["s"] + 0.01 < x < w["e"] - 0.01), None)
                if w: F.append(("alta", "MIDSENTENCE", f"{nom}: la {borde} de su frase corta su palabra «{w['t']}»", f"{x:.2f} s"))
            continue
        if s["kind"] != "ambiente": continue
        ella, voz = voces(clips[s["k"]], A[s["k"]])
        for x, fd, borde in ((s["a"], s.get("fa", 0.03), "entrada"), (s["b"], s.get("fb", 0.03), "salida")):
            if dentro(x, ella, 0.03):
                w = next((w["t"] for w in A[s["k"]]["words"] if w["s"] < x < w["e"]), None)
                F.append(("alta", "MIDSENTENCE", f"{nom}: la {borde} corta su voz" + (f" en «{w}»" if w else " a mitad de frase"), f"{x:.2f} s"))
            elif dentro(x, voz) and fd < 0.3:
                F.append(("media", "MIDSENTENCE", f"{nom}: la {borde} corta la voz de otra persona sin fundido", f"{x:.2f} s"))
        if not any(dentro(x, ella, 0.03) for x in (s["a"], s["b"])) and pisa(s["a"], s["b"], ella) > 0.3:
            F.append(("media", "MIDSENTENCE", f"{nom}: su voz queda de fondo bajo la música, sin subtítulo", f"{pisa(s['a'], s['b'], ella):.1f} s de su voz"))
    # 3) piezas de texto: dentro del cuadro y de la zona segura; el título sin pisar los subtítulos
    caps = subtitulos(tl, A)
    titulo = titulo if titulo is not None else (P.get("titulo") or TL.get("titulo") or "")
    sub = sub if sub is not None else (P.get("sub") or TL.get("sub") or "")
    tit = title_sprite(titulo, sub) if titulo else None
    piezas = [(f"subtítulo «{c['text']}»", c["img"], c["x"], c["y"]) for c in caps]
    if tit is not None:
        if ty is None and TL.get("ty") and TL.get("titulo") == titulo: ty = float(TL["ty"])   # la altura con que se renderizó
        if ty is None: ty = titulo_y(tl, A, tit, caps)
        piezas.insert(0, ("título", tit, 0.0, ty - tit.shape[0] / 2))
    for nom, im, x, y in piezas:
        ys, xs = np.nonzero(im[..., 3] > 0.85 * 255)
        if len(ys) < 400: continue
        X, Y = xs + int(round(x)), ys + int(round(y))
        fuera = float(np.mean((X < 0) | (X >= W) | (Y < 0) | (Y >= H)))
        if fuera > 0.03: F.append(("media", "CLIPPED", f"{nom}: {100 * fuera:.0f} % se sale del cuadro", f"x={x:.0f} y={y:.0f}"))
        mala = float(np.mean((Y < 250) | (Y > 1460) | ((X > 900) & (Y > 800) & (Y < 1460))))   # barra de arriba, abajo, columna de íconos
        if mala > 0.25: F.append(("baja", "SAFE_ZONE", f"{nom}: {100 * mala:.0f} % en la zona que tapa la app", f"x={x:.0f} y={y:.0f}"))
    if tit is not None:
        _, a0, _, a1 = tinta(tit); top, bot = ty - tit.shape[0] / 2 + a0, ty - tit.shape[0] / 2 + a1
        pis = [c["text"] for c in caps if c["s"] < TITULO_T[1] and c["e"] > TITULO_T[0]
               and c["y"] + tinta(c["img"])[1] < bot and c["y"] + tinta(c["img"])[3] > top]
        if pis: F.append(("media", "SOLAPE", f"el título tapa el subtítulo «{pis[0]}»", f"título en y={ty:.0f}"))
    # 4) el título no tapa caras (YuNet sobre los cuadros de la toma, con el encuadre del render)
    if tit is not None and caras:
        al = tit[..., 3] > 127; Hc = tit.shape[0]; yt = int(round(ty - Hc / 2))
        det = cv2.FaceDetectorYN.create(os.path.join(STUDIO, "models", "yunet.onnx"), "", (540, 960), 0.6, 0.3, 50)
        hits, n_ = [], 0
        for t in np.arange(TITULO_T[0] + 0.55, TITULO_T[1] - 0.45, 0.25):          # 0.75 … 2.75 s: el título entero
            if t >= armado: break
            si = toma_en(tl, t); s = tl[si]
            fr = leer_cuadro(clips[s["k"]]["video"], s["a"] + t - s["o0"])
            if fr is None: continue
            n_ += 1
            _, f = det.detect(fr)
            z, x0, y0, _, _ = encuadre(A[s["k"]], s, si, t)
            for r in ([] if f is None else f):
                fx, fy, fw, fh = (2 * r[0] - x0) * z, (2 * r[1] - y0) * z, 2 * r[2] * z, 2 * r[3] * z   # 540×960 -> toma -> salida
                if fh < 64: continue                                                  # caras chiquitas del fondo: no cuentan
                cx0, cy0, cx1, cy1 = fx + 0.15 * fw, fy + 0.2 * fh, fx + 0.85 * fw, fy + 0.95 * fh   # ojos y boca (como qa_visual)
                ix0, iy0, ix1, iy1 = int(max(cx0, 0)), int(max(cy0, yt, 0)), int(min(cx1, W)), int(min(cy1, yt + Hc, H))
                if ix1 > ix0 and iy1 > iy0 and float(al[iy0 - yt:iy1 - yt, ix0:ix1].sum()) / ((cx1 - cx0) * (cy1 - cy0)) > 0.08:
                    hits.append(round(float(t), 2)); break
        if len(hits) >= 2:
            F.append(("media", "TEXT_ON_FACE", f"el título tapa una cara en {len(hits)} de {n_} muestras (ej. {hits[:4]} s)", f"título en y={ty:.0f}"))
    # un renglón por tipo de hallazgo (el informe los dice en palabras), con el detalle de todos
    out = []
    for g, k in dict.fromkeys((f[0], f[1]) for f in F):
        xs = [f for f in F if f[:2] == (g, k)]
        out.append((g, k, xs[0][2] + (f" (y {len(xs) - 1} más)" if len(xs) > 1 else ""), " · ".join(f"{f[2]} [{f[3]}]" for f in xs)[:600]))
    return out


# ================================================================== principal
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+"); ap.add_argument("--titulo", default=""); ap.add_argument("--sub", default="")
    ap.add_argument("--length", type=float, default=0); ap.add_argument("--name"); ap.add_argument("--grupo", type=int)
    ap.add_argument("--no-render", action="store_true"); ap.add_argument("--no-deliver", action="store_true")
    ap.add_argument("--tema", default="", help="nombres propios y temas (mejoran la transcripción de lo que ella dice)")
    ap.add_argument("--qa", action="store_true", help="solo los controles del montaje sobre un plan ya guardado: evento.py <proyecto> --qa")
    a = ap.parse_args()
    if a.tema: os.environ["EVENTO_TEMA"] = a.tema
    if a.qa:                                                                # sin preparar, analizar ni renderizar nada
        pd = a.inputs[0] if os.path.isdir(a.inputs[0]) else os.path.join(PROJECTS, a.inputs[0])
        F = qa_montaje(pd, titulo=a.titulo or None, sub=a.sub or None)
        for f in F: log(f"  {f[0]:5s} {f[1]:12s} {f[2]}")
        log(f"QA del montaje: {'sin hallazgos' if not F else str(len(F)) + ' hallazgo(s)'}")
        return
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
    if not chosen:
        log("✗ no quedó ninguna toma utilizable (movidas, oscuras, voz cortada o lo que pide no grabar): no se arma el montaje")
        json.dump(dict(ok=False, findings=[("alta", "DUR", "no se eligió ninguna toma", "sumar tomas del evento")], pedido=length, armado=0.0),
                  open(os.path.join(pd, "qa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
        sys.exit(1)
    log(f"elegidas {len(chosen)} tomas · {sum(x['b'] - x['a'] for x in chosen):.1f} s (pedido {length:.0f} s) de {good:.0f} s de material")
    for x in chosen:
        log(f"  {clips[x['k']]['file'][:28]:28s} {x['a']:6.1f}-{x['b']:6.1f}  {x['kind']:8s} {x['score']:5.2f}  {x.get('text', '')[:70]}")
    json.dump(dict(chosen=chosen, clips=clips, titulo=a.titulo, sub=a.sub, pedido=length),     # (con las palabras: el QA rehace los subtítulos)
              open(os.path.join(pd, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    try: Fm = qa_montaje(pd, titulo=a.titulo, sub=a.sub, caras=a.no_render)      # controles del montaje antes de renderizar (las caras
    #                                                                             bajo el título se miran después, con la altura del render)
    except Exception as e: Fm = [("media", "QA", f"no se pudieron correr los controles del montaje: {e!r}"[:200], "")]
    for f in Fm: log(f"  QA montaje · {f[0]} · {f[2]}")
    if a.no_render: return
    out = build(clips, chosen, pd, a.titulo, a.sub, name)
    q = qa(out, sum(x["b"] - x["a"] for x in chosen) + 3.0)
    tj = os.path.join(pd, "timeline.json")                                  # la cara bajo el título se mide con la altura del render
    if a.titulo and os.path.exists(tj):
        try: Fm = qa_montaje(pd, titulo=a.titulo, sub=a.sub, ty=json.load(open(tj, encoding="utf-8")).get("ty"))
        except Exception: pass
    F = q["findings"] + Fm
    q["ok"] = not any(f[0] == "alta" for f in F)                           # alta: no se entrega · media/baja: se entrega con aviso
    json.dump(dict(ok=q["ok"], findings=F, lufs=q["lufs"], dur=q["dur"], pedido=length, armado=sum(x["b"] - x["a"] for x in chosen)),
              open(os.path.join(pd, "qa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)   # lo lee el informe de auto.py
    if not q["ok"]: log(f"QA: HALLAZGOS {[f[2] for f in F if f[0] == 'alta']} · {q['dur']:.1f} s · {q['lufs']} LUFS · {time.time() - t0:.0f} s")
    elif F: log(f"QA: OK con AVISO ({'; '.join(f[2] for f in F)[:180]}) · {q['dur']:.1f} s · {q['lufs']} LUFS · {time.time() - t0:.0f} s")
    else: log(f"QA: OK · {q['dur']:.1f} s · {q['lufs']} LUFS · {time.time() - t0:.0f} s")
    if q["ok"] and not a.no_deliver:
        for d in DELIVER:
            if os.path.isdir(d):
                shutil.copy(out, os.path.join(d, os.path.basename(out)))
                shutil.copy(os.path.join(pd, f"{name}_liviano.mp4"), os.path.join(d, f"{name}_liviano.mp4"))
                log("entregado en", d)


if __name__ == "__main__":
    main()
