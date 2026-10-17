# Estudio de edición — QUIÉN HABLA (punto 5): verificación de voz con WavLM-SV contra la "huella de voz" del cliente.
# Cada frase se compara con la huella de Lilian; lo que no es su voz se marca como periodista (REPORTER).
# Tres modos según la fuente (modo()): conferencia de prensa (reglas de prensa), discurso/mensaje (voz del propio video) y
# SESIÓN del Senado por TV (voz del propio video + vocativos de la presidencia; sin las reglas de prensa). Una señal de TV SIN
# señales de sesión (entrevista, programa, radio) sigue con las reglas de prensa: ahí sí hay quien le pregunta.
#   python speakers.py build  [fuente_con_etiquetas]  -> clients/<cliente>_voiceprint.npy + umbral (calibrado con la fuente etiquetada a mano)
#   python speakers.py label  <fuente>                -> escribe "reporter" en sources/<fuente>/source.json
#   python speakers.py eval   [fuente]                -> precisión contra la VERDAD congelada (VERDAD_FIJA) o las etiquetas a mano de la fuente
import os as _os; _os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # Mac: operaciones sin MPS caen al procesador
import os, sys, json, wave, re
import numpy as np, torch

STUDIO = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(STUDIO, "models", "wavlm-base-plus-sv")
SR16 = 16000
import plataforma as PL
dev = PL.DEVICE
_m = {}


def model():
    if not _m:
        from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
        _m["fe"] = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
        _m["m"] = WavLMForXVector.from_pretrained(MODEL).to(dev).eval()
    return _m["fe"], _m["m"]


def load_audio(path):
    import scipy.signal as ss
    w = wave.open(path); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    return ss.resample_poly(a, 1, 3).astype(np.float32)


def embed(a16, s, e):
    fe, m = model()
    x = a16[int(s * SR16):int(e * SR16)]
    if len(x) < int(0.4 * SR16): x = np.pad(x, (0, int(0.4 * SR16) - len(x)))
    with torch.no_grad():
        inp = fe(x, sampling_rate=SR16, return_tensors="pt").to(dev)
        v = m(**inp).embeddings[0].float().cpu().numpy()
    return v / (np.linalg.norm(v) + 1e-9)


def chunks(s, e, maxlen=3.0):
    n = max(1, int(np.ceil((e - s) / maxlen)))
    return [(s + (e - s) * i / n, s + (e - s) * (i + 1) / n) for i in range(n)]


def ventanas(s_, por_palabras=False, hueco=0.5):
    """tramos de audio con que se mide la voz de una frase. Por defecto la frase entera en trozos de ≤ 3 s (conferencia y
    discurso: sin cambios). Sesión por TV (por_palabras): solo donde hay PALABRAS; los huecos > 0.5 s dentro de la frase (la TV que baja
    el sonido, aplausos, la presidencia de fondo) no cuentan: «psicólogos … capacitados … que puedan atender este caso» (LS1
    332–341 s) son 4 s de voz y 5 s de huecos, y el promedio de la frase entera quedaba lejos de ella -> 'otra voz'.
    Trozos de palabras < 0.4 s se descartan (embed los rellena con ceros); si queda < 0.8 s de voz, la frase entera"""
    if not por_palabras or not s_.get("words"): return chunks(s_["s"], s_["e"])
    runs = []
    for w in s_["words"]:
        if runs and w["s"] - runs[-1][1] <= hueco: runs[-1][1] = max(runs[-1][1], w["e"])
        else: runs.append([w["s"], w["e"]])
    out = [c for a, b in runs if b - a >= 0.4 for c in chunks(a, b)]
    return out if sum(b - a for a, b in out) >= 0.8 else chunks(s_["s"], s_["e"])


def sentences(source):
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import importlib, plan, content
    importlib.reload(plan); importlib.reload(content)
    return plan, content.SENT


def sentence_embeddings(P, SENT, por_palabras=False):
    a16 = load_audio(P.SRC["voice"])
    out = []
    for s in SENT:
        vs = [embed(a16, a, b) for a, b in ventanas(s, por_palabras)]       # sesión por TV: solo los tramos con palabras (ventanas)
        out.append(np.mean(vs, 0))
    return np.array(out)


