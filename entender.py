# Estudio de edición — ENTENDER un video antes de editarlo: qué es y cómo se edita (sin que nadie lo diga).
# Mide formato (orientación, resolución real, píxeles no cuadrados, HDR), cuánto se habla y cuánto de eso es LILIAN (huella de
# voz), cuántas otras voces, música/aplausos de fondo, caras (cuántas, tamaño, si una es Lilian: huella de cara), movimiento de
# cámara, si ya viene editado (subtítulos, cortes, tarjeta final) y si tiene zócalo de TV. Con eso decide el TIPO y recomienda
# formato + estilo + comando. En una carpeta, además agrupa las tomas sueltas por evento (fecha del archivo).
#   python entender.py <video>            -> ficha + recomendación
#   python entender.py <carpeta>          -> ficha de cada video + grupos por evento + plan (analysis/entender_<carpeta>.json)
#   python entender.py --evaluar          -> contra lo etiquetado a mano (analysis/entender_verdad.json)
import os, sys, json, re, subprocess, datetime, hashlib
import numpy as np, cv2

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO)
MODELS = os.path.join(STUDIO, "models")
CLIENTS = os.path.join(STUDIO, "clients")
CACHE = os.path.join(STUDIO, "analysis", "entender_cache"); os.makedirs(CACHE, exist_ok=True)
VID = (".mp4", ".mov", ".m4v", ".mkv")

TIPOS = {
    "conferencia": ("CONFERENCIA / DECLARACIÓN (ella habla, con o sin periodistas)",
                    'python ingest.py "{v}" --name {n} --tema "…" && STUDIO_SOURCE={n} python make_video.py --style redes --angle <ángulo>'),
    "discurso": ("DISCURSO en un acto (ella habla con micrófono ante el público)",
                 'python ingest.py "{v}" --name {n} --tema "…" && STUDIO_SOURCE={n} python make_video.py --style redes --angle <ángulo>'),
    "mensaje": ("MENSAJE A CÁMARA (ella sola, de frente)",
                'python ingest.py "{v}" --name {n} --tema "…" && STUDIO_SOURCE={n} python make_video.py --style redes --angle <ángulo>'),
    "reunion": ("REUNIÓN (varias personas hablan por turnos)", 'python reunion.py ingest "{v}" --name {n} --tema "…"'),
    "tv": ("TV / RADIO / SENADO (señal de un canal, con zócalo)", 'python ingest.py "{v}" --name {n} --layout panel --tema "…"  (estilo datos)'),
    "evento": ("EVENTO / RECORRIDA (tomas del lugar, gente, saludos; ella casi no habla)",
               'python evento.py "<carpeta>" --grupo <N> --titulo "…" --sub "<fecha>"  (montaje con música, junto con las tomas del mismo evento)'),
    "clip": ("TOMA CORTA (< 20 s)", 'python evento.py "<carpeta>" --grupo <N> --titulo "…"  (montaje con las otras tomas del mismo evento)'),
    "editado": ("YA EDITADO (subtítulos / cortes / tarjeta final)", 'referencia: python analyze_batch.py refs "<carpeta>" <etiqueta>'),
}


