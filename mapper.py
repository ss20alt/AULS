# Estudio de edición — MAPA DE CONTENIDO AUTOMÁTICO (punto 6): bloques de idea, tipo, importancia, titulares e historias.
# Lo que antes armaba un editor a mano (content.json) ahora sale de la transcripción + quién habla + la energía de la voz.
#   python mapper.py draft   <fuente>   -> sources/<fuente>/content_draft.json + content_review.html (borrador para revisar)
#   python mapper.py approve <fuente>   -> el borrador pasa a content.json (el mapa que usan los estilos)
#   python mapper.py eval               -> compara el mapa automático con el mapa manual de lilian_conferencia_bcp
# Si una fuente no tiene mapa aprobado, content.py usa el borrador automático (avisando que no está aprobado).
import os, sys, json, re, math, unicodedata, html
from collections import Counter

STUDIO = os.path.dirname(os.path.abspath(__file__))

STOP = set("""a al algo algunos ante antes aquí acá así aunque bien cada como con contra cual cuando cuánto de del desde donde dos e el él ella ellas
ellos en entre era eran es esa esas ese eso esos esta está están estaba estado estamos estar estas este esto estos estoy fue fueron ha
hace hacer hacia han has hasta hay he la las le les lo los más me mi mis mucho muy nada ni no nos nosotros o otra otro otros para pero poco
por porque pues que qué quien se sea según ser si sí sin sino sobre son su sus también tan tanto te tener tengo tiene tienen todo todos
tu tú tus un una uno unos usted ustedes va vamos van ver vez y ya yo vos sos digo dijo dije decir ahora entonces bueno acá allá ahí cosa
cosas vuelvo puede pueden hoy hecho mismo misma parte lado lugar tipo forma manera vengo voy vas va iba ir sido había hacen hizo hago
tenía tenemos teníamos verdad aparte""".split())
STOP |= set("""nuestro nuestra nuestros nuestras vuestro vuestra aquel aquella aquellos aquellas aquello cuyo cuya cuyos cuyas cuanto cuanta
cuantos cuantas cuál cuáles dónde cómo siempre nunca jamás nuevamente dentro fuera toda todas mucha muchas muchos poca pocas pocos demás
debe deben debemos debería deberían deberíamos podemos podría podrían quiero queremos quiere necesitamos necesita somos soy será serán
sería serían hubo haya hayan haga hagan creo cree creemos sabe sabemos sabrá dice dicen hemos tal tales sólo solo solamente realmente
además luego después incluso casi menos sigue siguen gracias llamado llamada llamados llamadas denominado denominada
uno tres cuatro cinco seis siete ocho nueve diez ambos ambas nadie alguien ninguno ninguna cualquier cualquiera""".split())
CARGOS = {"senador", "senadora", "senadores", "senadoras", "diputado", "diputada", "diputados", "intendente", "intendenta", "concejal",
          "concejales", "presidente", "presidenta", "ministro", "ministra", "gobernador", "gobernadora", "director", "directora", "fiscal",
          "juez", "jueza", "doctor", "doctora", "profesor", "profesora", "trabajador", "trabajadores", "productor", "productores"}

# Vocabulario GENÉRICO del discurso político en castellano (no de esta conferencia): marcadores que abren un tema nuevo,
# arranques que continúan la idea anterior, y palabras que pesan en un titular. Lo propio de cada cliente va en clients/<cliente>.json ("keywords").
MARK_STRONG = [r"^por otro lado\b", r"^en (primer|segundo|tercer|último) lugar\b", r"^por último\b", r"^finalmente\b", r"^además\b",
               r"^también\b", r"^(y )?ahora (te|le|les) (voy a decir|digo)\b", r"^lo que (yo )?vengo\b", r"^quiero (decir|dejar|aclarar)\b",
               r"^(y )?(esto|eso) (inició|empezó|comenzó)\b", r"^(y )?hay muchas\b", r"^otro (tema|punto)\b", r"^respecto (a|de)\b", r"^en cuanto a\b"]
VOC = r"^(y )?¿?vos\b|^(y )?¿?usted,"                                     # se dirige a un rival: arranca un bloque de ataque
CONT = [r"^como\b", r"^por lo tanto\b", r"^entre (los|las) cuales\b", r"^que\b", r"^pero\b", r"^porque\b", r"^con (el|la|los|las)\b",
        r"^una?\b", r"^y se\b", r"^y lo que\b", r"^no me\b", r"^él que\b", r"^eso es\.?$", r"^de\b", r"^y (hasta|si|eso)\b", r"^o sea\b",
        r"^no,? no\b", r"^no hay\b", r"^sí,\b", r"^todavía\b", r"^es decir\b", r"^incluso\b", r"^sobre todo\b"]
