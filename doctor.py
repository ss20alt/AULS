# Estudio de edición — AUTOCHEQUEO DE LA INSTALACIÓN (para la Mac del equipo o cualquier máquina nueva).
# Verifica que el estudio funciona IGUAL que en la máquina donde se entrenó: dispositivo, ffmpeg, modelos, fuentes, y que los 15 estilos
# dibujan los mismos fotogramas que las referencias (generadas en la máquina original con la NVIDIA).
#   python doctor.py                 -> chequeo completo (≈ 5–15 min en una MacBook Air M3) + informe en tests/doctor_informe.txt
#   python doctor.py --rapido        -> sin transcripción ni comparación de estilos (≈ 1 min)
#   python doctor.py --referencias   -> (solo en la máquina original) genera las referencias de los 15 estilos
#   python doctor.py --comparar-ingesta <fuente>   -> compara una ingesta hecha en esta máquina con la de referencia (lilian_conf_auto)
import os, sys, json, time, subprocess, shutil, importlib, traceback
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO); os.chdir(STUDIO)
TEST = os.path.join(STUDIO, "tests")
REF = os.path.join(TEST, "referencia")
PRUEBA = "_prueba"                                   # proyecto de prueba incluido en el paquete (fuente: conferencia BCP)
TIMES = (8.0, 30.0)
STYLES = ["news", "ink", "report", "headline", "fx", "call", "split", "karaoke", "doc", "tv", "claves", "cita", "editorial", "campana", "podcast", "redes"]
R = []


def check(name, ok, detail="", warn=False):
    R.append(dict(name=name, ok=bool(ok), warn=warn and not ok, detail=str(detail)[:600]))
    mark = "OK " if ok else ("AVISO" if warn else "FALLA")
    print(f"  {mark} {name}" + ("" if ok or not detail else f"\n        {str(detail)[:400]}"), flush=True)


def no_grain():
    import torch
    torch.randn = lambda *a, **k: torch.zeros(*a, **{x: y for x, y in k.items() if x in ("device", "dtype")})


def style_ctx(style, project=PRUEBA):
    """el proyecto de prueba vestido con cada estilo (sin preparar nada nuevo)"""
    import build, autocfg, make_video as MV
    pdir = os.path.join(STUDIO, "projects", project)
    base = json.load(open(os.path.join(pdir, "cfg.json"), encoding="utf-8"))
    cfg = dict(base); cfg.update(MV.STYLE_DEFAULTS[style]); cfg["style"] = style
    for k in ("cutaways", "hits", "headlines", "chapters", "titles", "chips", "hook_text", "red_word", "hook_tag", "beats", "face_hidden_s", "letterbox"):
        cfg.pop(k, None)
    ctx = build.Ctx(cfg, pdir)
    autocfg.enrich_beats(cfg, ctx)
    if style == "cita": cfg["face_hidden_s"] = round(ctx.hook_end, 2)
    ctx.cam.zoom_mul = cfg.get("zoom_mul", 1.0)
    return cfg, ctx


def render_style_frames(style):
    import core
    cfg, ctx = style_ctx(style)
    S = importlib.import_module("styles." + style).Style(ctx); S.setup()
    out = {}
    for t in TIMES:
        n = int(round(t * 30)); it = ctx.item_at(n)
        if it["kind"] == "speech" and getattr(S, "uses_video", True):
            i = ctx._idx[id(it)]; rd = core.Reader(ctx.selects, ctx.SEL0[i] + (n - it["out"])); fr = S.compose(n, it, rd); rd.close()
        else: fr = S.compose(n, it, None)
        out[t] = core.to_np(fr)
    if hasattr(S, "cp"): S.cp.close()
    return out


