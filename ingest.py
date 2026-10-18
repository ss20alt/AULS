# Estudio de edición — PREPARACIÓN AUTOMÁTICA de un video en bruto (punto 1).
# Un solo comando deja la fuente lista para editar:
#   python ingest.py <video> --name <fuente> [--client lilian] [--steps all|video,audio,asr,face]
# Salida en studio/sources/<fuente>/:
#   work.mp4 (1080x1920, 30 fps, SDR, H.264) · audio48.wav · voice.wav (voz limpia) · transcript.json (palabra por palabra)
#   face.npy (cara cuadro a cuadro) · meta.json (formato original) · source.json (registro que usa el estudio)
import os, sys, json, subprocess, time, wave, argparse
import numpy as np, cv2
from scipy.ndimage import gaussian_filter1d, median_filter

STUDIO = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(STUDIO, "sources")
CLIENTS = os.path.join(STUDIO, "clients")
W, H, FPS, SR = 1080, 1920, 30, 48000
log = lambda *a: print("[ingest]", *a, flush=True)


# ------------------------------------------------------------------ 1. formato
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path], capture_output=True, text=True, encoding="utf-8")
    j = json.loads(r.stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd: rot = int(sd["rotation"])
    rot = int(v.get("tags", {}).get("rotate", rot))
    w, h = int(v["width"]), int(v["height"])
    # píxeles no cuadrados: las exportaciones del DJI guardan un 9:16 "aplastado" en 1728×1080 / 1080×1080 / 1280×720
    # (SAR 45:128, 9:16, 81:256) -> la imagen real es 608×1080 / 405×720 VERTICAL; sin esto se trataba como horizontal
    try: sn, sd = (int(x) for x in (v.get("sample_aspect_ratio") or "1:1").split(":"))
    except ValueError: sn, sd = 1, 1
    if sn <= 0 or sd <= 0: sn, sd = 1, 1
    if (sn, sd) != (1, 1): w = int(round(w * sn / sd / 2)) * 2
    if abs(rot) % 180 == 90: w, h = h, w                       # ffmpeg aplica la rotación al decodificar
    num, den = (int(x) for x in v.get("r_frame_rate", "30/1").split("/"))
    trc = v.get("color_transfer", "")
    return dict(path=path, width=w, height=h, rotation=rot, sar=f"{sn}:{sd}", fps=num / max(1, den), codec=v["codec_name"], pix_fmt=v.get("pix_fmt"),
                transfer=trc, primaries=v.get("color_primaries", ""), hdr=trc in ("arib-std-b67", "smpte2084"),
                duration=float(j["format"]["duration"]), audio=a is not None, audio_codec=a["codec_name"] if a else None,
                audio_channels=int(a["channels"]) if a else 0)


# ------------------------------------------------------------------ 2. video de trabajo
def video_filter(info, crop_x=None):
    f = []
    if info["hdr"]:                                            # HLG / PQ -> SDR BT.709 (mapeo de tonos). npl=300: exposición y contraste como
                                                               # se ve el original (con 110 quedaba demasiado claro y lavado; elegido por el usuario 2026-10-14)
        f.append("zscale=t=linear:npl=300,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
    if info.get("sar", "1:1") != "1:1":                        # píxeles no cuadrados -> cuadrados ANTES de recortar (DJI exportado)
        f.append("scale=trunc(iw*sar/2)*2:ih:flags=lanczos,setsar=1")
    w, h = info["width"], info["height"]
    if h >= w:                                                 # vertical: escalar a 1080x1920 (recorte mínimo si no es 9:16)
        f.append(f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}")
    else:                                                      # horizontal: llevar a 1920 de alto y recortar 9:16 alrededor de la cara
        sw = int(round(w * H / h / 2) * 2)
        cx = crop_x if crop_x is not None else sw / 2
        x0 = int(min(max(cx - W / 2, 0), sw - W))
        f.append(f"scale={sw}:{H}:flags=lanczos,crop={W}:{H}:{x0}:0")
    f.append(f"fps={FPS}")
    return ",".join(f)


def make_work(info, out, crop_x=None):
    vf = video_filter(info, crop_x)
    import plataforma as PL
    cmd = ["ffmpeg", "-v", "error", "-y", *PL.HWDEC, "-i", info["path"], "-map", "0:v:0", "-vf", vf,
           *PL.venc(16, "40M", "80M", 30, 0), "-pix_fmt", "yuv420p",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", "-an", out]
    r = PL.run_ffmpeg(cmd)
    if r.returncode: raise RuntimeError(r.stderr[-1200:])


def landscape_face_x(info):
    """para videos horizontales: posición horizontal mediana de la cara (escala de salida) para el recorte 9:16"""
    sw = int(round(info["width"] * H / info["height"] / 2) * 2)
    aw, ah = 480, int(480 * info["height"] / info["width"])
    vf = (video_filter(dict(info, width=info["width"], height=info["height"]), crop_x=None).split(",scale=")[0] + "," if info["hdr"] else "") + f"scale={aw}:{ah},fps=2"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", info["path"], "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    xs = []
    while True:
        b = p.stdout.read(aw * ah)
        if len(b) < aw * ah: break
        g = np.frombuffer(b, np.uint8).reshape(ah, aw)
        fc = casc.detectMultiScale(g, 1.1, 5, minSize=(16, 16))
        if len(fc): x, y, w, h = max(fc, key=lambda f: f[2] * f[3]); xs.append((x + w / 2) / aw)
    return float(np.median(xs)) * sw if xs else None


# ------------------------------------------------------------------ 2b. formato PANEL (horizontal de baja resolución, p. ej. Senado TV 854×480)
# Recortar 9:16 de un horizontal chico obliga a agrandar 4×. En el formato panel, el video de trabajo ya trae la composición
# vertical: un recorte horizontal de la persona (que sigue su cara con suavidad y evita los sobreimpresos de la TV) en una franja
# fija, y alrededor la misma imagen desenfocada y oscurecida. El estilo 'datos' dibuja encima títulos, datos y subtítulos.
PANEL = (0, 400, 1080, 840)                                     # x, y, ancho, alto del recuadro en el video de trabajo


def square_px(info):
    """filtro que lleva los píxeles a cuadrados (DJI exportado) antes de leer cuadros con el tamaño de meta.json"""
    return "scale=trunc(iw*sar/2)*2:ih,setsar=1," if info.get("sar", "1:1") != "1:1" else ""


def face_track_source(path, w, h, fps=5, y_max=None, pre=""):
    """posición de la cara en el video original (para el recorte del panel), a `fps` muestras por segundo"""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", f"{pre}fps={fps},format=gray", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    obs, i = [], 0
    while True:
        b = p.stdout.read(w * h)
        if len(b) < w * h: break
        g = np.frombuffer(b, np.uint8).reshape(h, w)
        f = casc.detectMultiScale(g[:y_max] if y_max else g, 1.1, 5, minSize=(max(24, h // 10),) * 2)
        if len(f): x, y, fw, fh = max(f, key=lambda r: r[2] * r[3]); obs.append((i / fps, x + fw / 2, y + fh / 2, fw))
        i += 1
    return np.array(obs)


def make_work_panel(info, out, d, crop_h=None, x_limits=None, y0=None):
    """video de trabajo en formato panel. Guarda en panel.json el recorte usado (para el registro y las pruebas)"""
    import plataforma as PL
    sw, sh = info["width"], info["height"]
    px, py, pw, ph = PANEL
    crop_h = crop_h or int(sh * 0.75)                           # el 25 % de abajo suele ser el zócalo de la TV
    crop_w = int(round(crop_h * pw / ph))
    y0 = int(sh * 0.025) if y0 is None else y0
    xl = x_limits or (0, sw)
    obs = face_track_source(info["path"], sw, sh, y_max=y0 + crop_h, pre=square_px(info))
    T = info["duration"]; N = int(T * FPS)
    if len(obs):
        cx = np.interp(np.arange(N) / FPS, obs[:, 0], median_filter(obs[:, 1], size=9, mode="nearest"))
        cx = gaussian_filter1d(cx, FPS * 2.0)                   # sigue la cara despacio: encuadre fijo, sin saltos
    else: cx = np.full(N, sw / 2)
    x0 = np.clip(cx - crop_w / 2, xl[0], xl[1] - crop_w).round().astype(int)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", info["path"], "-vf", f"{square_px(info)}fps={FPS}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE, bufsize=sw * sh * 3 * 4)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            *PL.venc(16, "40M", "80M", 30, 0), "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
                            "-colorspace", "bt709", "-color_range", "tv", "-an", out], stdin=subprocess.PIPE)
    k, nb = 0, sw * sh * 3
    while True:
        b = dec.stdout.read(nb)
        if len(b) < nb: break
        fr = np.frombuffer(b, np.uint8).reshape(sh, sw, 3)
        xa = int(x0[min(k, N - 1)])
        c = fr[y0:y0 + crop_h, xa:xa + crop_w]
        c = cv2.resize(c, (pw, ph), interpolation=cv2.INTER_LANCZOS4)
        c = cv2.addWeighted(c, 1.45, cv2.GaussianBlur(c, (0, 0), 1.6), -0.45, 0)                     # nitidez suave tras agrandar
        small = cv2.resize(fr[y0:y0 + crop_h], (96, int(96 * crop_h / sw)), interpolation=cv2.INTER_AREA)   # fondo: la misma imagen, desenfocada
        Wq, Hq = W // 4, H // 4                                 # desenfoque a 1/4 y después agrandado: igual a la vista (dif. ≤ 1 nivel)
        sc = max(Wq / small.shape[1], Hq / small.shape[0])      # y 8× más rápido (65 -> 8 ms por cuadro; Senado de 12 min: 25 -> ~6 min)
        bg = cv2.resize(small, (int(small.shape[1] * sc) + 2, int(small.shape[0] * sc) + 2), interpolation=cv2.INTER_LINEAR)
        oy, ox = (bg.shape[0] - Hq) // 2, (bg.shape[1] - Wq) // 2
        bg = cv2.resize(cv2.GaussianBlur(bg[oy:oy + Hq, ox:ox + Wq], (0, 0), 4.5), (W, H), interpolation=cv2.INTER_LINEAR)
        can = cv2.convertScaleAbs(bg, alpha=0.45)
        can[py:py + ph, px:px + pw] = c
        enc.stdin.write(can.tobytes()); k += 1
    dec.wait(); enc.stdin.close(); enc.wait()
    sin = []                                                    # tramos sin la persona en cuadro (la TV muestra láminas u otra toma)
    if len(obs) > 1:
        g = np.diff(obs[:, 0]); sin = [(round(float(obs[j, 0] + 0.2), 2), round(float(obs[j + 1, 0] - 0.2), 2)) for j in np.where(g > 1.5)[0]]
    json.dump(dict(panel=PANEL, crop=[int(crop_w), int(crop_h)], y0=y0, x_limits=list(xl), frames=k, face_samples=int(len(obs)),
                   x0_range=[int(x0.min()), int(x0.max())], sin_cara=sin), open(os.path.join(d, "panel.json"), "w"), indent=1)
    if enc.returncode: raise RuntimeError("no se pudo codificar el video de trabajo (panel)")
    return k


# ------------------------------------------------------------------ 3. audio y voz
def make_audio(info, d):
    a48, voice = os.path.join(d, "audio48.wav"), os.path.join(d, "voice.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", info["path"], "-map", "0:a:0", "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", a48], check=True)
    # cadena de limpieza de voz (la misma usada en las ediciones aprobadas): sin graves de fondo, ruido reducido, voz presente y nivel estable
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a48, "-af",
                    "highpass=f=85,afftdn=nr=10:nf=-42:tn=1,equalizer=f=220:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1.2:g=2.5,"
                    "acompressor=threshold=-24dB:ratio=3:attack=8:release=150:makeup=3,loudnorm=I=-16:LRA=8:TP=-2",
                    "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", voice], check=True)
    return a48, voice


