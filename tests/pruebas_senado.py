# Pruebas del área SENADO / TV (speakers.py): en una SESIÓN del Senado por TV, quién habla lo decide la voz del propio video
# y los vocativos de la presidencia, NO las reglas de conferencia de prensa ("ustedes", pregunta con "¿", voz bajada por la TV).
# Una señal de TV SIN señales de sesión (entrevista) sigue con las reglas de prensa: ahí quien pregunta habla largo y con un timbre
# que puede parecerse al de ella. La verdad de quién habla está CONGELADA (speakers.VERDAD_FIJA): volver a etiquetar una fuente no
# la cambia. Rápidas y sin GPU: las frases salen de la transcripción guardada (sin plan/content: no se toca el estado de regress) y
# las huellas de voz se simulan (el modelo WavLM no se carga).
import os, sys, json
import numpy as np

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LS1, VERD, BCP = "auto_2026_10_14_ls1", "lilian_senado_feminicidios", "lilian_conferencia_bcp"


def _sj(fuente):
    return json.load(open(os.path.join(STUDIO, "sources", fuente, "source.json"), encoding="utf-8"))


def _norm(w):
    import unicodedata, re
    w = unicodedata.normalize("NFD", w.lower()); w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", w)


def _partir(s, lim=30.0):
    """como content.build_sentences: una "frase" de > 30 s se parte en su mejor pausa (trozos ≤ 22 s, ≥ 3 s, nunca antes de "de / que…").
    En LS1, "La creación de juzgados … psicólogos capacitados … y dar la celeridad…" (35 s) -> "psicólogos capacitados…" queda sola"""
    SOFT = {"de", "del", "a", "al", "que", "con", "en", "para", "por", "como", "la", "el", "los", "las", "un", "una", "su", "sus", "lo", "le", "se"}
    START = {"entonces", "y", "pero", "porque", "también", "hoy", "acá", "aca", "ahí", "ahi", "finalmente", "gracias", "nosotros", "yo"}   # igual que content.py
    if s[-1]["e"] - s[0]["s"] <= lim or len(s) < 8: return [s]
    best, bi = -1e9, None
    for i in range(2, len(s) - 2):
        a, b = s[i - 1], s[i]
        if b["s"] - s[0]["s"] < 3.0 or s[-1]["e"] - a["e"] < 3.0: continue
        nxt = _norm(b["t"])
        if nxt in SOFT: continue
        sc = (b["s"] - a["e"]) + (0.25 if b["t"][:1].isupper() else 0) + (0.2 if nxt in START else 0) + (0.3 if a["t"][-1:] in ",;:" else 0)
        if sc > best: best, bi = sc, i
    if bi is None: return [s]
    return _partir(s[:bi], 22.0) + _partir(s[bi:], 22.0)


def _frases(fuente):
    """frases completas (por puntuación, las de > 30 s partidas como en content.py) desde la transcripción alineada guardada,
    sin las palabras borradas (delete / bad). Sin plan/content: rápido y sin tocar los módulos que regress tiene cargados"""
    d = os.path.join(STUDIO, "sources", fuente); sj = _sj(fuente)
    tp = os.path.join(d, "transcript_aligned.json")
    if not os.path.exists(tp): tp = sj["transcript"] if os.path.isabs(sj["transcript"]) else os.path.join(d, sj["transcript"])
    fuera = [tuple(x[:2]) for x in sj.get("delete", []) + sj.get("bad", [])]
    W = [w for sg in json.load(open(tp, encoding="utf-8")) for w in sg["words"] if not any(a <= w.get("ws", w["s"]) <= b for a, b in fuera)]
    S, cur = [], []
    for w in W:
        cur.append(dict(t=w["w"].strip(), s=w["s"], e=w["e"]))
        if cur[-1]["t"][-1:] in ".?!": S.append(cur); cur = []
    if cur: S.append(cur)
    S = [p for c in S for p in _partir(c)]
    return [dict(k=k, s=c[0]["s"], e=c[-1]["e"], dur=c[-1]["e"] - c[0]["s"], words=c, text=" ".join(w["t"] for w in c)) for k, c in enumerate(S)]


def _k(S, inicio):
    return next(s_["k"] for s_ in S if s_["text"].lower().startswith(inicio.lower()))