def build(source="lilian_conferencia_bcp"):
    P, SENT = sentences(source)
    E = sentence_embeddings(P, SENT)
    lab = np.array([s["spk"] == "L" for s in SENT])
    dur = np.array([s["dur"] for s in SENT])
    # validación "dejando uno afuera": la huella se arma sin la frase que se evalúa
    sims = []
    for i in range(len(SENT)):
        mask = lab.copy(); mask[i] = False; mask &= dur >= 1.5
        vp = E[mask].mean(0); vp /= np.linalg.norm(vp)
        sims.append(float(E[i] @ vp))
    sims = np.array(sims)
    cands = np.linspace(sims.min(), sims.max(), 400)
    acc = [((sims >= c) == lab).mean() for c in cands]
    thr = float(cands[int(np.argmax(acc))])
    vp = E[lab & (dur >= 1.5)].mean(0); vp /= np.linalg.norm(vp)
    client = P.SRC["client"]
    np.save(os.path.join(STUDIO, "clients", f"{client}_voiceprint.npy"), vp)
    meta = dict(threshold=round(thr, 4), accuracy_loo=round(float(max(acc)), 3), n_lilian=int(lab.sum()), n_otros=int((~lab).sum()),
                sim_lilian_median=round(float(np.median(sims[lab])), 3), sim_otros_median=round(float(np.median(sims[~lab])), 3))
    json.dump(meta, open(os.path.join(STUDIO, "clients", f"{client}_voiceprint.json"), "w"), indent=1)
    print("[voz] huella creada:", meta)
    for i, s in enumerate(SENT):
        ok = (sims[i] >= thr) == lab[i]
        if not ok: print(f"   ✗ {s['s']:6.1f}s {'L' if lab[i] else 'R'} sim {sims[i]:.3f}  {s['text'][:70]}")
    return meta


VOCATIVE = re.compile(r"(^\W*|gracias,?\s+)senadora\b|\bsenadora\W*$")      # "senadora" como vocativo (ella nunca se llama así)
# SESIÓN: solo cuenta como otra voz lo que se le dice A ELLA (la presidencia), nunca "ustedes" ni una pregunta con "¿" (en una
# sesión no hay periodistas: ella les habla al presidente y a los colegas, y sus preguntas son retóricas).
# "Gracias a usted, señora senadora." · "Presidenta, señora senadora, por costumbre…" · "Tiene la palabra la senadora…" -> otra voz;
# "la exposición de la senadora Yolanda Paredes", "a cada senador y a cada senadora", "senadores y senadoras" -> ella
OTRA_VOZ_SESION = re.compile(
    r"(^\W*|gracias,?\s+|gracias a usted,?\s+)(señora\s+)?senadora\b"           # "Senadora, …" / "Gracias, senadora…"
    r"|(?<!cada )(?<!la )(?<!las )(?<!y )\bsenadora\W*$"                         # "…, senadora." al final (no "a cada senadora.")
    r"|(?<!la )\bseñora senadora\b"                                               # "usted, señora senadora" (no "la señora senadora X")
    r"|^\W*gracias a usted\b"                                                     # la presidencia le devuelve el agradecimiento
    r"|\btiene (usted )?la palabra\b[^.?!]*\bsenador|\bsenadora?\b[^.?!]*\btiene (usted )?la palabra")   # "Tiene la palabra la senadora…"
# palabras del RECINTO (solo suman a un vocativo de la presidencia: "mis colegas" o "la plenaria de ayer" salen en una entrevista)
RECINTO = re.compile(r"\bcolegas\b|\bplenaria\b|\bhonorables?\b|\btiene (usted )?la palabra\b|\bpido la palabra\b|\buso de la palabra\b"
                     r"|\bcuarto intermedio\b|\borden del d[ií]a\b|\bseñores senadores\b")
# antes de "presidente/a" = se habla DEL presidente, no se le habla a él ("el presidente Peña", "al presidente", "como presidente")
_NO_VOC = {"el", "la", "los", "las", "del", "al", "un", "una", "su", "sus", "mi", "tu", "nuestro", "nuestra", "este", "esta", "ese",
           "esa", "aquel", "aquella", "como", "de", "ex", "vice", "actual", "nuevo", "nueva", "futuro", "futura", "otro", "otra"}


