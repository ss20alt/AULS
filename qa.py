# Estudio de edición — QA automático de cada video: mide y compara contra el ADN de las referencias; emite hallazgos con ajustes sugeridos.
#   python qa.py <proyecto>   -> projects/<p>/qa.json + qa.md + qa_sheet.png
import os, sys, json, re, difflib, subprocess
import numpy as np, cv2
from core import FPS, SAFE, W, H
import plan as P
import analyze_refs as AR

STUDIO = os.path.dirname(os.path.abspath(__file__))


def ref_dna():
    allr = json.load(open(os.path.join(STUDIO, "analysis", "all.json"), encoding="utf-8"))
    med = lambda k: float(np.median([r[k] for r in allr if r.get(k) is not None]))
    return dict(face_h_frac=med("face_h_frac"), face_cx=med("face_cx_frac"), face_cy=med("face_cy_frac"), brightness=med("brightness"),
                saturation=med("saturation"), contrast=med("contrast"), lufs=float(np.median([r["audio"]["lufs"] for r in allr if r.get("audio")])))


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    t = r.stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", t); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", t); LRA = re.findall(r"LRA:\s+(-?[\d.]+) LU", t)
    return dict(lufs=float(I[-1]), true_peak=float(TP[-1]), lra=float(LRA[-1]))


