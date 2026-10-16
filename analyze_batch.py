# Estudio de edición — análisis de una TANDA de videos (referencias editadas o brutos nuevos).
# Por video: ADN cuantitativo de analyze_refs (cortes, movimiento, color, cara, audio), transcripción con tiempos por palabra,
# nivel de fondo entre palabras (¿hay música bajo la voz?), hoja grande de fotogramas para leer textos/gráficos.
# Para los brutos, además: a qué referencia editada corresponde cada tramo (frases en común) -> cómo se editó de verdad.
#   python analyze_batch.py refs  <carpeta> <tag> [--desde "AAAA-MM-DD HH:MM"] [--prefijo N]   -> analysis/<tag>/T01.json, …
#   python analyze_batch.py raw   <carpeta> <tag>      -> analysis/<tag>/B01.json, B01_sheet.jpg, B01_words.json, index.json
#   python analyze_batch.py match <tag_refs> <tag_raw>  -> analysis/<tag_raw>/match.json (bruto -> referencia, tramos)
import os, sys, json, subprocess, hashlib, re, difflib
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
VID = (".mp4", ".mov", ".m4v", ".mkv")


def norm(t):
    t = t.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"): t = t.replace(a, b)
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", p],
                                  capture_output=True, text=True, encoding="utf-8").stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    rot = next((sd.get("rotation") for sd in v.get("side_data_list", []) if "rotation" in sd), 0) or 0
    w, h = v.get("width"), v.get("height")
    sar = v.get("sample_aspect_ratio") or "1:1"                     # DJI: 9:16 guardado "aplastado" en 1728×1080 (SAR 45:128)
    sn, sd = (int(x) for x in sar.split(":")) if ":" in sar and "0" not in sar.split(":") else (1, 1)
    if (sn, sd) != (1, 1): w = int(round(w * sn / sd / 2)) * 2
    if abs(rot) == 90: w, h = h, w
    n, d = v.get("avg_frame_rate", "0/1").split("/")
    return dict(dur=float(j["format"]["duration"]), w=w, h=h, rot=rot, fps=round(float(n) / float(d), 2) if float(d) else 0,
                codec=v.get("codec_name"), transfer=v.get("color_transfer"), audio=any(s["codec_type"] == "audio" for s in j["streams"]))