def otra_voz_sesion(texto):
    """frase CORTA (≤ 8 palabras) que se le dice a ella (OTRA_VOZ_SESION): justo donde la huella es poco fiable (1–2 s). Las largas
    las decide la voz: un "Gracias, senadora Paredes, por su exposición tan clara…" de ella a una colega no se pierde"""
    t = texto.lower().strip()
    return len(t.split()) <= 8 and bool(OTRA_VOZ_SESION.search(t))


def vocativo_presidencia(texto):
    """¿le habla A LA PRESIDENCIA de la sesión? "presidente/a" como vocativo: "Sigo, presidente." · "¿Cómo es posible, presidente,
    que…?" · "Gracias, señora presidenta". No cuenta el presidente DEL que se habla (lo que se dice en una entrevista): "el
    presidente Peña", "al presidente", "el señor presidente", "presidente de la República", "Presidente Peña dijo…" (sigue un nombre)"""
    VOC = re.compile(r"(?:^|[,;:.¿¡]\s*|\bgracias\s+)(?:(?:señor|señora)\s+)?president[ae](?=\s*(?:[,.;:?!…]|$))", re.I)
    for m_ in VOC.finditer(texto.strip()):                                 # separado por signos o en el borde: "Sigo, presidente." ·
        prev = re.findall(r"[^\W\d_]+", texto.strip()[:m_.start()].lower())[-1:]   # "¿Cómo es posible, presidente, que…?" ·
        if prev and prev[-1] in _NO_VOC: continue                         # "Gracias, señora presidenta" · NO: "candidata a presidenta"
        return True
    return False


def es_sesion(SENT):
    """¿SESIÓN del Senado (ella le habla a la presidencia y a la cámara) o entrevista / programa de TV? entender.py llama "tv" a
    todo lo que tiene zócalo de canal ("TV / RADIO / SENADO"), y en una entrevista quien pregunta habla largo ("Senadora, ¿qué opina
    usted de…?", > 8 palabras): eso lo separan las reglas de prensa, no la voz sola (otra voz de timbre parecido, ~0.80 contra la
    huella, quedaba como suya). Sesión = ≥ 2 frases con vocativo de la presidencia, o 1 + una palabra del recinto (RECINTO).
    LS1: 18 de 58 frases con "…, presidente/a" y 5 del recinto. En una entrevista se habla DEL presidente, no AL presidente"""
    voc = sum(1 for s_ in SENT if vocativo_presidencia(s_["text"]))
    rec = sum(1 for s_ in SENT if RECINTO.search(s_["text"].lower()))
    return voc >= 2 or (voc >= 1 and rec >= 1)


def modo(src, SENT=()):
    """cómo se decide quién habla, según la fuente (source.json / plan.SRC: "tipo" de entender.py, "layout" de ingest) y sus frases:
    'monologo' discurso / mensaje: una sola persona; agrupa las voces del propio video (_agrupar_voces)
    'sesion'   señal de TV (tipo tv, o formato panel sin tipo de conferencia) CON señales de sesión (es_sesion): voces del propio
               video + vocativos de la presidencia en frases cortas (otra_voz_sesion). Antes pasaba por las reglas de prensa y LS1
               perdía 4 frases suyas (≈ 40 s): "Ahí ven ustedes, esa es la cronología…", "¿Cómo es posible, presidente…?",
               "psicólogos capacitados…" quedaban como periodista
    'prensa'   conferencia de prensa (por defecto, BCP) y TV SIN señales de sesión (entrevista, programa: hay quien le pregunta):
               huella + "usted/ustedes" + pregunta con "¿" -> periodista (sin cambios). Sin frases (SENT vacío) la TV va acá"""
    t = src.get("tipo")
    if t in ("discurso", "mensaje"): return "monologo"
    if (t == "tv" or (src.get("layout") == "panel" and t != "conferencia")) and es_sesion(SENT): return "sesion"
    return "prensa"


