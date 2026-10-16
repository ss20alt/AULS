# Estudio de edición — FORMATO REUNIÓN (video horizontal con varias personas que hablan, cámara en mano).
# Lo aprendido con "Gustavo Mussi se suma a Causa Republicana" (IMG_4801, 2026-10-14), automatizado:
#   python reunion.py ingest <video> --name <fuente> --tema "nombres y términos"   # color fiel, voz, transcripción, quién habla, qué cara habla
#   python reunion.py people <fuente> [set S1 "Nombre" "Cargo"] [approve]          # nombres de cada voz (hoja de caras para confirmar)
#   python reunion.py edit <fuente> --length 150 --titulo "LÍNEA 1|LÍNEA 2"        # elegir ideas completas, bordes verificados, render, control, entrega
#   python reunion.py eval <fuente>                                                 # comparar voces/elección contra una edición manual de referencia
# Reglas del formato (pedidas por el usuario):
#   · informativo, SIN gancho; color igual al bruto (hable npl=300, sin subir brillo); imagen estática (cara anclada + estabilización);
#   · nunca cortar a mitad de frase ni de idea; cada persona termina su idea; respiración (~0.4 s) antes de cada cambio;
#   · fundido EN MOVIMIENTO solo cuando cambia la persona; entre bloques de la misma persona, cambio de encuadre (un fundido da "doble cara");
#   · bordes verificados con transcripción AISLADA del inicio y el final de cada bloque (las caídas de energía dentro de una palabra engañan).
import os, sys, json, re, time, wave, math, shutil, subprocess, argparse, unicodedata, difflib
import numpy as np, cv2
from scipy.ndimage import gaussian_filter1d

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO); sys.path.insert(0, os.path.join(STUDIO, "lib"))
SOURCES = os.path.join(STUDIO, "sources")
PROJECTS = os.path.join(STUDIO, "projects")
CLIENTS = os.path.join(STUDIO, "clients")
MODELS = os.path.join(STUDIO, "models")
FPS, SR = 30, 48000
TM = ("zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=300,format=gbrpf32le,zscale=p=bt709,"
      "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv:d=error_diffusion,format=yuv420p")
DELIVER_DIRS = [os.path.join(os.path.expanduser("~"), "Downloads"), os.path.join(os.path.expanduser("~"), "Documents", "videosclaudesubir")]
log = lambda *a: print("[reunión]", *a, flush=True)


def src_dir(name): return os.path.join(SOURCES, name)
def R(name, *p): return os.path.join(SOURCES, name, "reunion", *p)
def jload(p): return json.load(open(p, encoding="utf-8"))
def jsave(o, p): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ ]", "", t).strip()


def read_wav(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    return a, w.getframerate()


_WH = {}


def whisper():
    if "m" not in _WH:
        import plataforma as PL
        _WH["m"] = PL.whisper_model("large-v3")
    return _WH["m"]


def asr_clip(a16, s, e, prompt=None):
    """transcripción AISLADA de un tramo (con 0.8 s de silencio a cada lado): la verdad sobre los bordes"""
    pad = np.zeros(int(0.8 * 16000), np.float32)
    x = a16[max(0, int(s * 16000)):int(e * 16000)]
    segs, _ = whisper().transcribe(np.concatenate([pad, x, pad]), language="es", beam_size=5, vad_filter=False,
                                   condition_on_previous_text=False, initial_prompt=prompt)
    return " ".join(t.text.strip() for t in segs)


# =========================================================================================== 1. INGESTA
def ingest(video, name, tema="", client="lilian"):
    import ingest as IG
    t0 = time.time()
    os.makedirs(R(name), exist_ok=True)
    cl = jload(os.path.join(CLIENTS, client + ".json")) if os.path.exists(os.path.join(CLIENTS, client + ".json")) else {}
    info = IG.probe(video); jsave(info, R(name, "meta.json"))
    log(f"{os.path.basename(video)}: {info['width']}x{info['height']} · {info['duration']:.1f}s · {'HDR' if info['hdr'] else 'SDR'}")
    a48, a16 = R(name, "a48.wav"), R(name, "a16.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "48000", a48], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", a16], check=True)
    prompt = f"Reunión con {cl.get('role', '').lower()} {cl.get('name', '')}. {tema}".strip()
    a, _ = read_wav(a16)
    segs, _ = whisper().transcribe(a, language="es", word_timestamps=True, vad_filter=True, beam_size=5,
                                   vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=200), initial_prompt=prompt)
    tr = [dict(s=x.start, e=x.end, text=x.text, words=[dict(w=w.word.strip(), s=w.start, e=w.end, p=w.probability) for w in x.words]) for x in segs]
    jsave(tr, R(name, "transcript.json"))
    log(f"transcripción: {sum(len(s['words']) for s in tr)} palabras ({time.time() - t0:.0f}s)")
    src = dict(name=name, client=client, original=os.path.abspath(video), tema=tema, prompt=prompt, glossary={}, layout="reunion",
               created=time.strftime("%Y-%m-%d %H:%M"))
    old = R(name, "source.json")
    if os.path.exists(old):
        for k in ("glossary", "titulo"): src[k] = jload(old).get(k, src.get(k))
    jsave(src, old)
    sentences(name)
    voices(name)
    faces(name)
    people_draft(name)
    log(f"fuente lista: sources/{name}/reunion · {time.time() - t0:.0f}s")


def sentences(name):
    """frases: palabras hasta . ? ! o una pausa ≥ 1.0 s"""
    tr = jload(R(name, "transcript.json"))
    words = [w for s in tr for w in s["words"] if w["w"]]
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and w["s"] - cur[-1]["e"] >= 1.0:
            out.append(cur); cur = []
        cur.append(w)
        if w["w"][-1] in ".?!":
            out.append(cur); cur = []
    if cur: out.append(cur)
    S = [dict(i=k, s=c[0]["s"], e=c[-1]["e"], text=" ".join(x["w"] for x in c), words=c) for k, c in enumerate(out)]
    jsave(S, R(name, "sentences.json"))
    return S


# ------------------------------------------------------------------------------------------- quién habla
def voices(name, thr_cluster=0.30):
    """huella de voz por frase (WavLM); la cliente por su huella guardada; el resto se agrupa por parecido (una etiqueta por persona)"""
    import speakers as SP
    from scipy.cluster.hierarchy import linkage, fcluster
    S = jload(R(name, "sentences.json"))
    src = jload(R(name, "source.json"))
    a16 = SP.load_audio(R(name, "a48.wav"))
    E = np.array([np.mean([SP.embed(a16, a, b) for a, b in SP.chunks(s["s"], max(s["e"], s["s"] + 0.4))], 0) for s in S])
    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
    client = src["client"]
    vp = np.load(os.path.join(CLIENTS, f"{client}_voiceprint.npy")); thr = jload(os.path.join(CLIENTS, f"{client}_voiceprint.json"))["threshold"]
    sim = E @ vp
    dur = np.array([s["e"] - s["s"] for s in S])
    isL = sim >= thr
    lab = np.array(["L" if x else "?" for x in isL], dtype=object)
    idx = np.where(~isL & (dur >= 0.8))[0]
    if len(idx) >= 2:
        Z = linkage(E[idx], method="average", metric="cosine")
        cl = fcluster(Z, t=thr_cluster, criterion="distance")
        # etiquetas por orden de aparición; grupos con < 6 s de voz se unen al grupo más parecido
        tot = {c: dur[idx][cl == c].sum() for c in set(cl)}
        cent = {c: E[idx][cl == c].mean(0) for c in set(cl)}
        big = [c for c in tot if tot[c] >= 6.0] or list(tot)
        remap = {c: (c if c in big else max(big, key=lambda b: float(cent[c] @ cent[b]))) for c in tot}
        order = []
        for k in idx:
            c = remap[cl[list(idx).index(k)]]
            if c not in order: order.append(c)
        for j, k in enumerate(idx): lab[k] = f"S{order.index(remap[cl[j]]) + 1}"
    # frases cortas o sin decidir: heredan de la vecina más cercana (el embedding de < 1 s no es fiable)
    for k in range(len(S)):
        if lab[k] == "?" or dur[k] < 1.0:
            nb = [j for j in (k - 1, k + 1) if 0 <= j < len(S) and dur[j] >= 1.0 and lab[j] != "?"]
            if nb: lab[k] = lab[min(nb, key=lambda j: min(abs(S[j]["s"] - S[k]["e"]), abs(S[k]["s"] - S[j]["e"])))]
            elif lab[k] == "?": lab[k] = "L" if sim[k] >= thr - 0.05 else "S1"
    # frases cortas pegadas a la anterior (< 0.4 s) siguen a quien venía hablando ("En favor del." "Del país." "Y de nuestro partido.")
    for k in range(1, len(S)):
        if dur[k] < 1.2 and S[k]["s"] - S[k - 1]["e"] < 0.4 and sim[k] < 0.9:
            lab[k] = lab[k - 1]
    # una frase corta aislada dentro de un turno largo de otra persona suele ser error del embedding
    for k in range(1, len(S) - 1):
        if lab[k - 1] == lab[k + 1] != lab[k] and dur[k] < 2.5 and S[k]["s"] - S[k - 1]["e"] < 1.5 and S[k + 1]["s"] - S[k]["e"] < 1.5 and sim[k] < 0.9:
            lab[k] = lab[k - 1]
    for s, l, v in zip(S, lab, sim): s["spk"] = str(l); s["sim_client"] = round(float(v), 3)
    jsave(S, R(name, "sentences.json"))
    np.save(R(name, "voice_emb.npy"), E)
    turns = []
    for s in S:
        if turns and turns[-1]["spk"] == s["spk"] and s["s"] - turns[-1]["e"] < 3.0: turns[-1]["e"] = s["e"]; turns[-1]["n"] += 1
        else: turns.append(dict(spk=s["spk"], s=s["s"], e=s["e"], n=1))
    jsave(turns, R(name, "turns.json"))
    log("voces:", ", ".join(f"{t['spk']} {t['s']:.0f}-{t['e']:.0f}s" for t in turns if t["e"] - t["s"] >= 3))
    return S, turns


