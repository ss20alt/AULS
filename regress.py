# Estudio de edición — BANCO DE PRUEBAS DE REGRESIÓN (punto 2). Cada cambio al estudio se valida contra TODO lo aprendido:
# cortes auditados, guiones de todos los estilos × ángulos (sin renderizar), quién habla, alineación, palabras inventadas,
# mapa de contenido, marca del cliente y cada corrección que mandó el cliente (feedback.py).
#   python regress.py                 -> corre el banco completo (cada fuente en su propio proceso) · sale con código 1 si algo falla
#   python regress.py --fast          -> sin las pruebas que cargan modelos de voz (≈ 30 s)
#   python regress.py --source X      -> (interno) pruebas de una fuente, imprime JSON
import os, sys, json, subprocess, time

STUDIO = os.path.dirname(os.path.abspath(__file__))
STYLES = ["news", "ink", "report", "headline", "fx", "call", "split",                       # estilos de la primera tanda
          "karaoke", "doc", "tv", "claves", "cita", "editorial", "campana", "podcast",    # estilos de 1 minuto (styles/base.py)
          "redes"]                                                                        # el look que publica el equipo (§3o)
MODES = [("2 min", 120.0, False), ("1 min", 60.0, True), ("3 min", 180.0, True), ("4 min", 240.0, True)]   # (nombre, duración, ¿exacta?)
LEGACY = "lilian_conferencia_bcp"
# medidas hechas a mano sobre la energía de la voz (fuente legacy): (palabra, borde, segundo, tolerancia)
GOLDEN_ALIGN = [("protegidos.", "e", 28.28, 0.08), ("No", "s", 147.67, 0.08), ("hacer.", "e", 205.55, 0.06), ("Vos,", "s", 205.77, 0.08)]