def _agrupar_voces(SENT, E, sims, thr, vp):
    """DISCURSO / MENSAJE / SESIÓN: en un acto con parlantes (o por la TV) su voz suena distinta a la huella (0.78–0.94 en vez de
    ≥ 0.85) y ella dice "ustedes" todo el tiempo (no es la prensa). Se agrupan las voces DEL PROPIO video; la voz de ella = el
    grupo con más tiempo entre los que se parecen a la huella; otra voz = grupo lejos de la huella y lejos de ella (el locutor
    que la presenta, la presidencia de la sesión). Frases < 1 s quedan "L" (después heredan de la vecina: _heredar_cortas)"""
    from scipy.cluster.hierarchy import linkage, fcluster
    dur = np.array([s_["dur"] for s_ in SENT])
    idx = [i for i in range(len(SENT)) if dur[i] >= 1.0]
    spk = ["L"] * len(SENT)
    if len(idx) < 3: return spk
    lab = fcluster(linkage(E[idx], "average", metric="cosine"), t=0.30, criterion="distance")
    groups = {}
    for i, g in zip(idx, lab): groups.setdefault(g, []).append(i)
    cen = {g: (lambda c: c / np.linalg.norm(c))(E[m].mean(0)) for g, m in groups.items()}
    cand = [g for g in groups if float(cen[g] @ vp) >= thr - 0.10] or list(groups)
    main = max(cand, key=lambda g: dur[groups[g]].sum())
    for g, m in groups.items():
        if g == main: continue
        far_vp = float(cen[g] @ vp) < thr - 0.06; far_main = float(cen[g] @ cen[main]) < 0.80
        for i in m:
            if far_vp and far_main and sims[i] < thr - 0.04: spk[i] = "R"
    return spk


def _heredar_cortas(SENT, spk, fija=lambda s_: False):
    """frases muy cortas (< 1 s): el embedding es poco fiable -> heredan el hablante de la frase vecina (≥ 1 s) más cercana,
    salvo las que el texto ya decide (fija)"""
    for i, s_ in enumerate(SENT):
        if s_["dur"] < 1.0 and not fija(s_):
            nb = [j for j in (i - 1, i + 1) if 0 <= j < len(SENT) and SENT[j]["dur"] >= 1.0]
            if nb: spk[i] = spk[min(nb, key=lambda j: min(abs(SENT[j]["s"] - s_["e"]), abs(s_["s"] - SENT[j]["e"])))]
    return spk


def _decidir_sesion(SENT, E, sims, thr, vp):
    """SESIÓN DEL SENADO por TV: decide la voz (grupos del propio video, como en un discurso) y el texto solo suma lo que se le
    dice a ella (otra_voz_sesion, si la voz no es claramente la suya: < 0.93). "ustedes", una pregunta con "¿" o la voz bajada
    por la TV ya NO la mandan a otra voz (en LS1 eran 4 de 6 tramos 'R', corregidos a mano en lilian_senado_feminicidios).
    Solo con es_sesion(): sin corte por voz de cada frase, otra voz larga de timbre parecido quedaría como suya (entrevista)"""
    spk = _agrupar_voces(SENT, E, sims, thr, vp)
    otra = lambda s_: otra_voz_sesion(s_["text"])
    for i, s_ in enumerate(SENT):
        if otra(s_) and sims[i] < 0.93: spk[i] = "R"
    return _heredar_cortas(SENT, spk, fija=otra)