# ------------------------------------------------------------------------------------------- qué cara habla
def _yunet(w, h):
    p = os.path.join(MODELS, "yunet.onnx")
    if not os.path.exists(p):
        import urllib.request
        os.makedirs(MODELS, exist_ok=True)
        urllib.request.urlretrieve("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx", p)
    return cv2.FaceDetectorYN.create(p, "", (w, h), 0.55, 0.3, 50)


def faces(name, fps=5):
    """una pasada a 960x540 y 5 fps: caras (YuNet) + actividad de la BOCA (diferencia de la zona boca vs ojos entre cuadros).
       Por cada ventana de 6 s de cada turno, la cara que habla = más actividad de boca (desempate: tamaño y centro)."""
    meta = jload(R(name, "meta.json"))
    w, h = 960, 540
    vf = ("scale=960:540," + TM if meta.get("hdr") else "scale=960:540") + f",fps={fps}"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", meta["path"], "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    det = _yunet(w, h)
    rec = cv2.FaceRecognizerSF.create(os.path.join(MODELS, "sface.onnx"), "")
    frames, prev, motion = [], None, []
    k = 0
    while True:
        b = p.stdout.read(w * h * 3)
        if len(b) < w * h * 3: break
        fr = np.frombuffer(b, np.uint8).reshape(h, w, 3)
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        _, f = det.detect(fr)
        dets = []
        if f is not None:
            for r in f:
                x, y, fw, fh = r[:4]; lm = r[4:14].reshape(5, 2)
                dd = dict(cx=float(x + fw / 2) * 2, cy=float(y + fh / 2) * 2, size=float(max(fw, fh)) * 2, lm=lm, box=(x, y, fw, fh))
                dets.append(dd)
        if prev is not None:
            pg, pdets = prev[0], prev[1]
            for d in dets:
                best = min(pdets, key=lambda q: abs(q["cx"] - d["cx"]) + abs(q["cy"] - d["cy"]), default=None)
                if best is None or abs(best["cx"] - d["cx"]) + abs(best["cy"] - d["cy"]) > d["size"] * 0.5: d["act"] = None; continue
                lm = d["lm"]; fw = d["box"][2]
                mx0, mx1 = int(lm[3, 0] - fw * 0.12), int(lm[4, 0] + fw * 0.12)
                my0, my1 = int(lm[2, 1] + fw * 0.08), int(max(lm[3, 1], lm[4, 1]) + fw * 0.22)
                ex0, ex1 = int(lm[0, 0] - fw * 0.1), int(lm[1, 0] + fw * 0.1)
                ey0, ey1 = int(min(lm[0, 1], lm[1, 1]) - fw * 0.1), int(max(lm[0, 1], lm[1, 1]) + fw * 0.08)
                def reg(a, x0, x1, y0, y1): return a[max(0, y0):max(1, y1), max(0, x0):max(1, x1)]
                m1, m0 = reg(g, mx0, mx1, my0, my1), reg(pg, mx0, mx1, my0, my1)
                e1, e0 = reg(g, ex0, ex1, ey0, ey1), reg(pg, ex0, ex1, ey0, ey1)
                if m1.size < 20 or m1.shape != m0.shape or e1.shape != e0.shape or e1.size < 20: d["act"] = None; continue
                d["act"] = float(np.abs(m1 - m0).mean() - np.abs(e1 - e0).mean())
        frames.append([dict(cx=d["cx"], cy=d["cy"], size=d["size"], act=d.get("act"), **({"emb": d["emb"]} if "emb" in d else {})) for d in dets])
        small = cv2.resize(g, (240, 135))
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev[2], small)
            motion.append(float(np.hypot(dx, dy) * 8 / (30 / fps)))          # px por cuadro de 30 fps, en escala 1920
        prev = (g, dets, small); k += 1
    # huellas de cara a resolución COMPLETA (SFace necesita ~112 px de cara): 1 cuadro por segundo
    vf2 = (TM + ",fps=1") if meta.get("hdr") else "fps=1"
    p2 = subprocess.Popen(["ffmpeg", "-v", "error", "-i", meta["path"], "-vf", vf2, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    det2 = cv2.FaceDetectorYN.create(os.path.join(MODELS, "yunet.onnx"), "", (1920, 1080), 0.6, 0.3, 50)
    sec = 0
    while True:
        b = p2.stdout.read(1920 * 1080 * 3)
        if len(b) < 1920 * 1080 * 3: break
        fr2 = np.frombuffer(b, np.uint8).reshape(1080, 1920, 3)
        _, f2 = det2.detect(fr2)
        k5 = sec * fps
        if f2 is not None and k5 < len(frames):
            for r in f2:
                cx, cy = float(r[0] + r[2] / 2), float(r[1] + r[3] / 2)
                d = min(frames[k5], key=lambda q: abs(q["cx"] - cx) + abs(q["cy"] - cy), default=None)
                if d is None or abs(d["cx"] - cx) + abs(d["cy"] - cy) > max(r[2], r[3]) * 0.6: continue
                try:
                    e = rec.feature(rec.alignCrop(fr2, r)).flatten(); d["emb"] = [round(float(v), 4) for v in e / (np.linalg.norm(e) + 1e-9)]
                except Exception: pass
        sec += 1
    jsave(dict(fps=fps, frames=frames), R(name, "faces_raw.json"))
    mv = gaussian_filter1d(np.array(motion + [0.0]), 2)
    spans, cur = [], None
    for i, v in enumerate(mv):                                               # paneos/acercamientos de la cámara (> 6 px por cuadro)
        if v > 6 and cur is None: cur = i / fps
        if v <= 6 and cur is not None:
            if i / fps - cur >= 0.6: spans.append([round(cur, 2), round(i / fps, 2)])
            cur = None
    jsave(spans, R(name, "motion.json")); log(f"cámara en movimiento: {spans}")
    return face_windows(name)


def face_windows(name, w_act=0.5, w_size=0.25, w_cen=0.35, w_sync=1.2):
    """elige, por ventana de 6 s de cada turno, la cara que habla. Una cara cortada por el borde del cuadro no puede ganar;
       la boca que se mueve manda; dentro de un turno la elección debe ser coherente (la misma persona)."""
    raw = jload(R(name, "faces_raw.json")); frames, fps = raw["frames"], raw["fps"]
    # identidades: huellas de cara agrupadas (la misma persona en todo el video, aunque la cámara se mueva)
    from scipy.cluster.hierarchy import linkage, fcluster
    embs = [(i, j, np.array(d["emb"])) for i, fr_ in enumerate(frames) for j, d in enumerate(fr_) if "emb" in d]
    if len(embs) >= 4:
        X = np.array([e for *_, e in embs])
        lab = fcluster(linkage(X, method="average", metric="cosine"), t=0.60, criterion="distance")
        for (i, j, _), l in zip(embs, lab): frames[i][j]["ident"] = int(l)
        # cada detección sin huella hereda la identidad de la detección con huella más cercana (misma posición, ±2 s)
        anchors = [(i, frames[i][j]) for i, j, _ in embs]
        for i, fr_ in enumerate(frames):
            for d in fr_:
                if "ident" in d: continue
                near = [a for k, a in anchors if abs(k - i) <= 2 * fps and abs(a["cx"] - d["cx"]) < d["size"] * 0.6 and abs(a["cy"] - d["cy"]) < d["size"] * 0.6]
                if near: d["ident"] = min(near, key=lambda a: abs(a["cx"] - d["cx"]) + abs(a["cy"] - d["cy"]))["ident"]
    rms = energy(name)
    env = np.array([rms[max(0, int(i / fps * 100) - 10):int(i / fps * 100) + 10].mean() if int(i / fps * 100) < len(rms) else -90 for i in range(len(frames))])
    turns = jload(R(name, "turns.json"))
    windows = []
    for t in turns:
        if t["e"] - t["s"] < 1.5: continue
        nwin = max(1, int(round((t["e"] - t["s"]) / 6.0)))
        for j in range(nwin):
            a = t["s"] + (t["e"] - t["s"]) * j / nwin; b = t["s"] + (t["e"] - t["s"]) * (j + 1) / nwin
            obs = [(i / fps, d) for i in range(int(a * fps), min(len(frames), int(b * fps) + 1)) for d in frames[i]]
            if not obs: continue
            # agrupar detecciones de la ventana por posición (personas)
            groups = []
            for tt, d in obs:
                gsel = None
                for gg in groups:
                    if abs(gg["cx"] - d["cx"]) < max(gg["size"], d["size"]) * 0.6 and abs(gg["cy"] - d["cy"]) < max(gg["size"], d["size"]) * 0.6: gsel = gg; break
                if gsel is None: gsel = dict(cx=d["cx"], cy=d["cy"], size=d["size"], acts=[], n=0, pts=[], sync=[], ids=[]); groups.append(gsel)
                if "ident" in d: gsel["ids"].append(d["ident"])
                gsel["n"] += 1; gsel["pts"].append((tt, d["cx"], d["cy"], d["size"]))
                gsel["cx"] += (d["cx"] - gsel["cx"]) / gsel["n"]; gsel["cy"] += (d["cy"] - gsel["cy"]) / gsel["n"]; gsel["size"] += (d["size"] - gsel["size"]) / gsel["n"]
                if d["act"] is not None: gsel["acts"].append(d["act"]); gsel["sync"].append((d["act"], float(env[int(round(tt * fps))])))
            nmin = 0.3 * max(gg["n"] for gg in groups)
            cand = [gg for gg in groups if gg["n"] >= nmin and len(gg["acts"]) >= 3]
            if not cand: cand = [max(groups, key=lambda gg: gg["n"])]
            inside = [gg for gg in cand if gg["cx"] - gg["size"] * 0.45 > 0 and gg["cx"] + gg["size"] * 0.45 < 1920 and gg["cy"] - gg["size"] * 0.45 > 0]
            cand = inside or cand                                                    # caras cortadas por el borde: fuera
            acts = np.array([np.median(gg["acts"]) if gg["acts"] else -9 for gg in cand])
            def corr(pairs):                                                         # boca que se mueve al ritmo de la voz que se oye
                if len(pairs) < 6: return 0.0
                x, y = np.array(pairs).T
                return float(np.corrcoef(x, y)[0, 1]) if x.std() > 1e-6 and y.std() > 1e-6 else 0.0
            syncs = np.array([corr(gg["sync"]) for gg in cand])
            sizes = np.array([gg["size"] for gg in cand]); cen = np.array([1 - abs(gg["cx"] - 960) / 960 for gg in cand])
            z = lambda v: (v - v.mean()) / (v.std() + 1e-6) if len(v) > 1 else v * 0
            score = w_sync * z(syncs) + w_act * z(acts) + w_size * z(sizes) + w_cen * z(cen)
            idents = [max(set(gg["ids"]), key=gg["ids"].count) if gg["ids"] else None for gg in cand]
            zs = z(syncs) + 0.5 * z(acts)
            windows.append(dict(spk=t["spk"], turn=turns.index(t), s=round(a, 2), e=round(b, 2),
                                cands=[dict(cx=round(gg["cx"]), cy=round(gg["cy"]), size=round(gg["size"]), act=round(float(acts[i]), 2), sync=round(float(syncs[i]), 2),
                                            ident=idents[i], av=round(float(zs[i]), 2),
                                            score=round(float(score[i]), 2)) for i, gg in enumerate(cand)]))
    # voz <-> cara: con TODAS las ventanas de cada voz, la identidad cuya boca va al ritmo de esa voz (asignación sin repetir personas)
    acc = {}
    for w in windows:
        if len(w["cands"]) < 2: continue
        for c in w["cands"]:
            if c["ident"] is None: continue
            acc.setdefault(w["spk"], {}).setdefault(c["ident"], []).append(c["av"])
    assign, taken = {}, set()
    talk = {}
    for w in windows: talk[w["spk"]] = talk.get(w["spk"], 0) + w["e"] - w["s"]
    # huellas de cara conocidas: la cliente (y personas aprobadas antes) se reconocen por su cara, no por la boca
    cent = {}
    for (i, j, e), l in zip(embs, lab) if len(embs) >= 4 else []:
        cent.setdefault(int(l), []).append(e)
    cent = {l: (np.mean(v, 0) / (np.linalg.norm(np.mean(v, 0)) + 1e-9)) for l, v in cent.items() if len(v) >= 5}
    src = jload(R(name, "source.json"))
    known = {}
    cfp = os.path.join(CLIENTS, f"{src['client']}_faceprint.npy")
    if os.path.exists(cfp): known["L"] = np.load(cfp)
    for spk, fpv in known.items():
        if not cent: break
        l, sim_ = max(((l, float(c @ fpv)) for l, c in cent.items()), key=lambda x: x[1])
        if sim_ >= 0.45 and spk in talk: assign[spk] = l; taken.add(l); log(f"cara de {spk} reconocida por su huella (similitud {sim_:.2f})")
    kp = os.path.join(CLIENTS, f"{src['client']}_people")
    face_names = {}
    if os.path.isdir(kp) and cent:
        for f in os.listdir(kp):
            if f.endswith(".npy") and not f.endswith(".voz.npy"):
                v = np.load(os.path.join(kp, f)); l, sim_ = max(((l, float(c @ v)) for l, c in cent.items()), key=lambda x: x[1])
                if sim_ >= 0.5: face_names[l] = (f[:-4], round(sim_, 2))
    jsave({str(l): v for l, v in face_names.items()}, R(name, "known_faces.json"))
    # personas YA confirmadas por el usuario: la VOZ (huella guardada al aprobar) dice quién habla y la CARA registrada dice dónde
    # está. La sincronía de labios sola se equivocó en IMG_4801 (puso a Mussi hablando con la cara de Aarón): voz + cara mandan.
    voz_names = {}
    try:
        vreg = {f[:-8]: np.load(os.path.join(kp, f)) for f in os.listdir(kp) if f.endswith(".voz.npy")} if os.path.isdir(kp) else {}
        if vreg and face_names:
            S_ = jload(R(name, "sentences.json")); E_ = np.load(R(name, "voice_emb.npy"))
            by_name = {}
            for l, (nm, sm) in face_names.items():
                if sm >= 0.6 and (nm not in by_name or sm > face_names[by_name[nm]][1]): by_name[nm] = l
            for spk in sorted(talk, key=lambda k: -talk[k]):
                if spk in assign: continue
                ks = [k for k, s_ in enumerate(S_) if s_["spk"] == spk and s_["e"] - s_["s"] >= 1.0]
                if len(ks) < 3: continue
                m = E_[ks].mean(0); m /= np.linalg.norm(m) + 1e-9
                sims = sorted(((float(m @ v), nm) for nm, v in vreg.items()), reverse=True)
                best, nm = sims[0]
                margin = best - (sims[1][0] if len(sims) > 1 else 0.0)
                if best >= 0.90 and margin >= 0.05 and nm in by_name and by_name[nm] not in taken:
                    assign[spk] = by_name[nm]; taken.add(by_name[nm]); voz_names[spk] = (nm, round(best, 3))
                    log(f"voz de {spk} reconocida: {nm} (similitud {best:.2f}, margen {margin:.2f}) -> su cara registrada")
    except Exception as e: log(f"(huellas de voz: {e!r})")
    jsave(voz_names, R(name, "known_voices.json"))
    np.save(R(name, "face_centroids.npy"), dict(cent), allow_pickle=True)
    for spk in sorted(acc, key=lambda k: -talk.get(k, 0)):
        if spk in assign: continue
        opts = [(np.mean(v) * np.sqrt(len(v)), idn) for idn, v in acc[spk].items() if idn not in taken and len(v) >= 2]
        if opts:
            sc, idn = max(opts); assign[spk] = idn; taken.add(idn)
    jsave({k: int(v) for k, v in assign.items()}, R(name, "voice_face.json"))
    log("voz -> cara (identidad):", assign)
    # coherencia dentro del turno: si la cámara no se movió mucho, la persona que habla es la misma; se elige la que más veces gana
    for w in windows:
        own = [c for c in w["cands"] if assign.get(w["spk"]) is not None and c["ident"] == assign[w["spk"]]]
        best = max(own, key=lambda c: c["size"]) if own else max(w["cands"], key=lambda c: c["score"])
        w.update(cx=best["cx"], cy=best["cy"], size=best["size"], act=best["act"], by="identidad" if own else "señales")
    for ti in {w["turn"] for w in windows}:
        ws = [w for w in windows if w["turn"] == ti]
        base = [(w["cx"], w["cy"], w["size"], max(c["score"] for c in w["cands"]) - sorted([c["score"] for c in w["cands"]] + [-9])[-2]) for w in ws]
        for i, w in enumerate(ws):
            nb = [base[j] for j in range(max(0, i - 5), min(len(ws), i + 6)) if j != i]      # ±30 s del mismo turno, ponderado por la claridad
            if len(nb) < 2 or len(w["cands"]) < 2 or w.get("by") == "identidad": continue
            votes = {}
            for c in w["cands"]:
                votes[(c["cx"], c["cy"])] = sum(min(m, 3.0) for x, y, sz, m in nb if abs(x - c["cx"]) < c["size"] * 0.7 and abs(y - c["cy"]) < c["size"] * 0.7)
            tot = sum(min(m, 3.0) for *_, m in nb)
            key = max(votes, key=votes.get)
            if votes[key] >= 0.6 * tot and key != (w["cx"], w["cy"]):
                c = next(c for c in w["cands"] if (c["cx"], c["cy"]) == key)
                w.update(cx=c["cx"], cy=c["cy"], size=c["size"], act=c["act"], fixed="mayoría del turno")
    jsave(windows, R(name, "face_windows.json"))
    log(f"caras: {len(windows)} ventanas con la cara que habla")
    return windows


# ------------------------------------------------------------------------------------------- nombres
TITLES = r"(ex diputad[oa]|diputad[oa]|ex senador[a]?|senador[a]?|correligionari[oa]|concejal[a]?|intendente|gobernador[a]?|ministr[oa]|doctor[a]?|licenciad[oa])"


def people_draft(name):
    S = jload(R(name, "sentences.json")); src = jload(R(name, "source.json"))
    cl = jload(os.path.join(CLIENTS, src["client"] + ".json"))
    spk_time, first = {}, {}
    for s in S:
        spk_time[s["spk"]] = spk_time.get(s["spk"], 0) + s["e"] - s["s"]; first.setdefault(s["spk"], s["s"])
    # nombres mencionados por la anfitriona, en orden ("el ex diputado Gustavo Mussi ... y el correligionario Aarón Ruiz Díaz")
    text = " ".join(s["text"] for s in S if s["spk"] == "L")
    cands = []
    for m in re.finditer(TITLES + r"\s+((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s?){2,3})", text):
        nm = m.group(2).strip(" ,.")
        if nm not in [c[1] for c in cands]: cands.append((m.group(1), nm))
    for nm, rp in src.get("glossary", {}).items():
        cands = [(t, n.replace(nm, rp)) for t, n in cands]
    ppl, gi = {}, 0
    vfm = jload(R(name, "voice_face.json")) if os.path.exists(R(name, "voice_face.json")) else {}
    kf = jload(R(name, "known_faces.json")) if os.path.exists(R(name, "known_faces.json")) else {}
    for spk in sorted(spk_time, key=lambda k: first[k]):
        if spk_time[spk] < 3: continue
        kv = jload(R(name, "known_voices.json")) if os.path.exists(R(name, "known_voices.json")) else {}
        if spk == "L": ppl[spk] = dict(name=cl.get("name"), role=cl.get("role"), source="ficha del cliente")
        elif spk in kv and str(vfm.get(spk)) in kf and kf[str(vfm[spk])][0] == kv[spk][0]:   # voz Y cara de alguien ya confirmado
            nm = kv[spk][0]
            prev_role = next((x.get("role", "") for x in jload(os.path.join(CLIENTS, src["client"] + "_people.json")).values() if x.get("name") == nm), "") \
                if os.path.exists(os.path.join(CLIENTS, src["client"] + "_people.json")) else ""
            ppl[spk] = dict(name=nm, role=prev_role, source=f"reconocido por su voz y su cara (voz {kv[spk][1]}, cara {kf[str(vfm[spk])][1]})")
        elif str(vfm.get(spk)) in kf:                                       # persona ya conocida: reconocida por su cara
            nm, sim_ = kf[str(vfm[spk])]
            prev_role = next((x.get("role", "") for x in jload(os.path.join(CLIENTS, src["client"] + "_people.json")).values() if x.get("name") == nm), "")                 if os.path.exists(os.path.join(CLIENTS, src["client"] + "_people.json")) else ""
            ppl[spk] = dict(name=nm, role=prev_role, source=f"reconocido por su cara (similitud {sim_})")
        else:
            t, nm = cands[gi] if gi < len(cands) else ("", f"Persona {spk}")
            gi += 1
            ppl[spk] = dict(name=nm, role=t.capitalize(), source="sugerido (orden en que fueron presentados)")
        ppl[spk].update(seconds=round(spk_time[spk], 1), first=round(first[spk], 1))
    old = R(name, "people.json")
    if os.path.exists(old):
        prev = jload(old)
        if prev.get("approved"): return prev
    out = dict(approved=False, people=ppl)
    jsave(out, old)
    people_sheet(name)
    return out


def people_sheet(name):
    """hoja con la cara de cada voz (para confirmar nombres)"""
    meta = jload(R(name, "meta.json")); W_ = jload(R(name, "face_windows.json")); pp = jload(R(name, "people.json"))["people"]
    tiles = []
    for spk, info in pp.items():
        ws = [w for w in W_ if w["spk"] == spk]
        if not ws: continue
        w = max(ws, key=lambda x: x["size"])
        t = (w["s"] + w["e"]) / 2
        vf = (TM + "," if meta.get("hdr") else "")
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", meta["path"], "-frames:v", "1", "-vf", vf + "format=bgr24",
                            "-f", "rawvideo", "-"], capture_output=True)
        fr = np.frombuffer(r.stdout[:1920 * 1080 * 3], np.uint8).reshape(1080, 1920, 3).copy()
        s = int(w["size"] * 1.6); x0 = int(max(0, w["cx"] - s)); y0 = int(max(0, w["cy"] - s))
        crop = cv2.resize(fr[y0:y0 + 2 * s, x0:x0 + 2 * s], (360, 360))
        cv2.rectangle(crop, (0, 300), (360, 360), (0, 0, 0), -1)
        cv2.putText(crop, f"{spk}: {info['name']}"[:28], (8, 335), 0, 0.62, (255, 255, 255), 2)
        tiles.append(crop)
    if tiles: cv2.imwrite(R(name, "people.png"), np.hstack(tiles))