KIND_RULES = [                                                             # (tipo, patrones) — gana el que más suma
    ("propuesta", [r"voy a presentar", r"proyecto de ley", r"propong", r"propuesta", r"vamos a (presentar|impulsar)", r"\bproyecto\b"]),
    ("logro", [r"\bleyes\b", r"cambiaron la vida", r"mi (último )?trabajo", r"\blogr(é|ó|amos|aron|ado|ada|ados|adas)\b", r"\bhice\b",
               r"realidad", r"conseguimos", r"aprobamos"]),
    ("ataque", [r"\bvos\b", r"\bsos\b", r"\bfuiste\b", r"\bhiciste\b", r"\bestabas\b", r"\bestás\b", r"cobard", r"vende ?patria", r"\bte importa\b",
                r"\binició\b", r"mentir", r"traici", r"corrupt"]),
    ("denuncia", [r"irresponsab", r"enfrentamiento", r"doloroso", r"en vilo", r"\bculpa\b", r"zozobra", r"denunci", r"abuso"]),
    ("dato", [r"\bbanco", r"sistema financiero", r"\binforme", r"liquidez", r"sumario", r"\b(?!(?:19|20)\d\d\b)\d+", r"consultas", r"control",
              r"millones", r"por ciento"]),
    ("mensaje", [r"ciudadan", r"tranquil", r"garantiz", r"protegid", r"\bcalma\b", r"certeza", r"pueblo", r"quiero decirles", r"familias"]),
]
CLOSE_W = [r"mensaje", r"calma", r"certeza", r"ciudadan", r"garantiz", r"tranquil", r"pueblo", r"merecen", r"familias", r"compromiso"]
STRONG_W = {"crisis", "intervención", "sólido", "fuerte", "garantizados", "protegidos", "irresponsable", "cobardía", "calma", "zozobra", "sumario",
            "liquidez", "salud", "educación", "jubilados", "ahorros", "ley", "proyecto", "irregularidad", "presencia", "certeza", "préstamos",
            "reclamos", "enfrentamiento", "control", "corrupción", "mentira", "seguridad", "justicia", "empleo", "trabajo", "pobreza", "deuda",
            "impuestos", "inflación", "transparencia", "denuncia", "traición", "abandono", "propuesta", "reforma", "presupuesto", "jubilación"}
EPITHETS = ["vende patria", "irresponsable", "cobarde", "mentiroso", "corrupto", "traidor", "incapaz", "ausente", "hipócrita", "sinvergüenza"]
PRED_ADJ = r"\b(está|están|estaba|estaban|es|son|sigue|siguen|queda|quedan)\s+(muy\s+)?(sólid[oa]s?|fuertes?|garantizad[oa]s?|protegid[oa]s?|segur[oa]s?|estables?|tranquil[oa]s?|firmes?)\b"
VERBISH = re.compile(r"(ó|aron|ieron|aba|aban|ía|ían|ando|iendo|amos|emos|imos|ado|ido|ar|er|ir|\w{4}an|(ar|er|ir|ando|iendo)(se|lo|la|le|los|las|les|nos|me|te))$")
# adjetivo después del sustantivo ("JUSTICIA RÁPIDA", "FAMILIAS PARAGUAYAS", "SALUD MENTAL"): terminaciones típicas
ADJISH = re.compile(r"(al|ales|ble|bles|ivo|iva|ivos|ivas|ico|ica|icos|icas|oso|osa|osos|osas|ario|aria|arios|arias|ente|entes|ante|antes|"
                    r"ado|ada|ados|adas|ido|ida|idos|idas|ista|istas|ano|ana|anos|anas|ense|enses|dor|dora|dores|doras|il|iles|ero|era|eros|"
                    r"eras|ino|ina|inos|inas|ayo|aya|ayos|ayas|eno|ena|enos|enas|ior|iores|uro|ura|uros|uras)$")
PRENOM = {"último", "última", "últimos", "últimas", "primer", "primera", "primeros", "primeras", "nuevo", "nueva", "nuevos", "nuevas", "gran",
          "grandes", "mayor", "mejor", "peor", "verdadero", "verdadera", "único", "única", "buen", "buena", "mala", "segundo", "segunda", "plena"}
CLITIC = {"te", "le", "les", "me", "nos", "se", "lo", "la", "los", "las"}


def deacc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def toks(text):
    return re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", text)


def low(t): return t.lower().strip("¿?¡!.,;:")


def has(pats, text): return any(re.search(p, text) for p in pats)


# ------------------------------------------------------------------ segmentación
def kind_scores(text):
    return {kind: sum(len(re.findall(p, text, flags=re.I)) for p in pats) for kind, pats in KIND_RULES}


