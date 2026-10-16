# Estudio de edición — CIFRAS EN PANTALLA: encontrar en lo que ella dice las cifras que vale la pena mostrar (estadísticas con
# lo que cuentan: "258 feminicidios", "37.825 denuncias de violencia familiar", "72 horas"), y SOLO esas. Fechas, horas, años,
# números de ley/artículo, cantidades chicas ("dos veces") y números sueltos no salen. Pocas por video (las más fuertes,
# separadas): si el video no tiene cifras de peso, no se muestra ninguna. Lo usan los estilos (styles/cifras_capa.py).
#   python cifras.py <fuente>            -> candidatas de la fuente entera con su puntaje (para revisar)
#   python cifras.py --json <words.json> -> idem sobre una transcripción suelta (analysis/<tag>/Txx_words.json)
import re, sys, json, os

UNITS = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
         "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
         "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22,
         "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
         "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
         "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
         "cuatrocientas": 400, "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
         "setecientas": 700, "ochocientos": 800, "ochocientas": 800, "novecientos": 900, "novecientas": 900}
MULT = {"mil": 1000, "millon": 10 ** 6, "millones": 10 ** 6, "billon": 10 ** 12, "billones": 10 ** 12}
# lo que se cuenta: sustantivos de estadística (pesan más). Raíz -> ícono de la tarjeta
STAT = {"feminicidi": "lazo", "victim": "lazo", "muert": "lazo", "asesinat": "lazo", "tentativ": "alerta", "denunci": "documento",
        "caso": "documento", "ley": "documento", "proyecto": "documento", "expediente": "documento", "causa": "documento",
        "hij": "personas", "niñ": "personas", "nin": "personas", "mujer": "personas", "person": "personas", "famili": "personas",
        "jubilad": "personas", "asegurad": "personas", "aportante": "personas", "trabajador": "personas", "afiliad": "personas",
        "ciudadan": "personas", "habitante": "personas", "vecin": "personas", "joven": "personas", "adolescente": "personas",
        "huerfan": "personas", "estudiant": "personas", "docente": "personas", "medic": "personas", "paciente": "personas",
        "intendent": "personas", "senador": "personas", "diputad": "personas", "concejal": "personas", "comunidad": "personas",
        "distrito": "personas", "departament": "personas", "municipi": "personas", "escuela": "documento", "hospital": "documento",
        "banco": "documento", "empresa": "documento", "empleo": "personas", "puesto": "personas", "voto": "documento",
        "guarani": "documento", "dolar": "documento", "millon": "documento", "porcent": "alerta", "por ciento": "alerta",
        "hora": "calendario", "dia": "calendario", "semana": "calendario", "mes": "calendario", "año": "calendario", "ano": "calendario",
        "kilometr": "alerta", "hectarea": "alerta", "tonelad": "alerta", "juzgad": "mazo", "tribunal": "mazo", "fiscal": "mazo",
        "detenid": "mazo", "imputad": "mazo", "condena": "mazo", "sentencia": "mazo", "allanamient": "mazo"}
MONTHS = {"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre", "octubre", "noviembre", "diciembre"}
FUNC = {"de", "del", "la", "el", "los", "las", "y", "a", "en", "que", "por", "para", "con", "un", "una", "se", "lo", "al", "su", "sus", "es",
        "son", "fue", "fueron", "hay", "mas", "más", "menos", "casi", "unos", "unas", "como", "o"}
NOUN_STOP = FUNC | {"veces", "vez", "minutos", "segundos", "puntos", "mismo", "misma", "solo", "sola", "primer", "primero", "primera",
                    "segundo", "segunda", "tercer", "tercero", "tercera", "y", "media"}


def norm(t):
    t = t.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"): t = t.replace(a, b)
    return t


def clean(t): return re.sub(r"[^\wáéíóúüñ%.,]", "", t.lower())