def registrar_voces(name, p=None):
    """huella de VOZ de cada persona aprobada (promedio de sus frases ≥ 1 s): la próxima reunión con ella se reconoce sola"""
    p = p or jload(R(name, "people.json"))
    if not p.get("approved") or not os.path.exists(R(name, "voice_emb.npy")): return
    src = jload(R(name, "source.json")); kp = os.path.join(CLIENTS, f"{src['client']}_people"); os.makedirs(kp, exist_ok=True)
    S_ = jload(R(name, "sentences.json")); E_ = np.load(R(name, "voice_emb.npy"))
    for spk, v in p["people"].items():
        if spk == "L": continue
        ks = [k for k, s_ in enumerate(S_) if s_["spk"] == spk and s_["e"] - s_["s"] >= 1.0]
        if len(ks) < 3: continue
        m = E_[ks].mean(0); m /= np.linalg.norm(m) + 1e-9
        np.save(os.path.join(kp, v["name"] + ".voz.npy"), m.astype(np.float32)); print(f"  huella de voz guardada: {v['name']} ({len(ks)} frases)")


def people_cmd(name, args):
    p = jload(R(name, "people.json"))
    if args and args[0] == "set":
        spk, nm, role = args[1], args[2], (args[3] if len(args) > 3 else "")
        p["people"].setdefault(spk, {}).update(name=nm, role=role, source="usuario"); jsave(p, R(name, "people.json")); people_sheet(name)
    elif args and args[0] == "approve":
        p["approved"] = True; jsave(p, R(name, "people.json"))
        vf = R(name, "voice_face.json"); cf = R(name, "face_centroids.npy")
        if os.path.exists(vf) and os.path.exists(cf):
            vfm, cent = jload(vf), np.load(cf, allow_pickle=True).item()
            src = jload(R(name, "source.json")); kp = os.path.join(CLIENTS, f"{src['client']}_people"); os.makedirs(kp, exist_ok=True)
            for spk, l in vfm.items():
                if spk != "L" and spk in p["people"] and l in cent:
                    np.save(os.path.join(kp, p["people"][spk]["name"] + ".npy"), cent[l]); print(f"  huella de cara guardada: {p['people'][spk]['name']}")
            registrar_voces(name, p)
            regp = os.path.join(CLIENTS, f"{src['client']}_people.json")
            reg = jload(regp) if os.path.exists(regp) else {}
            for spk, v in p["people"].items():
                if spk != "L": reg[v["name"]] = dict(name=v["name"], role=v.get("role", ""), seen_in=sorted(set(reg.get(v["name"], {}).get("seen_in", []) + [name])))
            jsave(reg, regp)
    for k, v in p["people"].items(): print(f"  {k}: {v['name']} · {v['role']} ({v.get('seconds')} s, desde {v.get('first')} s) [{v.get('source')}]")
    print("  aprobado:", p["approved"], "· hoja de caras:", R(name, "people.png"))


