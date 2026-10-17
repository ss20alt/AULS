# Estudio de edición — ENTENDER un video antes de editarlo: qué es y cómo se edita (sin que nadie lo diga).
# Mide formato (orientación, resolución real, píxeles no cuadrados, HDR), cuánto se habla y cuánto de eso es LILIAN (huella de
# voz), cuántas otras voces, música/aplausos de fondo, caras (cuántas, tamaño, si una es Lilian: huella de cara), movimiento de
# cámara, si ya viene editado (subtítulos, cortes, tarjeta final) y si tiene zócalo de TV. Con eso decide el TIPO y recomienda
# formato + estilo + comando. En una carpeta, además agrupa las tomas sueltas por evento (hora de la toma, tope por evento y GPS).
# Un archivo roto o a medio sincronizar no frena nada: sale como tipo "roto" con el motivo.
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
    # archivo que no se puede leer: grabación cortada (batería: la cámara no cerró el archivo), copia o Drive a medio sincronizar,
    # o sin imagen. NO frena la tanda: queda en el informe con el motivo y los demás videos se editan igual
    "roto": ("NO SE PUDO LEER (archivo roto, incompleto o todavía sincronizando)",
             'esperar que termine de copiarse / sincronizar (Drive) o copiarlo de nuevo desde la cámara; después: python auto.py "{v}"'),
}


# ------------------------------------------------------------------ falla del ESTUDIO (de esta PC), no del video
class FallaEstudio(RuntimeError):
    """el problema es de ESTA PC, no del video: falta ffmpeg/ffprobe, un módulo de Python, un modelo o una huella; ffmpeg sin zscale
    (los HDR del iPhone salen sin cuadros); placa de video sin memoria. NO se marca 'roto': el aviso diría 'copialo de nuevo desde la
    cámara' (falso) y en una PC con la instalación incompleta saldrían TODOS rotos sin editar nada -> error a la vista con lo que falta"""


_ESTUDIO = {}                                                    # herramientas ya revisadas en esta corrida (se revisan una sola vez)


def _herramientas():
    """ffprobe y ffmpeg que ARRANCAN (no alcanza con que estén en el PATH: un ffmpeg sin sus DLL está pero no corre) y si ffmpeg trae
    zscale (sin él, los HDR del iPhone no dan ni un cuadro y parecerían archivos dañados)"""
    if not _ESTUDIO:
        def corre(cmd):
            try: p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError): return None
            return p.stdout if p.returncode == 0 else None
        filtros = corre(["ffmpeg", "-hide_banner", "-filters"])
        _ESTUDIO.update(ffprobe=corre(["ffprobe", "-version"]) is not None, ffmpeg=filtros is not None,
                        zscale=bool(filtros and re.search(r"\szscale\s", filtros)))
    return _ESTUDIO


def revisar_estudio(audio=True, hdr=False):
    """antes de MEDIR un video: ¿está en esta PC todo lo que hace falta? Si falta algo -> FallaEstudio con la lista en palabras (no
    'roto'). Barato: archivos y módulos se miran sin cargarlos; ffmpeg/ffprobe una vez por corrida. auto.py puede llamarla una vez al
    empezar la tanda (revisar_estudio(hdr=True)) y cortar con el motivo antes de leer ningún video"""
    h, falta = _herramientas(), []
    if not h["ffprobe"] or not h["ffmpeg"]: falta.append("ffmpeg/ffprobe que funcione (instalar ffmpeg y agregarlo al PATH)")
    elif hdr and not h["zscale"]: falta.append("el filtro zscale de ffmpeg (sin él los videos HDR del iPhone no se pueden leer: instalar el ffmpeg completo)")
    req = [(MODELS, "yunet.onnx"), (MODELS, "sface.onnx"), (CLIENTS, "lilian_faceprint.npy")]           # caras (video_features)
    if audio: req += [(CLIENTS, "lilian_voiceprint.npy"), (CLIENTS, "lilian_voiceprint.json"),        # voz (audio_features + speakers)
                      (MODELS, os.path.join("wavlm-base-plus-sv", "config.json"))]
    falta += [os.path.relpath(os.path.join(d, f), STUDIO).replace(os.sep, "/") for d, f in req if not os.path.isfile(os.path.join(d, f))]
    if audio:
        import importlib.util as IU
        falta += [f"el módulo de Python {m}" for m in ("faster_whisper", "torch", "transformers", "scipy") if IU.find_spec(m) is None]
    if falta:
        raise FallaEstudio("el estudio no está completo en esta PC (no es el video): falta " + "; ".join(falta)
                           + ". Revisá la instalación con: python doctor.py --rapido")