def boundary_score(S, k, cur):
    """¿empieza un bloque nuevo en la frase k? (frases de la misma persona)"""
    a, b = S[k - 1], S[k]
    if a["spk"] == "R": return -9.0                                        # la primera frase después de la pregunta es la respuesta
    if b.get("soft_start"): return -9.0                                    # trozo de una frase larga sin puntuación que sigue a la anterior
    blk_dur = S[cur[-1]]["e"] - S[cur[0]]["s"]
    blk_first_q = S[cur[0]]["spk"] == "R"
    t = b["text"].lower().lstrip("¿¡ ").strip()
    gap = b["s"] - a["e"]
    sc = 0.0
    if has(MARK_STRONG, t): sc += 3.0
    if re.search(VOC, b["text"].lower()): sc += 2.5 if not re.search(VOC, a["text"].lower()) else 0.5
    if b["text"].lstrip().startswith("¿") and not a["text"].rstrip().endswith("?"): sc += 1.0
    if gap >= 1.6: sc += 1.5
    elif gap >= 1.0: sc += 0.8
    if has(CONT, t): sc -= 2.5
    if b["dur"] < 2.0 and not has(MARK_STRONG, t): sc -= 1.5
    if b["dur"] < 2.0 and k + 1 < len(S) and S[k + 1]["spk"] == "L" and has(MARK_STRONG, S[k + 1]["text"].lower().lstrip("¿¡ ")):
        sc -= 3.0                                                           # frase corta antes de un "Por otro lado…": es el remate del bloque actual
    if blk_dur >= 25: sc += 3.5                                            # un bloque de más de 25 s ya no entra como idea suelta
    elif blk_dur >= 18: sc += 1.0
    if blk_dur < 5: sc -= 1.5
    if blk_first_q and gap >= 1.5: sc += 1.5                               # la respuesta a una pregunta termina en una pausa larga
    if a["text"].rstrip().endswith("?") and a["spk"] == "L" and not b["text"].lstrip().startswith("¿"): sc += 0.5   # cierre de una pregunta retórica
    nouns = {low(w) for w in toks(b["text"]) if w[:1].isupper() and low(w) not in STOP} - {low(w) for w in toks(a["text"])}
    if len(nouns) >= 2 and not b["text"].startswith(("¿", "Y ", "y ")): sc += 0.7    # aparece un nombre propio nuevo ("Gustavo Leite")
    kb, kc = kind_scores(b["text"]), kind_scores(" ".join(S[i]["text"] for i in cur if S[i]["spk"] == "L"))   # cambia el tipo de idea
    if kb and kc:
        bb, cc = max(kb, key=kb.get), max(kc, key=kc.get)
        if bb != cc and kb[bb] >= 2 and kc[cc] >= 2 and kb.get(cc, 0) == 0: sc += 1.5
    return sc


OPERATIVA = re.compile(r"\b(podr[íi]an? (mostrar|pasar|poner|proyectar)|(muestren|pasen|pongan|proyecten|pasame|pasáme|poneme|ponéme) (la|el|las|los)\b|"
                       r"si (me )?permiten? (mostrar|pasar|proyectar)|(mostrar|pasar|proyectar) (la|el) (imagen|video|lámina|gráfico)|"
                       r"(se escucha|me escuchan)\b|(¿)?(tengo|tenemos) (sonido|micrófono|audio)\b)", re.I)


def segment(S, thr=2.0):
    """-> lista de bloques [índices de frases] + frases sueltas (preámbulos de periodista, agradecimientos)"""
    blocks, cur, skip = [], [], []
    k = 0
    while k < len(S):
        s = S[k]
        if s["spk"] == "R":                                                # turno de periodista: la pregunta es la última frase con "?"
            j = k
            while j + 1 < len(S) and S[j + 1]["spk"] == "R": j += 1
            run = list(range(k, j + 1))
            qs = [i for i in run if "?" in S[i]["text"]]
            if cur: blocks.append(cur); cur = []
            if qs and j + 1 < len(S):
                skip += [i for i in run if i < qs[-1]]
                cur = [i for i in run if i >= qs[-1]]
            else: skip += run
            k = j + 1; continue
        if s["dur"] <= 9.0 and OPERATIVA.search(s["text"]):             # le pide al operador que muestre algo / prueba de sonido:
            if cur: blocks.append(cur); cur = []                         # no es contenido (cierra el bloque y no entra)
            skip.append(k); k += 1; continue
        if cur and boundary_score(S, k, cur) >= thr: blocks.append(cur); cur = []
        cur.append(k); k += 1
    if cur: blocks.append(cur)
    return blocks, skip


# ------------------------------------------------------------------ titulares
def idf_table(S):
    df = Counter()
    for s in S: df.update({low(w) for w in toks(s["text"])})
    n = len(S)
    return lambda w: math.log((n + 1) / (df.get(w, 0) + 0.5))


def word_db(P, w):
    seg = P.R10[int(w["s"] * 100):int(w["e"] * 100) + 1]
    return float(seg.max()) if len(seg) else -60.0


def _surface(words, key):
    """palabra tal como aparece en el bloque (para anclar el titular al momento en que se dice)"""
    key = deacc(key.lower())
    return next((w["t"].strip(".,¿?¡!;:") for w in words if deacc(low(w["t"])).startswith(key[:max(4, len(key) - 2)])), key)


DET_SG, DET_PL = {"el", "la", "su", "nuestro", "nuestra", "un", "una", "este", "esta"}, {"los", "las", "sus", "nuestros", "nuestras", "unos", "unas", "estos", "estas"}
PREP = {"en", "de", "del", "a", "al", "con", "por", "para", "sobre", "entre", "desde", "hacia", "sin", "según"}
SKIP_ADJ = {"distintos", "distintas", "diferentes", "varios", "varias", "todos", "todas", "mismos", "mismas", "otros", "otras", "pocos", "muchos"}