def parse_number(toks, i):
    """número que empieza en toks[i] (dígitos '37.825', '1,5', '20%' o palabras 'treinta y siete mil'): (valor, palabras usadas) o None"""
    t = clean(toks[i]); extra = 0
    while re.fullmatch(r"\d{1,3}(?:\.\d{3})*", t) and i + 1 + extra < len(toks) and re.fullmatch(r"\.\d{3}[.,%]?", clean(toks[i + 1 + extra])):
        t += clean(toks[i + 1 + extra]); extra += 1                    # whisper parte "37.825" en "37" + ".825"
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(%?)[.,]?", t)
    if m:
        v = float(m.group(1).replace(".", "")) + (float("0." + m.group(2)) if m.group(2) else 0.0)
        j = i + 1 + extra
        if j < len(toks) and norm(clean(toks[j])).rstrip(".,") in MULT: v *= MULT[norm(clean(toks[j])).rstrip(".,")]; j += 1
        return v, j - i, bool(m.group(3))
    total, cur, j, used = 0, 0, i, False
    while j < len(toks):
        w = norm(clean(toks[j])).rstrip(".,%")
        if w in UNITS: cur += UNITS[w]; used = True; j += 1
        elif w in MULT and used: total += max(1, cur) * MULT[w]; cur = 0; j += 1
        elif w == "y" and used and j + 1 < len(toks) and norm(clean(toks[j + 1])).rstrip(".,") in UNITS and UNITS[norm(clean(toks[j + 1])).rstrip(".,")] < 10: j += 1
        else: break
        if toks[j - 1].rstrip()[-1:] in ".,;:?!": break
    if not used: return None
    return float(total + cur), j - i, False


def stat_root(w):
    w = norm(w)
    for r, ic in STAT.items():
        if w.startswith(norm(r)): return r, ic
    return None, None


def candidates(words):
    """words = [{w|t, s, e, ...}] -> cifras candidatas [{value, label, icon, i0, i1, s, e, score, why}]"""
    toks = [x.get("w", x.get("t", "")) for x in words]
    out, i = [], 0
    while i < len(toks):
        r = parse_number(toks, i)
        if r is None: i += 1; continue
        v, n, pct = r
        j = i + n
        prev = [norm(clean(t)).rstrip(".,") for t in toks[max(0, i - 2):i]]
        nxt = [norm(clean(t)).rstrip(".,") for t in toks[j:j + 4]]
        raw = clean(toks[i])
        why, score = [], 0.0
        # descartes: años/fechas, horas, artículos/leyes, cantidades chicas, ordinales, números sin nada que contar
        is_year = 1900 <= v <= 2100 and float(v).is_integer() and ("." not in raw or (prev and prev[-1] in ("del", "el", "en", "ano", "desde", "hasta", "de")))
        if is_year and not (nxt and stat_root(nxt[0])[0] and nxt[0] not in ("ano", "anos")): i = j; continue
        if nxt[:2] and nxt[0] == "de" and len(nxt) > 1 and nxt[1] in MONTHS: i = j; continue          # "12 de octubre"
        if prev and prev[-1] in ("articulo", "ley", "numero", "nro", "resolucion", "decreto", "las", "la", "zona", "canal", "pagina"): i = j; continue
        if nxt and nxt[0] == "y" and len(nxt) > 1 and re.fullmatch(r"\d+", nxt[1] or ""): i = j; continue    # "21 y 30" (hora)
        if v < 5 and not pct: i = j; continue
        # lo que se cuenta: la primera palabra con contenido después del número (saltando "mil de", "de")
        k = j; label = []
        while k < len(toks) and k < j + 3:                              # primera palabra con contenido (saltando "de", "mil de"…)
            w = clean(toks[k]).rstrip(".,;:")
            if norm(w) in FUNC: k += 1; continue
            if norm(w) in NOUN_STOP or re.fullmatch(r"[\d.,%]+", w): break
            label.append(toks[k].strip().rstrip(".,;:?!")); k += 1; break
        endp = lambda q: toks[q].rstrip()[-1:] in ".,;:?!"
        if label and not endp(k - 1):
            while k + 1 < len(toks) and len(label) < 6:
                a, b = norm(clean(toks[k])).rstrip(".,;:"), norm(clean(toks[k + 1])).rstrip(".,;:")
                if a in ("de", "del") and b not in FUNC and not re.fullmatch(r"[\d.,%]+", b):            # "denuncias de violencia (familiar)"
                    label += [toks[k].strip(), toks[k + 1].strip().rstrip(".,;:?!")]; k += 2
                    if endp(k - 1): break
                    c = norm(clean(toks[k])).rstrip(".,;:") if k < len(toks) else ""
                    if c and c not in FUNC and endp(k): label.append(toks[k].strip().rstrip(".,;:?!")); k += 1
                    break
                elif a in ("y", "e") and stat_root(b)[0]:                                             # "hijos e hijas", "niñas y niños"
                    label += [toks[k].strip(), toks[k + 1].strip().rstrip(".,;:?!")]; k += 2
                    if endp(k - 1): break
                else: break
        # se corrige al toque: "hay 20 víctimas, 21 ya, de feminicidios" -> la cifra es 21 (lo último que dice)
        if k < len(toks):
            r2 = parse_number(toks, k)
            if r2 and k + r2[1] < len(toks) and norm(clean(toks[k + r2[1]])).rstrip(".,;:") == "ya" and abs(r2[0] - v) <= max(3, 0.2 * v):
                v = r2[0]; why.append("se corrigió: " + clean(toks[k]))
        if pct: label = ["por ciento"] + label; score += 2; why.append("%")
        if not label: i = j; continue
        root, ic = stat_root(label[0] if not pct else (label[1] if len(label) > 1 else "porcent"))
        if norm(label[0]) in NOUN_STOP: i = j; continue
        TIME = ("año", "ano", "dia", "hora", "semana", "mes")
        if root in TIME: score += 1.0; why.append(f"tiempo '{root}' (edad/duración: casi nunca es estadística)")
        elif root: score += 3; why.append(f"cuenta '{root}'")
        else: score += 0.5; why.append("sustantivo común")
        if v >= 20: score += 1; why.append("≥20")
        if v >= 100: score += 1; why.append("≥100")
        if v < 10 and not pct: score -= 1; why.append("<10")
        if raw[:1].isdigit(): score += 0.5                                           # dicho como cifra
        out.append(dict(value=v, pct=pct, label=" ".join(label), icon=ic or "documento", i0=i, i1=k, s=words[i].get("s"),
                        e=words[min(k, len(words) - 1)].get("e"), score=round(score, 1), why=why,
                        text=" ".join(toks[max(0, i - 4):min(len(toks), k + 3)])))
        i = j
    return out