# =========================================================================================== 2. ELEGIR IDEAS COMPLETAS
FILLER = re.compile(r"^(muchas gracias|gracias|bienvenid[oa]s?|muy bien|exactamente|s[ií],? senador[a]?|excelente|bueno|entonces,? bienvenid|a muerte|yo s[eé])\W*$")
VOCAT = re.compile(r"^(gracias,?\s*)?(senador[a]?|presidenta?|lilian)\W*$")


def energy(name):
    p = R(name, "rms10.npy")
    if not os.path.exists(p):
        a, sr = read_wav(R(name, "a48.wav")); hop = sr // 100; n = len(a) // hop
        np.save(p, (20 * np.log10(np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)).astype(np.float32))
    return np.load(p)


ANAPH = re.compile(r"^(asi como|eso|esto|esa|ese|por eso|por lo tanto|entonces|tambien|ademas|pero|porque|que|sino|como|y eso|y esto|y ese|ahi|"
                   r"es lo que|es por eso|no venimos|por este|por esta|por estos)\b")


STRONG = re.compile(r"\b(venimos a|no venimos|tenemos que|necesitamos|compromiso|recuperar|valores|sumar|despertar|preocupad|"
                    r"proyecto|candidatura|apoyo|movimiento|concordia|reclamar|armen de valor|en favor del pais|recuperacion)")
WEAK = re.compile(r"\b(recuerdo|ojitos|no estoy hablando mal|no estoy cepillando|hay veces|bingos?|jaja|bueno,? algo|no se ni|"
                  r"estoy aca con|acá con|nos representa|me siento muy honrad|extraordinario)")


def camera_motion(name):
    p = R(name, "motion.json")
    return jload(p) if os.path.exists(p) else []


CONT = re.compile(r"^(en favor|a favor|para|de|del|con|sin|hacia|a los|a las|y de|y del|y a|y en|en el|en la|en los|en las|en su|en sus|"
                  r"en nuestr\w+|por el|por la|a \w+(ar|er|ir))\b")
DANGLING = {"de", "del", "a", "al", "la", "el", "los", "las", "y", "o", "que", "en", "con", "para", "por", "un", "una", "su", "sus", "mi", "nuestro", "nuestra", "como", "pero", "sin"}
TIGHT = re.compile(r"^(que|porque|sino|donde|cuando|quien|quienes|cual|cuales)\b")   # subordinada pegada: la frase anterior no terminó


def ideas(name, max_len=32.0, gap=1.4):
    """ideas = frases seguidas de la misma persona; se separan por pausas ≥ 0.9 s y por largo (≤ 30 s, siempre en final de frase).
       Las frases de relleno (gracias, vocativos, 'muy bien') quedan aparte."""
    S = jload(R(name, "sentences.json"))
    out, cur = [], None
    for s in S:
        t = norm(s["text"])
        fill = bool(FILLER.match(t)) or bool(VOCAT.match(t)) or len(t.split()) <= 1
        lower = s["text"].strip()[:1].islower()
        cont = cur is not None and cur["spk"] == s["spk"] and not cur["filler"] and s["s"] - cur["e"] < 2.5 and (
            bool(CONT.match(t)) or lower or (bool(TIGHT.match(t)) and s["s"] - cur["e"] < 0.6))
        by_len = cur is not None and s["e"] - cur["s"] > max_len and S[cur["sents"][-1]]["text"].rstrip()[-1:] in ".?!"
        brk = not cont and (cur is None or cur["spk"] != s["spk"] or fill or cur["filler"] or s["s"] - cur["e"] >= gap or by_len)
        if brk:
            # cortada solo por largo, en pleno discurso: la idea nueva depende de la anterior
            cut_len = cur is not None and cur["spk"] == s["spk"] and not fill and not cur["filler"] and s["s"] - cur["e"] < 0.3
            if cur: out.append(cur)
            cur = dict(spk=s["spk"], s=s["s"], e=s["e"], sents=[s["i"]], filler=fill, cut_len=cut_len)
        else:
            cur["sents"].append(s["i"]); cur["e"] = s["e"]
    if cur: out.append(cur)
    for k, p in enumerate(out):
        p["k"] = k; p["text"] = " ".join(S[i]["text"] for i in p["sents"]); p["dur"] = p["e"] - p["s"]
    return out, S


def list_ideas(name):
    I, S = ideas(name)
    ppl = jload(R(name, "people.json"))["people"]
    for p in I:
        if p["filler"] or p["dur"] < 1.0: continue
        who = ppl.get(p["spk"], {}).get("name", p["spk"])
        print(f"  #{p['k']:<3} {p['s']:7.1f}-{p['e']:7.1f} ({p['dur']:4.1f}s) {who[:16]:16s} {p['text'][:150]}")