# ------------------------------------------------------------------ 4. transcripción
def transcribe(voice, out, prompt):
    import scipy.signal as ss, plataforma as PL
    w = wave.open(voice); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    a16 = ss.resample_poly(a, 1, 3).astype(np.float32)
    m = PL.whisper_model("large-v3")
    segs, _ = m.transcribe(a16, language="es", word_timestamps=True, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=200),
                           beam_size=5, condition_on_previous_text=False, initial_prompt=prompt)
    res = [dict(start=s.start, end=s.end, text=s.text, words=[dict(w=x.word, s=x.start, e=x.end, p=x.probability) for x in s.words]) for s in segs]
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    del m
    return res


# ------------------------------------------------------------------ 5. seguimiento de la cara (por fotograma, en el video de trabajo)
def track_face(work, out, step=2, client="lilian"):
    """cara de ELLA cuadro a cuadro en el video de trabajo (1080×1920). YuNet a 540×960 (ve caras chicas: de pie en una mesa
    lejana) + huella de cara del cliente cada ~10 muestras para quedarse con ELLA cuando hay varias personas; entre medio, la
    más cercana a la anterior. Si no hay huella o modelos, el detector clásico (Haar) como antes."""
    import plataforma as PL
    M = os.path.join(STUDIO, "models"); fpp = os.path.join(CLIENTS, f"{client}_faceprint.npy")
    if not os.path.exists(os.path.join(M, "yunet.onnx")): return _track_face_haar(work, out, step)
    aw, ah, S = 540, 960, 2
    det = cv2.FaceDetectorYN.create(os.path.join(M, "yunet.onnx"), "", (aw, ah), 0.55, 0.3, 50)
    rec = cv2.FaceRecognizerSF.create(os.path.join(M, "sface.onnx"), "") if os.path.exists(os.path.join(M, "sface.onnx")) else None
    fp = None
    if rec is not None and os.path.exists(fpp):
        fp = np.load(fpp).astype(np.float32).ravel(); fp /= np.linalg.norm(fp)
    p = subprocess.Popen(["ffmpeg", "-v", "error", *PL.HWDEC, "-i", work, "-vf", f"scale={aw}:{ah}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    obs, i, prev, k_id, sims = [], 0, None, 0, []
    while True:
        buf = p.stdout.read(aw * ah * 3)
        if len(buf) < aw * ah * 3: break
        if i % step == 0:
            fr = np.frombuffer(buf, np.uint8).reshape(ah, aw, 3)
            _, f = det.detect(fr)
            f = [] if f is None else [r for r in f if r[2] >= 12 and r[1] + r[3] / 2 < ah * 0.8]
            pick = None
            if f:
                # ¿cuál es ella? con varias caras (o cada 6 muestras con una) se mira la huella: un AFICHE con la cara de otro candidato
                # detrás de ella (Encarnación: Jhony Valenzuela) hacía saltar el encuadre de una cara a la otra cada pocos segundos
                ver = fp is not None and (prev is None or len(f) > 1 or k_id % 6 == 0)
                simil = {}
                if ver:
                    for j, r in enumerate(sorted(f, key=lambda r: -r[2] * r[3])[:4]):
                        try:
                            e = rec.feature(rec.alignCrop(fr, r)).ravel(); e /= np.linalg.norm(e) + 1e-9; simil[id(r)] = float(e @ fp)
                        except cv2.error: simil[id(r)] = -1.0
                    best = max(f, key=lambda r: simil.get(id(r), -1.0))
                    if simil.get(id(best), -1.0) >= 0.38: pick = best; sims.append(simil[id(best)])
                    f = [r for r in f if simil.get(id(r), 1.0) >= 0.22]      # las que seguro NO son ella (otra persona, afiche) quedan afuera
                if pick is None and f:
                    if prev is not None:
                        near = min(f, key=lambda r: np.hypot(r[0] + r[2] / 2 - prev[0], r[1] + r[3] / 2 - prev[1]))
                        if np.hypot(near[0] + near[2] / 2 - prev[0], near[1] + near[3] / 2 - prev[1]) < max(40, 2.5 * near[2]): pick = near
                    if pick is None and fp is None: pick = max(f, key=lambda r: r[2] * r[3])
                k_id += 1
            if pick is not None:
                x, y, w, h = pick[:4]
                prev = (x + w / 2, y + h / 2)
                obs.append((i, (x + w / 2) * S, (y + h / 2) * S, max(w, h) * S))
        i += 1
    N = i
    if not obs: return _track_face_haar(work, out, step)
    obs = np.array(obs)
    res = np.zeros((N, 3))
    for k in range(3):
        v = median_filter(obs[:, k + 1], size=9, mode="nearest")
        res[:, k] = np.interp(np.arange(N), obs[:, 0], v)
    res[:, 0] = gaussian_filter1d(res[:, 0], 12); res[:, 1] = gaussian_filter1d(res[:, 1], 12); res[:, 2] = gaussian_filter1d(res[:, 2], 30)
    np.save(out, res)
    return dict(frames=N, detections=len(obs), coverage=round(len(obs) * step / N, 3), cara=round(float(np.median(obs[:, 3])) / 1920, 3),
                ella=round(float(np.median(sims)), 2) if sims else None)


def _track_face_haar(work, out, step=2):
    aw, ah, S = 270, 480, 4
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    import plataforma as PL
    p = subprocess.Popen(["ffmpeg", "-v", "error", *PL.HWDEC, "-i", work, "-vf", f"scale={aw}:{ah}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    obs, i, prev = [], 0, None
    while True:
        buf = p.stdout.read(aw * ah)
        if len(buf) < aw * ah: break
        if i % step == 0:
            g = np.frombuffer(buf, np.uint8).reshape(ah, aw)
            faces = casc.detectMultiScale(g[: int(ah * 0.75)], 1.08, 5, minSize=(22, 22))
            if len(faces):
                def score(f):
                    x, y, w, h = f
                    d = 0 if prev is None else np.hypot(x + w / 2 - prev[0], y + h / 2 - prev[1])
                    return w * h - d * 6
                x, y, w, h = max(faces, key=score)
                prev = (x + w / 2, y + h / 2)
                obs.append((i, (x + w / 2) * S, (y + h / 2) * S, w * S))
        i += 1
    N = i
    if not obs: raise RuntimeError("no se detectó ninguna cara en el video")
    obs = np.array(obs)
    res = np.zeros((N, 3))
    for k in range(3):
        v = median_filter(obs[:, k + 1], size=9, mode="nearest")
        res[:, k] = np.interp(np.arange(N), obs[:, 0], v)
    res[:, 0] = gaussian_filter1d(res[:, 0], 12); res[:, 1] = gaussian_filter1d(res[:, 1], 12); res[:, 2] = gaussian_filter1d(res[:, 2], 30)
    np.save(out, res)
    return dict(frames=N, detections=len(obs), coverage=round(len(obs) * step / N, 3))


# ------------------------------------------------------------------ orquestación
ALL_STEPS = ("video", "audio", "asr", "face", "align", "speakers", "map", "arbitro")


def ingest(video, name, client="lilian", steps=ALL_STEPS, tema="", material=None, layout="auto", panel_x=None):
    t0 = time.time()
    d = os.path.join(SOURCES, name); os.makedirs(d, exist_ok=True)
    J = lambda *p: os.path.join(d, *p)
    cl = json.load(open(os.path.join(CLIENTS, client + ".json"), encoding="utf-8")) if os.path.exists(os.path.join(CLIENTS, client + ".json")) else {}
    info = probe(video)
    json.dump(info, open(J("meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"{os.path.basename(video)}: {info['width']}x{info['height']} rot {info['rotation']}° {info['fps']:.2f} fps · {info['duration']:.1f}s · "
        f"{'HDR ' + info['transfer'] if info['hdr'] else 'SDR'} · audio {info['audio_codec']}"
        + (f" · píxeles {info['sar']} (imagen real {info['width']}x{info['height']})" if info.get("sar", "1:1") != "1:1" else ""))
    if min(info["width"], info["height"]) < 720:
        log(f"AVISO: resolución real baja ({info['width']}x{info['height']}): el video final se verá blando. Si existe el archivo "
            f"ORIGINAL de la cámara (sin exportar desde una app), usá ese.")
    tipo = fecha = None
    try:                                                         # ENTENDER el video antes de editarlo (entender.py): qué es y cómo se edita
        import entender as EN
        t = time.time(); r = EN.entender(video); tipo = r["tipo"]; fecha = r.get("fecha")
        log(f"entendido como: {EN.TIPOS[tipo][0]} · {'; '.join(r['por_que'])} ({time.time() - t:.0f}s)")
        if tipo in ("reunion", "evento", "clip", "editado"): log(f"AVISO: para este tipo conviene: {EN.TIPOS[tipo][1]}")
        if tipo == "tv" and layout == "auto": layout = "panel"; log("señal de TV -> formato panel (recuadro + datos)")
    except Exception as e: log(f"(no se pudo entender el video: {e!r})")
    if "video" in steps:
        t = time.time()
        if layout == "panel":
            n = make_work_panel(info, J("work.mp4"), d, x_limits=panel_x)
            log(f"video de trabajo 1080x1920 en formato panel listo: {n} cuadros · {json.load(open(J('panel.json')))} ({time.time() - t:.0f}s)")
        else:
            cx = landscape_face_x(info) if info["width"] > info["height"] else None
            make_work(info, J("work.mp4"), cx)
            log(f"video de trabajo 1080x1920 listo ({time.time() - t:.0f}s)")
    if "audio" in steps and info["audio"]:
        t = time.time(); make_audio(info, d); log(f"voz limpia lista ({time.time() - t:.0f}s)")
    if "asr" in steps:
        t = time.time()
        res = transcribe(J("voice.wav"), J("transcript.json"), (cl.get("whisper_prompt", "Conferencia de prensa.") + " " + tema).strip())
        log(f"transcripción: {sum(len(s['words']) for s in res)} palabras ({time.time() - t:.0f}s)")
    if "face" in steps:
        stp = 2 if info["duration"] <= 240 else (3 if info["duration"] <= 600 else 4)     # videos largos: cada 3–4 cuadros (se interpola y suaviza igual)
        t = time.time(); st = track_face(J("work.mp4"), J("face.npy"), step=stp); log(f"cara: {st} ({time.time() - t:.0f}s)")
    _register(d, name, client, video, tema, material, layout, tipo, fecha)
    if "align" in steps:                                         # punto 4: tiempos exactos por alineación forzada + palabras inventadas
        import align
        t = time.time(); _, rep = align.run(name); g = align.ghosts(name); log(f"alineación: {rep} · palabras inventadas: {len(g)} ({time.time() - t:.0f}s)")
    if "speakers" in steps:                                      # punto 5: quién habla (huella de voz del cliente)
        import speakers
        t = time.time(); _, _, rep = speakers.label(name); log(f"voces de periodistas: {rep} ({time.time() - t:.0f}s)")
    if "map" in steps:                                           # punto 6: mapa de contenido automático (borrador para aprobar)
        import mapper
        t = time.time(); m, out, _ = mapper.draft(name); log(f"mapa de contenido: {len(out)} bloques, historias {list(m['stories'])} ({time.time() - t:.0f}s)")
    if "arbitro" in steps:                                       # árbitro: desacuerdos whisper vs modelo acústico, para revisar con un clic
        import arbitro
        t = time.time(); r = arbitro.scan(name); log(f"árbitro: {len(r['items'])} desacuerdos para revisar (python arbitro.py review {name}) ({time.time() - t:.0f}s)")
    log(f"fuente lista: sources/{name}/ · total {time.time() - t0:.0f}s")
    return json.load(open(J("source.json"), encoding="utf-8"))


# ------------------------------------------------------------------ la MISMA grabación ya ingresada (con cualquier nombre)
# Una fuente se reconoce por su ARCHIVO ORIGINAL, no por el nombre: LS1 entró como "lilian_senado_feminicidios" (corregida a mano:
# hablante, texto, mapa aprobado, datos.json) y otra vez como "auto_2026_10_14_ls1" sin nada de eso. Mismo archivo = misma huella
# (tamaño + primer MB; las fuentes nuevas la guardan) o, en las viejas sin huella, misma ruta absoluta y misma duración (± 0.5 s:
# los IMG_xxxx del teléfono repiten nombre con el tiempo); si el archivo cambió de carpeta (Drive, otra PC, la Mac del equipo),
# mismo NOMBRE de archivo y misma duración. La primera vez que una fuente vieja se reconoce así, se le guarda la huella: una mudanza
# o un cambio de nombre posterior se sigue reconociendo. Entre varias, manda la que tiene más correcciones HUMANAS.
def huella(path):
    """tamaño + sha1 del primer MB del original: el mismo video aunque se mueva de carpeta o se renombre (lee solo 1 MB)"""
    import hashlib
    try:
        with open(path, "rb") as f: return f"{os.path.getsize(path)}:{hashlib.sha1(f.read(1 << 20)).hexdigest()[:16]}"
    except OSError: return None


def _dur_fuente(d, sj):
    """duración de una fuente ya ingresada: meta.json (ffprobe del original) o, en las fuentes viejas sin meta.json (conferencia BCP),
    la cabecera de su voz (voice_full.wav dura lo mismo que el original: 434.81 s)"""
    try: return float(json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["duration"])
    except Exception: pass
    try:
        v = sj.get("voice") or "voice.wav"; w = wave.open(v if os.path.isabs(v) else os.path.join(d, v))
        return w.getnframes() / float(w.getframerate())
    except Exception: return None


def _nombre_archivo(p):
    """nombre del archivo de una ruta guardada en Windows O en la Mac (en la Mac os.path.basename no corta en '\\'), sin mayúsculas"""
    return (p or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()


def mismo_original(d, sj, video, hv=None, dur=None, propio=False):
    """¿la fuente d (su source.json = sj) es del archivo `video`? -> "huella" | "ruta" | "nombre" (cómo se reconoció) o None.
    Con huella guardada manda la huella (en esa ruta pudo quedar otro archivo). Sin huella (las fuentes viejas): la misma ruta (y la
    misma duración, si se conoce) o, si se movió de carpeta, el mismo nombre de archivo Y la misma duración (± 0.5 s; sin duración
    no alcanza el nombre). `propio`: es sources/<nombre armado de este archivo> (auto.slug) -> el nombre ya coincide; antes esa
    carpeta se reusaba siempre y un archivo movido de carpeta no debe volver a ingresarse (GPU, minutos) como <nombre>_2"""
    if sj.get("huella") and hv: return "huella" if sj["huella"] == hv else None
    orig = sj.get("original") or ""
    ruta = bool(orig) and os.path.normcase(os.path.abspath(orig)) == os.path.normcase(os.path.abspath(video))
    if not (ruta or propio or (orig and _nombre_archivo(orig) == _nombre_archivo(video))): return None
    df = _dur_fuente(d, sj) if dur else None                         # (se lee solo si la ruta o el nombre coinciden)
    igual = df is not None and abs(df - float(dur)) <= 0.5
    if ruta: return "ruta" if (df is None or igual) else None         # (otra duración: el teléfono repitió el nombre en esa carpeta)
    return "nombre" if igual else None


def sellar_huella(d, sj, hv):
    """guarda la huella del original en una fuente vieja que se acaba de reconocer por ruta o por nombre (así una mudanza o un cambio
    de nombre posterior se sigue reconociendo). Se escribe aparte y se reemplaza: un corte a mitad no deja un source.json roto"""
    sp = os.path.join(d, "source.json"); tmp = sp + ".tmp"
    try:
        json.dump(dict(sj, huella=hv), open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, sp); return True
    except OSError:
        try: os.remove(tmp)
        except OSError: pass
        return False


def borrador_editado(d):
    """¿alguien corrigió a mano el borrador del mapa (content_draft.json) sin aprobarlo todavía? La página de revisión que arma
    mapper.py pide justamente eso («Para corregir: editar content_draft.json»). mapper escribe el borrador y enseguida
    content_review.html (mismo segundo) -> borrador más nuevo que la página por más de 2 s = corregido a mano.
    -> True | False (tal cual lo escribió mapper.py, o no hay borrador) | None (sin la página no se puede saber)"""
    dr, rv = os.path.join(d, "content_draft.json"), os.path.join(d, "content_review.html")
    if not os.path.exists(dr): return False
    if not os.path.exists(rv): return None
    try: return os.path.getmtime(dr) > os.path.getmtime(rv) + 2.0
    except OSError: return None


def utilizable(d, sj):
    """¿tiene sus archivos de trabajo (video, voz, transcripción, cara)? Las fuentes viejas apuntan a otras carpetas (v2/, edicion/)
    y en otra PC pueden no estar: entonces no se edita con ella, pero sus correcciones se heredan igual"""
    res = lambda x: x if os.path.isabs(x) else os.path.join(d, x)
    return all(sj.get(k) and os.path.exists(res(sj[k])) for k in ("video", "voice", "transcript", "face"))


def correcciones(d, sj):
    """correcciones HUMANAS de una fuente -> (puntaje, ["2 de hablante", "mapa aprobado", …]): lo que se pierde si el mismo archivo
    entra como fuente nueva. Los borrados marcados 'auto' (align.ghosts) y los periodistas (speakers.label) se rehacen solos: no cuentan"""
    pts, det = 0, []
    for k, peso, uno, varios in (("speaker_fix", 3, "de hablante", "de hablante"), ("fixes", 3, "de texto", "de texto"),
                                 ("nocut", 2, "zona sin corte", "zonas sin corte"), ("glossary", 1, "del glosario", "del glosario")):
        n = len(sj.get(k) or [])
        if n: pts += peso * n; det.append(f"{n} {uno if n == 1 else varios}")
    man = [x for x in (sj.get("delete") or []) + (sj.get("bad") or []) if len(x) < 3 or x[2] != "auto"]
    if man: pts += len(man); det.append(f"{len(man)} {'borrado' if len(man) == 1 else 'borrados'} a mano")
    for f, peso, txt in (("content.json", 5, "mapa aprobado"), ("datos.json", 4, "datos.json"), ("feedback.json", 2, "casos del equipo")):
        if os.path.exists(os.path.join(d, f)): pts += peso; det.append(txt)
    if not os.path.exists(os.path.join(d, "content.json")) and borrador_editado(d):  # titulares/bloques corregidos y todavía sin aprobar
        pts += 3; det.append("borrador del mapa corregido a mano")
    try: dec = sum(1 for i in json.load(open(os.path.join(d, "arbitro.json"), encoding="utf-8")).get("items", []) if i.get("decision"))
    except Exception: dec = 0
    if dec: pts += dec; det.append(f"{dec} {'duda del árbitro revisada' if dec == 1 else 'dudas del árbitro revisadas'}")
    if (sj.get("tema") or sj.get("prompt") or "").strip(): pts += 1; det.append("tema con nombres")
    return pts, det


def fuentes_del_original(video, dur=None, excluir=(), propio=None, sellar=False):
    """fuentes ya ingresadas del MISMO archivo -> [dict(name, puntos, detalle, usable, layout, tema, por)], la más corregida primero
    (empate: la utilizable y después la más nueva, hecha con las reglas de hoy). `dur`: duración del archivo (si se conoce).
    `propio`: el nombre armado de este archivo (ver mismo_original). `sellar`: a las viejas reconocidas por ruta o por nombre se les
    guarda la huella (no en --solo-plan ni en las pruebas: solo cuando de verdad se trabaja con el archivo)"""
    hv = huella(video) if os.path.isfile(video) else None
    out, selladas = [], []
    for n in (sorted(os.listdir(SOURCES)) if os.path.isdir(SOURCES) else []):
        if n in excluir: continue
        d = os.path.join(SOURCES, n); sp = os.path.join(d, "source.json")
        if not os.path.isfile(sp): continue                         # (las reuniones viven en <fuente>/reunion/: las ve auto.reunion_previa)
        try: sj = json.load(open(sp, encoding="utf-8"))
        except Exception: continue
        por = mismo_original(d, sj, video, hv, dur, propio=n == propio)
        if not por: continue
        if sellar and hv and por != "huella" and sellar_huella(d, sj, hv): selladas.append(n)
        pts, det = correcciones(d, sj)
        out.append(dict(name=n, puntos=pts, detalle=det, usable=utilizable(d, sj), layout=sj.get("layout") or "auto",
                        tema=(sj.get("tema") or "").strip(), created=str(sj.get("created", "")), por=por))
    if selladas: log(f"huella del archivo original guardada en {', '.join('sources/' + n for n in selladas)} (así se reconoce aunque cambie de carpeta o de nombre)")
    out.sort(key=lambda x: x["created"], reverse=True)               # (orden estable: primero la más nueva…)
    out.sort(key=lambda x: (-x["puntos"], not x["usable"]))          # …y por encima, la más corregida y utilizable
    return out


def _heredar(d, src, video, name, dur=None):
    """el mismo archivo ya entró con OTRO nombre: se traen sus correcciones humanas (hablante, texto, zonas sin corte, borrados a
    mano, glosario, --tema, datos.json + material/) a lo que falte en esta. Son tiempos del MISMO audio: valen igual. El mapa
    aprobado (content.json) NO se copia (ni el borrador corregido a mano): se ancla en el texto de las frases y otra transcripción
    puede no coincidir."""
    cs = [c for c in fuentes_del_original(video, dur, excluir=(name,), sellar=True) if c["puntos"] > 0]   # (ingesta real: se sellan las viejas)
    if not cs: return None
    c = cs[0]; pd = os.path.join(SOURCES, c["name"])
    prev = json.load(open(os.path.join(pd, "source.json"), encoding="utf-8"))
    traido = []
    for k in ("speaker_fix", "fixes", "nocut", "glossary", "keywords", "prompt", "bad"):
        if prev.get(k) and not src.get(k): src[k] = prev[k]; traido.append(k)
    man = [x for x in prev.get("delete") or [] if len(x) < 3 or x[2] != "auto"]          # borrados a mano (los 'auto' los rehace align)
    if man and not [x for x in src.get("delete") or [] if len(x) < 3 or x[2] != "auto"]:
        src["delete"] = list(src.get("delete") or []) + man; traido.append("delete")
    if prev.get("tema") and not (src.get("tema") or "").strip(): src["tema"] = prev["tema"]; traido.append("tema")
    if prev.get("material") and not src.get("material"): src["material"] = prev["material"]
    try:                                                            # datos del tema: tarjetas por palabra disparadora (no dependen de los tiempos)
        import shutil
        if os.path.isfile(os.path.join(pd, "datos.json")) and not os.path.exists(os.path.join(d, "datos.json")):
            shutil.copy2(os.path.join(pd, "datos.json"), os.path.join(d, "datos.json")); traido.append("datos.json")
            if os.path.isdir(os.path.join(pd, "material")) and not os.path.exists(os.path.join(d, "material")):
                shutil.copytree(os.path.join(pd, "material"), os.path.join(d, "material"))      # las láminas de datos.json ("fondos")
    except OSError as e: log(f"(no se pudo copiar datos.json de {c['name']}: {e})")
    if not traido: return None
    src["heredado_de"] = c["name"]
    log(f"el mismo archivo ya estaba ingresado como sources/{c['name']} ({', '.join(c['detalle'])}): se traen sus correcciones "
        f"({', '.join(traido)})" + (f" · otras fuentes del mismo archivo: {', '.join(x['name'] for x in cs[1:])}" if len(cs) > 1 else ""))
    return c["name"]


def _register(d, name, client, video, tema="", material=None, layout="auto", tipo=None, fecha=None):
    J = lambda *p: os.path.join(d, *p)
    src = dict(name=name, client=client, original=os.path.abspath(video), video="work.mp4", voice="voice.wav", transcript="transcript.json", face="face.npy",
               glossary={}, reporter=[], bad=[], delete=[], created=time.strftime("%Y-%m-%d %H:%M"), tema=tema, material=material)
    hv = huella(video)
    if hv: src["huella"] = hv                                       # reconoce el MISMO archivo aunque entre con otro nombre o desde otra carpeta
    if layout == "panel": src.update(layout="panel", panel=list(PANEL))
    if tipo: src["tipo"] = tipo                                     # conferencia | discurso | mensaje | tv | … (entender.py)
    if fecha: src["fecha"] = fecha                                  # fecha real de la toma (nombre del archivo o metadatos), no la de hoy
    old = J("source.json")
    if os.path.exists(old):                                     # conservar correcciones ya hechas sobre esta fuente
        prev = json.load(open(old, encoding="utf-8"))
        for k in ("glossary", "reporter", "bad", "delete", "reporter_auto", "fixes", "nocut", "speaker_fix", "keywords", "prompt", "heredado_de"):
            if k in prev: src[k] = prev[k]
        if "tipo" in prev and not tipo: src["tipo"] = prev["tipo"]
        if "fecha" in prev and not fecha: src["fecha"] = prev["fecha"]
        if prev.get("tema") and not tema: src["tema"] = prev["tema"]          # re-ingesta sin --tema: no se pierden los nombres ya dados
        if prev.get("material") and not material: src["material"] = prev["material"]
    try: _heredar(d, src, video, name, _dur_fuente(d, {}))       # el mismo archivo con OTRO nombre: sus correcciones humanas (meta.json ya escrito)
    except Exception as e: log(f"(no se pudieron buscar correcciones de otra fuente del mismo archivo: {e!r})")
    json.dump(src, open(old, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--name", required=True); ap.add_argument("--client", default="lilian")
    ap.add_argument("--steps", default="all")
    ap.add_argument("--tema", default="", help="nombres propios y términos del video (mejoran la transcripción), p. ej. 'Banco Central, IPS, Gustavo Leite'")
    ap.add_argument("--material", default=None, help="paquete de fotos/clips del tema en assets/material/ (p. ej. bcp)")
    ap.add_argument("--layout", default="auto", choices=["auto", "panel"], help="panel: horizontal de baja resolución (TV) -> recuadro con la persona + zona para datos")
    ap.add_argument("--panel-x", default=None, help="límites horizontales del recorte en el original, p. ej. '165,712' (evita reloj y logo de la TV)")
    a = ap.parse_args()
    steps = ALL_STEPS if a.steps == "all" else tuple(a.steps.split(","))
    ingest(a.video, a.name, a.client, steps, tema=a.tema, material=a.material, layout=a.layout,
           panel_x=tuple(int(v) for v in a.panel_x.split(',')) if a.panel_x else None)