def audio16(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768


_WM = {}
def whisper():
    if "m" not in _WM:
        import plataforma as PL
        _WM["m"] = PL.whisper_model("large-v3")
    return _WM["m"]


def transcribe(a, prompt=None):
    segs, info = whisper().transcribe(a, language="es", beam_size=5, word_timestamps=True, vad_filter=True,
                                      condition_on_previous_text=False, initial_prompt=prompt)
    words, sents = [], []
    for s in segs:
        ws = [dict(w=w.word.strip(), s=round(w.start, 2), e=round(w.end, 2)) for w in (s.words or []) if w.word.strip()]
        words += ws
        if ws: sents.append(dict(s=ws[0]["s"], e=ws[-1]["e"], text=s.text.strip()))
    return words, sents


def bed_level(a, words):
    """nivel (dBFS) del audio ENTRE palabras (huecos ≥ 0.25 s) vs. durante la voz: con música de fondo los huecos no caen a silencio"""
    if len(a) == 0: return None
    hop = 160; n = len(a) // hop
    db = 20 * np.log10(np.sqrt((a[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    sp = np.zeros(n, bool)
    for w in words: sp[int(w["s"] * 100):int(w["e"] * 100) + 1] = True
    gaps = []
    run = 0
    for i in range(n):
        if not sp[i]: run += 1
        else:
            if run >= 25: gaps.append(db[i - run + 5:i - 5])
            run = 0
    g = np.concatenate(gaps) if gaps else np.array([])
    voice = float(np.percentile(db[sp], 70)) if sp.any() else None
    gap = float(np.median(g)) if len(g) > 50 else None
    # música: hueco "lleno" (> -50 dB) y parejo; voz sola: hueco cerca del ruido de fondo
    return dict(voice_db=round(voice, 1) if voice is not None else None, gap_db=round(gap, 1) if gap is not None else None,
                gap_n=len(gaps), music=bool(gap is not None and voice is not None and gap > -48 and voice - gap < 22))


def big_sheet(p, info, n=24, cols=6, tw=216):
    """n fotogramas parejos, con el segundo impreso, para LEER textos y gráficos"""
    th = int(round(tw * info["h"] / info["w"]))
    tiles = []
    for k in range(n):
        t = info["dur"] * (k + 0.5) / n
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", "-vf", f"scale={tw}:{th}",
                            "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
        fr = np.frombuffer(r.stdout, np.uint8)
        fr = fr.reshape(th, tw, 3).copy() if fr.size == th * tw * 3 else np.zeros((th, tw, 3), np.uint8)
        cv2.rectangle(fr, (0, 0), (58, 18), (0, 0, 0), -1)
        cv2.putText(fr, f"{t:5.1f}s", (2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        tiles.append(fr)
    while len(tiles) % cols: tiles.append(np.zeros_like(tiles[0]))
    return np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)])


def run(kind, folder, tag, desde=None, prefix=None):
    """desde = "AAAA-MM-DD HH:MM": solo los archivos descargados/modificados desde ese momento (tandas nuevas en la misma carpeta)"""
    import analyze_refs as AR, datetime
    out = os.path.join(HERE, "analysis", tag); os.makedirs(out, exist_ok=True)
    files, seen = [], {}
    t_min = datetime.datetime.strptime(desde, "%Y-%m-%d %H:%M").timestamp() if desde else None
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(VID): continue
        p = os.path.join(folder, f)
        if t_min is not None and os.path.getmtime(p) < t_min: continue
        h = hashlib.md5(open(p, "rb").read(4 << 20)).hexdigest() + str(os.path.getsize(p))
        if h in seen: print("duplicado:", f, "=", seen[h], flush=True); continue
        seen[h] = f; files.append(p)
    idx = []
    for k, p in enumerate(files):
        vid = (prefix or ("T" if kind == "refs" else "B")) + f"{k + 1:02d}"
        info = probe(p); info.update(id=vid, file=os.path.basename(p), path=p)
        print(vid, info["file"], f"{info['dur']:.1f}s", flush=True)
        jp = os.path.join(out, vid + ".json")
        if not os.path.exists(jp):
            try:
                if kind == "refs":
                    res, sheet = AR.analyze(p); res.pop("zone_motion", None)
                    cv2.imwrite(os.path.join(out, vid + "_dna.jpg"), sheet)
                else: res = {}
            except Exception as e: res = dict(error=repr(e))
            a = audio16(p) if info["audio"] else np.zeros(0, np.float32)
            words, sents = transcribe(a) if len(a) > 16000 else ([], [])
            res.update(info=info, bed=bed_level(a, words), n_words=len(words),
                       wpm=round(len(words) / max(1e-6, (words[-1]["e"] - words[0]["s"]) / 60), 1) if len(words) > 2 else None,
                       speech_start=words[0]["s"] if words else None, speech_end=words[-1]["e"] if words else None)
            json.dump(dict(words=words, sents=sents), open(os.path.join(out, vid + "_words.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            cv2.imwrite(os.path.join(out, vid + "_sheet.jpg"), big_sheet(p, info), [cv2.IMWRITE_JPEG_QUALITY, 88])
            json.dump(res, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        res = json.load(open(jp, encoding="utf-8"))
        idx.append(dict(id=vid, file=info["file"], dur=round(info["dur"], 1), size=f"{info['w']}x{info['h']}", fps=info["fps"],
                        transfer=info["transfer"], cuts_per_min=res.get("cuts_per_min"), music=(res.get("bed") or {}).get("music"),
                        wpm=res.get("wpm"), n_words=res.get("n_words")))
        print("  ", {k_: v for k_, v in idx[-1].items() if k_ not in ("file",)}, flush=True)
    json.dump(idx, open(os.path.join(out, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def match(tag_refs, tag_raw, n=4):
    """frases del bruto que aparecen en una referencia editada (n palabras seguidas iguales) -> tramos usados y cómo se cortaron"""
    A = os.path.join(HERE, "analysis")
    refs = {f[:3]: json.load(open(os.path.join(A, tag_refs, f), encoding="utf-8"))["words"]
            for f in sorted(os.listdir(os.path.join(A, tag_refs))) if f.endswith("_words.json")}
    out = {}
    for f in sorted(os.listdir(os.path.join(A, tag_raw))):
        if not f.endswith("_words.json"): continue
        bw = json.load(open(os.path.join(A, tag_raw, f), encoding="utf-8"))["words"]
        if len(bw) < n: continue
        bt = [norm(w["w"]) for w in bw]
        grams = {}
        for i in range(len(bt) - n + 1): grams.setdefault(tuple(bt[i:i + n]), []).append(i)
        for rid, rw in refs.items():
            rt = [norm(w["w"]) for w in rw]
            hits = []
            for j in range(len(rt) - n + 1):
                for i in grams.get(tuple(rt[j:j + n]), []): hits.append((i, j))
            if len(hits) < 3: continue
            # tramos: secuencias donde bruto y referencia avanzan juntos
            hits.sort(key=lambda x: x[1]); spans = []
            for i, j in hits:
                if spans and 0 <= j - spans[-1]["rj1"] <= 2 and 0 <= i - spans[-1]["bi1"] <= 6:
                    spans[-1].update(bi1=i, rj1=j)
                else: spans.append(dict(bi0=i, bi1=i, rj0=j, rj1=j))
            spans = [s for s in spans if s["rj1"] - s["rj0"] >= 2]
            if not spans: continue
            cov = sum(s["rj1"] - s["rj0"] + n for s in spans) / max(1, len(rt))
            out.setdefault(f[:3], []).append(dict(ref=rid, coverage_of_ref=round(cov, 2), spans=[
                dict(raw_s=bw[s["bi0"]]["s"], raw_e=bw[min(len(bw) - 1, s["bi1"] + n - 1)]["e"], ref_s=rw[s["rj0"]]["s"],
                     ref_e=rw[min(len(rw) - 1, s["rj1"] + n - 1)]["e"],
                     text=" ".join(w["w"] for w in rw[s["rj0"]:s["rj1"] + n])[:160]) for s in spans]))
    json.dump(out, open(os.path.join(A, tag_raw, "match.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for b, ms in out.items():
        for m in sorted(ms, key=lambda m: -m["coverage_of_ref"]):
            print(b, "->", m["ref"], f"cubre {m['coverage_of_ref'] * 100:.0f}% de la referencia, {len(m['spans'])} tramos")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd in ("refs", "raw"):
        opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
        run(cmd, sys.argv[2], sys.argv[3], desde=opt("--desde"), prefix=opt("--prefijo"))
    elif cmd == "match": match(sys.argv[2], sys.argv[3])