def select_sents(name, spec):
    """bloques elegidos por frase: "0,25,30-33,85-90" (números de 'python reunion.py frases <fuente>'); cada rango = un bloque"""
    S = jload(R(name, "sentences.json"))
    out = []
    for part in spec.split(","):
        part, _, cut = part.strip().partition("@")                       # "0@29.1": termina en la pausa de 29.1 s dentro de la frase 0
        a, _, b = part.partition("-"); a = int(a); b = int(b) if b else a
        ss = list(range(a, b + 1))
        spk = S[a]["spk"]
        assert all(S[i]["spk"] == spk for i in ss), f"el rango {part} mezcla personas"
        if cut:
            t = float(cut); ws = S[b]["words"]
            upto = sum(1 for w in ws if (w["s"] + min(w["e"], w["s"] + 0.5)) / 2 < t)
            text = " ".join(S[i]["text"] for i in ss[:-1]) + (" " if len(ss) > 1 else "") + " ".join(w["w"] for w in ws[:upto]).rstrip(",;") + "."
            out.append(dict(spk=spk, s=S[a]["s"], e=ws[upto - 1]["e"] if ws[upto - 1]["e"] < t else t, sents=ss, text=text, upto=upto))
            continue
        if out and out[-1]["sents"][-1] + 1 == a and out[-1]["spk"] == spk:
            out[-1]["sents"] += ss; out[-1]["e"] = S[b]["e"]; out[-1]["text"] += " " + " ".join(S[i]["text"] for i in ss); continue
        out.append(dict(spk=spk, s=S[a]["s"], e=S[b]["e"], sents=ss, text=" ".join(S[i]["text"] for i in ss)))
    return out, S


def list_sents(name):
    S = jload(R(name, "sentences.json")); ppl = jload(R(name, "people.json"))["people"]
    for x in S:
        print(f"  {x['i']:<4} {x['s']:7.2f}-{x['e']:7.2f} {ppl.get(x['spk'], {}).get('name', x['spk'])[:14]:14s} {x['text'][:140]}")


def select_ids(name, ids):
    I, S = ideas(name)
    by = {p["k"]: p for p in I}
    out = []
    for k in ids:
        p = by[k]
        if out and out[-1]["spk"] == p["spk"] and p["s"] - out[-1]["e"] < 2.5:          # ideas seguidas de la misma persona: un solo bloque
            out[-1]["sents"] += p["sents"]; out[-1]["e"] = p["e"]; out[-1]["text"] += " " + p["text"]; continue
        out.append(dict(spk=p["spk"], s=p["s"], e=p["e"], sents=list(p["sents"]), text=p["text"]))
    last = out[-1]
    nxt = [s for s in S if s["s"] > last["e"] and s["s"] - last["e"] < 1.2 and s["e"] - s["s"] < 1.5]
    if nxt and re.match(r"bienvenid", norm(nxt[0]["text"])): last["sents"].append(nxt[0]["i"]); last["e"] = nxt[0]["e"]
    return out, S