def _decidir_prensa(SENT, E, sims, thr):
    """CONFERENCIA DE PRENSA (las reglas de siempre, sin cambios; BCP ≥ 98 % en regress): huella + la prensa se dirige a ella
    ("senadora", "usted", "ustedes") + pregunta de periodista con "¿" + perfiles locales de ella y de la prensa"""
    import re as _re
    def qrule(s_, v):
        w_ = set(_re.findall(r"[a-záéíóúñü]+", s_["text"].lower()))
        return s_["text"].lstrip().startswith("¿") and not (w_ & {"vos", "te", "tu", "tus"}) and v < thr + 0.07
    def decide(s_, v):
        t = s_["text"].lower()
        words = set(_re.findall(r"[a-záéíóúñü]+", t))
        if v < thr: return "R"
        if VOCATIVE.search(t): return "R"                                                      # "Gracias, senadora." / "Senadora, ¿…?": le hablan a ella
        if words & {"senadora", "usted", "ustedes"} and v < 0.93: return "R"                # la prensa se dirige a ella
        if qrule(s_, v): return "R"                                                              # pregunta de periodista
        return "L"
    spk = [decide(s_, v) for s_, v in zip(SENT, sims)]
    # adaptación a cada video: perfiles locales de "Lilian" y "prensa" con las frases claras; los casos dudosos se deciden contra ambos
    cue0 = lambda s_: bool(set(_re.findall(r"[a-záéíóúñü]+", s_["text"].lower())) & {"senadora", "usted", "ustedes"}) or bool(VOCATIVE.search(s_["text"].lower()))
    dur = np.array([s_["dur"] for s_ in SENT])
    confL = (sims >= 0.93) & (dur >= 1.5)
    confR = np.array([(v < thr - 0.03 or cue0(s_)) and s_["dur"] >= 1.0 for s_, v in zip(SENT, sims)])
    if confR.sum() >= 2 and confL.sum() >= 3:
        cL = E[confL].mean(0); cL /= np.linalg.norm(cL)
        cR = E[confR].mean(0); cR /= np.linalg.norm(cR)
        for i, s_ in enumerate(SENT):
            if confL[i] or cue0(s_) or qrule(s_, sims[i]): continue
            spk[i] = "L" if float(E[i] @ cL) - float(E[i] @ cR) > 0 else "R"
    cue = lambda s_: bool(set(_re.findall(r"[a-záéíóúñü]+", s_["text"].lower())) & {"senadora", "usted", "ustedes"})
    for i in range(1, len(SENT)):                                     # serie de preguntas retóricas de ella ("¿Vos dónde estás…? ¿Y de la educación?")
        a, b = SENT[i - 1], SENT[i]
        if spk[i] == "R" and spk[i - 1] == "L" and a["text"].rstrip().endswith("?") and b["text"].lstrip().startswith("¿") and b["s"] - a["e"] < 1.2 and not cue(b) and sims[i] >= thr:
            spk[i] = "L"
    # frases muy cortas (< 1 s): el embedding es poco fiable -> heredan el hablante de la frase vecina más cercana
    return _heredar_cortas(SENT, spk, fija=cue)


def decidir(m, SENT, E, sims, thr, vp):
    """quién habla en cada frase ("L" ella / "R" otra voz) según el modo de la fuente (modo()); sin modelo: E = huellas por frase"""
    if m == "monologo": return _heredar_cortas(SENT, _agrupar_voces(SENT, E, sims, thr, vp))
    if m == "sesion": return _decidir_sesion(SENT, E, sims, thr, vp)
    return _decidir_prensa(SENT, E, sims, thr)


def _tramos(SENT, spk):
    """frases "R" seguidas (< 1 s entre una y otra) -> tramos de otra voz con 0.2 s de margen"""
    rep, cur = [], None
    for s, k in zip(SENT, spk):
        if k == "R":
            if cur and s["s"] - cur[1] < 1.0: cur[1] = s["e"] + 0.2
            else:
                if cur: rep.append(cur)
                cur = [round(s["s"] - 0.2, 2), round(s["e"] + 0.2, 2)]
    if cur: rep.append(cur)
    return rep