# ------------------------------------------------------------------ formato
def _lugar(tags):
    """GPS de la toma, si el teléfono lo guardó: iPhone com.apple.quicktime.location.ISO6709 '-25.2839-057.5041+131.900/',
    Android 'location' '-25.2815-057.6222/' -> [lat, lon] (grados decimales). La cámara DJI no trae: None"""
    t = {k.lower(): v for k, v in (tags or {}).items()}
    for k in ("com.apple.quicktime.location.iso6709", "location", "location-eng"):
        m = re.match(r"\s*([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)", str(t.get(k) or ""))
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if abs(lat) <= 90 and abs(lon) <= 180 and (lat, lon) != (0.0, 0.0): return [round(lat, 5), round(lon, 5)]   # ±DDMM.M (otro formato ISO) o 0,0 = sin dato
    return None


def _tags_baratos(p):
    """solo los metadatos (sin streams ni cuadros: milisegundos) -> GPS + hora local de la grabación (iPhone guarda la hora con su
    zona: '2026-01-10T17:48:52-0300'). Para completar la caché vieja (de antes del GPS) sin volver a medir el video.
    None = ffprobe no corrió (no está / se colgó): entender NO guarda (si no, la caché quedaría 'completa' sin GPS para siempre)"""
    try:
        j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_entries", "format_tags:stream_tags", p],
                                      capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout or "{}")
    except (OSError, subprocess.SubprocessError): return None
    except ValueError: j = {}
    tags = dict((j.get("format") or {}).get("tags") or {})
    for s in j.get("streams") or []: tags = {**(s.get("tags") or {}), **tags}            # los del formato mandan
    return dict(gps=_lugar(tags), creada_local=tags.get("com.apple.quicktime.creationdate"))


def _roto(motivo):
    """ficha mínima de un archivo que no se puede leer: no frena la tanda (entender lo informa como tipo 'roto')"""
    return dict(dur=0.0, w=0, h=0, sar="1:1", hdr=False, audio=False, created=None, gps=None, creada_local=None, roto=motivo)