def source_tests(source, fast):
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import io, contextlib
    quiet = contextlib.redirect_stdout(io.StringIO())
    with quiet:
        import plan as P, content as C, selector2 as S2, audit_cuts, brand as B
    from core import FPS
    R = []
    def check(name, ok, detail=""): R.append(dict(name=name, ok=bool(ok), detail=str(detail)[:400]))

    # 0. ingesta de píxeles no cuadrados (DJI exportado: 9:16 guardado en 1728×1080, SAR 45:128) -> vertical 608×1080, sin aplastar
    if source == LEGACY:
        import tempfile, ingest as IG
        tmp = os.path.join(tempfile.gettempdir(), "studio_sar_test.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1728x1080:rate=30:duration=0.4",
                        "-vf", "setsar=45/128", "-c:v", "libx264", "-pix_fmt", "yuv420p", tmp])
        inf = IG.probe(tmp); vf = IG.video_filter(inf)
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", tmp, "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True).stdout
        check("ingesta: DJI con píxeles no cuadrados se lee VERTICAL (608×1080) y sale 1080×1920 sin aplastar",
              (inf["width"], inf["height"]) == (608, 1080) and "setsar=1" in vf and len(out) == 1080 * 1920, (inf["width"], inf["height"], vf[:60]))

    # 0b. cifras en pantalla (cifras.py): estadísticas de peso SÍ; fechas, horas, edades, leyes, "dos veces" NO
    if source == LEGACY:
        import cifras as CF
        def shown(text):
            ws = [dict(w=w, s=i * 0.4, e=i * 0.4 + 0.3) for i, w in enumerate(text.split())]
            return [(CF.fmt(c["value"], c["pct"]), c["label"]) for c in CF.pick(CF.candidates(ws), lambda c: c["s"], dur=600, max_n=9, gap=0.1)]
        cases = [("En el 2025 hubo 37 feminicidios y 69 hijos huérfanos.", [("37", "feminicidios"), ("69", "hijos")]),
                 ("Tenemos 37 .825 denuncias de violencia familiar.", [("37.825", "denuncias de violencia familiar")]),
                 ("Del 2020 al 2025 hubo 258 víctimas de feminicidio.", [("258", "víctimas de feminicidio")]),
                 ("Una joven de 22 años, estudiante de Derecho.", []), ("Anoche, a las 21 y 30, hubo un intento.", []),
                 ("El 12 de octubre presentamos la Ley 5777 dos veces.", []), ("Para el 2028 vamos a ganar.", []),
                 ("Durante 20 años se construyó y hoy 72 horas para saber.", []),
                 ("En lo que va del 2026 hay 20 víctimas, 21 ya, de feminicidios.", [("21", "víctimas")])]
        bad = [(t, shown(t), exp) for t, exp in cases if shown(t) != exp]
        check("cifras: detecta las estadísticas y descarta fechas, horas, edades, leyes y cantidades chicas; toma la cifra corregida (9 frases)", not bad, bad[:3])
        # formato evento: lo que ella pide no grabar no sale nunca; sus frases tienen que entenderse solas
        import evento as EV
        off = ["Y como yo soy siempre bien personaje, esta parte no se va a grabar.", "Vamos a apagar todo.", "Apaguen la cámara, por favor.",
               "No lo graben esto.", "Esto no sale, ¿eh?"]
        ok_ = ["Vamos a grabar un video para las redes.", "Un fuerte aplauso para cada uno de ustedes.", "Hoy apagamos las velitas de Arnaldo."]
        bad = [t for t in off if not EV.OFFREC.search(t)] + [t for t in ok_ if EV.OFFREC.search(t)]
        A_ = dict(words=[dict(t=w, s=i * 0.4, e=i * 0.4 + 0.3) for i, w in enumerate(
            "Un fuerte aplauso para todos. Y como soy personaje, esta parte no se va a grabar. Vamos a apagar todo.".split())])
        cut = EV.off_record(A_)
        susp = [t for t in ("Pero no importa, va a saber igual.", "porque todo el mundo le va a contar.", "Eso es lo que queremos.") if not (t[:1].islower() or EV.SUELTA.match(t))]
        check("evento: 'no se va a grabar / apaguen' corta la toma desde ahí; frases colgadas no entran", not bad and cut is not None and 1.5 < cut < 2.0 and not susp,      # corta al EMPEZAR esa frase (2.0 s − 0.3)
              (bad, cut, susp))
        # grabación cortada: arrancó con ella ya hablando / terminó mientras hablaba -> esas frases sueltas no se usan
        import numpy as np_
        W2 = [dict(t=w, s=i * 0.4, e=i * 0.4 + 0.35) for i, w in enumerate("este desafío y él lo dijo. Le va a ayudar a Eduardo. Y estoy segura".split())]
        hablando = np_.full(1500, -18.0); hablando[0] = -180.0; hablando[900:] = -27.0      # voz desde el primer cuadro (acto, piso −27)
        callado = hablando.copy(); callado[1:60] = -45.0                                    # arranca de silencio
        e1 = P.recording_edges(W2, hablando, 15.0); e2 = P.recording_edges(W2, callado, 15.0)
        check("bordes de grabación: arranque con ella ya hablando y final cortado se descartan; si arranca de silencio, no",
              len(e1) == 2 and "empezó" in e1[0][2] and "terminó" in e1[1][2] and len(e2) == 1 and e2[0][1] == 1e9, (e1, e2))
        # evento: un trozo que termina en coma se une con el siguiente; frase colgada ("…pedido y") no entra
        ws3 = [dict(t=w, s=i * 0.5, e=i * 0.5 + 0.4) for i, w in enumerate("Yo tengo, tenía un,".split())] + \
              [dict(t=w, s=3.0 + i * 0.5, e=3.0 + i * 0.5 + 0.4) for i, w in enumerate("hice un compromiso con Mari.".split())]
        ss3 = EV.sentences(ws3)
        check("evento: 'Yo tengo, tenía un,' + 'hice un compromiso…' quedan en UNA frase", len(ss3) == 1 and ss3[0]["text"].endswith("Mari."), [x["text"] for x in ss3])
        # JAMÁS letra manuscrita / informal (pedido explícito del usuario 2026-10-16): ningún archivo del estudio la usa
        import glob as _g, re as _re
        INF = _re.compile(r"inkfree|segoepr|segoesc|comic(bd|i|z)?\.ttf|marker ?felt|chalkboard|gabriola|brush ?script|script\.fon", _re.I)
        usa = [os.path.relpath(f, STUDIO) for f in _g.glob(os.path.join(STUDIO, "*.py")) + _g.glob(os.path.join(STUDIO, "styles", "*.py"))
               + _g.glob(os.path.join(STUDIO, "lib", "*.py")) if os.path.basename(f) != "regress.py" and INF.search(open(f, encoding="utf-8").read())]
        check("marca: ninguna letra manuscrita/informal en el estudio (títulos con Montserrat de la marca)", not usa, usa)
        auto = [c for c in CF.candidates(P.WORDS) if c["score"] >= 3.5]
        check("cifras: la conferencia BCP (sin estadísticas) no muestra ninguna tarjeta", not auto, [(c["value"], c["label"]) for c in auto][:4])
        # titulares automáticos (prueba de estrés 2026-10-16: "FUERTE EN NUESTRA", "DEBE QUEDAR", "AQUEL PROYECTO", "LOS DATOS" por un año)
        import mapper as MP
        S_ = [dict(text=t, spk="L") for t in ("Hoy presento una propuesta.", "Este proyecto empieza hoy.", "Nuestro país sabrá responder.")]
        ns = MP.nouns_of(S_)
        k1 = MP.kind_scores("En el 2024, presidente, habíamos hecho una propuesta fruto del trabajo de seis años.")
        k2 = MP.kind_scores("Si hoy estuviera vigente, lograríamos la coordinación de las instituciones.")
        malos = ["FUERTE EN NUESTRA", "DEBE QUEDAR", "AQUEL PROYECTO", "TRATAMIENTO CUANTO", "¿CÓMO ES?", "2026", "SIEMPRE LLEGA", "CABALLERO LEVANTÓ"]
        buenos = ["NO HAY CRISIS", "SISTEMA SÓLIDO", "VENDE PATRIA", "¿DÓNDE ESTABAS?", "AHORROS GARANTIZADOS", "JUSTICIA RÁPIDA", "PROYECTO DE LEY",
                  "FAMILIAS PARAGUAYAS", "GUSTAVO LEITE", "MENSAJE DE CALMA", "¿CÓMO ES POSIBLE?"]
        fallan = [h for h in malos if not MP.titular_malo(h)] + [h for h in buenos if MP.titular_malo(h)]
        check("titulares: sustantivos por contexto ('una propuesta', no 'empieza'); un año no es dato; 'lograríamos' no es logro; "
              "el control separa titulares malos de buenos",
              {"propuesta", "proyecto", "país"} <= ns and not ({"empieza", "sabrá"} & ns) and k1["propuesta"] > k1["dato"] and k2["logro"] == 0 and not fallan,
              (sorted(ns), k1, k2["logro"], fallan))
        # agrupado por evento: la señal de TV y la reunión van siempre aparte (aunque se graben el mismo día)
        import entender as EN_
        fk = lambda f, t, h: dict(file=f, tipo=t, fecha=f"2026-10-14T{h}:00")
        gs = EN_.grupos([fk("tv.mp4", "tv", "10:47"), fk("reu.mov", "reunion", "10:58"), fk("a.mp4", "clip", "11:00"), fk("b.mp4", "evento", "11:20")])
        check("eventos: TV y reunión no se juntan con las tomas del día; las tomas sí", sorted(len(g) for g in gs) == [1, 1, 2], [[r["file"] for r in g] for g in gs])
        # estilo datos: la placa nunca lleva una fecha fija escrita en el código
        fijas = [f for f in _g.glob(os.path.join(STUDIO, "styles", "*.py")) if _re.search(r"[\"'][^\"'\n]*\b\d{2}/\d{2}/20\d{2}\b", open(f, encoding="utf-8").read())]
        check("datos: la placa SENADO usa la fecha real de la toma (ninguna fecha fija en los estilos)", not fijas, fijas)
        # QA: segunda opinión de cara con YuNet (Haar pierde perfiles: 5-ene daba FACE_LOST con la cara a la vista)
        import qa as QA_
        vq = os.path.join(STUDIO, "tests", "cara_perfil.mp4")
        if os.path.exists(vq):
            so = QA_.segunda_opinion(vq)
            check("QA: la segunda opinión (YuNet) ve la cara de perfil que Haar pierde", (so["face_rate"] or 0) >= 0.8, so)

    # 1. auditoría de fronteras de frase: ninguna salida incluye voz de la frase siguiente
    rows = audit_cuts.audit()
    bad = [(round(r["out"], 2), r["a"][-20:], r["b"][:20]) for r in rows if r["cruzada"]]
    check("cortes: fronteras sin voz cruzada", not bad, bad[:4])

    # 2. guiones de todos los estilos × ángulos (EDL sin renderizar)
    Lw = [w for w in P.WORDS if C.WORD_SPK.get(round(w["s"], 3)) == "L"]
    Rw = [w for w in P.WORDS if C.WORD_SPK.get(round(w["s"], 3)) == "R" and w["e"] - w["s"] >= 0.10]
    import espectador as ESP
    n_edl = 0; long_, mid, other, nocut, holes, unanswered, spect = [], [], [], [], [], [], []
    for mode, max_s, exact in MODES:
        seen = {}
        for angle in C.STORIES:
            for style in STYLES:
                sig = (angle, style in S2.STYLE_SHOW_Q, style not in ("headline", "call", "split"))   # el guion solo depende de esto
                if sig in seen: n_edl += 1; continue
                with contextlib.redirect_stdout(io.StringIO()):
                    try: script, edl, parts = S2.build(angle, style, max_s=max_s, log=lambda *a: None, exact=exact)
                    except Exception as e: check(f"guion {mode} {style}/{angle}", False, repr(e)); continue
                seen[sig] = True; n_edl += 1
                spect += [(mode, angle) + tuple(f) for f in ESP.script_checks(parts) if f[0] in ("DANGLING", "HOOK_ECHO")]
                for tag, ks in parts:                                                 # bloques sin huecos y preguntas siempre con respuesta
                    if any(ks[i + 1] != ks[i] + 1 for i in range(len(ks) - 1)): holes.append((mode, angle, tag, ks))
                    if C.SENT[ks[-1]]["spk"] != "L": unanswered.append((mode, angle, tag))
                tot = edl["total"] / FPS
                corto_ok = bool(edl.get("falta")) and "no tiene ideas" in edl["falta"]["motivo"]      # material insuficiente, avisado: no es error
                if not edl["ok"] or (exact and abs(tot - max_s) > 1e-3 and not corto_ok) or (not exact and tot > max_s + 1e-6):
                    long_.append((mode, style, angle, round(tot, 2)))
                sp = [it for it in edl["items"] if it["kind"] == "speech"]
                for k, it in enumerate(sp):
                    a_, b_ = it["fs"] / FPS, it["fe"] / FPS
                    for side, t in (("in", a_), ("out", b_)):
                        if not it.get("e" + side, True) or it.get("soft_" + side): continue
                        if side == "in" and k > 0 and sp[k - 1]["fe"] == it["fs"]: continue           # tramos seguidos: el audio no se corta
                        if side == "out" and k + 1 < len(sp) and sp[k + 1]["fs"] == it["fe"]: continue
                        f_ = int(round(t * FPS))
                        if min(P.edge_db(f_ - 1), P.edge_db(f_)) < -30.0: continue      # a un lado del corte la voz ya cae: no parte una palabra
                        w = next((w for w in Lw if w["s"] + 0.04 < t < w["e"] - 0.04), None)       # borde a mitad de una palabra de ella
                        if w: mid.append((mode, angle, side, round(t, 2), w["t"]))
                        z = next(((za, zb) for za, zb in P.SRC.get("nocut", []) if za < t < zb), None)
                        if z: nocut.append((mode, angle, side, round(t, 2), z))
                    if it.get("role") == "A":
                        for w in Rw:
                            if a_ <= (w["s"] + w["e"]) / 2 <= b_ and not any(l["s"] < w["e"] and l["e"] > w["s"] for l in Lw)                                     and (P.R10[int(w["s"] * 100):int(w["e"] * 100) + 1] > -36).any():
                                other.append((mode, angle, round(w["s"], 2), w["t"]))
    check(f"guiones: {n_edl} EDL ({len(STYLES)} estilos × ángulos × 2 / 1 / 3 / 4 min) con la duración correcta", not long_ and n_edl > 0, long_[:5])
    check("guiones: ningún bloque con huecos (frases salteadas dentro de una idea)", not holes, holes[:4])
    check("guiones: toda pregunta del periodista va con la respuesta de ella", not unanswered, unanswered[:4])
    check("espectador: ninguna escena sin su antecedente ni gancho repetido enseguida", not spect, spect[:4])
    # el espectador detecta los errores plantados a propósito
    try:                                                         # las frases plantadas son de la conferencia BCP: en otras fuentes no existen
        k_pl, k_hook, k_q = C.find_sent("Por lo tanto, es lo que teníamos"), C.find_sent("Él que es un"), C.find_sent("¿Admitió las irregularidades")
    except KeyError:
        k_pl = None
    if k_pl is not None:
        planted = {"DANGLING": [("hook", [k_hook]), ("x", [k_pl])], "UNANSWERED": [("x", [k_q])],
                   "HOOK_ECHO": [("hook", [k_hook]), ("vp", [k_hook - 2, k_hook - 1, k_hook])], "HOLE": [("x", [k_hook - 2, k_hook - 1, k_hook + 1])]}
        miss = [k for k, pp in planted.items() if k not in {f[0] for f in ESP.script_checks(pp)}]
        check("espectador: detecta los 4 errores de guion plantados", not miss, miss)
    check("guiones: ningún corte a mitad de una palabra de ella", not mid, sorted(set(mid))[:6])
    check("guiones: ninguna palabra audible de otra voz dentro de sus tomas", not other, sorted(set(other))[:6])
    check("guiones: respetan las zonas 'acá no se corta' del cliente", not nocut, nocut[:4])

    # 2b. subtítulos: en los tramos internos (pausas recortadas, sin corte real) no se pierde ninguna palabra aunque el ASR del recorte falle
    import asr as A_
    lost = []
    for angle in list(C.STORIES)[:2]:
        with contextlib.redirect_stdout(io.StringIO()):
            script, edl, parts = S2.build(angle, "news", max_s=60.0, log=lambda *a: None)
            ref = A_.source_words(edl, None); deaf = A_.source_words(edl, [])
        inner = [it for it in edl["items"] if it["kind"] == "speech" and not it.get("eout", True)]
        for it in inner:                                                    # palabras cuyo tiempo de fuente cae dentro de un tramo interno
            a_, b_ = it["fs"] / FPS, it["fe"] / FPS
            n_ref = sum(1 for v in ref.values() for w in v if a_ <= w["w0"] < b_)
            n_deaf = sum(1 for v in deaf.values() for w in v if a_ <= w["w0"] < b_)
            if n_deaf < n_ref: lost.append((angle, round(a_, 1), n_ref - n_deaf))
    check("subtítulos: los tramos internos no pierden palabras", not lost, lost[:4])
    # 2c. cada toma de ella tiene subtítulo para (casi) todas sus palabras, también si una frase suena dos veces (gancho + contexto)
    bare = []
    for mode, max_s, exact in MODES[1:]:
        for angle in C.STORIES:
            with contextlib.redirect_stdout(io.StringIO()):
                script, edl, parts = S2.build(angle, "cita", max_s=max_s, log=lambda *a: None, exact=exact)
                got = A_.source_words(edl, None)
            for it in [i for i in edl["items"] if i["kind"] == "speech" and i.get("role") == "A"]:
                a_, b_ = it["fs"] / FPS, it["fe"] / FPS
                mine = [w for w in Lw if a_ <= (w["s"] + w["e"]) / 2 < b_ and not any(x <= w["s"] <= y for x, y in P.BAD)]
                have = sum(1 for w in got.get(it["scene"], []) if a_ - 0.05 <= w["w0"] <= b_)
                if len(mine) >= 4 and have < 0.9 * len(mine) and len(mine) - have >= 2:     # 1 palabra de borde puede quedar afuera a propósito
                    bare.append((mode, angle, it["sid"], have, len(mine)))
    check("subtítulos: cada toma de ella tiene sus palabras (≥ 90 %), aunque la frase se repita", not bare, bare[:4])
    # 2d. la última palabra de cada toma no se pierde si el ASR del recorte la escribe algo corrida en el tiempo (whisper adelanta
    #     palabras después de una pausa: "garantizados." del cierre de 4 min). Se simula adelantando el ASR 0.9 s.
    shifted = []
    for angle in list(C.STORIES)[:3]:
        with contextlib.redirect_stdout(io.StringIO()):
            script, edl, parts = S2.build(angle, "news", max_s=180.0, log=lambda *a: None, exact=True)
            ref = A_.source_words(edl, None)
            hyp = [dict(t=w["t"], s=w["s"] - 0.9, e=w["s"] - 0.6) for v in ref.values() for w in v]       # como en el caso real: 0.9 s antes
            got = A_.source_words(edl, hyp)
        for sc in ref:
            if ref[sc] and got.get(sc) and ref[sc][-1]["t"] != got[sc][-1]["t"]: shifted.append((angle, sc, ref[sc][-1]["t"]))
    check("subtítulos: la última palabra no se pierde si el ASR la escribe corrida en el tiempo", not shifted, shifted[:4])

    # 3. mapa de contenido coherente
    miss = [(k, b) for k, st in C.STORIES.items() for b in [st.get("hook"), st.get("close")] + st.get("body", []) if b and b not in C.BEAT]
    check(f"mapa: {len(C.BEATS)} bloques y {len(C.STORIES)} historias resuelven", C.BEATS and C.STORIES and not miss, miss[:5])

    # 3b. titulares del mapa automático de esta fuente: frases nominales (sin "FUERTE EN NUESTRA", "DEBE QUEDAR", "2026")
    if not fast or source == LEGACY:
        import mapper as MP
        try:
            with contextlib.redirect_stdout(io.StringIO()): _, outm, _ = MP.draft(source, write=False)
            malos = [(o["tag"][0], MP.titular_malo(o["tag"][0])) for o in outm if MP.titular_malo(o["tag"][0])]
            check(f"titulares automáticos: {len(outm)} bloques, ninguno mal formado", not malos, malos[:5])
        except Exception as e: check("titulares automáticos: el mapa se arma", False, repr(e))
        finally:
            import importlib
            with contextlib.redirect_stdout(io.StringIO()): importlib.reload(P); importlib.reload(C)

    # 4. marca del cliente desde su ficha (no del código)
    cj = json.load(open(os.path.join(STUDIO, "clients", P.SRC["client"] + ".json"), encoding="utf-8"))
    check("marca: nombre/cargo/@ salen de la ficha del cliente", (B.NAME, B.ROLE, B.HANDLE) == (cj["name"], cj["role"], cj["handle"]), (B.NAME, B.ROLE, B.HANDLE))

    # 5. correcciones del cliente (feedback.json): cada una es una prueba permanente
    fp = os.path.join(P.SRC["dir"], "feedback.json")
    for c in (json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else []):
        ap = c.get("applied") or {}
        if "fixes" in ap:
            fx = ap["fixes"]; got = " ".join(w["t"] for w in P.WORDS if fx["t0"] <= (w["s"] + w["e"]) / 2 <= fx["t1"])
            check(f"cliente {c['id']}: texto «{fx['text']}»", got.strip() == fx["text"].strip(), f"queda «{got}»")
        elif "speaker" in ap:
            a_, b_ = ap["range"]; got = P.speaker_at((a_ + b_) / 2)
            check(f"cliente {c['id']}: hablante {ap['speaker']} en {a_:.1f}s", got == ap["speaker"], got)
        elif "nocut" in ap:
            check(f"cliente {c['id']}: zona sin corte {ap['nocut']}", list(ap["nocut"]) in [list(z) for z in P.SRC.get("nocut", [])])
        else:
            check(f"cliente {c['id']}: «{c['note'][:50]}» (sin regla automática: revisar a mano)", True, "pendiente de triage")

    if source == LEGACY and not fast:
        # 5b. cada estilo dibuja sin errores y pasa el QA visual (contraste, cara, espejo, zona segura) sobre un proyecto real
        import qa_visual, doctor
        name = doctor.PRUEBA                                                    # proyecto de prueba incluido en el paquete, vestido con cada estilo
        for style in STYLES:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    cfg_st, _ = doctor.style_ctx(style)
                    fv = qa_visual.run(name, step=45, log=lambda *a: None, cfg=cfg_st)
                serious = [f for f in fv if f[0] != "baja"]
                check(f"estilo {style}: dibuja y pasa el QA visual ({name})", not serious, [f[2] for f in fv][:3])
            except Exception as e:
                check(f"estilo {style}: dibuja y pasa el QA visual ({name})", False, repr(e))

    if source == LEGACY and not fast:
        # 5c. el QA visual encuentra los errores plantados a propósito (caja roja sobre el saco, espejo, texto sobre la cara, rótulo sobre
        #     el escudo, texto que se sale del cuadro)
        expect = dict(redbox="CARD_BLEND", mirror="MIRROR", face="TEXT_ON_FACE", emblem="CONTRAST", clipped="CLIPPED", widecap="CLIPPED")
        missed = []
        for ctl, code in expect.items():
            cp = subprocess.run([sys.executable, os.path.join(STUDIO, "tests", "controles_visuales.py"), ctl], cwd=STUDIO,
                                capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            if f"'{code}'" not in cp.stdout: missed.append(ctl)
        check("QA visual: detecta los 6 errores visuales plantados", not missed, missed)

    if source == LEGACY:
        # 6. alineación contra medidas manuales
        errs = []
        for tok, side, ref, tol in GOLDEN_ALIGN:
            w = min((w for w in P.WORDS if w["t"] == tok), key=lambda w: abs(w[side] - ref))
            if abs(w[side] - ref) > tol: errs.append((tok, side, round(w[side], 3), ref))
        check("alineación: bordes de palabra medidos a mano (±60–80 ms)", not errs, errs)
        if not fast:
            import align, speakers, mapper
            with contextlib.redirect_stdout(io.StringIO()): g = align.ghosts(source, write=False)
            zones = P.DELETE + P.BAD
            outside = [x for x in g if not any(a - 0.05 <= x[0] <= b for a, b in zones)]
            undetected = [z for z in P.DELETE if not any(z[0] - 0.05 <= x[0] <= z[1] for x in g)]
            check("palabras inventadas: detecta las marcadas a mano y ninguna más", not outside and not undetected, (outside, undetected))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): speakers.evaluate(source)
            import re
            m = re.search(r"precisión contra etiquetas manuales: ([\d.]+)%", buf.getvalue())
            acc = float(m.group(1)) if m else 0.0
            check(f"quién habla: precisión {acc:.1f}% (mínimo 98%)", acc >= 98.0, acc)
            # árbitro de la transcripción: sin la corrección confirmada, tiene que encontrar la frase que whisper salteó (151.8 s)
            import arbitro, importlib
            os.environ["STUDIO_NO_FIXES"] = "1"
            try:
                with contextlib.redirect_stdout(io.StringIO()): r = arbitro.scan(source, write=False)
            finally:
                os.environ.pop("STUDIO_NO_FIXES", None)
                with contextlib.redirect_stdout(io.StringIO()): importlib.reload(P); importlib.reload(C)
            top = [i for i in r["items"][:3] if i["t0"] < 152.6 and i["t1"] > 151.6]
            check("árbitro: encuentra la frase que whisper salteó («le trató de sicaria») entre los 3 primeros", bool(top), [(i["whisper"], i["oye"]) for i in r["items"][:3]])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf): mapper.evaluate(source)
            m = re.search(r"precisión (\d+)%, cobertura (\d+)%", buf.getvalue())
            p_, r_ = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
            check(f"mapa automático: fronteras precisión {p_}% / cobertura {r_}% (mín. 90/85)", p_ >= 90 and r_ >= 85, (p_, r_))
    return R