def freeze_and_black(path, end_n):
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS)
    prev = None; run = 0; freezes = []; blacks = []; i = 0; lum = []
    while True:
        ok, fr = cap.read()
        if not ok: break
        g = cv2.cvtColor(cv2.resize(fr, (108, 192)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        lum.append(float(g.mean()))
        if prev is not None:
            d = float(np.abs(g - prev).mean())
            if d < 0.12: run += 1
            else:
                if run >= 18: freezes.append((round((i - run) / fps, 2), round(run / fps, 2)))
                run = 0
        if g.mean() < 6: blacks.append(round(i / fps, 2))
        prev = g; i += 1
    if run >= 18: freezes.append((round((i - run) / fps, 2), round(run / fps, 2)))
    cap.release()
    return freezes, blacks, np.array(lum)


def wer_captions(words, hyp, sc_map):
    """fidelidad del texto: palabras de los subtítulos vs lo que oye whisper en el audio ya recortado"""
    out = {}
    for sc, S in sc_map.items():
        ref = [P.norm(w["t"]) for w in words if w["sc"] == int(sc)]
        hy = [P.norm(h["t"]) for h in hyp if S["o0"] - 0.3 <= (h["s"] + h["e"]) / 2 <= S["o1"] + 0.3]
        ref = "".join(r for r in ref if r); hy = "".join(h for h in hy if h)             # a nivel de caracteres: "vende patria" ≡ "vendepatria"
        if len(ref) < 24: continue                                        # escenas de pocas palabras: la métrica no es estable
        sm = difflib.SequenceMatcher(None, ref, hy, autojunk=False)
        out[sc] = round(sm.ratio(), 3)
    return out


def acoustic_referee(voice_path, words, hyp, SC, scenes):
    """para cada escena dudosa: parecido (letras) de lo que oye wav2vec2 con el subtítulo y con el ASR del recorte"""
    import align as A, arbitro as AR2, wave as _w
    import scipy.signal as ss
    w = _w.open(voice_path); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    a16 = ss.resample_poly(a, 1, 3).astype(np.float32)
    proc, model, vocab = A.load_model(); inv = {v: k for k, v in vocab.items()}
    plain = lambda s: AR2._plain(re.sub(r"[^a-záéíóúüñ]", "", s.lower()))
    out = {}
    for sc in scenes:
        v = SC[str(sc)] if str(sc) in SC else SC[sc]
        o0, o1 = v["o0"], v["o1"]
        g = AR2.greedy(a16[int(o0 * 16000):int(o1 * 16000)], o0, proc, model, inv)
        heard = plain("".join(c for c, t in g))
        sub_ = plain("".join(x["t"] for x in words if x["sc"] == int(sc)))
        asr_ = plain("".join(x.get("t", "") for x in hyp if o0 - 0.05 <= x["s"] <= o1 + 0.05))
        s1 = difflib.SequenceMatcher(None, heard, sub_, autojunk=False).ratio()
        s2 = difflib.SequenceMatcher(None, heard, asr_, autojunk=False).ratio()
        out[str(sc)] = dict(subtitulo=round(s1, 2), asr=round(s2, 2), gana="subtítulo" if s1 >= 0.6 and s1 >= s2 else "asr")
    return out


def segunda_opinion(video, rect=None, cada=15):
    """el detector clásico (Haar) pierde caras de perfil, con anteojos o lejanas: antes de dar por perdida/chica la cara se mira
    con YuNet (el mismo de la ingesta). Devuelve tasa de cara, alto mediano en la escala de Haar (calibrado: Haar ≈ 0.95 × YuNet en
    las mismas caras) y, si se pide, el brillo de una zona (la imagen real dentro de un diseño con fondo)."""
    mp = os.path.join(STUDIO, "models", "yunet.onnx")
    det = cv2.FaceDetectorYN.create(mp, "", (540, 960), 0.55, 0.3, 50) if os.path.exists(mp) else None
    cap = cv2.VideoCapture(video); i = n = hit = 0; hs, br = [], []
    while True:
        if i % cada:
            if not cap.grab(): break
            i += 1; continue
        ok, fr = cap.read()
        if not ok: break
        n += 1
        if det is not None:
            _, f = det.detect(cv2.resize(fr, (540, 960)))
            f = [] if f is None else [r for r in f if r[2] >= 12]
            if f: hit += 1; hs.append(max(f, key=lambda r: r[2] * r[3])[3] / 960 * 0.95)
        if rect:
            x, y, w, h = rect
            br.append(float(cv2.cvtColor(fr[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY).mean()))
        i += 1
    cap.release()
    return dict(face_rate=round(hit / max(1, n), 2) if det is not None else None,
                face_h_frac=round(float(np.median(hs)), 3) if hs else None, brillo_zona=round(float(np.mean(br)), 1) if br else None)


def run(name):
    pdir = os.path.join(STUDIO, "projects", name)
    J = lambda *p: os.path.join(pdir, *p)
    video = J(f"{name}.mp4")
    edl = json.load(open(J("edl.json"), encoding="utf-8"))
    words = json.load(open(J("words.json"), encoding="utf-8"))
    SC = json.load(open(J("scenes.json"), encoding="utf-8"))
    hyp = json.load(open(J("hyp.json"), encoding="utf-8")) if os.path.exists(J("hyp.json")) else []
    import build as _b
    cfg = _b.get_cfg(name)
    dna = ref_dna()
    F = []                                                   # hallazgos: (severidad, código, texto, ajuste)
    M = {}

    res, sheet = AR.analyze(video, small=True)                          # UNA pasada (con la placa, a 270×480): métricas + congelados + negros
    M["video"] = {k: res[k] for k in ("dur", "fps", "brightness", "saturation", "contrast", "face_rate", "face_h_frac", "face_cx_frac", "face_cy_frac", "zoom_events", "pan_energy")}
    M["audio"] = loudness(video)
    if "freezes" in res: freezes, blacks = res.pop("freezes"), res.pop("blacks")
    else: freezes, blacks, _ = freeze_and_black(video, edl["end_n"])
    te = json.load(open(J("tramos_estilo.json"))) if os.path.exists(J("tramos_estilo.json")) else {}     # tramos que el estilo declara a propósito
    quietos = te.get("quietos", [])
    freezes = [(t0, d) for t0, d in freezes if not any(a_ - 0.4 <= t0 and t0 + d <= b_ + 0.4 for a_, b_ in quietos)]
    M["freezes"] = freezes; M["blacks"] = blacks

    # --- duración
    target = cfg["target"]
    if abs(res["dur"] - target) > 0.1: F.append(("alta", "DUR", f"duración {res['dur']:.2f}s ≠ objetivo {target}s", "ajustar guion/tarjeta final"))
    # --- audio
    a = M["audio"]
    if not (-15.5 <= a["lufs"] <= -12.5): F.append(("media", "LUFS", f"loudness {a['lufs']} LUFS (referencias ≈ {dna['lufs']:.1f})", "subir/bajar loudnorm I"))
    if a["true_peak"] > -1.0: F.append(("alta", "TP", f"true peak {a['true_peak']} dBFS (> -1)", "bajar TP"))
    mi = J("mix_info.json")
    if os.path.exists(mi):
        mx = json.load(open(mi)); M["mezcla"] = mx
        if mx["dif"] > 21: F.append(("media", "MUSIC_LOW", f"música {mx['dif']} dB bajo la voz (casi inaudible; ideal 14–20)", "subir music_db +3"))
        if mx["dif"] < 13: F.append(("alta", "MUSIC_HIGH", f"música solo {mx['dif']} dB bajo la voz (compite con la voz)", "bajar music_db"))
    # --- congelados / negros (excepto respiración 'pre' de 5 fr y cierre)
    for t0, d in freezes:
        if t0 * FPS < edl["total"] - edl["end_n"] - 1 and d > (2.5 if cfg.get("style") == "call" else 0.7): F.append(("media", "FREEZE", f"imagen casi congelada {d}s desde {t0}s", "revisar zona (cuadro quieto)"))
    if blacks: F.append(("alta", "BLACK", f"cuadros negros en {blacks[:5]}", "revisar transiciones"))
    # --- cara (si Haar duda, segunda opinión con YuNet antes de marcar)
    fh, fcy = res.get("face_h_frac"), res.get("face_cy_frac")
    covered = (sum(c_[4] for c_ in cfg.get("cutaways", [])) + cfg.get("face_hidden_s", 0.0) + sum(b_ - a_ for a_, b_ in te.get("sin_cara", []))
               + edl.get("end_n", 0) / FPS) / max(1.0, res["dur"])        # fotos / gancho desenfocado / placa final: sin cara a propósito
                                                                           # (en un video de 14 s la placa final es el 18 %: daba FACE_LOST)
    zona = te.get("zona_imagen")                                          # estilos con fondo de diseño (datos): la imagen real va en un recuadro
    duda = (fh is not None and fh < dna["face_h_frac"] * 0.80) or res["face_rate"] < 0.80 - covered
    if duda or zona:
        so = segunda_opinion(video, zona); M["video"]["segunda_opinion"] = so
        if duda and so["face_rate"] is not None:
            if so["face_rate"] > res["face_rate"]: res["face_rate"] = so["face_rate"]
            if so["face_h_frac"] and (fh is None or so["face_h_frac"] > fh): fh = so["face_h_frac"]
    if fh is not None:
        if fh < dna["face_h_frac"] * 0.80:
            if cfg.get("zoom_limit"):                                       # más zoom = imagen blanda: se acepta y se avisa
                F.append(("baja", "FACE_SMALL", f"cara pequeña ({fh:.3f} de alto vs ref {dna['face_h_frac']:.3f}) por la resolución del original ({cfg['zoom_limit']})", "pedir el archivo original de la cámara"))
            else: F.append(("media", "FACE_SMALL", f"cara pequeña ({fh:.3f} de alto vs ref {dna['face_h_frac']:.3f})", "subir zoom base +0.06"))
        if fh > dna["face_h_frac"] * 1.6: F.append(("media", "FACE_BIG", f"cara muy grande ({fh:.3f})", "bajar zoom base"))
    M["video"]["cara_tapada_esperada"] = round(covered, 2)
    if res["face_rate"] < 0.80 - covered: F.append(("media", "FACE_LOST", f"cara detectada solo en {res['face_rate'] * 100:.0f}% de muestras (esperado ≥ {100 * (0.80 - covered):.0f}%; ¿tapada por gráficos?)", "revisar cards sobre la cara"))
    # --- ritmo / eventos visuales
    SEGS = [i for i in edl["items"] if i["kind"] == "speech"]
    n_scene = len(set(s["scene"] for s in SEGS)); n_shot = len(set(s["shot"] for s in SEGS))
    M["ritmo"] = dict(escenas=n_scene, tomas=n_shot, tomas_por_min=round(n_shot / (res["dur"] / 60), 1), asl_toma=round((edl["total"] - edl["end_n"]) / FPS / max(1, n_shot), 2))
    if M["ritmo"]["asl_toma"] > 7.0 and cfg.get("style") != "call": F.append(("baja", "PACE_SLOW", f"toma media {M['ritmo']['asl_toma']}s (referencias dinámicas: 4–5s)", "bajar shot_max"))
    # --- subtítulos
    import importlib
    try:
        import build
        ctx = build.Ctx(cfg, pdir)
        ch = ctx.CHUNKS
        cps = [len(" ".join(c["words"])) / max(0.05, c["e"] - c["s"] + c.get("hold", 0.0)) for c in ch]     # tiempo real de lectura
        short = [round(c["s"], 1) for c in ch if c["e"] - c["s"] < 0.30]
        M["subs"] = dict(n=len(ch), cps_med=round(float(np.median(cps)), 1), cps_max=round(float(np.max(cps)), 1), cortos=short[:8])
        if np.max(cps) > 24: F.append(("media", "CPS", f"subtítulo veloz {np.max(cps):.0f} car/s (máx recomendado ≈ 20)", "dividir fragmentos largos"))
        if short: F.append(("baja", "SUB_SHORT", f"{len(short)} subtítulos < 0.30 s en {short[:5]}", "unir fragmentos"))
        sp_frames = sum(s["n"] for s in SEGS)
        cov = sum(min(c["e"], (edl['total'] - edl['end_n']) / FPS) - c["s"] for c in ch) * FPS / max(1, sum(s["n"] for s in SEGS if ctx.SC[s["scene"]]["role"] not in ("H", "Q")))
        M["subs"]["cobertura"] = round(float(cov), 2)
        if cov < 0.85: F.append(("media", "SUB_COV", f"subtítulos cubren {cov * 100:.0f}% del habla", "revisar chunking"))
    except Exception as e:
        F.append(("baja", "QA_ERR", f"no se pudieron analizar subtítulos: {e}", ""))
    # --- fidelidad de texto
    if hyp:
        wr = wer_captions(words, hyp, SC)
        M["texto_fidelidad"] = wr
        low = {sc: r for sc, r in wr.items() if r < 0.80}
        if low:                                                            # desempate: ¿qué oye el modelo acústico, el subtítulo o el ASR del recorte?
            ref = acoustic_referee(J("voice_cut.wav"), words, hyp, SC, low)
            M["texto_desempate"] = ref
        for sc, r in low.items():
            d = (M.get("texto_desempate") or {}).get(str(sc), {})
            if d.get("gana") == "subtítulo": continue                      # el audio confirma el subtítulo: el ASR del recorte se equivocó
            F.append(("media", "TXT", f"escena {sc}: subtítulos vs ASR coinciden {r * 100:.0f}% — revisar glosario/errores de oído", "ver words.json / arbitro.py"))
    # --- cortes: nunca sobre la voz, nunca a mitad de frase
    floor = float(np.percentile(P.R10, 5)) if len(P.R10) else -60.0         # ruido de la sala (acto con parlantes: −28 dB; conferencia: ≈ −50)
    thr_e = max(-28.0, floor + 9.0)
    def _real(i, side):                                   # corte MIENTRAS ella habla: dentro de una palabra suya o sin respiro (< 0.12 s) hasta la siguiente
        f = i["fs"] if side == "in" else i["fe"]; t = f / FPS
        if P.edge_db(f) <= thr_e: return False
        nb = (t - 0.35) if side == "in" else (t + 0.35)
        if not (P.speaker_at(nb) == "L" and P.speaker_at(t) == "L"): return False
        near = [w for w in P.WORDS if t - 3 < w["s"] < t + 3]
        if any(w["s"] + 0.03 < t < w["e"] - 0.03 for w in near): return True
        if side == "out": gap = min([w["s"] - t for w in near if w["s"] >= t - 0.03] or [9])
        else: gap = min([t - w["e"] for w in near if w["e"] <= t + 0.03] or [9])
        return gap < 0.12
    soft = [round(i["out"] / FPS, 1) for i in SEGS if i.get("soft_in") and i.get("ein") and _real(i, "in")] +            [round((i["out"] + i["n"]) / FPS, 1) for i in SEGS if i.get("soft_out") and i.get("eout") and _real(i, "out")]
    interr = [round(i["out"] / FPS, 1) for i in SEGS if i.get("soft_in") and i.get("ein") and not _real(i, "in")] +              [round((i["out"] + i["n"]) / FPS, 1) for i in SEGS if i.get("soft_out") and i.get("eout") and not _real(i, "out")]
    M["cortes_sobre_voz"] = soft; M["cortes_con_fundido_aceptables"] = interr
    if soft: F.append(("media", "CUT_VOICE", f"{len(soft)} cortes caen sobre la voz de la senadora (con fundido): {soft[:6]}", "elegir bloques con pausa"))
    # --- otra voz dentro de una toma de ella: palabra de una frase de periodista, audible y NO superpuesta a su voz
    try:
        import content as _C
        LW = [w for w in P.WORDS if _C.WORD_SPK.get(round(w["s"], 3)) == "L"]
        leak = []
        for i in SEGS:
            if i.get("role") != "A": continue
            a_, b_ = i["fs"] / FPS, i["fe"] / FPS
            for w in P.WORDS:
                if _C.WORD_SPK.get(round(w["s"], 3)) != "R" or not a_ <= (w["s"] + w["e"]) / 2 <= b_: continue
                if w["e"] - w["s"] < 0.10: continue                                         # tiempo desconocido (voz lejana que la alineación no oyó)
                if any(l["s"] < w["e"] and l["e"] > w["s"] for l in LW): continue          # hablan a la vez: no se puede cortar
                if (P.R10[int(w["s"] * 100):int(w["e"] * 100) + 1] > -36).any(): leak.append((round((i["out"] + (w["s"] - a_) * FPS) / FPS, 1), w["t"]))
        M["otra_voz"] = leak
        if leak: F.append(("media", "OTHER_VOICE", f"{len(leak)} palabras de otra voz dentro de tomas de la senadora: {leak[:6]}", "recortar el borde de la toma"))
    except Exception as e:
        F.append(("baja", "QA_ERR", f"no se pudo revisar otras voces: {e}", ""))
    # --- QA visual (contraste, texto sobre la cara, bordes espejados, zona segura, tarjetas que se pierden en el fondo)
    try:
        import qa_visual
        vf = qa_visual.reutilizable(name, cfg, 15)                         # los cuadros son los mismos que revisó la verificación previa
        M["qa_visual"] = "reutilizado de la verificación previa (mismos cuadros)" if vf is not None else "recalculado"
        for f in (vf if vf is not None else qa_visual.run(name, step=15, log=lambda *a: None)): F.append(f)
    except Exception as e:
        F.append(("baja", "QA_ERR", f"no se pudo correr el QA visual: {e}", ""))
    mid = []
    for sc, Sx in SC.items():
        ws = [w["t"] for w in words if w["sc"] == int(sc)]
        if not ws: continue
        w0 = next((w for w in words if w["sc"] == int(sc)), None)
        try:
            import content as _C
            sent = max((s_ for s_ in _C.SENT if s_["s"] <= (w0.get("w0") or 0) + 0.01), key=lambda s_: s_["s"])
            late = (w0.get("w0") or 0) - sent["s"] > 0.7                     # empieza más de 0.7 s después del inicio real de su frase
        except Exception: late = not (ws[0][:1].isupper() or ws[0][:1] in "¿¡")
        if late: mid.append((Sx["sid"], "empieza: " + ws[0]))
        if ws[-1][-1] not in ".?!": mid.append((Sx["sid"], "termina: " + ws[-1]))
    M["frases_incompletas"] = mid
    if mid: F.append(("alta", "MIDSENTENCE", f"escenas que empiezan/terminan a mitad de frase: {mid[:5]}", "usar bloques completos"))
    # --- color
    lb = cfg.get("letterbox")                                             # franjas negras de diseño (documental): se mide solo la imagen
    bright = res["brightness"] * 1920 / (lb[1] - lb[0]) if lb else res["brightness"]
    bz = (M["video"].get("segunda_opinion") or {}).get("brillo_zona")
    if bz is not None: bright = bz                                        # fondo bordó de diseño (datos): cuenta solo el recuadro con la imagen
    M["video"]["brillo_imagen"] = round(bright, 1)
    if bright < 70: F.append(("baja", "DARK", f"imagen oscura (brillo {bright:.1f})", "subir exposición"))
    json.dump(dict(metrics=M, findings=F), open(J("qa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cv2.imwrite(J("qa_sheet.png"), sheet)
    md = [f"# QA {name}", "", "## Métricas", "```", json.dumps(M, ensure_ascii=False, indent=1), "```", "", "## Hallazgos"]
    md += [f"- [{s}] **{c}** {t} → {adj}" for s, c, t, adj in F] or ["- (sin hallazgos)"]
    open(J("qa.md"), "w", encoding="utf-8").write("\n".join(md))
    return M, F


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    M, F = run(sys.argv[1])
    print(json.dumps(M, ensure_ascii=False, indent=1))
    print("HALLAZGOS:")
    for f in F: print(" ", f)