def select(name, length=150.0, end_card=3.0, breath=0.4):
    """presentación de la anfitriona (hasta la frase que anuncia el tema) + ideas de cada invitado, en orden natural;
       cada persona termina su idea; nada que dependa de una frase anterior que no está; nada durante un paneo de cámara"""
    I, S = ideas(name)
    src = jload(R(name, "source.json")); ppl = jload(R(name, "people.json"))["people"]
    tema = [norm(x) for x in re.split(r"[,;]", src.get("tema", "")) if len(norm(x)) > 2]
    tema_words = {w for x in tema for w in x.split() if len(w) > 3}
    guests = [k for k in ppl if k != "L"]
    last_names = {k: norm(ppl[k]["name"]).split()[-1] for k in guests}
    moving = camera_motion(name)
    budget = length - end_card
    # ideas de menos de 4.5 s ("Ese combustible. Que recibimos.") casi nunca se entienden solas
    C = [p for p in I if not p["filler"] and p["dur"] >= 4.5 and p["spk"] in ppl]

    # palabras y frases del tema pesan según lo raras que son en la charla ("Partido Colorado" está en todas partes, "Causa Republicana" no)
    alltxt = " " + " ".join(norm(x["text"]) for x in S) + " "
    wcount = {}
    for w in alltxt.split(): wcount[w] = wcount.get(w, 0) + 1
    w_word = {w: 1.0 / (1 + wcount.get(w, 0) / 5) for w in tema_words}
    w_phrase = {x: 3.0 / (1 + alltxt.count(" " + x + " ") / 4) for x in tema}
    # el título es la noticia: sus palabras (sin los nombres) por raíz ("SE SUMA" ~ "sumar", "sumarse")
    names = {w for k in ppl for w in norm(ppl[k]["name"]).split()}
    stems = [w[:5] for w in norm((src.get("titulo") or "").replace("|", " ")).split() if len(w) > 3 and w not in names]

    def score(text, dur):
        t = norm(text); words = t.split()
        hits = sum(w_word.get(w, 0) for w in words) + sum(v for x, v in w_phrase.items() if x in t)
        sc = hits / max(20, len(words)) * 40 + 2 * sum(1 for k in guests if last_names[k] in t) + (1.5 if 6 <= dur <= 30 else 0)
        sc += 1.5 * min(4, sum(1 for w in words if any(w.startswith(st) for st in stems)))
        sc += 2.0 * len(STRONG.findall(t)) - 2.5 * len(WEAK.findall(t))
        sc -= 3 * len(re.findall(r"\b(gracias|bienvenid|nobleza)", t))
        if len(words) < 7: sc -= 4                                             # fragmento: no se entiende solo
        if text.strip()[:1].islower(): sc -= 8                                 # empieza a mitad de frase
        if re.search(r"(^|\s)-\w\b|\b\d+\s+-", text): sc -= 15                    # transcripción rota ("Partido 1 -C."): subtítulo y corte inseguros
        return sc
    is_moving = lambda t: any(a < t + 1.0 and b > t - 0.5 for a, b in moving)

    def rare(text):                                                     # palabras con imagen propia ("león", "dormido", "despertar")
        return {w for w in norm(text).split() if len(w) >= 4 and wcount.get(w, 0) <= 4}

    def redundant(p):                                                   # repite la imagen de otro bloque de la misma persona (2 palabras se toleran)
        mine = set()
        for q in chosen:
            if q["spk"] == p["spk"] and q is not p and q.get("k") != p.get("k") or (q.get("k") == p.get("k") and q is not p and not set(q["sents"]) & set(p["sents"])):
                if q["spk"] == p["spk"]: mine |= rare(" ".join(S[i]["text"] for i in q["sents"]))
        return max(0, len(rare(p["text"]) & mine) - 2)
    for p in C:
        p["score"] = score(p["text"], p["dur"])
        p["anaph"] = bool(ANAPH.match(norm(p["text"])))
        p["moving"] = is_moving(p["s"])

    def clean_end(i):                                                   # la frase i cierra: lo que sigue no la continúa
        if S[i]["text"].rstrip()[-1:] not in ".?!": return False
        lw = norm(S[i]["text"]).split()
        if not lw or lw[-1] in DANGLING: return False                   # "Y tratar de." / "En favor del." quedan colgadas
        j = i + 1
        if j >= len(S) or S[j]["spk"] != S[i]["spk"] or S[j]["s"] - S[i]["e"] >= 1.4: return True
        nt = S[j]["text"].strip(); t = norm(nt)
        if S[j]["s"] - S[i]["e"] < 0.35 and (ANAPH.match(t) or len(norm(S[i]["text"]).split()) < 4): return False
        return not (nt[:1].islower() or CONT.match(t) or TIGHT.match(t))

    def free_start(i):                                                  # una frase que puede abrir un fragmento sola
        t = norm(S[i]["text"])
        if S[i]["text"].strip()[:1].islower() or CONT.match(t) or ANAPH.match(t) or FILLER.match(t) or VOCAT.match(t): return False
        if len(t.split()) < 3 or WEAK.search(t) or re.match(r"^bueno\b", t): return False   # "Nos dicen." / "Bueno, algo extraordinario." no abren
        # sin pausa detrás de algo que no es una frase plena ("Ustedes tienen un compromiso." | "Un compromiso serio…",
        # "Es lo que nos trae hoy aquí." | "Junto a ustedes.") = sigue la misma frase
        pv = S[i - 1] if i > 0 else None
        if not pv or pv["spk"] != S[i]["spk"] or S[i]["s"] - pv["e"] >= 0.4: return True
        pt = norm(pv["text"])
        return len(pt.split()) >= 6 and not (ANAPH.match(pt) or CONT.match(pt) or TIGHT.match(pt))

    for p in C:                                                         # se cortó por largo en pleno discurso: depende de la anterior,
        if p.get("cut_len") and not p["anaph"]:                         # salvo que su primera frase abra sola
            p["anaph"] = not free_start(p["sents"][0])

    def window(p, room, min_dur=7.0):
        """la mejor ventana de frases completas de la idea p que entra en 'room' segundos:
           arranca en una frase que se entiende sola y termina en final de frase sin dejar colgada una continuación"""
        best = None; ss = list(p["sents"]); tk = taken()
        while ss[-1] + 1 < len(S) and S[ss[-1] + 1]["spk"] == p["spk"] and S[ss[-1] + 1]["s"] - S[ss[-1]]["e"] < 1.4 \
                and S[ss[-1] + 1]["e"] - p["s"] < 45:                     # el discurso sigue sin pausa: la ventana puede seguirlo
            ss.append(ss[-1] + 1)
        for a in range(len(ss)):
            glued = ss[a] - 1 in tk and S[ss[a] - 1]["spk"] == p["spk"]       # continúa un bloque ya elegido
            if ss[a] in tk or (not glued and a == 0 and (p["anaph"] or WEAK.search(norm(S[ss[0]]["text"])) or re.match(r"^bueno\b", norm(S[ss[0]]["text"])))) or (not glued and a > 0 and not free_start(ss[a])) or is_moving(S[ss[a]]["s"]): continue
            for b in range(a, len(ss)):
                if ss[b] in tk: break
                d = S[ss[b]]["e"] - S[ss[a]]["s"]
                if d > room: break
                if d < min_dur or not clean_end(ss[b]): continue
                text = " ".join(S[i]["text"] for i in ss[a:b + 1])
                sc = score(text, d) + (0.5 if a == 0 else 0) + 0.12 * d       # a igual contenido, aprovechar el lugar
                key = sc - 5 * redundant(dict(spk=p["spk"], k=p["k"], sents=ss[a:b + 1], text=text))
                if os.environ.get("REUNION_DEBUG") == "2": print(f"      win {S[ss[a]]['s']:.1f}-{S[ss[b]]['e']:.1f} sc={sc:.1f} {text[:70]}")
                if best is None or key > best["key"] + 0.01 or (abs(key - best["key"]) <= 0.01 and d > best["dur"]):
                    best = dict(p, key=key, sents=ss[a:b + 1], s=S[ss[a]]["s"], e=S[ss[b]]["e"], dur=d, text=text, score=sc, anaph=a == 0 and p["anaph"])
        return best
    # 1) presentación: desde la primera idea de la anfitriona hasta la frase que nombra a los invitados y el tema
    host = [p for p in C if p["spk"] == "L"]
    chosen = []
    if host:
        intro = dict(host[0]); sents = []
        for i in intro["sents"]:
            sents.append(i)
            t = norm(" ".join(S[j]["text"] for j in sents))
            if all(last_names[k] in t for k in guests) and any(x in t for x in tema) and S[i]["text"].rstrip()[-1:] in ".?!":
                break
        intro.update(sents=sents, e=S[sents[-1]]["e"]); intro["dur"] = intro["e"] - intro["s"]; intro["must"] = True
        chosen.append(intro)
    def trace(step):
        if os.environ.get("REUNION_DEBUG"):
            print(f"   [{step:>3}] " + "  ".join(f"{p['spk']}:{p['s']:.0f}-{p['e']:.0f}{'*' if p.get('must') else ''}" for p in sorted(chosen, key=lambda p: p["s"])), f"= {used():.1f}")
    used = lambda spk=None: sum(p["dur"] + breath for p in chosen if spk is None or p["spk"] == spk)
    taken = lambda: {i for q in chosen for i in q["sents"]}
    # 2) reparto del tiempo: anfitriona ≤ 40 % del total; invitados en proporción a lo que hablaron (mínimo 18 % cada uno)
    talk = {k: sum(p["dur"] for p in C if p["spk"] == k) for k in ppl}
    gtot = sum(talk[k] for k in guests) or 1
    quota = {"L": 0.40 * budget}
    rest = budget - min(used("L"), quota["L"])
    for k in guests: quota[k] = max(0.18 * budget, rest * talk[k] / gtot)
    # protagonista: el invitado que nombra el título (p. ej. "EX DIPUTADO GUSTAVO MUSSI") se lleva la mayor parte del tiempo
    tit = norm((src.get("titulo") or "") + " " + (src.get("tema") or "").split(",")[0])
    prot = next((k for k in guests if last_names[k] in tit), None)
    if prot:
        quota[prot] = max(quota[prot], 0.45 * budget)
        for k in guests:
            if k != prot: quota[k] = max(0.18 * budget, min(quota[k], budget - quota["L"] * 0.75 - quota[prot]))

    def follows(p):                                                 # la frase anterior de la misma persona ya está elegida
        prev = [i for i in range(p["sents"][0] - 1, -1, -1) if S[i]["spk"] == p["spk"]]
        return bool(prev) and prev[0] in taken()

    def ok_base(p):
        if any(p is q or p["k"] == q.get("k") for q in chosen) or set(p["sents"]) & taken() or p["moving"]: return False
        return not p["anaph"] or follows(p)                         # depende de la idea anterior: solo si esa idea está elegida

    def ok_win(p):                                                  # la idea todavía tiene frases sin elegir
        return not p["moving"] and not set(p["sents"]) <= taken()

    def room(spk):
        return min(budget + 3 - used(), quota.get(spk, 0) + 8 - used(spk)) - breath

    def ok(p):
        nxt = p["sents"][-1] + 1
        if not clean_end(p["sents"][-1]) and nxt not in taken(): return False
        return ok_base(p) and used() + p["dur"] + breath <= budget + 3 and used(p["spk"]) + p["dur"] <= quota.get(p["spk"], 0) + 8
    short = length < 90
    if short:
        for k in guests:
            if k != prot: quota[k] = min(quota[k], 0.30 * budget)
    # 3a) el protagonista entra sí o sí: sus mejores ideas hasta su cuota (si la presentación es larga, se acorta ésta)
    if prot:
        reserve = 0 if short else sum(0.18 * budget - 3 for k in guests if k != prot)
        while used(prot) < quota[prot] - 4:                             # de a una: la mejor idea entera o el mejor tramo que entre
            opts, r = [], min(room(prot), budget - reserve - used() - breath)
            for p in C:
                if p["spk"] != prot or p["score"] <= 0: continue
                if ok(p) and p["dur"] <= r: opts.append(p)
                elif ok_win(p) and r >= 7:
                    w = window(p, r)
                    if w: opts.append(w)
            opts = [o for o in opts if o["score"] - 5 * redundant(o) > 2]
            if not opts: break
            chosen.append(max(opts, key=lambda o: o["score"] - 5 * redundant(o)))
        if not any(p["spk"] == prot for p in chosen):
            r = budget + 3 - used() - breath
            ws = [w for w in (window(p, r) for p in C if p["spk"] == prot and not p["moving"]) if w]
            best = max(ws, key=lambda w: w["score"], default=None)
            if best is None:
                best = max([p for p in C if p["spk"] == prot and not p["moving"] and not p["anaph"]], key=lambda p: p["score"], default=None)
            if best:
                chosen.append(best); best["must"] = True
    if os.environ.get("REUNION_DEBUG"):
        for p in C: print(f"      idea #{p['k']} {p['spk']} {p['s']:.0f}-{p['e']:.0f} sc={p['score']:.1f} red={redundant(p)} anaph={p['anaph']} clean={clean_end(p['sents'][-1])}")
    trace("3b")
    # 3b) cada invitado: su conclusión (la última idea con contenido) si se entiende sola (en videos cortos, solo si sobra tiempo)
    for g in guests:
        if g == prot: continue
        lst = [p for p in C if p["spk"] == g and not p["anaph"] and not p["moving"] and p["score"] > 0]
        if lst and ok(lst[-1]) and (not short or used() + lst[-1]["dur"] <= budget): chosen.append(lst[-1])
    trace("3c")
    # 3c) prioridad por persona: protagonista -> anfitriona -> resto
    # 4) el resto por puntaje, varias pasadas (una idea elegida habilita a la que la continúa)
    for _ in range(3):
        for p in sorted(C, key=lambda p: -(p["score"] - 5 * redundant(p))):
            if used() >= budget - 1.5: break
            if redundant(p) and p["score"] - 5 * redundant(p) <= 2: continue
            if ok(p): chosen.append(p)
            elif ok_win(p) and p["score"] > 2 and room(p["spk"]) >= 7:
                w = window(p, room(p["spk"]))
                if w and w["score"] - 5 * redundant(w) > 2: chosen.append(w)
    trace("4b")
    # 4b) mínimo garantizado para cada invitado (≈18 %): si quedó corto, entra su mejor idea y sale la más floja de quien se pasó
    for g in guests:
        if short and g != prot: continue
        while used(g) < 0.18 * budget - 3:
            need = 0.18 * budget + 6 - used(g)
            cand = []
            for p in C:
                if p["spk"] != g or not ok_win(p): continue
                if ok_base(p) and p["dur"] <= need and (clean_end(p["sents"][-1]) or p["sents"][-1] + 1 in taken()): cand.append(p)
                else:
                    w = window(p, max(need, 8))
                    if w: cand.append(w)
            cand = [p for p in cand if p["score"] - 5 * redundant(p) > 0]
            if not cand: break
            chosen.append(max(cand, key=lambda p: p["score"] - 5 * redundant(p)))
            over = [q for q in chosen if not q.get("must") and q["spk"] != g and used(q["spk"]) > quota.get(q["spk"], 0)]
            if used() > budget + 3 and over: chosen.remove(min(over, key=lambda q: q["score"]))
    chosen.sort(key=lambda p: p["s"])
    trace("4c")
    # 4c) arranques débiles de una idea ("Bueno, algo extraordinario.") se sueltan
    def strip_weak():
        for p in chosen:
            while len(p["sents"]) > 1 and not p.get("must"):
                t0 = norm(S[p["sents"][0]]["text"])
                if WEAK.search(t0) or FILLER.match(t0) or re.match(r"^bueno,? algo", t0):
                    p["sents"] = p["sents"][1:]; p["s"] = S[p["sents"][0]]["s"]; p["dur"] = p["e"] - p["s"]
                else: break
    strip_weak()
    trace("5")
    # 5) si sobra, se recorta la idea más larga en un final de frase (nunca la presentación por debajo de su anuncio)
    def trim_tail(p, min_dur=0.0):                                     # saca frases del final hasta un final limpio
        k = len(p["sents"]) - 1
        while k > 0 and not (clean_end(p["sents"][k - 1]) and S[p["sents"][k - 1]]["e"] - p["s"] >= min_dur): k -= 1
        if k == 0 or S[p["sents"][k - 1]]["e"] - p["s"] < 4.0: return False   # nunca dejar un muñón de idea
        p["sents"] = p["sents"][:k]; p["e"] = S[p["sents"][-1]]["e"]; p["dur"] = p["e"] - p["s"]; return True

    def needed_by_next(p):                                              # la idea siguiente elegida continúa a esta (sin pausa): no se le recorta el final
        return any(q is not p and q["spk"] == p["spk"] and 0 <= q["s"] - p["e"] < 2.5 for q in chosen)
    while used() > budget + 3:
        over = used() - budget
        drop = [p for p in chosen if not p.get("must") and not needed_by_next(p) and p["dur"] + breath >= over - 3
                and used(p["spk"]) - p["dur"] >= (0.18 * budget - 3 if p["spk"] != "L" else 0)]
        if drop and over > 8:
            chosen.remove(min(drop, key=lambda p: p["score"])); continue
        cand = [p for p in chosen if len(p["sents"]) > 1 and not p.get("must") and not needed_by_next(p)]
        if not cand:
            rem = [p for p in chosen if not p.get("must")]
            if not rem: break
            chosen.remove(min(rem, key=lambda p: p["score"])); continue
        def tail_weight(p):
            t = norm(S[p["sents"][-1]]["text"]); return 2.0 * len(STRONG.findall(t)) - 2.5 * len(WEAK.findall(t))
        lg = min(cand, key=lambda p: (tail_weight(p), -p["dur"]))
        if not trim_tail(lg): lg["must"] = True                           # no tiene otro final limpio: queda entera
    trace("5a'")
    # 5a') hacer lugar a una idea fuerte que quedó afuera: recortar colas débiles de otras ideas (en finales de frase, ≥ 8 s cada una)
    def tail_w(p):
        t = norm(S[p["sents"][-1]]["text"]); return 2.0 * len(STRONG.findall(t)) - 2.5 * len(WEAK.findall(t))
    for p in sorted(C, key=lambda p: -p["score"]):
        if p["score"] - 5 * redundant(p) < 2 or not ok_base(p): continue
        if not clean_end(p["sents"][-1]) and p["sents"][-1] + 1 not in taken(): continue
        if used(p["spk"]) + p["dur"] > quota.get(p["spk"], 0) + 8: continue
        backup = [(q, list(q["sents"]), q["e"], q["dur"]) for q in chosen]
        while used() + p["dur"] + breath > budget + 3:
            cand = [q for q in chosen if not q.get("must") and len(q["sents"]) > 1 and not needed_by_next(q)
                    and S[q["sents"][-2]]["e"] - q["s"] >= 8 and tail_w(q) <= 0]
            if not cand: break
            q = min(cand, key=lambda q: (tail_w(q), -q["dur"]))
            if not trim_tail(q, 8): break
        if used() + p["dur"] + breath <= budget + 3: chosen.append(p); chosen.sort(key=lambda x: x["s"])
        else:
            for q, ss, e, d in backup: q["sents"], q["e"], q["dur"] = ss, e, d
    trace("5a")
    # 5a) si quedó tiempo libre (por sacar una idea entera), segunda pasada de relleno
    for _ in range(2):
        for p in sorted(C, key=lambda p: -p["score"]):
            if p["score"] - 5 * redundant(p) > 0 and used() + p["dur"] + breath <= budget + 3 and ok(p): chosen.append(p)
            elif budget - used() >= 7 and ok_win(p) and p["score"] > 2 and room(p["spk"]) >= 7:   # el hueco se llena con un tramo
                w = window(p, room(p["spk"]))
                if w and w["score"] > 2: chosen.append(w)
    chosen.sort(key=lambda p: p["s"])
    strip_weak()
    trace("5b")
    # 5b) ideas seguidas de la misma persona (sin pausa larga) van en UN bloque: nunca un corte en medio de "…a sumar. No venimos a restar."
    merged = []
    for p in chosen:
        if merged and merged[-1]["spk"] == p["spk"] and p["s"] - merged[-1]["e"] < 2.5 and p["sents"][0] == merged[-1]["sents"][-1] + 1:
            merged[-1] = dict(merged[-1], sents=merged[-1]["sents"] + p["sents"], e=p["e"]); merged[-1]["dur"] = merged[-1]["e"] - merged[-1]["s"]
        else: merged.append(p)
    chosen = merged
    # 6) cierre: un "Bienvenidos." corto enseguida después de la última idea se suma
    last = chosen[-1]
    nxt = [s for s in S if s["s"] > last["e"] and s["s"] - last["e"] < 1.2 and s["e"] - s["s"] < 1.5]
    if nxt and re.match(r"bienvenid", norm(nxt[0]["text"])): last["sents"] = last["sents"] + [nxt[0]["i"]]; last["e"] = nxt[0]["e"]
    return [dict(spk=p["spk"], s=S[p["sents"][0]]["s"], e=S[p["sents"][-1]]["e"], sents=p["sents"], text=" ".join(S[i]["text"] for i in p["sents"]))
            for p in chosen], S