def label(source, write=True):
    P, SENT = sentences(source)
    client = P.SRC["client"]
    vp = np.load(os.path.join(STUDIO, "clients", f"{client}_voiceprint.npy"))
    thr = json.load(open(os.path.join(STUDIO, "clients", f"{client}_voiceprint.json")))["threshold"]
    m = modo(P.SRC, SENT)                                                   # TV: sesión del Senado o entrevista (es_sesion)
    E = sentence_embeddings(P, SENT, por_palabras=m == "sesion")            # sesión: solo los tramos con palabras (ventanas)
    sims = E @ vp
    spk = decidir(m, SENT, E, sims, thr, vp)
    rep = _tramos(SENT, spk)
    if write:
        sp = os.path.join(P.SRC["dir"], "source.json")
        sj = json.load(open(sp, encoding="utf-8")); sj["reporter"] = rep; sj["reporter_auto"] = True
        json.dump(sj, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tv = P.SRC.get("tipo") == "tv" or (P.SRC.get("layout") == "panel" and P.SRC.get("tipo") != "conferencia")
    como = {"monologo": f" ({P.SRC.get('tipo')}: decide la voz del propio video)",
            "prensa": " (TV sin señales de sesión: reglas de prensa, como en una entrevista)" if tv else "",
            "sesion": " (sesión del Senado por TV: voz del propio video + vocativos de la presidencia, sin reglas de prensa)"}[m]
    print(f"[voz] {source}{como}: {sum(1 for k in spk if k == 'R')} frases de otras voces -> tramos {rep}")
    return spk, sims, rep


# VERDAD CONGELADA de "quién habla" (verificada a mano; segundos del audio del ARCHIVO). label() escribe "reporter" en source.json
# y lo pisa en cada corrida (también el paso "speakers" de ingest): una verdad leída de ahí se vuelve circular (el código comparado
# con su propia salida vieja). Esta no la toca nadie. Vale para toda fuente del MISMO archivo (_fija_de): por nombre, por la huella
# del original (ingest.huella: tamaño + sha1 del 1.er MB) o por el nombre del original + la duración (fuentes viejas sin huella).
#   otra_voz: tramos de otra persona (lo demás es de ella) · dudoso: nadie lo decidió a mano -> no cuenta en la precisión
VERDAD_FIJA = {
    "conferencia_bcp": dict(                                                   # la fuente etiquetada a mano con que se calibró la huella
        fuentes=("lilian_conferencia_bcp",), archivo="IMG_4572.MOV", huella="477656732:ad68b81617e239ac", dur=434.81,
        otra_voz=[[70.4, 78.5], [304.9, 313.6], [345.9, 348.3], [360.2, 363.1], [398.0, 406.3], [432.4, 435.0]]),
    "senado_ls1": dict(                                                        # sesión del Senado por TV, 14/10/2026
        fuentes=("lilian_senado_feminicidios", "auto_2026_10_14_ls1"), archivo="2026-10-14-LS1.mp4", huella="88538260:3125abc7d57041b3",
        dur=741.36,
        # de ella por el cliente (speaker_fix): 229–248 s «Ahí ven ustedes…» y 465–486 s «¿Cómo es posible, presidente…?»; de ella
        # también 332–341 s «psicólogos capacitados…». Otra voz por el TEXTO (le hablan a ella o a la presidencia, ella no se llama
        # "señora senadora"): 687 s «Gracias a usted, señora senadora.», 734 s «Gracias a usted, señora presidenta.», 738 s
        # «Presidenta, señora senadora, por costumbre…»
        otra_voz=[[687.15, 689.59], [734.1, 736.23], [737.94, 741.56]],
        # «Sigo, presidente.» (0.8 s): por el texto es de ella, pero el "otra voz" de feminicidios lo puso la máquina y nadie lo
        # corrigió a mano -> no cuenta hasta que el usuario lo confirme (si es de ella: quitarlo de acá; nunca pasarlo a otra_voz sin él)
        dudoso=[[249.58, 250.88]]),
}


def _dur_fuente(d, sj):
    """duración de una fuente: meta.json (ffprobe del original) o la cabecera de su voz (fuentes viejas sin meta.json, BCP)"""
    try: return float(json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["duration"])
    except Exception: pass
    try:
        v = sj.get("voice") or "voice.wav"; w = wave.open(v if os.path.isabs(v) else os.path.join(d, v))
        return w.getnframes() / float(w.getframerate())
    except Exception: return None


def _fija_de(source, sj):
    """(clave, entrada) de VERDAD_FIJA para el archivo de `source`: por nombre; si no, la huella del original (si la fuente la
    tiene, manda ella: el archivo de esa ruta pudo cambiar); si no, el nombre del original SIN carpeta (otra PC, otra ruta) y la
    duración ± 0.5 s. Una re-ingesta del mismo archivo con otro nombre (que hereda speaker_fix) usa la misma verdad"""
    for clave, v in VERDAD_FIJA.items():
        if source in v["fuentes"]: return clave, v
    orig = os.path.basename(str(sj.get("original") or "").replace("\\", "/")).lower()
    for clave, v in VERDAD_FIJA.items():
        if sj.get("huella"):
            if sj["huella"] == v["huella"]: return clave, v
        elif orig and orig == v["archivo"].lower():
            df = _dur_fuente(os.path.join(STUDIO, "sources", source), sj)
            if df is not None and abs(df - v["dur"]) <= 0.5: return clave, v
    return None, None


def _quitar(ts, a, b):
    """tramos `ts` sin la parte que cae en [a, b] (igual que plan._sub_ranges)"""
    return [r for x, y in ts for r in ([(x, y)] if y <= a or x >= b else [(x, a)] * (x < a) + [(b, y)] * (y > b))]


def verdad(source, sj=None):
    """VERDAD de quién habla para `source` -> dict(nombre, otra=[tramos de otra voz], ella=[tramos de ella], dudoso=[…], parcial)
    o None (no hay con qué comparar). `sj`: el source.json ya leído (si no, se lee). En orden:
      1. VERDAD_FIJA del mismo archivo: congelada, no cambia aunque se vuelva a etiquetar cualquier fuente
      2. fuente etiquetada a mano (sin reporter_auto) con "reporter": ese "reporter" + speaker_fix (igual que plan.load_source)
      3. fuente automática con correcciones del cliente (speaker_fix, propias o heredadas por ingest._heredar): SOLO esos tramos
         (parcial). Su "reporter" lo escribió label(): compararlo con label() sería medir el código contra sí mismo
    Sin "reporter" ni speaker_fix: None. Un "reporter" vacío de ingest NO quiere decir "nadie más habla" (daba 100 % engañoso)"""
    if sj is None: sj = json.load(open(os.path.join(STUDIO, "sources", source, "source.json"), encoding="utf-8"))
    clave, v = _fija_de(source, sj)
    if v: return dict(nombre=clave, otra=sorted(tuple(x) for x in v["otra_voz"]), ella=[],
                      dudoso=sorted(tuple(x) for x in v.get("dudoso", [])), parcial=False)
    fix = sj.get("speaker_fix") or []
    if not sj.get("reporter_auto") and sj.get("reporter"):
        rep = [tuple(x[:2]) for x in sj["reporter"]]
        for a, b, who, *_ in fix: rep = _quitar(rep, a, b) + ([(a, b)] if who == "R" else [])
        return dict(nombre=source, otra=sorted(rep), ella=[], dudoso=[], parcial=False)
    if fix:
        otra, ella = [], []
        for a, b, who, *_ in fix:                                          # en orden: la última corrección de un tramo manda
            otra, ella = _quitar(otra, a, b), _quitar(ella, a, b)
            (otra if who == "R" else ella).append((a, b))
        return dict(nombre=f"{source} (solo speaker_fix)", otra=sorted(otra), ella=sorted(ella), dudoso=[], parcial=True)
    return None


def etiquetas_verdad(V, SENT):
    """"L" / "R" de cada frase según la verdad V (por el CENTRO de la frase, como siempre); None = no cuenta (dudoso, o en una
    verdad parcial, fuera de lo corregido a mano)"""
    out = []
    for s_ in SENT:
        c = (s_["s"] + s_["e"]) / 2
        dentro = lambda ts: any(a <= c <= b for a, b in ts)
        if dentro(V["dudoso"]): out.append(None)
        elif dentro(V["otra"]): out.append("R")
        elif not V["parcial"] or dentro(V["ella"]): out.append("L")
        else: out.append(None)
    return out


def evaluate(source="lilian_conferencia_bcp"):
    V = verdad(source)
    if V is None:
        print(f"[voz] {source}: no hay verdad para comparar (ni congelada en VERDAD_FIJA, ni etiquetas a mano, ni speaker_fix)"); return None
    spk, sims, rep = label(source, write=False)
    P, SENT = sentences(source)
    lab = etiquetas_verdad(V, SENT)
    cuentan = [i for i, b in enumerate(lab) if b is not None]
    if not cuentan:
        print(f"[voz] {source}: ninguna frase cae en lo verificado a mano ({V['nombre']})"); return None
    ok = sum(spk[i] == lab[i] for i in cuentan); acc = ok / len(cuentan)
    nd = len(lab) - len(cuentan)
    print(f"[voz] precisión contra etiquetas manuales: {acc * 100:.1f}% ({ok}/{len(cuentan)})"
          + (f" · verdad: {V['nombre']}" if V["nombre"] != source else "")
          + (f" · solo las frases corregidas a mano ({nd} sin verdad)" if V["parcial"] else f" · {nd} por confirmar (no cuentan)" if nd else ""))
    for i in cuentan:
        s = SENT[i]
        if spk[i] != lab[i]: print(f"   ✗ {s['s']:6.1f}s manual {lab[i]} auto {spk[i]} sim {sims[i]:.3f}  {s['text'][:70]}")
    if not V["parcial"]:
        for i, s in enumerate(SENT):
            if lab[i] is None: print(f"   ? {s['s']:6.1f}s por confirmar · auto {spk[i]} sim {sims[i]:.3f}  {s['text'][:70]}")
    return float(acc)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    src = sys.argv[2] if len(sys.argv) > 2 else "lilian_conferencia_bcp"
    {"build": build, "label": label, "eval": evaluate}[cmd](src)