def pruebas(check):
    sys.path.insert(0, STUDIO)
    if not all(os.path.exists(os.path.join(STUDIO, "sources", f, "source.json")) for f in (LS1, VERD)):
        return                                                                     # paquete / clon sin la sesión del Senado: no aplica
    import speakers as SPK
    S = _frases(LS1)
    k_ahi, k_psi, k_como = _k(S, "Ahí ven ustedes"), _k(S, "psicólogos capacitados"), _k(S, "¿Cómo es posible")
    k_pres = [s_["k"] for s_ in S if s_["text"].lower().startswith("gracias a usted")]

    k_sigo, k_presi = _k(S, "Sigo, presidente"), _k(S, "Presidenta, señora senadora")
    tv = {"tipo": "tv", "layout": "panel"}
    # entrevista de TV (no hay material real): quien pregunta habla largo; ella habla DEL presidente, no AL presidente
    preg = ["Senadora, ¿qué opina usted del veto del presidente Peña a la ley de juzgados especializados?",
            "Y en concreto, ¿cuándo podría tratarse otra vez el proyecto en la comisión de legislación?",
            "Hay quienes dicen que estos juzgados costarían demasiado dinero al Estado, ¿qué les responde?"]
    resp = ["Mire, nosotros vamos a insistir con el proyecto porque las mujeres no pueden seguir esperando una respuesta.",
            "El presidente de la República tiene que entender que esto es una emergencia y que no admite más demoras.",
            "Lo que cuesta de verdad es una vida, y cada semana perdemos a otra mujer por la violencia de su pareja.",
            "Por eso pedimos que la comisión dictamine cuanto antes y que el pleno lo trate sin más vueltas."]
    orden = [("R", preg[0]), ("L", resp[0]), ("L", resp[1]), ("R", preg[1]), ("L", resp[2]), ("R", preg[2]), ("L", resp[3])]
    ENT = [dict(k=k, s=6.5 * k, e=6.5 * k + 6.0, dur=6.0, text=t) for k, (_, t) in enumerate(orden)]
    ver_ent = [q for q, _ in orden]

    # 1. el modo: TV con señales de SESIÓN -> voz + vocativos; TV sin ellas (entrevista, o sin frases) -> reglas de prensa, como
    #    antes; conferencia -> prensa (BCP intacta); discurso -> monólogo
    want = {LS1: "sesion", VERD: "sesion", BCP: "prensa", "auto_img_4572": "prensa", "lilian_encarnacion_acto": "monologo"}
    got = {f: SPK.modo(_sj(f), S if f in (LS1, VERD) else ()) for f in want if os.path.exists(os.path.join(STUDIO, "sources", f, "source.json"))}
    otros = dict(entrevista=SPK.modo(tv, ENT), sin_frases=SPK.modo(_sj(LS1)))
    check("senado: sesión del Senado (por la TV) decide con la voz; TV sin señales de sesión (entrevista) y conferencia con reglas de prensa",
          got == {f: m for f, m in want.items() if f in got} and got.get(LS1) == "sesion" and otros == dict(entrevista="prensa", sin_frases="prensa"),
          (got, otros))

    # 2. texto: solo lo que se le dice A ELLA es otra voz ("Gracias a usted, señora senadora"); sus "ustedes" y "¿…?" no.
    #    Sesión = ella le habla A la presidencia ("Sigo, presidente."); en una entrevista se habla DEL presidente
    hits = {s_["k"] for s_ in S if SPK.otra_voz_sesion(s_["text"])}
    si = ["Tiene la palabra la senadora Lilian Samaniego.", "Gracias, senadora.", "Senadora, ¿qué opina?"]
    no = ["Apelo a cada senador y a cada senadora.", "El pueblo tiene la palabra.", "Como dijo la señora senadora Paredes, hay que actuar.",
          "Ahí ven ustedes, esa es la cronología.", "¿Cómo es posible, presidente, que no haya juzgados?",
          "Gracias, senadora Paredes, por su exposición tan clara sobre este tema."]
    voc_si = ["Sigo, presidente.", "Gracias, señora presidenta.", "Señor presidente, pido la palabra.", "Una ley, presidente, tiene que ser para todas."]
    voc_no = ["Le pedimos al presidente Peña que vete la ley.", "El presidente de la República tiene que actuar.", "Presidente Peña dijo otra cosa.",
              "Como presidente de la comisión, lo planteé.", "El señor presidente no respondió.", "La verdad es que el actual presidente no escucha."]
    mal = ([t for t in si if not SPK.otra_voz_sesion(t)] + [t for t in no if SPK.otra_voz_sesion(t)]
           + [t for t in voc_si if not SPK.vocativo_presidencia(t)] + [t for t in voc_no if SPK.vocativo_presidencia(t)])
    check("senado: vocativos de la presidencia = otra voz; sus 'ustedes' y preguntas retóricas no; 'presidente' vocativo = sesión",
          len(k_pres) >= 2 and hits == set(k_pres) | {k_presi} and not mal and SPK.es_sesion(S) and not SPK.es_sesion(ENT),
          ([S[k]["text"][:40] for k in sorted(hits)], mal))

    # 3. la voz de una frase de TV se mide solo donde hay palabras (los 5 s de huecos de "psicólogos … capacitados …" no cuentan)
    sp = S[k_psi]
    vw, vf = SPK.ventanas(sp, True), SPK.ventanas(sp, False)
    hueco = any(a < 338.5 and b > 336.0 for a, b in vw)
    check("senado: en TV la huella de una frase usa solo los tramos con palabras (conferencia: la frase entera, igual que antes)",
          not hueco and sum(b - a for a, b in vw) <= 5.0 and vf == SPK.chunks(sp["s"], sp["e"]),
          ([(round(a, 2), round(b, 2)) for a, b in vw], round(sum(b - a for a, b in vw), 2)))

    # 4. LS1 con voces simuladas como las de la TV (ella ≈ 0.86–0.93 contra la huella; la presidencia, otra voz): con las reglas de
    #    prensa "Ahí ven ustedes…" y "¿Cómo es posible…?" pasaban a periodista (el error real); en modo sesión quedan de ella
    vp = np.load(os.path.join(STUDIO, "clients", "lilian_voiceprint.npy")).astype(np.float32)
    thr = json.load(open(os.path.join(STUDIO, "clients", "lilian_voiceprint.json")))["threshold"]
    V = SPK.verdad(LS1)
    ver = SPK.etiquetas_verdad(V, S)
    rng = np.random.default_rng(7)
    unit = lambda x: x / np.linalg.norm(x)
    orto = lambda: unit((lambda z: z - (z @ vp) * vp)(rng.normal(size=len(vp))))
    ella, pres = unit(0.95 * vp + 0.312 * orto()), unit(0.55 * vp + 0.835 * orto())
    E = []
    for s_, v in zip(S, ver):
        quien = ella if v != "R" else pres                                    # "Sigo, presidente." (dudoso en la verdad) es de ella
        beta = 0.6 if s_["k"] == k_psi else (0.3 if s_["k"] in (k_ahi, k_como) else rng.uniform(0.2, 0.35))
        E.append(unit(quien + beta * orto()))
    E = np.array(E, dtype=np.float32); sims = E @ vp
    ses = SPK.decidir(SPK.modo(_sj(LS1), S), S, E, sims, thr, vp)
    prensa = SPK.decidir("prensa", S, E, sims, thr, vp)
    par = [(a, b) for a, b in zip(ses, ver) if b is not None]
    acc = np.mean([a == b for a, b in par])
    check("senado: LS1 (voces simuladas de TV): 'Ahí ven ustedes…', '¿Cómo es posible…?' y 'psicólogos…' son de ella; la presidencia es otra voz",
          all(ses[k] == "L" for k in (k_ahi, k_psi, k_como)) and all(ses[k] == "R" for k in k_pres + [k_presi]) and acc >= 0.98
          and prensa[k_ahi] == "R" and prensa[k_como] == "R",
          dict(sesion={S[k]["text"][:25]: ses[k] for k in [k_ahi, k_psi, k_como] + k_pres}, acierto=round(float(acc), 3),
               prensa={S[k]["text"][:25]: prensa[k] for k in (k_ahi, k_como)}))

    # 5. ENTREVISTA de TV simulada (lo que vio el revisor): quien pregunta tiene un timbre parecido al de ella (~0.79 contra la
    #    huella, como las otras voces de BCP: mediana 0.799) y habla largo. Va por las reglas de prensa: sus 3 preguntas son otra
    #    voz. Con las reglas de sesión (sin corte por voz de cada frase) quedaban como palabras de ella
    rng = np.random.default_rng(11)
    ella_tv, entrev = unit(0.90 * vp + 0.436 * orto()), unit(0.80 * vp + 0.60 * orto())
    E2 = np.array([unit((ella_tv if q == "L" else entrev) + 0.15 * orto()) for q in ver_ent], dtype=np.float32); sims2 = E2 @ vp
    m_ent = SPK.modo(tv, ENT)
    dec = SPK.decidir(m_ent, ENT, E2, sims2, thr, vp)
    con_sesion = SPK.decidir("sesion", ENT, E2, sims2, thr, vp)
    check("senado: entrevista de TV (otra voz larga de timbre parecido) -> reglas de prensa: las preguntas no quedan como palabras de ella",
          m_ent == "prensa" and dec == ver_ent and any(a == "L" for a, b in zip(con_sesion, ver_ent) if b == "R"),
          dict(modo=m_ent, prensa=dec, con_reglas_de_sesion=con_sesion, verdad=ver_ent, sims=[round(float(x), 3) for x in sims2]))

    # 6. verdad CONGELADA (VERDAD_FIJA): no depende del "reporter" que label() pisa en cada corrida (no es circular), vale para el
    #    mismo archivo con otro nombre (huella), una fuente automática con speaker_fix se mide SOLO en lo corregido a mano, y un
    #    "reporter" vacío no es verdad. «Sigo, presidente.» queda por confirmar (no cuenta)
    sj_fem = _sj(VERD)
    pisada = {k: v for k, v in sj_fem.items() if k != "speaker_fix"}
    pisada.update(reporter=[[229.26, 247.7], [465.17, 485.51]], reporter_auto=True)        # alguien volvió a etiquetar (con el error)
    reing = dict(_sj(LS1), huella="88538260:3125abc7d57041b3", speaker_fix=sj_fem.get("speaker_fix", []), heredado_de=VERD)
    otro = dict(reporter=[[1.0, 9.0], [20.0, 25.0]], reporter_auto=True, original="C:/x/otro.mp4",
                speaker_fix=[[1.0, 9.0, "L", "es ella"], [30.0, 32.0, "R", "otra voz"]])
    Vp = SPK.verdad("otro_video", sj=otro)
    lab_p = SPK.etiquetas_verdad(Vp, [dict(s=2.0, e=4.0), dict(s=21.0, e=24.0), dict(s=30.5, e=31.5)]) if Vp else None
    vacio = SPK.verdad("sin_etiquetar", sj=dict(reporter=[], original="C:/x/otro2.mp4"))
    sbcp = _sj(BCP)
    bcp_ok = SPK.verdad(BCP)["nombre"] == "conferencia_bcp" and (sbcp.get("reporter_auto") or SPK.verdad(BCP)["otra"] == sorted(tuple(x[:2]) for x in sbcp["reporter"]))
    img = os.path.exists(os.path.join(STUDIO, "sources", "auto_img_4572", "source.json"))
    det = dict(ls1=V and (V["nombre"], V["otra"], V["dudoso"]), pisada=SPK.verdad(VERD, sj=pisada) == V, reingesta=SPK.verdad("ls1_reingesta", sj=reing) == V,
               parcial=lab_p, vacio=vacio, bcp=bcp_ok, img_4572=(SPK.verdad("auto_img_4572") or {}).get("nombre") if img else "-",
               ls1_frases={k: ver[k] for k in (k_ahi, k_psi, k_como, k_sigo, k_presi)})
    check("senado: verdad congelada (no circular): LS1 y feminicidios con la misma, re-etiquetar no la cambia; parcial y vacía bien; BCP intacta",
          V is not None and V["nombre"] == "senado_ls1" and SPK.verdad(VERD) == V and det["pisada"] and det["reingesta"]
          and lab_p == ["L", None, "R"] and vacio is None and bcp_ok and det["img_4572"] in ("conferencia_bcp", "-")
          and [ver[k] for k in (k_ahi, k_psi, k_como)] == ["L"] * 3 and ver[k_sigo] is None and ver[k_presi] == "R"
          and all(ver[k] == "R" for k in k_pres), det)
