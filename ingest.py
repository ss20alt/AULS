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
                if fp is not None and (prev is None or k_id % 10 == 0):       # ¿cuál es ella? (huella de cara)
                    best = (-1.0, None)
                    for r in sorted(f, key=lambda r: -r[2] * r[3])[:5]:
                        try:
                            e = rec.feature(rec.alignCrop(fr, r)).ravel(); e /= np.linalg.norm(e) + 1e-9; sm = float(e @ fp)
                        except cv2.error: sm = -1.0
                        if sm > best[0]: best = (sm, r)
                    if best[0] >= 0.38: pick = best[1]; sims.append(best[0])
                if pick is None:
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


def _register(d, name, client, video, tema="", material=None, layout="auto", tipo=None, fecha=None):
    J = lambda *p: os.path.join(d, *p)
    src = dict(name=name, client=client, original=os.path.abspath(video), video="work.mp4", voice="voice.wav", transcript="transcript.json", face="face.npy",
               glossary={}, reporter=[], bad=[], delete=[], created=time.strftime("%Y-%m-%d %H:%M"), tema=tema, material=material)
    if layout == "panel": src.update(layout="panel", panel=list(PANEL))
    if tipo: src["tipo"] = tipo                                     # conferencia | discurso | mensaje | tv | … (entender.py)
    if fecha: src["fecha"] = fecha                                  # fecha real de la toma (nombre del archivo o metadatos), no la de hoy
    old = J("source.json")
    if os.path.exists(old):                                     # conservar correcciones ya hechas sobre esta fuente
        prev = json.load(open(old, encoding="utf-8"))
        for k in ("glossary", "reporter", "bad", "delete", "reporter_auto", "fixes", "nocut", "speaker_fix", "keywords", "prompt"):
            if k in prev: src[k] = prev[k]
        if "tipo" in prev and not tipo: src["tipo"] = prev["tipo"]
        if "fecha" in prev and not fecha: src["fecha"] = prev["fecha"]
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