def pick(cands, times, max_n=4, gap=3.5, min_score=3.5, per_min=2.0, dur=None):
    """las que se muestran: puntaje mínimo, separadas `gap` s (en un tramo de cifras van en fila, como hace el equipo: una tarjeta
    cada 3–4 s), como mucho `max_n` y `per_min` por minuto del video; empates de puntaje -> la que se dice primero"""
    if dur: max_n = min(max_n, max(1, int(per_min * dur / 60.0)))
    good = sorted([c for c in cands if c["score"] >= min_score and times(c) is not None], key=lambda c: (-c["score"], times(c)))
    out = []
    for c in good:
        t = times(c)
        if all(abs(t - times(o)) >= gap for o in out): out.append(c)
        if len(out) >= max_n: break
    return sorted(out, key=times)


def fmt(v, pct=False):
    if pct: return (f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")) + "%"
    if v >= 10 ** 6 and v % 10 ** 6 == 0: return f"{int(v // 10 ** 6)} millones" if v >= 2 * 10 ** 6 else "1 millón"
    return f"{int(round(v)):,}".replace(",", ".")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "--json":
        for p in sys.argv[2:]:
            ws = json.load(open(p, encoding="utf-8"))["words"]
            cs = candidates(ws); dur = (ws[-1]["e"] if ws else 60)
            sel = pick(cs, lambda c: c["s"], dur=dur)
            print(f"== {os.path.basename(p)}  ({len(cs)} candidatas, {len(sel)} elegidas)")
            for c in cs: print(f"  {'★' if c in sel else ' '} {c['score']:4.1f} {c['s']:6.1f}s {fmt(c['value'], c['pct']):>10} {c['label'][:34]:34s} | {c['text'][:70]}")
    else:
        os.environ["STUDIO_SOURCE"] = sys.argv[1]
        import plan as P
        cs = candidates(P.WORDS)
        for c in cs: print(f"  {c['score']:4.1f} {c['s']:7.1f}s {fmt(c['value'], c['pct']):>10} {c['label'][:34]:34s} | {c['text'][:80]}")