def main():
    fast = "--fast" in sys.argv
    if "--source" in sys.argv:
        sys.stdout.reconfigure(encoding="utf-8")
        src = sys.argv[sys.argv.index("--source") + 1]
        print("@@JSON@@" + json.dumps(source_tests(src, fast), ensure_ascii=False))
        return 0
    sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    sources = sorted(d for d in os.listdir(os.path.join(STUDIO, "sources")) if os.path.exists(os.path.join(STUDIO, "sources", d, "source.json")))
    allr, fails = {}, 0
    for s in sources:
        env = dict(os.environ, STUDIO_SOURCE=s, PYTHONIOENCODING="utf-8")
        cp = subprocess.run([sys.executable, __file__, "--source", s] + (["--fast"] if fast else []), cwd=STUDIO, env=env, capture_output=True, text=True, encoding="utf-8")
        line = next((l for l in cp.stdout.splitlines() if l.startswith("@@JSON@@")), None)
        if line is None:
            allr[s] = [dict(name="la fuente carga sin errores", ok=False, detail=(cp.stderr or cp.stdout)[-600:])]
        else: allr[s] = json.loads(line[8:])
        print(f"\n== {s}")
        for r in allr[s]:
            fails += not r["ok"]
            print(f"  {'OK ' if r['ok'] else 'FALLA'} {r['name']}" + ("" if r["ok"] or not r["detail"] else f"\n        {r['detail']}"))
    n = sum(len(v) for v in allr.values())
    print(f"\n{n - fails}/{n} pruebas OK · {time.time() - t0:.0f}s")
    os.makedirs(os.path.join(STUDIO, "tests"), exist_ok=True)
    json.dump(dict(date=time.strftime("%Y-%m-%d %H:%M"), results=allr), open(os.path.join(STUDIO, "tests", "last_run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