def subject_before(clause, plural):
    """sujeto de 'X está ADJ': el sustantivo tras el último artículo que concuerda en número y no va después de una preposición
    ('sus ahorros en los distintos bancos están garantizados' -> ahorros)"""
    t = re.findall(r"[a-záéíóúñ]+", clause)
    dets = DET_PL if plural else DET_SG
    for i in range(len(t) - 1, -1, -1):
        if t[i] in dets and not (i > 0 and t[i - 1] in PREP):
            nxt = [w for w in t[i + 1:] if w not in STOP and w not in SKIP_ADJ]
            if nxt and not VERBISH.search(nxt[0]): return nxt[0]
    return None


def rule_headline(sents, words, is_q, used_heads, strong):
    """titulares por reglas editoriales (en este orden): pregunta retórica de ella · 'no hay X' (respuesta) · calificativo ·
    'N está ADJ' (sistema sólido, ahorros garantizados). Devuelve [titular, ancla] o None."""
    cands = []
    for s in sents:                                                        # "¿Vos dónde estabas cuando…?" -> ¿DÓNDE ESTABAS?
        t = s["text"].strip()
        m = re.search(r"(?:^|[.?!]\s*)(?:y\s+)?¿\s*(?:y\s+)?(?:vos,?\s+|usted,?\s+)?([a-záéíóúñ]+)\s+([a-záéíóúñ]+)(?:\s+([a-záéíóúñ]+))?", t, flags=re.I)
        if m and s["spk"] == "L" and m.group(1).lower() in ("qué", "dónde", "cuándo", "cómo", "quién", "por", "cuánto", "para"):
            w2 = m.group(2)
            if m.group(1).lower() in ("por", "para") and w2.lower() != "qué": continue
            if w2.lower() in CLITIC and m.group(3): w2 = f"{w2} {m.group(3)}"           # "¿Qué te importa?" (no "¿QUÉ TE?")
            elif w2.lower() in ("es", "son", "está", "están", "fue", "era", "hay", "se"):           # "¿Cómo es posible…?" (no "¿CÓMO ES?")
                if not m.group(3) or m.group(3).lower() in STOP: continue
                w2 = f"{w2} {m.group(3)}"
            cands.append((f"¿{m.group(1)} {w2}?".upper(), w2.split()[-1]))
    txt = " ".join(s["text"] for s in sents).lower()
    m = re.search(r"\bno hay\b(?:\s+(?:ni|ninguna|ningún|habrá|y))*\s+([a-záéíóúñ]+)", txt)     # "No, no hay ninguna crisis" -> NO HAY CRISIS
    if m and is_q and m.group(1) not in STOP: cands.append((f"NO HAY {m.group(1).upper()}", m.group(1)))
    for e in EPITHETS:                                                     # "Él que es un vende patria" -> VENDE PATRIA
        if re.search(r"\b" + e.replace(" ", r"\s*") + r"\b", txt): cands.append((e.upper(), e.split()[0]))
    if re.search(r"\bcobardía\b", txt): cands.append(("COBARDÍA", "cobardía"))
    for m in re.finditer(PRED_ADJ, txt):                                   # "el sistema financiero está sólido" -> SISTEMA SÓLIDO
        subj = subject_before(txt[max(0, m.start() - 140):m.start()], m.group(3).endswith("s"))
        if subj: cands.append((f"{subj} {m.group(3)}".upper(), m.group(3)))
    for h, a in cands:
        if h not in used_heads and len(h) <= 24: return [h, _surface(words, a)]
    return None


def titular_malo(h):
    """control de calidad de un titular automático: None si está bien; si no, el motivo (lo usa la prueba permanente)"""
    if not h: return None
    ws = [low(w) for w in toks(h)]
    if not ws: return None
    if h.startswith("¿"): return "pregunta incompleta" if ws[-1] in ("es", "son", "está", "están", "fue", "era", "hay", "se") else None
    if all(w.isdigit() for w in ws): return "es solo un número"
    if h.upper().startswith("NO HAY ") and len(ws) == 3: return None     # regla editorial ("NO HAY CRISIS")
    if h.upper() == "LAS CIFRAS": return None                             # bloque de estadísticas (como lo tituló el editor)
    fun = STOP | PREP | DET_SG | DET_PL
    if ws[-1] in fun: return f"termina en «{ws[-1]}»"
    if ws[0] in fun: return f"empieza con «{ws[0]}»"
    if len(ws) == 1 and ws[0] in SKIP_ADJ: return "adjetivo suelto"
    verbo = lambda w: ((VERBISH.search(w) or VERBISH.search(deacc(w))) and w not in STRONG_W and not ADJISH.search(deacc(w))
                       and not w.endswith(("ía", "ías")))                 # "DEFENSORÍA", "ECONOMÍA", "POLICÍA" son sustantivos
    if len(ws) <= 2 and any(verbo(w) for w in ws): return "tiene un verbo"
    return None