# ------------------------------------------------------------------ formato
def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", p],
                                  capture_output=True, text=True, encoding="utf-8").stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    rot = next((int(sd.get("rotation", 0)) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    try: sn, sd = (int(x) for x in (v.get("sample_aspect_ratio") or "1:1").split(":"))
    except ValueError: sn, sd = 1, 1
    if sn > 0 and sd > 0 and (sn, sd) != (1, 1): w = int(round(w * sn / sd / 2)) * 2
    if abs(rot) % 180 == 90: w, h = h, w
    tags = {**j["format"].get("tags", {}), **v.get("tags", {})}
    return dict(dur=float(j["format"].get("duration", 0)), w=w, h=h, sar=f"{sn}:{sd}", hdr=v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
                audio=any(s["codec_type"] == "audio" for s in j["streams"]), created=tags.get("creation_time"))


def fecha(path, info):
    """fecha de la toma: del nombre (DJI_20251205091856, VID_20260822_120059, IMG_…) o de los metadatos"""
    b = os.path.basename(path)
    m = re.search(r"(20\d{2})(\d{2})(\d{2})[_ ]?(\d{2})(\d{2})(\d{2})", b)
    if m:
        try: return datetime.datetime(*map(int, m.groups()))
        except ValueError: pass                                  # número largo que no es fecha (id de TikTok)
    if info.get("created"):
        try:                                                     # los metadatos vienen en UTC: hora local de la PC (Paraguay), como los nombres DJI
            d = datetime.datetime.fromisoformat(info["created"].replace("Z", "+00:00"))
            return (d.astimezone() if d.tzinfo else d).replace(tzinfo=None)
        except ValueError: pass
    m = re.search(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})", b)            # "2026-10-14-LS1.mp4": solo el día
    if m:
        try: return datetime.datetime(*map(int, m.groups()), 12, 0, 0)
        except ValueError: pass
    return None


# ------------------------------------------------------------------ audio: habla, voz de Lilian, otras voces, fondo
def audio_features(path, dur):
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    a = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                                     capture_output=True).stdout, np.int16).astype(np.float32) / 32768
    if len(a) < 16000: return dict(speech_ratio=0.0, lilian_share=0.0, other_voices=0, other_share=0.0, bed_db=None, voice_db=None, music=False)
    vad = get_speech_timestamps(a, VadOptions(threshold=0.5, min_silence_duration_ms=300, speech_pad_ms=60))
    seg = [(v["start"] / 16000, v["end"] / 16000) for v in vad]
    speech = sum(e - s for s, e in seg)
    hop = 160; n = len(a) // hop
    db = 20 * np.log10(np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    sp = np.zeros(n, bool)
    for s, e in seg: sp[int(s * 100):int(e * 100) + 1] = True
    voice_db = float(np.percentile(db[sp], 70)) if sp.any() else None
    gaps = db[~sp]
    bed_db = float(np.median(gaps)) if len(gaps) > 100 else None
    # voz: ventanas de ≤ 3 s sobre el habla (hasta 48, repartidas) -> parecido con la huella de Lilian
    import speakers as SPK
    vp = np.load(os.path.join(CLIENTS, "lilian_voiceprint.npy")); thr = json.load(open(os.path.join(CLIENTS, "lilian_voiceprint.json")))["threshold"]
    wins = [w for s, e in seg if e - s >= 1.0 for w in SPK.chunks(s, e, 3.0) if w[1] - w[0] >= 1.0]
    if len(wins) > 48: wins = [wins[int(i)] for i in np.linspace(0, len(wins) - 1, 48)]
    embs = np.array([SPK.embed(a, s, e) for s, e in wins]) if wins else np.zeros((0, 1))
    sims = embs @ (vp / np.linalg.norm(vp)) if len(embs) else np.zeros(0)
    lil = sims >= thr - 0.03
    others, other_share = 0, 0.0
    if (~lil).sum() >= 2:
        from scipy.cluster.hierarchy import linkage, fcluster
        E = embs[~lil]
        lab = fcluster(linkage(E, "average", metric="cosine"), t=0.32, criterion="distance")
        cnt = np.bincount(lab)[1:]
        others = int((cnt >= 2).sum()); other_share = float((~lil).mean())
    elif (~lil).sum() == 1: other_share = float((~lil).mean())
    return dict(speech_ratio=round(speech / max(1e-6, dur), 2), lilian_share=round(float(lil.mean()), 2) if len(lil) else 0.0,
                lilian_sim=round(float(np.median(sims)), 3) if len(sims) else None, other_voices=others, other_share=round(other_share, 2),
                voice_db=round(voice_db, 1) if voice_db is not None else None, bed_db=round(bed_db, 1) if bed_db is not None else None,
                music=bool(bed_db is not None and voice_db is not None and bed_db > -45 and voice_db - bed_db < 20), n_wins=len(wins))


# ------------------------------------------------------------------ imagen: caras, Lilian, cámara, subtítulos, zócalo, cortes
def video_features(path, info, fps=2.0):
    W = 640 if info["w"] >= info["h"] else 360
    Hh = int(round(W * info["h"] / max(1, info["w"]) / 2) * 2)
    vf = f"scale={W}:{Hh}" + (",zscale=t=linear:npl=300,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p" if info["hdr"] else "") + f",fps={fps}"
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    det = cv2.FaceDetectorYN.create(os.path.join(MODELS, "yunet.onnx"), "", (W, Hh), 0.6, 0.3, 50)
    rec = cv2.FaceRecognizerSF.create(os.path.join(MODELS, "sface.onnx"), "")
    fp = np.load(os.path.join(CLIENTS, "lilian_faceprint.npy")).astype(np.float32).ravel(); fp /= np.linalg.norm(fp)
    nf, big, lil, mot, cap, cut, frames = [], [], [], [], [], [], []
    prev = None; prevh = None
    while True:
        b = pr.stdout.read(W * Hh * 3)
        if len(b) < W * Hh * 3: break
        fr = np.frombuffer(b, np.uint8).reshape(Hh, W, 3)
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        _, f = det.detect(fr)
        f = [] if f is None else [r for r in f if r[2] * r[3] > (Hh * 0.035) ** 2]
        nf.append(len(f)); big.append(max([max(r[2], r[3]) / Hh for r in f], default=0.0))
        hit = 0.0
        for r in sorted(f, key=lambda r: -r[2] * r[3])[:3]:
            if r[3] < 28: continue
            try:
                e = rec.feature(rec.alignCrop(fr, r)).ravel(); e /= np.linalg.norm(e) + 1e-9
                hit = max(hit, float(e @ fp))
            except cv2.error: pass
        lil.append(hit)
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(np.float32(prev), np.float32(g)); mot.append(float(np.hypot(dx, dy)) / W)
        hs = cv2.calcHist([g], [0], None, [32], [0, 256]).ravel(); hs /= hs.sum() + 1e-9
        if prevh is not None: cut.append(float(np.abs(hs - prevh).sum()))
        prev, prevh = g, hs
        # subtítulo editado: texto blanco con borde negro en la banda 0.55–0.88 (como lo ponen las referencias)
        wh = (g > 238).astype(np.uint8); dk = (g < 40).astype(np.uint8)
        edge = wh & cv2.dilate(dk, np.ones((3, 3), np.uint8))
        band = edge[int(Hh * 0.55):int(Hh * 0.88), int(W * 0.15):int(W * 0.85)]
        cap.append(float(band.sum(1).max()) > W * 0.05)
        if len(frames) < 400: frames.append(cv2.resize(g, (160, int(160 * Hh / W))))
    n = len(nf)
    if n == 0: return {}
    # zócalo de TV: franja de abajo QUIETA y con mucho borde (texto) mientras el resto cambia
    st = np.array(frames, np.float32)
    hb = st.shape[1]; lo = st[:, int(hb * 0.72):, :]; hi = st[:, :int(hb * 0.6), :]
    tstd_lo = float(np.median(lo.std(0))); tstd_hi = float(np.median(hi.std(0)))
    edges_lo = float(np.mean([cv2.Canny(x.astype(np.uint8), 80, 160)[int(hb * 0.72):].mean() for x in frames[::max(1, len(frames) // 20)]])) / 255
    cuts = int(sum(1 for c in cut if c > 0.55))
    end_white = False
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-1.5", "-i", path, "-frames:v", "1", "-vf", "scale=64:-2", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        end_white = len(r) > 0 and float(np.frombuffer(r, np.uint8).mean()) > 225
    except Exception: pass
    lil_rate = float(np.mean(np.array(lil) >= 0.42))
    return dict(faces_mean=round(float(np.mean(nf)), 2), faces_multi=round(float(np.mean(np.array(nf) >= 2)), 2), face_big=round(float(np.median(big)), 3),
                face_rate=round(float(np.mean(np.array(nf) >= 1)), 2), lilian_face=round(lil_rate, 2), motion=round(float(np.median(mot)) if mot else 0.0, 4),
                motion_p90=round(float(np.percentile(mot, 90)) if mot else 0.0, 4), captions=round(float(np.mean(cap)), 2),
                cuts_per_min=round(cuts / max(1e-6, n / fps / 60), 1), end_white=end_white,
                tv_band=bool(edges_lo > 0.06 and tstd_lo < 0.6 * tstd_hi and info["w"] > info["h"]),
                band_edges=round(edges_lo, 3), band_still=round(tstd_lo / max(1e-6, tstd_hi), 2))


# ------------------------------------------------------------------ decidir
def decide(info, A, V):
    why = []
    vert = info["h"] > info["w"] * 1.1; horiz = info["w"] > info["h"] * 1.1
    # la tarjeta final blanca de la casa es la marca más segura (49 de 51 editados la tienen; ningún bruto termina en blanco)
    if V.get("end_white") or V.get("captions", 0) >= 0.35:
        why.append(("tarjeta final blanca" if V.get("end_white") else "") + (" · " if V.get("end_white") and V.get("captions", 0) >= 0.35 else "")
                   + (f"subtítulos en {V.get('captions', 0):.0%} de los cuadros" if V.get("captions", 0) >= 0.35 else ""))
        return "editado", why
    if info["dur"] < 20:
        why.append(f"dura {info['dur']:.0f} s"); return "clip", why
    if horiz and (V.get("tv_band") or V.get("band_edges", 0) >= 0.2):
        why.append(f"franja de abajo con mucho texto (zócalo de canal: densidad {V.get('band_edges', 0):.2f}; en brutos ≤ 0.15)"); return "tv", why
    sr, ls = A.get("speech_ratio", 0), A.get("lilian_share", 0)
    why.append(f"habla {sr:.0%} del tiempo; de eso, Lilian {ls:.0%}; otras voces: {A.get('other_voices', 0)}")
    if not horiz and A.get("other_voices", 0) >= 2 and ls < 0.6 and V.get("face_big", 0) < 0.12:
        why.append("vertical, varias voces que conversan y ella de cuerpo entero: recorrida / visita"); return "evento", why
    if sr < 0.25 or ls < 0.3:
        if horiz and V.get("faces_multi", 0) >= 0.4 and A.get("other_voices", 0) >= 1 and ls >= 0.15 and sr >= 0.4:
            why.append("varias caras a la vez y varias voces"); return "reunion", why
        why.append("ella casi no habla" if ls < 0.3 else "casi no hay habla"); return "evento", why
    if horiz and V.get("faces_multi", 0) >= 0.5 and A.get("other_voices", 0) >= 1 and ls <= 0.8:
        why.append(f"varias caras en {V['faces_multi']:.0%} de los cuadros + otras voces"); return "reunion", why
    if V.get("face_big", 0) >= 0.16 and V.get("faces_mean", 0) <= 1.6 and A.get("other_share", 0) < 0.1 and V.get("motion", 1) < 0.01:
        why.append(f"una cara grande ({V['face_big']:.0%} del alto), cámara quieta, sin otras voces"); return "mensaje", why
    if V.get("face_big", 0) < 0.12 and (A.get("music") or A.get("other_share", 0) < 0.1):
        why.append(f"cara chica ({V.get('face_big', 0):.0%} del alto: de pie, de lejos)" + (" y fondo de público/música" if A.get("music") else ""))
        return "discurso", why
    return "conferencia", why


def avisos(info, A, V):
    out = []
    if info["sar"] != "1:1": out.append(f"píxeles no cuadrados ({info['sar']}): imagen real {info['w']}×{info['h']} (ingest lo endereza)")
    if min(info["w"], info["h"]) < 720: out.append(f"resolución real baja ({info['w']}×{info['h']}): se verá blando; pedir el original de la cámara")
    if info["hdr"]: out.append("HDR (HLG/PQ): se convierte a SDR con hable npl=300")
    if A.get("music"): out.append("hay música/aplausos de fondo bajo la voz")
    if V.get("motion_p90", 0) > 0.03: out.append("cámara en mano que se mueve mucho: estabilizar / usar tomas cortas")
    return out


def entender(path, use_cache=True):
    key = hashlib.md5((os.path.abspath(path) + str(os.path.getsize(path))).encode()).hexdigest()[:16]
    cp = os.path.join(CACHE, key + ".json")
    if use_cache and os.path.exists(cp):                         # se guardan las MEDIDAS; la decisión se recalcula (las reglas mejoran)
        r = json.load(open(cp, encoding="utf-8"))
        r["tipo"], r["por_que"] = decide(r["info"], r["audio"], r["video"]); r["avisos"] = avisos(r["info"], r["audio"], r["video"])
        f = fecha(path, r["info"]); r["fecha"] = f.isoformat() if f else None; r["path"] = path
        return r
    info = probe(path)
    A = audio_features(path, info["dur"]) if info["audio"] else {}
    V = video_features(path, info)
    tipo, why = decide(info, A, V)
    f = fecha(path, info)
    r = dict(file=os.path.basename(path), path=path, info=info, audio=A, video=V, tipo=tipo, por_que=why, avisos=avisos(info, A, V),
             fecha=f.isoformat() if f else None)
    json.dump(r, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return r


def ficha(r):
    name = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(r["file"])[0].lower()).strip("_")[:28]
    t, cmd = TIPOS[r["tipo"]]
    s = [f"■ {r['file']}  ({r['info']['dur']:.0f} s · {r['info']['w']}×{r['info']['h']})", f"   → {t}", f"     porque: {'; '.join(r['por_que'])}"]
    for a in r["avisos"]: s.append(f"     ! {a}")
    s.append("     cómo: " + cmd.format(v=r["path"], n=name))
    return "\n".join(s)


SOLOS = ("tv", "reunion", "editado")                              # formatos que se editan solos: no se juntan con las tomas de un evento


def grupos(rs, horas=4):
    """tomas del mismo día y a menos de `horas` una de otra = mismo evento (la señal de TV, una reunión o un video ya editado
    van siempre aparte aunque se hayan grabado el mismo día)"""
    solos = [[r] for r in rs if r.get("fecha") and r["tipo"] in SOLOS]
    con = sorted([r for r in rs if r.get("fecha") and r["tipo"] not in SOLOS], key=lambda r: r["fecha"])
    out, cur = [], []
    for r in con:
        if cur and (datetime.datetime.fromisoformat(r["fecha"]) - datetime.datetime.fromisoformat(cur[-1]["fecha"])).total_seconds() > horas * 3600:
            out.append(cur); cur = []
        cur.append(r)
    if cur: out.append(cur)
    return sorted(out + solos, key=lambda g: g[0]["fecha"])


def evaluar():
    vp = os.path.join(STUDIO, "analysis", "entender_verdad.json")
    V = json.load(open(vp, encoding="utf-8"))
    ok, bad = 0, []
    for path, want in V.items():
        if not os.path.exists(path): continue
        r = entender(path)
        good = r["tipo"] in (want if isinstance(want, list) else [want])
        ok += good
        if not good: bad.append((os.path.basename(path)[:50], want, r["tipo"], r["por_que"]))
        print(f"{'✓' if good else '✗'} {os.path.basename(path)[:55]:55s} esperado {str(want):24s} → {r['tipo']}")
    n = sum(1 for p in V if os.path.exists(p))
    print(f"\n{ok}/{n} bien clasificados")
    for b in bad: print("  ✗", b)
    return ok, n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    arg = sys.argv[1]
    if arg == "--evaluar": evaluar(); sys.exit(0)
    paths = [os.path.join(arg, f) for f in sorted(os.listdir(arg)) if f.lower().endswith(VID)] if os.path.isdir(arg) else [arg]
    rs = []
    for p in paths:
        r = entender(p); rs.append(r); print(ficha(r), flush=True)
    if len(rs) > 1:
        print("\n== grupos por evento (misma fecha, tomas cercanas)")
        for g in grupos(rs):
            tipos = sorted({r["tipo"] for r in g})
            print(f"  {g[0]['fecha'][:16]} · {len(g)} tomas · {', '.join(tipos)}: " + ", ".join(r["file"] for r in g))
        tag = re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(os.path.normpath(arg)))[:30]
        json.dump(dict(videos=rs, grupos=[[r["file"] for r in g] for g in grupos(rs)]),
                  open(os.path.join(STUDIO, "analysis", f"entender_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