# =========================================================================================== 3. BORDES VERIFICADOS
def _match(expected, heard):
    if not expected or not heard: return False
    if expected.isdigit() or heard.isdigit(): return expected == heard
    return difflib.SequenceMatcher(None, expected, heard).ratio() >= 0.75


def _gaps(rms, t0, t1, quiet, min_len=0.10):
    """silencios (≥ min_len) entre t0 y t1 -> lista de (inicio, fin) en s"""
    a, b = max(0, int(t0 * 100)), min(len(rms), int(t1 * 100))
    q = rms[a:b] < quiet
    out, i = [], 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]: j += 1
            if (j - i) / 100 >= min_len: out.append(((a + i) / 100, (a + j) / 100))
            i = j
        else: i += 1
    return out


def asr_words(a16, s, e, prompt=None):
    """palabras (con tiempos absolutos) de un tramo oído aislado"""
    pad = 0.8; z = np.zeros(int(pad * 16000), np.float32)
    x = a16[max(0, int(s * 16000)):int(e * 16000)]
    segs, _ = whisper().transcribe(np.concatenate([z, x, z]), language="es", beam_size=5, vad_filter=False, word_timestamps=True,
                                   condition_on_previous_text=False, initial_prompt=prompt)
    return [(norm(w.word), s + w.start - pad, s + w.end - pad) for g in segs for w in g.words if norm(w.word)]


def fix_edges(name, blocks, S, log_lines):
    """inicio: justo antes de la 1.ª palabra y sin restos de otra voz; final: después de la última palabra COMPLETA.
       Se decide OYENDO el tramo aislado: si hay silencio real se corta ahí; si las palabras van pegadas, en el límite que da whisper."""
    a16, _ = read_wav(R(name, "a16.wav")); rms = energy(name)
    floor = float(np.percentile(rms, 8)); quiet = floor + 9
    prompt = jload(R(name, "source.json")).get("prompt")
    for b in blocks:
        first = [norm(w["w"]) for w in S[b["sents"][0]]["words"]][:2]
        last = [norm(w["w"]) for w in S[b["sents"][-1]]["words"]][:b.get("upto")]
        while len(last) > 1 and len(last[-1]) < 2 and not last[-1].isdigit(): last.pop()       # "-C." = basura de la transcripción
        if re.search(r"\b\d+\s+-\w", S[b["sents"][-1]]["text"]):
            while len(last) > 1 and last[-1].isdigit(): last.pop()
        last = last[-2:]
        # ---- inicio
        g = _gaps(rms, b["s"] - 1.2, b["s"] + 0.15, quiet, 0.08)
        st = max(0.0, (g[-1][1] - 0.10) if g else b["s"] - 0.12)
        for it in range(3):
            ws = asr_words(a16, st, st + 2.8, prompt)
            if not ws or _match(first[0], ws[0][0]): break
            hit = next((w for w in ws[1:5] if _match(first[0], w[0])), None)
            if hit:                                                       # sobra voz antes de la primera palabra
                prev_end = max(w[2] for w in ws if w[1] < hit[1])
                g2 = _gaps(rms, prev_end - 0.03, hit[1] + 0.05, quiet, 0.05)
                new = (g2[-1][1] - 0.05) if g2 else hit[1] - 0.03
                log_lines.append(f"  inicio {b['s']:.2f}: sobraba '{ws[0][0]}' antes de '{first[0]}' -> {new:.2f}{'' if g2 else ' (sin silencio: límite de la palabra)'}")
                st = new
            else:                                                         # falta la primera palabra
                g2 = _gaps(rms, st - 1.5, st - 0.02, quiet, 0.08)
                if not g2: break
                st = g2[-1][1] - 0.10; log_lines.append(f"  inicio {b['s']:.2f}: faltaba '{first[0]}' -> {st:.2f}")
        # ---- final
        g = _gaps(rms, b["e"] - 0.1, b["e"] + 1.6, quiet, 0.12)
        en = (g[0][0] + 0.12) if g else b["e"] + 0.2
        tried, retracted = {round(en, 2)}, False
        for it in range(4):
            ws = asr_words(a16, max(st, en - 3.2), en + 0.6, prompt)       # se oye un poco MÁS allá del corte para saber qué sigue
            inside = [w for w in ws if w[1] < en - 0.02]
            if not inside: break
            idx = max((i for i, w in enumerate(inside) if _match(last[-1], w[0])), default=None)
            if idx is None:                                               # la última palabra no está completa dentro del corte
                g2 = _gaps(rms, en + 0.02, en + 1.6, quiet, 0.12)
                if not g2: break
                if en - b["e"] > 0.6: break                                   # no se persigue más de 1 s: la transcripción no coincide
                en = g2[0][0] + 0.12; log_lines.append(f"  final {b['e']:.2f}: '{last[-1]}' estaba cortada -> {en:.2f}"); continue
            w_end = inside[idx][2]
            extra = [w for w in inside[idx + 1:] if w[1] < en - 0.05]
            if extra:                                                     # se coló el comienzo de lo que sigue
                g2 = _gaps(rms, w_end - 0.05, extra[0][1] + 0.05, quiet, 0.05)
                en = (g2[0][0] + 0.08) if g2 else extra[0][1] - 0.02
                retracted = True
                log_lines.append(f"  final {b['e']:.2f}: sobraba '{extra[0][0]}' -> {en:.2f}")
                if round(en, 2) in tried: break
                tried.add(round(en, 2)); continue
            if w_end > en - 0.03 and not retracted:                       # la palabra termina justo en el corte: buscar su silencio
                g2 = _gaps(rms, w_end - 0.05, w_end + 0.8, quiet, 0.08)
                if g2 and g2[0][0] > en: en = g2[0][0] + 0.10; log_lines.append(f"  final {b['e']:.2f}: '{last[-1]}' llegaba al borde -> {en:.2f}"); continue
            break
        b["st"], b["en"] = round(st, 3), round(en, 3)
    return blocks


