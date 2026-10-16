# Estudio de edición — CORRECCIONES DEL CLIENTE (punto 7): "en el 0:43 dice 'me trató de sicaria'" -> arreglo permanente + caso de prueba.
# El minuto que marca el cliente es del VIDEO ENTREGADO; se traduce al tiempo de la fuente con el EDL del proyecto.
#   python feedback.py add <proyecto> <m:ss> "<nota>"   -> registra el caso, aplica la corrección y lo agrega al banco de pruebas
#   python feedback.py list [fuente]                    -> casos registrados
# Tipos de nota que se entienden solos:
#   texto:    dice 'texto correcto'   (opcional: no 'texto mal')       -> fixes: texto re-alineado con el audio
#   corte:    "cortó / se come / falta el final / corta la palabra"   -> nocut: zona donde no se puede cortar
#   hablante: "es el periodista / no es ella / otra voz"               -> speaker_fix R ·  "es ella / es Lilian" -> speaker_fix L
import os, sys, json, re, time, difflib, unicodedata

STUDIO = os.path.dirname(os.path.abspath(__file__))
FPS = 30


def parse_t(s):
    p = [float(x) for x in s.replace(",", ".").split(":")]
    return p[0] * 60 + p[1] if len(p) == 2 else p[0]


def deacc(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def norm(s): return re.sub(r"[^a-zñ0-9 ]", "", deacc(s)).split()


def project_source(proj):
    pdir = os.path.join(STUDIO, "projects", proj)
    cfg = json.load(open(os.path.join(pdir, "cfg.json"), encoding="utf-8"))
    src = cfg.get("source") or (proj.split("__", 1)[1] if "__" in proj else "lilian_conferencia_bcp")
    return pdir, src


def out_to_src(edl, t_out):
    """segundo del video entregado -> segundo de la fuente (o None si cae en una tarjeta)"""
    f = t_out * FPS
    best = None
    for it in edl["items"]:
        if it["kind"] != "speech": continue
        a = it["out"] + it.get("pre", 0); b = a + it["n"]
        if a <= f < b: return (it["fs"] + (f - a)) / FPS, it
        d = min(abs(f - a), abs(f - b))
        if best is None or d < best[0]: best = (d, it, (it["fs"] if abs(f - a) < abs(f - b) else it["fe"]) / FPS)
    return (best[2], best[1]) if best and best[0] <= 0.7 * FPS else (None, None)


def classify(note):
    n = deacc(note)
    if re.search(r"\bdice\b|\bdeber[ií]a decir\b|\bsubt[ií]tulo\b|\bescrib|['\"“”‘’«»]", n): return "texto"
    if re.search(r"periodista|no es ella|otra voz|otra persona", n): return "hablante_R"
    if re.search(r"\bes ella\b|\bes lilian\b|\bhabla ella\b", n): return "hablante_L"
    if re.search(r"cort|se come|falta|incomplet|mocha|a medias", n): return "corte"
    return "otro"


def quoted(note):
    q = re.findall(r"['\"“”‘’«»]([^'\"“”‘’«»]+)['\"“”‘’«»]", note)
    return q


def realign(P, text, t0, t1):
    """tiempos de cada palabra del texto corregido dentro de [t0, t1] (alineación forzada CTC)"""
    import wave, numpy as np, scipy.signal as ss, align as A
    w = wave.open(P.SRC["voice"]); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    a16 = ss.resample_poly(a, 1, 3).astype(np.float32)
    proc, model, vocab = A.load_model()
    words = text.split()
    s0, e0 = max(0.0, t0 - 0.03), t1 + 0.15
    res = A.align_segment(a16[int(s0 * 16000):int(e0 * 16000)], [A.spoken(x) for x in words], s0, proc, model, vocab)
    out, prev = [], t0
    for x, r in zip(words, res):
        s, e = (r if r else (prev, prev + 0.2))
        s = max(prev, s - 0.08); e = max(e, s + 0.04)                    # mismo sesgo de inicio CTC que plan.load_words
        out.append([x, round(s, 3), round(e, 3)]); prev = e
    return out


def add(proj, t_str, note, source=None):
    pdir, src0 = project_source(proj)
    source = source or src0
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import plan as P
    edl = json.load(open(os.path.join(pdir, "edl.json"), encoding="utf-8"))
    t_out = parse_t(t_str)
    t_src, it = out_to_src(edl, t_out)
    if t_src is None:
        print(f"[feedback] {t_str} cae en una tarjeta (no hay fuente detrás): queda registrado sin corrección automática")
    kind = classify(note)
    sp = os.path.join(P.SRC["dir"], "source.json"); sj = json.load(open(sp, encoding="utf-8"))
    case = dict(id=f"c{int(time.time())}", date=time.strftime("%Y-%m-%d %H:%M"), project=proj, t_out=t_out, t_src=t_src, kind=kind, note=note, applied=None)
    if t_src is not None:
        near = [w for w in P.WORDS if abs((w["s"] + w["e"]) / 2 - t_src) < 4.0]
        case["context"] = " ".join(w["t"] for w in near)
    if kind == "texto" and t_src is not None:
        q = quoted(note)
        if not q:
            print("[feedback] no encontré el texto correcto entre comillas: queda registrado como 'otro'"); case["kind"] = kind = "otro"
        else:
            good = q[0]
            ng = norm(good)
            W = [w for w in P.WORDS if abs((w["s"] + w["e"]) / 2 - t_src) < 6.0]
            best = None                                                    # ventana de palabras de la fuente que más se parece al texto correcto
            for n in range(max(1, len(ng) - 2), len(ng) + 3):
                for i in range(0, max(0, len(W) - n) + 1):
                    win = W[i:i + n]
                    if not win: continue
                    r = difflib.SequenceMatcher(None, " ".join(ng), " ".join(x for w in win for x in norm(w["t"]))).ratio()
                    dist = min(abs(w["s"] - t_src) for w in win)
                    sc = r - 0.05 * dist
                    if best is None or sc > best[0]: best = (sc, win, r)
            sc, win, r = best
            t0, t1 = win[0]["s"], win[-1]["e"]
            # mayúscula / puntuación del original se respetan
            if win[0]["t"][:1].isupper(): good = good[:1].upper() + good[1:]
            if win[-1]["t"][-1] in ".?!," and good[-1] not in ".?!,": good += win[-1]["t"][-1]
            ws = realign(P, good, t0, t1)
            fx = dict(t0=round(t0 - 0.01, 3), t1=round(t1 + 0.01, 3), text=good, was=" ".join(w["t"] for w in win), words=ws, case=case["id"])
            sj["fixes"] = [f for f in sj.get("fixes", []) if not (f["t0"] < fx["t1"] and f["t1"] > fx["t0"])] + [fx]
            case["applied"] = dict(fixes=fx)
            print(f"[feedback] texto: «{fx['was']}» -> «{good}» ({t0:.2f}–{t1:.2f} s de la fuente, parecido {r:.2f})")
    elif kind == "corte" and t_src is not None:
        fs_, fe_ = (it["fs"] / FPS, it["fe"] / FPS) if it else (t_src, t_src)
        out_side = abs(fe_ - t_src) <= abs(fs_ - t_src)                    # el cliente marca el final o el principio de la toma
        e = fe_ if out_side else fs_
        # la palabra que el corte se come: la última antes del corte de salida / la primera después del corte de entrada
        if out_side: ws = [w for w in P.WORDS if w["s"] < e and w["e"] > e - 1.0][-1:]
        else: ws = [w for w in P.WORDS if w["e"] > e and w["s"] < e + 1.0][:1]
        a, b = (min(w["s"] for w in ws) - 0.05, max(w["e"] for w in ws) + 0.05) if ws else (e - 0.3, e + 0.3)
        sj["nocut"] = sj.get("nocut", []) + [[round(a, 3), round(b, 3), case["id"]]]
        case["applied"] = dict(nocut=[round(a, 3), round(b, 3)], edge=round(e, 3), words=[w["t"] for w in ws])
        print(f"[feedback] corte: zona sin corte {a:.2f}–{b:.2f} s de la fuente ({' '.join(w['t'] for w in ws)})")
    elif kind.startswith("hablante") and t_src is not None:
        import content as C
        s = next((s for s in C.SENT if s["s"] - 0.3 <= t_src <= s["e"] + 0.3), None)
        if s:
            who = kind[-1]
            sj["speaker_fix"] = sj.get("speaker_fix", []) + [[round(s["s"] - 0.1, 3), round(s["e"] + 0.1, 3), who, case["id"]]]
            case["applied"] = dict(speaker=who, sentence=s["text"][:80], range=[round(s["s"], 2), round(s["e"], 2)])
            print(f"[feedback] hablante: «{s['text'][:70]}» -> {'periodista' if who == 'R' else 'ella'}")
    json.dump(sj, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fp = os.path.join(P.SRC["dir"], "feedback.json")
    cases = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []
    cases.append(case)
    json.dump(cases, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[feedback] caso {case['id']} ({kind}) guardado en sources/{source}/feedback.json — ya forma parte del banco de pruebas (python regress.py)")
    return case


def fix_source(source, t0, t1, text, note="", who="equipo", win=None):
    """corrección de texto directa sobre la fuente (minuto de la FUENTE): re-alinea el texto con el audio y la guarda como caso"""
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import importlib, plan as P
    importlib.reload(P)
    was = " ".join(w["t"] for w in P.WORDS if t0 <= (w["s"] + w["e"]) / 2 <= t1)
    ws = realign(P, text, *(win or (t0, t1)))                             # ventana de audio propia (sin la cola de la palabra anterior)
    sp = os.path.join(P.SRC["dir"], "source.json"); sj = json.load(open(sp, encoding="utf-8"))
    cid = f"c{int(time.time() * 1000) % 10**10}"
    fx = dict(t0=round(t0, 3), t1=round(t1, 3), text=text, was=was, words=ws, case=cid)
    sj["fixes"] = [f for f in sj.get("fixes", []) if not (f["t0"] < fx["t1"] and f["t1"] > fx["t0"])] + [fx]
    json.dump(sj, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fp = os.path.join(P.SRC["dir"], "feedback.json")
    cases = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []
    cases = [c for c in cases if not (c.get("applied") or {}).get("fixes", {}).get("t0") == fx["t0"]]
    cases.append(dict(id=cid, date=time.strftime("%Y-%m-%d %H:%M"), project="(fuente)", t_out=t0, t_src=t0, kind="texto", note=note or f"{who}: «{text}»", applied=dict(fixes=fx)))
    json.dump(cases, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[feedback] {source} {t0:.2f}–{t1:.2f}: «{was}» -> «{text}»  {[(w[0], w[1]) for w in ws]}")
    return fx


def list_cases(source=None):
    for s in sorted(os.listdir(os.path.join(STUDIO, "sources"))):
        if source and s != source: continue
        fp = os.path.join(STUDIO, "sources", s, "feedback.json")
        if not os.path.exists(fp): continue
        for c in json.load(open(fp, encoding="utf-8")):
            print(f"{s:24s} {c['id']} {c['date']} {c['kind']:10s} {c['project']} @ {c['t_out']:.1f}s -> {c['note']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "add": add(sys.argv[2], sys.argv[3], sys.argv[4], *(sys.argv[5:6]))
    elif sys.argv[1] == "list": list_cases(sys.argv[2] if len(sys.argv) > 2 else None)