_NC = {}
def nouns_of(S):
    """palabras que en esta transcripción aparecen después de un artículo, posesivo o demostrativo: son sustantivos
    ("una propuesta", "este proyecto", "nuestro país"); un verbo nunca va ahí ("empieza", "sabrá", "llega")"""
    k = id(S)
    if k not in _NC:
        dets = DET_SG | DET_PL | {"al", "del", "aquel", "aquella", "aquellos", "aquellas", "ese", "esa", "esos", "esas", "mi", "mis", "tu", "tus",
                                  "otro", "otra", "otros", "otras", "cada", "mucha", "muchas", "muchos", "toda", "todas", "dicho", "dicha"}
        ns = set()
        for x in S:
            t = [low(w) for w in toks(x["text"])]
            for a, b in zip(t, t[1:]):
                if a in dets and b not in STOP and not VERBISH.search(deacc(b)): ns.add(b)
        _NC[k] = ns
    return _NC[k]


def headline(P, S, ks, idf, used_heads, strong=None, kind=None):
    """titular: primero las reglas editoriales; si ninguna aplica, la frase nominal más fuerte del bloque
    (palabras raras en la conferencia + vocabulario fuerte + dichas con énfasis; se evitan verbos sueltos)"""
    strong = {x.lower() for x in (strong or STRONG_W)}
    sents = [S[k] for k in ks if S[k]["spk"] == "L"] or [S[k] for k in ks]
    words = [w for s in sents for w in s["words"]]
    r = rule_headline(sents, words, S[ks[0]]["spk"] == "R", used_heads, strong)
    dbs = [word_db(P, w) for w in words]
    med = sorted(dbs)[len(dbs) // 2] if dbs else -30
    def wscore(i):
        t = low(words[i]["t"])
        if t in STOP or len(t) < 3: return None
        sc = idf(t) + (2.0 if t in strong else 0.0)
        if VERBISH.search(deacc(t)) and t not in strong: sc -= 1.5           # un verbo suelto no es titular ("INICIÓ", "RECLAMARON")
        sc += 0.25 * max(0.0, dbs[i] - med)                               # énfasis de la voz
        return sc
    NOUNS = nouns_of(S)
    proper = lambda i: words[i]["t"][:1].isupper() and i > 0 and words[i - 1]["t"][-1] not in ".?!" and low(words[i]["t"]) not in STOP
    nounish = lambda i: (low(words[i]["t"]) in NOUNS or proper(i) or low(words[i]["t"]) in strong) and not (
        VERBISH.search(deacc(low(words[i]["t"]))) and low(words[i]["t"]) not in strong and not proper(i))
    ADJ_SEGURO = re.compile(r"(al|ales|ble|bles|ivo|iva|ivos|ivas|ico|ica|icos|icas|oso|osa|osos|osas|ario|aria|arios|arias|ense|enses|ayo|aya|ayos|ayas|ado|ada|ados|adas|ido|ida|idos|idas)$")
    def adjish(i):                                                        # "senador" termina como adjetivo pero en el texto es sustantivo ("el senador")
        w = deacc(low(words[i]["t"]))
        if w.endswith("mente") or not ADJISH.search(w): return False
        if low(words[i]["t"]) in CARGOS: return False                      # "DEPARTAMENTO SENADOR" no: senador es sustantivo
        return low(words[i]["t"]) not in NOUNS or bool(ADJ_SEGURO.search(w))
    capw = lambda i: words[i]["t"][:1].isupper() and low(words[i]["t"]) not in STOP
    inicio = lambda i: i == 0 or words[i - 1]["t"][-1] in ".?!"
    def corrida(i):                                                       # nombre propio entero ("Gustavo Leite", "Corte Suprema de Justicia")
        a = b = i
        while a > 0 and capw(a - 1) and words[a - 1]["t"][-1] not in ".,?!;:" and not inicio(a - 1): a -= 1
        while b + 1 < len(words) and capw(b + 1) and words[b]["t"][-1] not in ".,?!;:": b += 1
        return a, b
    def entero(i, j):                                                     # no cortar un nombre por la mitad ("SUPREMA DE JUSTICIA", "DAISY PAOLA")
        if capw(i) and corrida(i)[0] < i: return False
        if capw(j) and corrida(j)[1] > j: return False
        return True
    solo_num = lambda i: low(words[i]["t"]).isdigit()
    cands = []
    for i in range(len(words)):
        s0 = wscore(i)
        if s0 is None: continue
        if (nounish(i) and not solo_num(i) and entero(i, i) and low(words[i]["t"]) not in SKIP_ADJ | PRENOM | {"fuerte", "fuertes", "sólido", "sólida"}
                and not (adjish(i) and low(words[i]["t"]) not in NOUNS)):    # un adjetivo solo ("FUERTE") no es titular
            cands.append((s0, i, i))                                      # palabra sola: solo un sustantivo ("EMPIEZA", "SABRÁ", "DISTINTAS" no)
        if (i + 2 < len(words) and capw(i) and proper(i + 1) and proper(i + 2) and all(words[x]["t"][-1] not in ".,?!;:" for x in (i, i + 1))
                and entero(i, i + 2)):                                    # nombre completo de tres palabras ("Daisy Paola Jiménez")
            s1_, s2_ = wscore(i + 1), wscore(i + 2)
            if s1_ is not None and s2_ is not None: cands.append((s0 + s1_ + s2_ + 0.8, i, i + 2))
        # frase de 2-3 palabras: sustantivo + adjetivo · nombre propio · adjetivo antepuesto + sustantivo · sustantivo + "de" + sustantivo
        if i + 1 < len(words) and words[i]["t"][-1] not in ".,?!":
            s1 = wscore(i + 1)
            pair = (nounish(i) and adjish(i + 1)) or (proper(i) and proper(i + 1)) or (low(words[i]["t"]) in PRENOM and nounish(i + 1))
            if s1 is not None and pair and entero(i, i + 1): cands.append((s0 + s1 + 0.8, i, i + 1))
            if i + 2 < len(words) and low(words[i + 1]["t"]) in ("de", "del") and words[i + 1]["t"][-1] not in ".,?!":
                s2 = wscore(i + 2)
                w2_ = low(words[i + 2]["t"])
                y_ok = nounish(i + 2) or (w2_.endswith("s") and len(w2_) >= 5 and not capw(i + 2))     # "pedidos de INFORMES"
                if (s2 is not None and nounish(i) and y_ok and not solo_num(i + 2) and not VERBISH.search(deacc(w2_)) and entero(i, i + 2)
                        and not (capw(i) and not capw(i + 2))):           # "JUAN DE NORTE" no; "CIUDAD DE ENCARNACIÓN" sí
                    cands.append((s0 + s2 + 0.6, i, i + 2))                   # "PEDIDOS DE INFORMES", "FALTA DE SEGURIDAD"
    if not cands: return (r + [""]) if r else ["", "", ""]
    if kind != "ataque":                                                  # "la senadora Yolanda Paredes", "el amigo Juan Afara": a quien ella
        def mencion(i, j):                                                # nombra o agradece no es el tema del bloque (en un ataque, sí)
            return (all(capw(x) for x in range(i, j + 1) if low(words[x]["t"]) not in ("de", "del")) and i > 0
                    and low(words[i - 1]["t"]) in CARGOS | {"compañero", "compañera", "amigo", "amiga", "colega", "don", "doña"})
        cands = [((c[0] - 100.0) if mencion(c[1], c[2]) else c[0], c[1], c[2]) for c in cands]   # el nombre solo si no hay otra cosa
    cands.sort(reverse=True)
    h = None
    for sc, i, j in cands:
        t_ = " ".join(w["t"].strip(".,¿?¡!;:") for w in words[i:j + 1])
        if len(t_) <= 24 and t_.upper() not in used_heads and (sc if sc > -50 else sc + 100.0) >= 3.0: h = t_; break
    if h is None and not r: return ["", "", ""]                            # nada con fuerza de titular: el bloque va sin titular
    if h is None: i = j = -1
    else: anchor = max((words[x]["t"].strip(".,¿?¡!;:") for x in range(i, j + 1)), key=lambda t: idf(low(t)))
    if r: h, anchor, i, j = r[0], r[1], -1, -1                            # regla editorial manda; la frase nominal pasa a bajada
    # bajada: la mejor frase que no se superpone con el titular
    sub = ""
    for sc2, a, b in cands:
        if b < i or a > j:
            t2 = " ".join(w["t"].strip(".,¿?¡!;:") for w in words[a:b + 1])
            ws2 = [low(words[x]["t"]) for x in range(a, b + 1)]
            named = b > a and all(words[x]["t"][:1].isupper() for x in (a, b))             # "Gustavo Leite", "Estados Unidos"
            if not (any(w in strong for w in ws2) or named) or VERBISH.search(deacc(ws2[0])): continue
            if 6 <= len(t2) <= 28 and low(t2) not in h.lower() and not any(w in h.lower() for w in ws2): sub = t2[:1].upper() + t2[1:]; break
    return [h.upper(), anchor, sub]


# ------------------------------------------------------------------ mapa
def classify(S, ks, pos):
    if S[ks[0]]["spk"] == "R": return "pregunta"
    txt = " ".join(S[k]["text"] for k in ks)
    score = kind_scores(txt)
    best = max(score, key=lambda x: score[x])
    return best if score[best] > 0 else "mensaje"


def prefix(text, n=6):
    return " ".join(text.split()[:n]).rstrip(".,;:")


def draft(source, write=True):
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import importlib, plan as P
    importlib.reload(P)
    import content as C
    importlib.reload(C)
    S = C.SENT
    blocks, skip = segment(S)
    idf = idf_table(S)
    T = S[-1]["e"]
    out, used_heads = [], set()
    for bi, ks in enumerate(blocks):
        kind = classify(S, ks, S[ks[0]]["s"] / T)
        tag = headline(P, S, ks, idf, used_heads, STRONG_W | set(P.CLIENT.get("keywords", [])), kind); used_heads.add(tag[0])
        dur = S[ks[-1]]["e"] - S[ks[0]]["s"]
        txt = " ".join(S[k]["text"] for k in ks)
        strong = sum(1 for w in toks(txt) if w in STRONG_W or low(w) in {x.lower() for x in STRONG_W})
        imp = 3 + (1 if strong >= 2 else 0) + (1 if kind in ("mensaje", "pregunta", "ataque") and strong >= 1 else 0) - (1 if dur < 4 else 0) - (1 if strong == 0 else 0)
        try:                                                               # estadísticas de peso ("258 víctimas de feminicidio"): es de lo más
            import cifras as CF                                            # fuerte de un discurso -> el resumen no las deja afuera
            cs = [c for c in CF.candidates([w for k in ks for w in S[k].get("words", [])]) if c["score"] >= 3.5] if kind != "pregunta" else []
            if cs: imp = 5 if len(cs) >= 2 else imp + 1
            if len(cs) >= 2 and "LAS CIFRAS" not in used_heads:            # bloque de estadísticas: "LAS CIFRAS" (como lo tituló el editor)
                top = max(cs, key=lambda c: c["score"]); anc = (top["label"].split() or [tag[1]])[0]
                if tag[0]: used_heads.discard(tag[0])
                tag = ["LAS CIFRAS", anc, tag[2]]; used_heads.add("LAS CIFRAS"); kind = "dato" if kind == "mensaje" else kind
        except Exception: pass
        bid = re.sub(r"[^a-z0-9]+", "_", deacc(tag[1] or "bloque").lower()).strip("_")[:14] or "bloque"
        if any(o["id"] == bid for o in out): bid = f"{bid}_{bi}"
        out.append(dict(id=bid, firsts=[prefix(S[k]["text"]) for k in (ks[0], ks[-1])] if len(ks) > 1 else [prefix(S[ks[0]]["text"])],
                        topic=(tag[0].capitalize() + ": " if tag[0] else "") + prefix(S[ks[0]]["text"], 9), kind=kind, imp=max(1, min(5, imp)),
                        extra=0, tag=tag, s=round(S[ks[0]]["s"], 2), e=round(S[ks[-1]]["e"], 2), sents=ks, auto=True))
    # cierre: el mensaje final más claro (palabras de cierre, ubicado en la segunda mitad, hablado por ella)
    L = [o for o in out if o["kind"] != "pregunta"]
    cl = max(L, key=lambda o: sum(len(re.findall(p, " ".join(S[k]["text"] for k in o["sents"]), flags=re.I)) for p in CLOSE_W) + 2.0 * (o["s"] / T) + 0.3 * o["imp"])
    cl["kind"] = "cierre"
    out_stories = stories(S, out, cl)
    m = dict(blocks=[{k: v for k, v in o.items() if k not in ("s", "e", "sents")} for o in out], stories=out_stories,
             auto=dict(status="borrador", skip=[S[k]["text"][:50] for k in skip], timeline=[[o["id"], o["s"], o["e"]] for o in out]))
    if write:
        d = P.SRC["dir"]
        json.dump(m, open(os.path.join(d, "content_draft.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        review_html(source, S, out, m, os.path.join(d, "content_review.html"))
        print(f"[mapa] {source}: {len(out)} bloques, {len(out_stories)} historias -> content_draft.json + content_review.html (revisar y aprobar)")
    return m, out, skip


def stories(S, out, cl):
    """historias genéricas: cada una es un ángulo editorial (gancho, cuerpo por prioridad, cierre)"""
    Q = sorted([o for o in out if o["kind"] == "pregunta" and o is not cl], key=lambda o: (-o["imp"], o["e"] - o["s"]))
    hookq = next((o for o in Q if o["e"] - o["s"] <= 12.0), None)
    def frase_fuerte(o):
        """de las frases de ella en el bloque (2.5–9 s, completas): la que tiene la cifra de peso o más palabras fuertes"""
        import cifras as CF
        ks = [k for k in o["sents"] if S[k]["spk"] == "L" and 2.5 <= S[k]["dur"] <= 9.0 and S[k]["text"].rstrip()[-1:] in ".!?"]
        if not ks: return o["firsts"][0]
        def sc(k):
            cif = max([c["score"] for c in CF.candidates(S[k].get("words", []))] or [0.0])
            fu = sum(1 for w in toks(S[k]["text"]) if low(w) in {x.lower() for x in STRONG_W})
            return (3.0 if cif >= 3.5 else 0.0) + fu - 0.05 * S[k]["dur"]
        return prefix(S[max(ks, key=sc)]["text"])
    def hook_for(pool):
        if hookq: return dict(hook=hookq["id"])
        best = max(pool, key=lambda o: o["imp"]) if pool else None                 # sin preguntas: abre con la frase corta más fuerte
        return dict(hook_sent=frase_fuerte(best)) if best else {}
    by_imp = lambda xs: [o["id"] for o in sorted(xs, key=lambda o: -o["imp"]) if o is not cl and o is not hookq]
    st = {}
    st["resumen"] = dict(title="Lo más importante", **hook_for(out), body=by_imp(out), close=cl["id"])
    groups = {"mensaje": ("El mensaje", ("mensaje", "dato")), "prensa": ("Preguntas de la prensa", ("pregunta",)),
              "confrontacion": ("Respuesta a los ataques", ("ataque", "denuncia")), "propuestas": ("Lo que hago por el país", ("logro", "propuesta"))}
    for name, (title, kinds) in groups.items():
        pool = [o for o in out if o["kind"] in kinds and o is not cl]
        if len([o for o in pool if o is not hookq]) >= 2:
            h = hook_for(pool) if name != "confrontacion" else dict(hook_sent=max(pool, key=lambda o: o["imp"])["firsts"][0])
            st[name] = dict(title=title, **h, body=by_imp(pool) + [i for i in by_imp(out) if i not in by_imp(pool)][:2], close=cl["id"])
    return st


def review_html(source, S, out, m, path):
    rows = []
    for o in out:
        txt = html.escape(" ".join(S[k]["text"] for k in o["sents"]))
        mm = lambda t: f"{int(t // 60)}:{int(t % 60):02d}"
        rows.append(f"<tr><td class=t>{mm(o['s'])}–{mm(o['e'])}</td><td><b>{html.escape(o['id'])}</b><br><span class=k>{o['kind']} · imp {o['imp']}</span></td>"
                    f"<td><div class=h>{html.escape(o['tag'][0])}</div><div class=s>{html.escape(o['tag'][2])}</div><div class=a>ancla: {html.escape(o['tag'][1])}</div></td>"
                    f"<td class=x>{txt}</td></tr>")
    st = "".join(f"<li><b>{html.escape(k)}</b> — {html.escape(v['title'])}: gancho <i>{html.escape(v.get('hook') or v.get('hook_sent', ''))}</i>, "
                 f"cuerpo {html.escape(', '.join(v['body']))}, cierre <i>{html.escape(v['close'])}</i></li>" for k, v in m["stories"].items())
    page = f"""<!doctype html><meta charset=utf-8><title>Mapa de contenido — {html.escape(source)}</title>
<style>body{{font:14px system-ui;margin:24px;background:#0b1530;color:#e8ecf6}}table{{border-collapse:collapse;width:100%}}td{{border-top:1px solid #23325c;padding:8px;vertical-align:top}}
.t{{white-space:nowrap;color:#9aa6c4}}.k{{color:#ffc93c;font-size:12px}}.h{{font-weight:800;color:#ff4a55}}.s{{color:#cfd6ea}}.a{{color:#7f8bab;font-size:12px}}.x{{color:#b9c2da;max-width:640px}}</style>
<h1>Mapa de contenido (borrador automático) — {html.escape(source)}</h1>
<p>Revisar titulares y bloques. Para corregir: editar <code>content_draft.json</code>. Para aprobar: <code>python mapper.py approve {html.escape(source)}</code></p>
<h2>Historias</h2><ul>{st}</ul><h2>Bloques</h2><table>{''.join(rows)}</table>"""
    open(path, "w", encoding="utf-8").write(page)


def approve(source):
    d = os.path.join(STUDIO, "sources", source)
    m = json.load(open(os.path.join(d, "content_draft.json"), encoding="utf-8"))
    if os.path.exists(os.path.join(d, "content.json")):
        import shutil, time
        shutil.copy(os.path.join(d, "content.json"), os.path.join(d, f"content.prev_{time.strftime('%Y%m%d_%H%M%S')}.json"))
    m["auto"]["status"] = "aprobado"
    json.dump(m, open(os.path.join(d, "content.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[mapa] {source}: borrador aprobado -> content.json")


def evaluate(source="lilian_conferencia_bcp"):
    """fronteras de bloque automáticas vs. manuales (índice de frase)"""
    m, out, skip = draft(source, write=False)
    import content as C
    man = set(); manual_blocks = []
    for e in json.load(open(os.path.join(STUDIO, "sources", source, "content.json"), encoding="utf-8"))["blocks"]:
        ks = [C.find_sent(f) for f in e["firsts"]]
        man.add(min(ks)); manual_blocks.append((min(ks), e["id"], e["kind"], e["tag"][0]))
    auto = {o["sents"][0] for o in out}
    tp = len(man & auto); near = len({a for a in auto if a not in man and (a - 1 in man or a + 1 in man)})
    print(f"[mapa] fronteras: manual {len(man)} · auto {len(auto)} · exactas {tp} (precisión {tp / len(auto):.0%}, cobertura {tp / len(man):.0%}) · a una frase {near}")
    mk = {k: (i, kd, h) for k, i, kd, h in manual_blocks}
    for o in out:
        k0 = o["sents"][0]
        mm_ = mk.get(k0)
        print(f"  {'=' if mm_ else '+'} {o['s']:6.1f} {o['kind']:9s} imp{o['imp']} {o['tag'][0]:24s} | manual: {(mm_[1] + ' ' + mm_[2]) if mm_ else ''}")
    for k in sorted(man - auto): print(f"  - falta frontera en {k}: {mk[k][0]} ({mk[k][1]}) {C.SENT[k]['text'][:60]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    if cmd == "draft": draft(sys.argv[2])
    elif cmd == "approve": approve(sys.argv[2])
    else: evaluate(*(sys.argv[2:3] or []))