def probe(p):
    """formato real. Un archivo roto o a medio copiar NO es un error: ffprobe da '{}' (grabación cortada por batería: la cámara no
    escribió el índice final 'moov'; Drive que todavía sincroniza) o no hay imagen -> vuelve con roto='motivo en palabras'.
    Si el que no anda es ffprobe (no está instalado / no arranca) -> FallaEstudio: es la PC, no el archivo"""
    try:
        pr = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", p],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, stdin=subprocess.DEVNULL)
        j, err = json.loads(pr.stdout or "{}"), (pr.stderr or "").lower()
    except OSError as e:                                         # no se pudo LANZAR ffprobe (el archivo lo abre ffprobe, no Python)
        raise FallaEstudio(f"no se pudo ejecutar ffprobe ({e}): instalar ffmpeg y agregarlo al PATH (no es el video). "
                           f"Revisá la instalación con: python doctor.py --rapido") from e
    except (ValueError, subprocess.SubprocessError) as e: j, err = {}, str(e).lower()   # se colgó > 2 min (Drive bajándolo) o salida rara
    try: size = os.path.getsize(p)
    except OSError: return _roto("no se encuentra o no se puede abrir el archivo")
    S, F = j.get("streams") or [], j.get("format") or {}
    v = next((s for s in S if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    if size == 0: return _roto("archivo vacío (0 bytes): todavía se está copiando o sincronizando")
    if not S or not F:
        if "moov atom not found" in err:
            return _roto("el archivo no terminó de grabarse o de copiarse (le falta el índice final: grabación cortada por batería "
                         "o Drive todavía sincronizando)")
        return _roto("no es un video válido o está dañado" + (f" (ffprobe: {err.strip().splitlines()[-1][-90:]})" if err.strip() else ""))
    if v is None: return _roto("no tiene imagen" + (" (solo audio)" if any(s.get("codec_type") == "audio" for s in S) else ""))
    dur = float(F.get("duration") or v.get("duration") or 0)
    if dur <= 0: return _roto("sin duración: el archivo quedó incompleto")
    # copia cortada con el índice al principio (mp4 'faststart'): ffprobe la lee entera, pero faltan los datos del final. Cada pista
    # declara su tasa y su duración (del índice) -> bytes que debería pesar; en los 17 brutos reales pesa 0.92–1.0 de eso
    esper = sum(int(s.get("bit_rate") or 0) * float(s.get("duration") or dur) / 8 for s in S)
    if esper > 0 and size < 0.85 * esper:
        mb = lambda x: f"{x / 1e6:.1f}" if x < 1e7 else f"{x / 1e6:.0f}"
        return _roto(f"el archivo está cortado: tiene el {100 * size / esper:.0f} % de lo que debería pesar ({mb(size)} de {mb(esper)} MB: "
                     f"copia o descarga incompleta)")
    rot = next((int(sd.get("rotation", 0)) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    if w <= 0 or h <= 0: return _roto("la pista de imagen no tiene tamaño (archivo dañado)")
    try: sn, sd = (int(x) for x in (v.get("sample_aspect_ratio") or "1:1").split(":"))
    except ValueError: sn, sd = 1, 1
    if sn > 0 and sd > 0 and (sn, sd) != (1, 1): w = int(round(w * sn / sd / 2)) * 2
    if abs(rot) % 180 == 90: w, h = h, w
    tags = {**F.get("tags", {}), **v.get("tags", {})}
    return dict(dur=dur, w=w, h=h, sar=f"{sn}:{sd}", hdr=v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
                audio=any(s.get("codec_type") == "audio" for s in S), created=tags.get("creation_time"),
                gps=_lugar({**v.get("tags", {}), **F.get("tags", {})}), creada_local=tags.get("com.apple.quicktime.creationdate"))


def fecha_y_fuente(path, info):
    """fecha de la toma y DE DÓNDE salió (el agrupado por evento confía distinto en cada una):
      'nombre'    DJI_20251205091856, VID_20260822_120059, 20261014_102345 (la cámara la escribe al grabar: la más segura)
      'whatsapp'  "WhatsApp Video 2026-10-14 at 10.23.45.mp4" (hora del ENVÍO por WhatsApp, no de la grabación: aproximada)
      'metadatos' hora con zona del iPhone (com.apple.quicktime.creationdate) o creation_time (UTC -> hora de la PC, Paraguay)
      'dia'       solo el día: "VID-20261014-WA0012.mp4" (WhatsApp Android), "2026-10-14-LS1.mp4" -> 12:00 de relleno, hora DESCONOCIDA"""
    b = os.path.basename(path)
    m = re.search(r"(20\d{2})(\d{2})(\d{2})[_ ]?(\d{2})(\d{2})(\d{2})", b)
    if m:
        try: return datetime.datetime(*map(int, m.groups())), "nombre"
        except ValueError: pass                                  # número largo que no es fecha (id de TikTok)
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})\s+(?:at|a las|às)\s+(\d{1,2})[.:](\d{2})[.:](\d{2})(?:[\s ]*([AaPp])\.?\s*[Mm](?![A-Za-z]))?", b)
    if m:                                                        # WhatsApp en la PC/Mac (también "3.45.12 PM" con reloj de 12 h)
        y, mo, d, hh, mi, ss = map(int, m.groups()[:6]); ap = (m.group(7) or "").lower()
        if ap: hh = hh % 12 + (12 if ap == "p" else 0)
        try: return datetime.datetime(y, mo, d, hh, mi, ss), "whatsapp"
        except ValueError: pass
    for k in ("creada_local", "created"):
        if not info.get(k): continue
        try:
            d = datetime.datetime.fromisoformat(str(info[k]).replace("Z", "+00:00"))
            if k == "creada_local": d = d.replace(tzinfo=None)  # iPhone: hora del reloj donde se grabó (con su zona) -> tal cual
            else: d = (d.astimezone() if d.tzinfo else d).replace(tzinfo=None)   # UTC -> hora local de la PC (como los nombres DJI)
            if d.year >= 2000: return d, "metadatos"           # 1970 / 1904 = metadato vacío (WhatsApp y editores lo borran)
        except ValueError: pass
    m = (re.search(r"(?:VID|IMG)-(20\d{2})(\d{2})(\d{2})-WA\d+", b)            # WhatsApp en Android: el día en que llegó
         or re.search(r"(?<!\d)(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?!\d)", b))  # "2026-10-14-LS1.mp4", "video_20261014.mp4"
    if m:
        try: return datetime.datetime(*map(int, m.groups()), 12, 0, 0), "dia"
        except ValueError: pass
    return None, None


def fecha(path, info):
    """fecha de la toma (del nombre o de los metadatos; ver fecha_y_fuente)"""
    return fecha_y_fuente(path, info)[0]


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
    if info.get("roto"): return "roto", [info["roto"]]           # no se pudo leer: no se adivina nada
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


def _guardar(cp, r):
    """caché escrita de una vez (archivo temporal + reemplazo): otra corrida que la lea nunca ve un JSON a medias"""
    tmp = cp + f".{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh: json.dump(r, fh, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, cp)
    except OSError:                                              # Windows: otra corrida la tiene abierta -> queda la anterior (es solo caché)
        try: os.remove(tmp)
        except OSError: pass


def entender(path, use_cache=True):
    try: size = os.path.getsize(path)
    except OSError: size = -1                                    # no existe / no se puede abrir: probe lo dice como 'roto'
    key = hashlib.md5((os.path.abspath(path) + str(size)).encode()).hexdigest()[:16]
    cp = os.path.join(CACHE, key + ".json")
    if use_cache and size >= 0 and os.path.exists(cp):           # se guardan las MEDIDAS; la decisión se recalcula (las reglas mejoran)
        try:
            with open(cp, encoding="utf-8") as fh: r = json.load(fh)
        except ValueError: r = None                             # caché a medio escribir (corrida cortada): se mide de nuevo
        if r is not None:
            if "gps" not in r["info"]:                           # caché de antes del GPS: solo los metadatos (ffprobe barato), una vez
                t = _tags_baratos(path)
                if t is not None: r["info"].update(t); _guardar(cp, r)
                else: r["info"].update(gps=None, creada_local=None)   # ffprobe no corrió: sin dato por ahora, la caché queda como estaba
            r["tipo"], r["por_que"] = decide(r["info"], r["audio"], r["video"]); r["avisos"] = avisos(r["info"], r["audio"], r["video"])
            f, ff = fecha_y_fuente(path, r["info"]); r["fecha"] = f.isoformat() if f else None; r["fecha_fuente"] = ff; r["path"] = path
            return r
    info = probe(path)                                           # (sin ffprobe en la PC: FallaEstudio, no 'roto')
    A, V, dudoso = {}, {}, False
    if not info.get("roto"):
        # lo que falta en la PC se dice ANTES de medir: si no, un módulo, un modelo o un ffmpeg sin zscale hacían salir 'roto' a
        # TODOS los videos sanos con el aviso de copiarlos de nuevo (y no se editaba nada)
        revisar_estudio(audio=info["audio"], hdr=info["hdr"])
        try:
            A = audio_features(path, info["dur"]) if info["audio"] else {}
            V = video_features(path, info)
            if not V: info["roto"] = "no se pudo leer ningún cuadro de imagen (archivo dañado o incompleto)"
        except FallaEstudio: raise
        except (ImportError, OSError, MemoryError, RuntimeError, cv2.error) as e:
            # de la PC, no del archivo (el video lo lee ffmpeg, no Python): módulo o modelo que no carga (ImportError, OSError de
            # transformers, cv2.error de YuNet/SFace), placa sin memoria (RuntimeError de torch), ffmpeg que no arranca
            if isinstance(e, OSError) and e.filename and os.path.abspath(str(e.filename)) == os.path.abspath(path):
                info["roto"] = f"no se pudo abrir el archivo ({e.strerror or e})"
            else:
                mem = "memory" in str(e).lower() or isinstance(e, MemoryError)
                raise FallaEstudio(f"falla del estudio en esta PC, no del video {os.path.basename(path)} ({type(e).__name__}: {str(e)[:160]})"
                                   + (". Falta memoria: ¿hay otro render usando la placa de video? Esperá que termine y volvé a correr" if mem
                                      else ". Revisá la instalación con: python doctor.py --rapido")) from e
        except Exception as e:                                   # el archivo se lee al principio pero se rompe más adelante: no frena la tanda
            info["roto"] = f"no se pudo analizar ({type(e).__name__}: {str(e)[:120]})"; dudoso = True
    tipo, why = decide(info, A, V)
    f, ff = fecha_y_fuente(path, info)
    r = dict(file=os.path.basename(path), path=path, info=info, audio=A, video=V, tipo=tipo, por_que=why, avisos=avisos(info, A, V),
             fecha=f.isoformat() if f else None, fecha_fuente=ff)
    if info.get("roto"):                                         # sin caché: el archivo puede terminar de copiarse y la próxima vez se lee
        r["avisos"] = [f"no se pudo leer: {info['roto']}. Esperá que termine de copiarse o sincronizar (Drive) o copialo de nuevo "
                       f"desde la cámara; los demás videos se editan igual"
                       + (". Si les pasa a TODOS los videos, es el estudio de esta PC y no los archivos: python doctor.py --rapido" if dudoso else "")]
        return r
    _guardar(cp, r)
    return r


def ficha(r):
    name = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(r["file"])[0].lower()).strip("_")[:28]
    t, cmd = TIPOS[r["tipo"]]
    med = "no se pudo leer" if r["tipo"] == "roto" else f"{r['info']['dur']:.0f} s · {r['info']['w']}×{r['info']['h']}"
    s = [f"■ {r['file']}  ({med})", f"   → {t}", f"     porque: {'; '.join(r['por_que'])}"]
    for a in r["avisos"]: s.append(f"     ! {a}")
    s.append("     cómo: " + cmd.format(v=r["path"], n=name))
    return "\n".join(s)


SOLOS = ("tv", "reunion", "editado", "roto")                      # van siempre aparte: se editan solos (o no se pueden leer)


def _ini(r): return datetime.datetime.fromisoformat(r["fecha"])
def _fin(r): return _ini(r) + datetime.timedelta(seconds=float((r.get("info") or {}).get("dur") or 0))   # termina de grabar
def _gps(r):
    g = (r.get("info") or {}).get("gps")
    return (float(g[0]), float(g[1])) if g else None


def km(a, b):
    """distancia entre dos puntos GPS (lat, lon) en km (haversine)"""
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _huecos(g):
    """minutos sin grabar antes de cada toma (desde que TERMINÓ la anterior: un discurso de 11 min no es un hueco)"""
    out, fin = [], None
    for r in g:
        if fin is not None: out.append((_ini(r) - fin).total_seconds() / 60)
        fin = max(fin, _fin(r)) if fin is not None else _fin(r)
    return out


def _partir(g, tope):
    """un evento no dura más de `tope` horas (de la primera toma a la última): si se pasa, se parte en el hueco MÁS LARGO (de los
    casi iguales, el más cercano al medio: tomas parejas cada 1.5 h no quedan una por una) y se vuelve a mirar cada mitad.
    Si en todo el grupo no hay ni 1 min sin grabar, es UNA grabación continua (la DJI parte en archivos por tamaño y el nombre va al
    segundo: huecos de ±1 s, o se solapan; o una toma corta DENTRO de una larga) -> un solo evento aunque pase el tope: no hay dónde
    partir sin cortar la grabación (y con huecos ≤ 0, '0.8 × el mayor' quedaba por ENCIMA del mayor: no había candidato y se caía)"""
    if len(g) < 2 or (_ini(g[-1]) - _ini(g[0])).total_seconds() <= tope * 3600: return [g]
    hs = _huecos(g); m = max(hs)
    if m < 1: return [g]
    i = min((k for k, x in enumerate(hs) if x >= 0.8 * m), key=lambda k: abs(k + 1 - len(g) / 2)) + 1
    return _partir(g[:i], tope) + _partir(g[i:], tope)


def grupos(rs, horas=2, tope=4, lejos_km=1.0):
    """tomas del MISMO EVENTO (mismo acto, mismo lugar) juntas, como lo haría un editor:
      · hueco: más de `horas` sin grabar (desde el final de la toma anterior) = otra actividad
      · tope: un evento no dura más de `tope` h en total — un día con actividades a las 8, 11, 14, 17 y 20 h NO es un evento
        (antes solo miraba el hueco con la anterior < 4 h y todo el día quedaba junto). Los brutos reales: huecos ≤ 72 min.
        Una grabación continua (sin ni 1 min de corte) no se parte aunque pase el tope: dudas(g) lo marca
      · lugar: si la toma trae GPS (iPhone/Android) y está a más de `lejos_km` del último punto conocido del evento = otro lugar
        (la DJI no trae GPS: se junta por la hora; en una recorrida se compara con el ÚLTIMO punto, no con el primero)
      · tomas sin hora (WhatsApp Android "VID-20261014-WA0012": solo el día) no se mezclan con las de hora conocida: se juntan
        entre ellas por día (y por lugar). dudas(g) dice qué grupos conviene confirmar.
    La señal de TV, una reunión, un video ya editado o un archivo roto van siempre aparte aunque sean del mismo día."""
    con = [r for r in rs if r.get("fecha")]
    solos = [[r] for r in con if r["tipo"] in SOLOS]
    tomas = sorted([r for r in con if r["tipo"] not in SOLOS], key=lambda r: (r["fecha"], r.get("file", "")))
    abiertos = []
    for r in [x for x in tomas if x.get("fecha_fuente") != "dia"]:
        p, cand = _gps(r), []
        for g in abiertos:
            hueco = (_ini(r) - max(_fin(x) for x in g)).total_seconds()
            if hueco > horas * 3600: continue
            q = next((_gps(x) for x in reversed(g) if _gps(x)), None)        # último lugar conocido del evento
            if p and q and km(p, q) > lejos_km: continue
            cand.append((hueco, len(cand), g))
        if cand: min(cand)[2].append(r)                                     # dos actos a la vez (dos equipos): el más cercano en hora
        else: abiertos.append([r])
    out = [p for g in abiertos for p in _partir(g, tope)]
    dias = {}
    for r in [x for x in tomas if x.get("fecha_fuente") == "dia"]:          # sin hora: por día, y separadas por lugar si traen GPS
        p, gs = _gps(r), dias.setdefault(r["fecha"][:10], [])
        g = next((g for g in gs if not p or all(km(p, q) <= lejos_km for q in map(_gps, g) if q)), None)
        if g is None: gs.append([r])
        else: g.append(r)
    out += [g for gs in dias.values() for g in gs]
    return sorted(out + solos, key=lambda g: (g[0]["fecha"], g[0].get("file", "")))


def dudas(g, tope=4):
    """por qué conviene CONFIRMAR este grupo antes de editarlo (auto.py --solo-plan lo muestra); [] = grupo seguro"""
    out = []
    sin = [r for r in g if r.get("fecha_fuente") == "dia"]
    if sin: out.append(f"{len(sin)} toma(s) sin hora (solo el día, del nombre de WhatsApp o de la copia): se juntaron por el día")
    if any(r.get("fecha_fuente") == "whatsapp" for r in g): out.append("hora tomada del nombre de WhatsApp (la del envío, no la de la grabación)")
    if len(g) > 1 and not sin:
        for k, h in enumerate(_huecos(g)):
            if h > 60: out.append(f"pasan {h:.0f} min sin grabar antes de {g[k + 1].get('file', '?')} ({_ini(g[k + 1]):%H:%M}): ¿es el mismo acto?")
        dur_h = (_ini(g[-1]) - _ini(g[0])).total_seconds() / 3600
        if dur_h > tope: out.append(f"dura {dur_h:.1f} h (grabación continua, más que el tope de {tope} h de un evento): ¿es un solo acto?")
    P = [x for x in map(_gps, g) if x]
    d = max((km(a, b) for i, a in enumerate(P) for b in P[i + 1:]), default=0.0)
    if d > 0.3: out.append(f"tomas a {d:.1f} km entre sí (¿recorrida o dos lugares?)")
    return out


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


def _cli():
    arg = sys.argv[1]
    if arg == "--evaluar": evaluar(); return
    paths = [os.path.join(arg, f) for f in sorted(os.listdir(arg)) if f.lower().endswith(VID)] if os.path.isdir(arg) else [arg]
    rs = []
    for p in paths:
        r = entender(p); rs.append(r); print(ficha(r), flush=True)
    if len(rs) > 1:
        print("\n== grupos por evento (tomas cercanas en la hora y en el lugar)")
        gs = grupos(rs)
        for g in gs:
            tipos = sorted({r["tipo"] for r in g})
            print(f"  {g[0]['fecha'][:16]} · {len(g)} tomas · {', '.join(tipos)}: " + ", ".join(r["file"] for r in g))
            for d in dudas(g): print(f"      ? {d}")
        for r in rs:
            if not r.get("fecha"): print(f"  (sin fecha, va sola) {r['file']}")
        tag = re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(os.path.normpath(arg)))[:30]
        json.dump(dict(videos=rs, grupos=[[r["file"] for r in g] for g in gs], dudas=[dudas(g) for g in gs]),
                  open(os.path.join(STUDIO, "analysis", f"entender_{tag}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try: _cli()
    except FallaEstudio as e: print(f"\n✗ {e}", flush=True); sys.exit(2)    # es la PC, no los videos: se corta con lo que falta