def make_references():
    import cv2
    no_grain()
    os.makedirs(REF, exist_ok=True)
    for st in STYLES:
        fr = render_style_frames(st)
        for t, im in fr.items(): cv2.imwrite(os.path.join(REF, f"{st}_{t:04.1f}.png"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
        print("referencia", st, flush=True)
    import plataforma as PL
    json.dump(dict(maquina=PL.report(), fecha=time.strftime("%Y-%m-%d %H:%M"), tiempos=TIMES), open(os.path.join(REF, "origen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run(fast=False):
    t0 = time.time()
    print("== 1. máquina", flush=True)
    import plataforma as PL
    rep = PL.report()
    print("  " + json.dumps(rep, ensure_ascii=False))
    check(f"dispositivo de cálculo: {PL.DEVICE}", PL.DEVICE in ("cuda", "mps"),
          "sin aceleración: funciona pero mucho más lento (en una Mac con Apple Silicon debería decir 'mps')", warn=True)
    check("ffmpeg instalado", shutil.which("ffmpeg") and shutil.which("ffprobe"), "instalar: brew install ffmpeg")
    check("ffmpeg con zscale (HDR del iPhone -> SDR)", rep.get("zscale"), "el ffmpeg de Homebrew lo trae; si falta: brew reinstall ffmpeg")
    check(f"codificador de video: {PL.ENCODER}", PL.ENCODER in ("nvenc", "videotoolbox"), "usa x264 por software (funciona, más lento)", warn=True)
    try:
        fc = os.path.join(TEST, "_fc.txt"); open(fc, "w").write("[0:v]null[o]")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.2", "-/filter_complex", fc, "-map", "[o]",
                            "-f", "null", "-"], capture_output=True, text=True)
        check("ffmpeg acepta -/filter_complex (versión ≥ 7)", r.returncode == 0, r.stderr[-300:])
    except Exception as e: check("ffmpeg acepta -/filter_complex (versión ≥ 7)", False, e)

    print("== 2. librerías y modelos", flush=True)
    for mod in ("torch", "numpy", "cv2", "scipy", "PIL", "faster_whisper", "transformers"):
        try: importlib.import_module(mod); check(f"python: {mod}", True)
        except Exception as e: check(f"python: {mod}", False, e)
    for m in ("wav2vec2-large-xlsr-53-spanish", "wavlm-base-plus-sv"):
        check(f"modelo {m}", os.path.isdir(os.path.join(STUDIO, "models", m)) and os.listdir(os.path.join(STUDIO, "models", m)),
              "falta: python models/download_models.py")
    try:
        from faster_whisper.utils import download_model
        download_model("large-v3", local_files_only=True); check("modelo whisper large-v3 descargado", True)
    except Exception as e: check("modelo whisper large-v3 descargado", False, "falta: python models/download_models.py  (" + str(e)[:120] + ")")

    print("== 3. fuentes y datos de Lilian", flush=True)
    for f in ("georgia", "georgiab", "georgiai", "georgiaz"):
        check(f"fuente {f}", PL.has_font(f), f"no se encontró; se usa {os.path.basename(PL.sysfont(f))} (el diseño cambia un poco)", warn=True)
    check("fuente del @ (Bahnschrift en Windows / DIN Alternate en Mac)", PL.has_font("bahnschrift"), "se usa Montserrat", warn=True)
    for p in ("clients/lilian.json", "clients/lilian_voiceprint.npy", "sources/lilian_conferencia_bcp/source.json", f"projects/{PRUEBA}/selects.mp4"):
        check(f"archivo {p}", os.path.exists(os.path.join(STUDIO, p)))

    print("== 4. banco de pruebas (rápido)", flush=True)
    r = subprocess.run([sys.executable, "regress.py", "--fast"], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    last = [l for l in r.stdout.splitlines() if "pruebas OK" in l]
    fails = [l.strip() for l in r.stdout.splitlines() if "FALLA" in l]
    check("banco de pruebas: " + (last[-1].strip() if last else "no terminó"), r.returncode == 0, fails[:6] or r.stderr[-400:])

    if not fast:
        print("== 5. los 15 estilos dibujan igual que en la máquina original", flush=True)
        import numpy as np, cv2
        no_grain()
        worst = []
        t_c = time.time(); nfr = 0
        for st in STYLES:
            try:
                fr = render_style_frames(st); nfr += len(fr)
                diffs = []
                for t, im in fr.items():
                    ref = cv2.imread(os.path.join(REF, f"{st}_{t:04.1f}.png"))
                    if ref is None: diffs.append(("sin referencia", 0)); continue
                    d = np.abs(im.astype(int) - cv2.cvtColor(ref, cv2.COLOR_BGR2RGB).astype(int))
                    mean, pct = float(d.mean()), float((d.max(-1) > 24).mean() * 100)
                    diffs.append((round(mean, 2), round(pct, 2)))
                    if mean > 2.5 or pct > 1.0:
                        os.makedirs(os.path.join(TEST, "diferencias"), exist_ok=True)
                        side = np.hstack([cv2.cvtColor(im, cv2.COLOR_RGB2BGR), ref, (np.clip(d * 4, 0, 255)).astype(np.uint8)[..., ::-1]])
                        cv2.imwrite(os.path.join(TEST, "diferencias", f"{st}_{t:04.1f}.png"), cv2.resize(side, None, fx=0.4, fy=0.4))
                ok = all(isinstance(x[0], float) and x[0] <= 2.5 and x[1] <= 1.0 for x in diffs)
                close = all(isinstance(x[0], float) and x[0] <= 4.0 and x[1] <= 4.0 for x in diffs)    # p. ej. otra versión de Georgia en la Mac
                if ok or not close:
                    check(f"estilo {st}: diferencia media / % píxeles distintos {diffs}", ok, "ver tests/diferencias/ (yo | referencia | diferencia ×4)")
                else:
                    check(f"estilo {st}: diferencia pequeña {diffs} (probablemente la versión de una tipografía)", False,
                          "mirar tests/diferencias/: si solo cambian letras, está bien", warn=True)
            except Exception as e:
                check(f"estilo {st}: dibuja sin errores", False, traceback.format_exc()[-500:])
        fps_c = nfr / max(1e-6, time.time() - t_c)

        print("== 6. velocidad (estimación de tiempos)", flush=True)
        import core
        cfg, ctx = style_ctx("news")
        S = importlib.import_module("styles.news").Style(ctx); S.setup()
        rd = core.Reader(ctx.selects); t1 = time.time(); N = 90
        for n in range(N): S.compose(n, ctx.item_at(n), rd)
        rd.close(); fps = N / (time.time() - t1)
        mins = 1800 / fps / 60
        check(f"composición: {fps:.1f} fotogramas/s → render de 1 min ≈ {mins:.0f} min (más preparación y QA)", fps >= 2.0,
              "muy lento: revisar que diga 'mps' y que la Mac no esté en ahorro de energía", warn=True)

        print("== 7. transcripción y alineación (modelos de voz)", flush=True)
        try:
            import plan as P, align as A
            import scipy.signal as ss, wave
            w = wave.open(P.SRC["voice"]); sr = w.getframerate(); w.setpos(int(78.8 * sr))
            a = np.frombuffer(w.readframes(int(4.2 * sr)), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
            a16 = ss.resample_poly(a, 1, sr // 16000).astype(np.float32)
            t1 = time.time(); m = PL.whisper_model("large-v3")
            segs, _ = m.transcribe(a16, language="es", word_timestamps=True, beam_size=5)
            txt = " ".join(s.text for s in segs).lower(); dt = time.time() - t1
            check(f"whisper oye «no hay ninguna crisis… intervención» ({dt:.0f}s): «{txt.strip()[:60]}»", "crisis" in txt and "interven" in txt)
            proc, model, vocab = A.load_model()
            res = A.align_segment(a16, ["No,", "no", "hay", "ninguna", "crisis.", "No", "hay", "intervención."], 78.8, proc, model, vocab)
            ref = [w_ for w_ in P.WORDS if 79.0 < w_["s"] < 83.2]
            ok = all(r_ is not None for r_ in res) and len(ref) >= 8 and abs(res[4][1] - ref[4]["e"]) < 0.12
            check(f"alineación: «crisis» termina en {res[4][1]:.2f}s (referencia {ref[4]['e']:.2f}s)" if ok else "alineación de palabras", ok, (res, [(x['t'], x['e']) for x in ref[:8]]))
        except Exception as e:
            check("transcripción y alineación", False, traceback.format_exc()[-500:])

        print("== 8. codificar un video", flush=True)
        try:
            import core, numpy as np
            out = os.path.join(TEST, "_prueba_codec.mp4")
            wav = os.path.join(STUDIO, "projects", PRUEBA, "voice_cut.wav")
            enc = core.start_encoder(out, wav, 1.0, cq=18)
            for n in range(30): enc.stdin.write(np.full((1920, 1080, 3), (n * 8) % 255, np.uint8).tobytes())
            enc.stdin.close(); enc.wait()
            dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
            check(f"codificación H.264 + AAC ({PL.ENCODER}) · duración {dur}s", dur and abs(float(dur) - 1.0) < 0.1)
        except Exception as e:
            check("codificación de video", False, traceback.format_exc()[-400:])

    n_ok = sum(r_["ok"] for r_ in R); n_warn = sum(r_["warn"] for r_ in R); n_fail = len(R) - n_ok - n_warn
    verdict = "LISTO: funciona igual que en la máquina original" if n_fail == 0 else "HAY PROBLEMAS: ver las líneas FALLA"
    lines = [f"AUTOCHEQUEO DEL ESTUDIO — {time.strftime('%Y-%m-%d %H:%M')} — {verdict}", json.dumps(rep, ensure_ascii=False), ""]
    lines += [f"{'OK ' if r_['ok'] else ('AVISO' if r_['warn'] else 'FALLA')} {r_['name']}" + ("" if r_["ok"] else f"\n      {r_['detail']}") for r_ in R]
    lines += ["", f"{n_ok} OK · {n_warn} avisos · {n_fail} fallas · {time.time() - t0:.0f}s"]
    os.makedirs(TEST, exist_ok=True)
    open(os.path.join(TEST, "doctor_informe.txt"), "w", encoding="utf-8").write("\n".join(lines))
    print("\n" + verdict + f"  ({n_ok} OK · {n_warn} avisos · {n_fail} fallas · {time.time() - t0:.0f}s) → tests/doctor_informe.txt")
    return n_fail == 0


def compare_ingest(name, ref=None):
    """la ingesta del video bruto en esta máquina vs. la de referencia (misma fuente IMG_4572.MOV, ingestada en la máquina original)"""
    import numpy as np, difflib
    A = os.path.join(STUDIO, "sources", name)
    B = ref or (os.path.join(TEST, "ingesta_referencia") if os.path.isdir(os.path.join(TEST, "ingesta_referencia")) else os.path.join(STUDIO, "sources", "lilian_conf_auto"))
    ta = [w["w"].strip() for sg in json.load(open(os.path.join(A, "transcript.json"), encoding="utf-8")) for w in sg["words"]]
    tb = [w["w"].strip() for sg in json.load(open(os.path.join(B, "transcript.json"), encoding="utf-8")) for w in sg["words"]]
    sim = difflib.SequenceMatcher(None, " ".join(ta).lower(), " ".join(tb).lower(), autojunk=False).ratio()
    check(f"transcripción parecida a la de referencia: {sim * 100:.1f}% ({len(ta)} vs {len(tb)} palabras)", sim >= 0.90)
    fa, fb = np.load(os.path.join(A, "face.npy")), np.load(os.path.join(B, "face.npy"))
    n = min(len(fa), len(fb)); d = np.abs(fa[:n, :2] - fb[:n, :2]); d = d[np.isfinite(d).all(1)]
    check(f"seguimiento de la cara: diferencia mediana {np.median(d):.1f} px", np.median(d) < 6)
    sa, sb = json.load(open(os.path.join(A, "source.json"), encoding="utf-8")), json.load(open(os.path.join(B, "source.json"), encoding="utf-8"))
    tot = lambda rs: sum(b - a for a, b, *_ in rs)
    inter = sum(max(0, min(b1, b2) - max(a1, a2)) for a1, b1, *_ in sa.get("reporter", []) for a2, b2, *_ in sb.get("reporter", []))
    j = inter / max(1e-6, tot(sa.get("reporter", [])) + tot(sb.get("reporter", [])) - inter)
    check(f"voces de periodistas: coincidencia {j * 100:.0f}% con la referencia", j >= 0.75)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if "--referencias" in a: make_references()
    elif "--comparar-ingesta" in a: compare_ingest(a[a.index("--comparar-ingesta") + 1])
    else: sys.exit(0 if run(fast="--rapido" in a) else 1)