def internal_cuts(name, b, min_pause=1.0, keep=0.45):
    """dentro de una idea solo se acortan pausas largas (≥ 1.0 s), dejando 0.45 s; nunca se corta voz"""
    rms = energy(name); floor = float(np.percentile(rms, 8))
    g = _gaps(rms, b["st"] + 0.3, b["en"] - 0.3, floor + 9, min_pause)
    pieces, cur = [], b["st"]
    for a, z in g:
        pieces.append([cur, a + keep / 2]); cur = z - keep / 2
    pieces.append([cur, b["en"]])
    return [[int(round(x * FPS)), int(round(y * FPS))] for x, y in pieces if y - x > 0.3]


# =========================================================================================== 4. EDITAR (orquestación)
def edit(name, length=150.0, titulo=None, proj=None, render=True, deliver=True, ids=None, sents=None):
    t0 = time.time()
    src = jload(R(name, "source.json"))
    if titulo and titulo != src.get("titulo"):                          # el título pedido guía la selección (es la noticia) y queda guardado
        src["titulo"] = titulo; jsave(src, R(name, "source.json"))
    ppl = jload(R(name, "people.json"))
    if not ppl.get("approved"): log("AVISO: los nombres no están aprobados (python reunion.py people <fuente> approve)")
    proj = proj or f"reunion_{name}_{int(length)}s"
    pd = os.path.join(PROJECTS, proj); os.makedirs(pd, exist_ok=True)
    lines = []
    blocks, S = select_sents(name, sents) if sents else select_ids(name, ids) if ids else select(name, length)
    lines.append("IDEAS ELEGIDAS:")
    for b in blocks: lines.append(f"  [{b['spk']}] {b['s']:7.2f}-{b['e']:7.2f}  {b['text'][:110]}")
    fix_edges(name, blocks, S, lines)
    TAIL, XF = 12, 12
    segments, frames, out = [], [], 0
    for bi, b in enumerate(blocks):
        pcs = internal_cuts(name, b)
        for k, (fs, fe) in enumerate(pcs):
            segments.append(dict(block=f"b{bi}", speaker=b["spk"], fs=fs, fe=fe, out=out, first=k == 0, last=k == len(pcs) - 1))
            frames += [[f"b{bi}", f, len(segments) - 1, 0] for f in range(fs, fe)]
            out += fe - fs
        frames += [[f"b{bi}", pcs[-1][1] + k, -1, 0] for k in range(TAIL)]
        out += TAIL
    main_end = out
    for i, s in enumerate(segments):
        if s["first"] and i > 0 and segments[i - 1]["speaker"] != s["speaker"]:
            pf = frames[s["out"] - 1]
            for k in range(XF): frames[s["out"] + k][3] = [pf[0], pf[1] + 1 + k, (k + 1) / (XF + 1)]
    edl = dict(fps=FPS, segments=segments, frames=frames, main_end=main_end, total=main_end + 90,
               blocks=[[f"b{i}", b["spk"], b["st"], b["en"]] for i, b in enumerate(blocks)], tail=TAIL, xf=XF)
    jsave(edl, os.path.join(pd, "edl.json"))
    jsave(dict(blocks=blocks), os.path.join(pd, "blocks.json"))
    lines.append(f"DURACIÓN: {edl['total'] / FPS:.1f} s (pedido {length:.0f} s)")
    open(os.path.join(pd, "plan.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines), flush=True)
    if not render: return pd
    import reunion_render as RR
    RR.prepare(name, pd); RR.render(name, pd, titulo or src.get("titulo"))
    rep = qa(name, pd)
    if deliver and rep["ok"]: deliver_files(pd, proj)
    log(f"listo en {time.time() - t0:.0f}s · QA {'OK' if rep['ok'] else 'CON HALLAZGOS'} -> {pd}")
    return pd


# =========================================================================================== 5. CONTROL
def qa(name, pd):
    """bordes oídos en el video FINAL, negros, volumen, duración"""
    video = os.path.join(pd, "video.mp4"); edl = jload(os.path.join(pd, "edl.json")); B = jload(os.path.join(pd, "blocks.json"))["blocks"]
    S = jload(R(name, "sentences.json"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", os.path.join(pd, "final16.wav")], check=True)
    a, _ = read_wav(os.path.join(pd, "final16.wav"))
    prompt = jload(R(name, "source.json")).get("prompt")
    finds = []
    segs = edl["segments"]
    for bi, b in enumerate(B):
        ss = [s for s in segs if s["block"] == f"b{bi}"]
        t0 = ss[0]["out"] / FPS; t1 = (ss[-1]["out"] + ss[-1]["fe"] - ss[-1]["fs"]) / FPS
        first = norm(S[b["sents"][0]]["words"][0]["w"]); last = norm(S[b["sents"][-1]]["words"][:b.get("upto")][-1]["w"])
        head = norm(asr_clip(a, t0, t0 + 2.6, prompt)).split(); tail = norm(asr_clip(a, max(t0, t1 - 2.6), t1 + 0.35, prompt)).split()
        okh = bool(head) and (_match(first, head[0]) or (len(head) > 1 and _match(first, head[1]) and len(head[0]) <= 2))
        okt = bool(tail) and any(_match(last, h) for h in tail[-2:])
        if not okh and bi > 0:                  # tramo corto aislado = whisper alucina ("para más información visite"): se vuelve a oír CON contexto
            ws = asr_words(a, max(0.0, t0 - 2.5), t0 + 3.0, prompt)
            okh = any(_match(first, w[0]) and w[1] - 0.6 < t0 < w[2] + 0.2 for w in ws)   # whisper estira la palabra sobre la pausa previa
            if okh: head = [w[0] for w in ws if w[1] >= t0 - 0.4]
        if not okh: finds.append(dict(kind="INICIO", t=round(t0, 2), expected=first, heard=" ".join(head[:4])))
        if not okt: finds.append(dict(kind="FINAL", t=round(t1, 2), expected=last, heard=" ".join(tail[-4:])))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vf", "blackdetect=d=0.1:pix_th=0.05", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1]); peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
    blacks = re.findall(r"black_start:([\d.]+)", r.stderr)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True).stdout)
    if blacks: finds.append(dict(kind="NEGRO", t=blacks))
    if not -15.5 <= lufs <= -12.5: finds.append(dict(kind="VOLUMEN", lufs=lufs))
    rep = dict(ok=not finds, findings=finds, lufs=lufs, peak=peak, duration=round(dur, 2))
    jsave(rep, os.path.join(pd, "qa.json"))
    log(f"QA: {len(finds)} hallazgos · {dur:.1f}s · {lufs} LUFS · pico {peak} dBFS")
    for f in finds: log("  ", f)
    return rep


def deliver_files(pd, proj):
    import plataforma as PL
    lite = os.path.join(pd, "video_liviano.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(pd, "video.mp4"), *PL.venc_bitrate(6000), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", lite])
    for d in DELIVER_DIRS:
        if os.path.isdir(d):
            shutil.copy(os.path.join(pd, "video.mp4"), os.path.join(d, f"{proj}.mp4"))
            if os.path.exists(lite): shutil.copy(lite, os.path.join(d, f"{proj}_liviano.mp4"))
            log("entregado en", d)


# =========================================================================================== 6. COMPARAR con la edición manual aprobada
def evaluate(name, manual_edl=None):
    S = jload(R(name, "sentences.json"))
    MAN = {"L": [(0, 168)], "S1": [(169, 457)], "S2": [(461, 581)]}            # IMG_4801: Lilian / Mussi / Aarón (verificado a mano)
    ok = tot = 0
    for s in S:
        m = (s["s"] + s["e"]) / 2
        exp = next((k for k, rr in MAN.items() if any(a <= m <= b for a, b in rr)), None)
        if exp is None or s["e"] - s["s"] < 1.0: continue
        tot += 1; ok += s["spk"] == exp
        if s["spk"] != exp: print(f"   ✗ {s['s']:6.1f}s esperado {exp} -> {s['spk']}  {s['text'][:70]}")
    print(f"[eval] quién habla: {ok}/{tot} = {ok / max(1, tot) * 100:.1f}%")
    W_ = jload(R(name, "face_windows.json"))
    REF = {"L": (950, 260), "S1": (990, 340), "S2": (880, 400)}                 # zona de la cara de cada uno (aprox., tras el acercamiento)
    bad = [w for w in W_ if w["spk"] in REF and w["s"] > 182 and np.hypot(w["cx"] - REF[w["spk"]][0], w["cy"] - REF[w["spk"]][1]) > 260]
    print(f"[eval] cara que habla (tras el acercamiento de la cámara): {len([w for w in W_ if w['s'] > 182]) - len(bad)}/{len([w for w in W_ if w['s'] > 182])} ventanas coherentes")
    for w in bad[:10]: print("   ✗", w)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("arg"); ap.add_argument("rest", nargs="*")
    ap.add_argument("--name"); ap.add_argument("--tema", default=""); ap.add_argument("--client", default="lilian")
    ap.add_argument("--length", type=float, default=150); ap.add_argument("--titulo"); ap.add_argument("--proj")
    ap.add_argument("--no-render", action="store_true"); ap.add_argument("--no-deliver", action="store_true")
    ap.add_argument("--ideas", default=None, help="números de idea elegidos por el editor (python reunion.py ideas <fuente>)")
    ap.add_argument("--frases", default=None, help='rangos de frases, cada uno un bloque: "0,25,30-33" (python reunion.py frases <fuente>)')
    a = ap.parse_args()
    if a.cmd == "ingest": ingest(a.arg, a.name, a.tema, a.client)
    elif a.cmd == "people": people_cmd(a.arg, a.rest)
    elif a.cmd == "edit": edit(a.arg, a.length, a.titulo, a.proj, not a.no_render, not a.no_deliver,
                               [int(x) for x in a.ideas.split(",")] if a.ideas else None, a.frases)
    elif a.cmd == "frases": list_sents(a.arg)
    elif a.cmd == "ideas": list_ideas(a.arg)
    elif a.cmd == "eval": evaluate(a.arg)
    elif a.cmd == "voices": voices(a.arg)
    elif a.cmd == "faces": faces(a.arg)
    elif a.cmd == "facewin": face_windows(a.arg)
    elif a.cmd == "qa": qa(a.arg, os.path.join(PROJECTS, a.rest[0]))
