# Estudio de edición — fuente, transcripción por frases y planificación automática (selector de escenas + EDL).
# Los CORTES se deciden por energía de la voz (valles de silencio), no por los tiempos de whisper (que se desvían ~0.3 s).
import os, json, wave, re, unicodedata
import numpy as np
from core import LIL, FPS, SR, SPF

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_NAME = os.environ.get("STUDIO_SOURCE", "lilian_conferencia_bcp")        # fuente activa (studio/sources/<nombre>/source.json)


def load_source(name):
    d = os.path.join(STUDIO_DIR, "sources", name)
    sj = json.load(open(os.path.join(d, "source.json"), encoding="utf-8"))
    res = lambda x: x if os.path.isabs(x) else os.path.join(d, x)
    src = dict(name=name, dir=d, video=res(sj["video"]), voice=res(sj["voice"]), transcript=res(sj["transcript"]), face=res(sj["face"]),
               client=sj.get("client", "lilian"))
    src["raw_transcript"] = src["transcript"]                                # whisper tal cual (entrada de align.py)
    for k in ("prompt", "tema", "keywords", "material", "legacy_angles", "layout", "panel", "tipo", "fecha"): src[k] = sj.get(k)   # vocabulario, claves, material, formato (panel) y tipo (entender.py)
    al = os.path.join(d, "transcript_aligned.json")                           # tiempos exactos por alineación forzada (align.py), si existen
    src["aligned"] = os.path.exists(al) and not os.environ.get("STUDIO_NO_ALIGN")
    if src["aligned"]: src["transcript"] = al
    cp = os.path.join(STUDIO_DIR, "clients", src["client"] + ".json")
    client = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    gl = dict(client.get("glossary", {})); gl.update(sj.get("glossary", {}))
    tup = lambda xs: [tuple(x[:2]) for x in xs]
    rep = tup(sj.get("reporter", []))
    for a, b, who, *_ in sj.get("speaker_fix", []):                        # correcciones de hablante del cliente (feedback.py)
        rep = _sub_ranges(rep, a, b) + ([(a, b)] if who == "R" else [])
    src["fixes"] = sj.get("fixes", []); src["nocut"] = tup(sj.get("nocut", []))
    return src, client, gl, sorted(rep), tup(sj.get("bad", [])), tup(sj.get("delete", []))


def _sub_ranges(rs, a, b):
    out = []
    for x, y in rs:
        if y <= a or x >= b: out.append((x, y)); continue
        if x < a: out.append((x, a))
        if y > b: out.append((b, y))
    return out


SRC, CLIENT, GLOSSARY, REPORTER, BAD, DELETE = load_source(SOURCE_NAME)
# GLOSSARY: errores de oído / nombres propios (perfil del cliente + fuente) · REPORTER: tramos con voz de periodistas
# BAD: tramos inservibles (alucinaciones de whisper sobre silencio) · DELETE: palabras inventadas por whisper


def _fix(t):
    core = t.strip(".,¿?¡!")
    return t.replace(core, GLOSSARY[core]) if core in GLOSSARY else t


def load_words():
    tr = json.load(open(SRC["transcript"], encoding="utf-8"))
    W = [dict(t=w["w"].strip(), s=w["s"], e=w["e"], ws=w.get("ws", w["s"])) for sg in tr for w in sg["words"]]
    # palabras inventadas por whisper / tramos inservibles: se quitan por su tiempo ORIGINAL de whisper (las marcas se hicieron sobre ese tiempo)
    W = [w for w in W if not any(a <= w["ws"] <= b for a, b in DELETE + BAD)]
    if SRC.get("aligned"):                                                 # la alineación CTC marca el pico de la letra: el sonido arranca ≈0.08 s antes
        for i, w in enumerate(W):
            lo = W[i - 1]["e"] if i > 0 else 0.0
            w["s"] = max(lo, w["s"] - 0.08)
            if w["e"] < w["s"] + 0.02: w["e"] = w["s"] + 0.02                # palabra tapada por la anterior (voces superpuestas): nunca se solapan
    i = 0                                                                  # whisper apila palabras en el mismo instante: repartirlas
    while i < len(W):
        j = i
        while j + 1 < len(W) and abs(W[j + 1]["s"] - W[i]["s"]) < 0.02: j += 1
        if j > i:
            end = W[j + 1]["s"] if j + 1 < len(W) else W[j]["e"]
            end = min(end, W[i]["s"] + 0.9)
            for k in range(i, j + 1):
                W[k]["s"] = W[i]["s"] + (end - W[i]["s"]) * (k - i) / (j - i + 1)
                W[k]["e"] = W[i]["s"] + (end - W[i]["s"]) * (k - i + 1) / (j - i + 1)
        i = j + 1
    for w in W: w["t"] = _fix(w["t"])
    for fx in ([] if os.environ.get("STUDIO_NO_FIXES") else SRC.get("fixes", [])):     # texto corregido por el cliente (con tiempos re-alineados)
        new = [dict(t=t_, s=s_, e=e_, ws=s_, fixed=True) for t_, s_, e_ in fx["words"]]     # reemplaza lo que había o INSERTA si whisper no escribió nada
        W = sorted([w for w in W if not fx["t0"] <= (w["s"] + w["e"]) / 2 <= fx["t1"]] + new, key=lambda w: w["s"])
    for i in range(1, len(W)):                                             # punto seguido de "e/y/o/u" en minúscula: era la misma frase ("doloroso e irresponsable")
        if W[i - 1]["t"].endswith(".") and W[i]["t"] in ("e", "y", "o", "u"): W[i - 1] = dict(W[i - 1], t=W[i - 1]["t"][:-1])
    return W


WORDS = load_words()


def off_record_from(words):
    """segundo desde el que ella pidió NO grabar ("esta parte no se va a grabar", "apaguen", "no lo graben", "esto no sale"):
    desde ahí no se usa nada de la fuente (se marca como BAD). None si no lo pidió"""
    import re as _re
    OFF = _re.compile(r"no se (va a |vaya a )?grab|no (lo |la |me )?graben|apag(ar|uen|á|a)\b.{0,12}(todo|c[aá]mara|eso)|esto no (se )?(sale|publica|sube)"
                      r"|fuera de (c[aá]mara|micr[oó]fono)|\bcorten\b|off the record", _re.I)
    cur = []
    for w in words:
        cur.append(w)
        if w["t"][-1:] in ".?!":
            if OFF.search(" ".join(x["t"] for x in cur)): return max(0.0, cur[0]["s"] - 0.3)
            cur = []
    return None


OFF_RECORD = off_record_from(WORDS)
if OFF_RECORD is not None:
    BAD = sorted(BAD + [(OFF_RECORD, 1e9)])
    print(f"[plan] {SOURCE_NAME}: pide no grabar desde {OFF_RECORD:.1f} s -> esa parte no se usa", flush=True)
_wf = wave.open(SRC["voice"])
VOICE = np.frombuffer(_wf.readframes(_wf.getnframes()), np.int16).reshape(-1, 2).astype(np.float32).mean(1) / 32768
NF = len(VOICE) // SPF
R = np.array([20 * np.log10(np.sqrt(np.mean(VOICE[f * SPF:(f + 1) * SPF] ** 2)) + 1e-9) for f in range(NF)])     # dB por fotograma
QUIET = R < -40.0
_h = SR // 100
R10 = np.array([20 * np.log10(np.sqrt(np.mean(VOICE[i:i + _h] ** 2)) + 1e-9) for i in range(0, len(VOICE) - _h, _h)])     # dB cada 10 ms


def recording_edges(words, r10, dur):
    """frases que la GRABACIÓN cortó: la cámara arrancó con ella ya hablando (voz desde el primer cuadro, sin pausa) o cortó
    mientras hablaba (la última palabra sin punto final, o con "..."). Esas frases sueltas no se usan (BAD)."""
    out = []
    _rep_at = lambda t: any(a <= t <= b for a, b in REPORTER)        # otra voz (periodista / locutor)
    if not words: return out
    floor = float(np.percentile(r10, 5)); voice = float(np.percentile(r10, 70))
    head = r10[1:60]                                                      # 10–600 ms
    rng = max(6.0, voice - floor)                                         # rango útil de la sala (acto ruidoso: ~10 dB; sala callada: ~40)
    ya = float(np.max(head[:4])) >= floor + 0.6 * rng                     # ya hay voz a los 10–40 ms (no arranca de silencio)
    sin_pausa = min(float(np.mean(head[i:i + 25])) for i in range(0, 35)) >= floor + 0.35 * rng
    if len(head) >= 50 and words[0]["s"] < 0.25 and not _rep_at(0.3) and ya and sin_pausa:
        k = next((i for i, w in enumerate(words) if w["t"][-1:] in ".?!" and not w["t"].endswith("...")), None)
        if k is not None and words[k]["e"] - words[0]["s"] < 15.0:
            out.append((0.0, words[k]["e"] + 0.05, "la grabación empezó con ella ya hablando"))
    last = words[-1]["t"]
    if (last[-1:] not in ".?!" or last.endswith("...")) and not _rep_at(words[-1]["s"]):
        k = max((i for i, w in enumerate(words[:-1]) if w["t"][-1:] in ".?!" and not w["t"].endswith("...")), default=None)
        if k is not None and words[-1]["e"] - words[k]["e"] < 15.0:
            out.append((words[k]["e"] + 0.05, 1e9, "la grabación terminó con ella hablando"))
    return out


for _a, _b, _why in recording_edges(WORDS, R10, len(VOICE) / SR):
    BAD = sorted(BAD + [(_a, _b)])
    print(f"[plan] {SOURCE_NAME}: {_why} -> no se usa {_a:.1f}–{min(_b, len(VOICE) / SR):.1f} s", flush=True)


def _gap_frame(t0, t1):
    """borde de fotograma (30 fps) con menos energía (resolución 10 ms) entre t0 y t1: el hueco real entre dos palabras"""
    best, bf = 1e9, int(round(t0 * FPS))
    for f in range(int(t0 * FPS), int(t1 * FPS) + 1):
        i = int(round(f / FPS * 100))
        v = float(np.mean(R10[max(0, i - 1):i + 2]))
        if v < best: best, bf = v, f
    return bf


def _first_gap(t0, t1, thr=-31.0):
    """primer borde de fotograma después de t0 con hueco audible (< thr dB a 10 ms); si no hay, el más silencioso de la ventana"""
    for f in range(int(np.ceil(t0 * FPS)), int(t1 * FPS) + 1):
        i = int(round(f / FPS * 100))
        if float(np.mean(R10[max(0, i - 1):i + 2])) < thr:
            g = f                                             # bajar hasta el fondo de ese hueco
            while g + 1 <= int(t1 * FPS) and edge_db(g + 1) < edge_db(g): g += 1
            return g
    return _gap_frame(t0, t1)


def edge_db(f):
    i = int(round(f / FPS * 100)); return float(np.mean(R10[max(0, i - 1):i + 2]))


def norm(w):
    w = unicodedata.normalize("NFD", w.lower()); w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", w)


def speaker_at(t): return "R" if any(a <= t <= b for a, b in REPORTER) else "L"


def build_units():
    """frases completas: corte en puntuación final o pausa > 0.7 s; los fragmentos sin cierre se unen a la siguiente"""
    W = [w for w in WORDS if not any(a <= w["s"] <= b for a, b in BAD)]
    sents, cur = [], []
    for i, w in enumerate(W):
        cur.append(w)
        gap = (W[i + 1]["s"] - w["e"]) if i + 1 < len(W) else 9
        if w["t"][-1] in ".?!" or gap > 0.7: sents.append(cur); cur = []
    if cur: sents.append(cur)
    units = []
    for s in sents:
        a, b = s[0]["s"], s[-1]["e"]
        f0, f1 = int(a * FPS), int(b * FPS) + 1
        rms = float(np.mean(R[f0:f1])) if f1 > f0 else -99.0
        if rms < -30: continue                                              # alucinación sobre silencio
        units.append(dict(s=a, e=b, words=s, text=" ".join(x["t"] for x in s), spk=speaker_at((a + b) / 2), rms=rms))
    merged = []
    for u in units:
        if merged and merged[-1]["text"][-1] not in ".?!" and u["s"] - merged[-1]["e"] < 2.0 and merged[-1]["spk"] == u["spk"]:
            p = merged[-1]; p["e"] = u["e"]; p["words"] = p["words"] + u["words"]; p["text"] += " " + u["text"]
        else: merged.append(dict(u))
    for k, u in enumerate(merged): u["i"] = k; u["dur"] = u["e"] - u["s"]; u["q"] = "¿" in u["text"] or u["text"].rstrip().endswith("?")
    return merged


UNITS = build_units()


# ------------------------------------------------------------------ cortes por silencio
def quiet_runs(a, b):
    runs, f = [], a
    while f < b:
        if QUIET[f]:
            g = f
            while g + 1 < b and QUIET[g + 1]: g += 1
            runs.append((f, g)); f = g + 1
        else: f += 1
    return runs


VOICE_DB, SIL_DB, SIL_MIN = -38.0, -40.0, 4          # voz > -38 dB · silencio < -40 dB durante ≥ 4 fotogramas


def _silent_run_at(f):
    """¿el fotograma f pertenece a un silencio de al menos SIL_MIN fotogramas?"""
    if f < 0 or f >= NF or R[f] >= SIL_DB: return False
    a = f
    while a - 1 >= 0 and R[a - 1] < SIL_DB: a -= 1
    b = f
    while b + 1 < NF and R[b + 1] < SIL_DB: b += 1
    return b - a + 1 >= SIL_MIN


_WS = sorted(WORDS, key=lambda w: w["s"])


def _prev_word_end(t):
    e = [w["e"] for w in _WS if w["s"] < t - 0.06]
    return e[-1] if e else None


def _next_word_start(t):
    s = [w["s"] for w in _WS if w["s"] > t + 0.02]
    return s[0] if s else None


def _nocut(t, side):
    """zona marcada por el cliente como 'acá no se corta' (feedback.py): el borde sale hacia afuera de la zona"""
    for a, b in SRC.get("nocut", []):
        if a < t < b: return a if side == "in" else b
    return t


def cut_in(t, lead=3, reach=1.2):
    """entrada: justo antes de que empiece la voz de la primera palabra. NUNCA retrocede más allá de la palabra anterior
    (si no hay pausa entre frases, corta en el hueco real entre las dos palabras)"""
    t = _nocut(t, "in")
    f = int(round(t * FPS))
    prv = _prev_word_end(t)
    lim = int((prv - 0.02) * FPS) if prv is not None else 0
    def safe_lead(g):                                      # el preámbulo de silencio nunca incluye la cola de la palabra anterior
        s = max(lim, g - lead, 0)
        while s < g and edge_db(s) > -36.0: s += 1
        return s
    if _silent_run_at(f):                                  # whisper adelantado: avanzar hasta el inicio real de la voz
        g = f
        while g < min(NF - 1, f + int(0.7 * FPS)) and R[g] < VOICE_DB: g += 1
        return safe_lead(g)
    g = f                                                  # estamos con voz: retroceder hasta el silencio previo, sin pasar la palabra anterior
    while g > max(0, f - int(reach * FPS), lim) and not _silent_run_at(g - 1): g -= 1
    if _silent_run_at(g - 1) and g - 1 >= lim: return safe_lead(g)
    if prv is not None:                                    # sin silencio entre frases: los huecos entre SÍLABAS engañan ("ha-cer"), así que
        h = int(prv * FPS)                                 # se entra tras el primer SILENCIO real que empiece antes de que arranque la palabra nueva
        while h <= int((t + 0.15) * FPS) and not _silent_run_at(h): h += 1     # (como mucho se pierde una conjunción, nunca se cuela una sílaba)
        if h <= int((t + 0.15) * FPS) and _silent_run_at(h):
            while h < NF - 1 and R[h] < VOICE_DB: h += 1
            return safe_lead(h)
    return max(0, _first_gap(prv - 0.02, t + 0.06) if prv is not None else _gap_frame(t - 0.30, t + 0.04))     # misma ventana que cut_out: ambos eligen el mismo hueco


def cut_out(t, tail=4, reach=1.2):
    """salida: cuando termina la voz de la última palabra. NUNCA avanza hasta la palabra siguiente
    (si la frase siguiente arranca sin pausa, corta en el hueco real entre las dos palabras)"""
    t = _nocut(t, "out")
    f = int(round(t * FPS))
    nxt = _next_word_start(t - 0.05)
    lim = int((nxt + 0.04) * FPS) if nxt is not None else NF - 1
    if _silent_run_at(f):                                  # whisper atrasado: volver al final real de la voz
        g = f
        while g > max(0, f - int(0.7 * FPS)) and R[g] < VOICE_DB: g -= 1
        end = g + 1
    else:
        g = f
        while g < min(NF - 1, f + int(reach * FPS), lim) and not _silent_run_at(g): g += 1
        if not _silent_run_at(g):
            return _first_gap(t - 0.02, (nxt + 0.06) if nxt is not None else t + 0.30)
        end = g
    k = end
    while k < end + tail and k < NF and R[k] < SIL_DB and k < lim and edge_db(k + 1) < -36.0: k += 1     # la cola nunca toca la voz siguiente
    return min(k, max(lim, end))


# ------------------------------------------------------------------ EDL
PAUSE_Q = (14, 5)
PAUSE_A = (12, 5)          # pausas ≥ 0.4 s se acortan a 5+5 fotogramas (nunca se toca la voz)


def build_edl(script, target_s, end_min=60, end_max=110, pre_default=5, shot_max=5.0, pause_keep=None):
    """script: [(kind, sid, role, a, b)] kind 'seg' = escena nueva · 'seg+' = continúa la anterior (omite lo del medio)"""
    TARGET = int(round(target_s * FPS))
    items, out_f, shot, sc, shot_start_out = [], 0, -1, -1, 0
    prev_b, prev_fe0 = None, None
    for k, entry in enumerate(script):
        kind, sid, role, a, b = entry[:5]; opts = entry[5] if len(entry) > 5 else {}
        if kind == "seg": sc += 1; shot += 1; shot_start_out = out_f
        fs0 = int(round(a * FPS)) if opts.get("in_exact") else cut_in(a)
        fe0 = int(round(b * FPS)) if opts.get("out_exact") else cut_out(b)
        contiguous = prev_b is not None and 0 <= a - prev_b < 0.4 and items
        if contiguous:                                                     # tramo seguido en el original: el audio continúa, sin corte
            fs0 = prev_fe0
            if items[-1]["fe"] != prev_fe0: pass
        prev_b, prev_fe0 = b, fe0
        pre_n = (pre_default if (sc >= 2 and role == "A") else 0) if kind == "seg" else 0
        pmin, pkeep = PAUSE_Q if role in ("Q", "H") else PAUSE_A
        if pause_keep: pkeep = max(pkeep, pause_keep); pmin = max(pmin, 2 * pkeep + 2)      # respiraciones más largas (videos de duración fija)
        cuts = [(q0 + pkeep, q1 + 1 - pkeep) for q0, q1 in quiet_runs(fs0 + 1, fe0 - 1) if q1 - q0 + 1 >= pmin
                and not any(za * FPS - pkeep < q1 and zb * FPS + pkeep > q0 for za, zb in SRC.get("nocut", []))]   # zona marcada por el cliente: la pausa no se toca
        edges = [fs0] + [x for c in cuts for x in c] + [fe0]
        pcs = [(edges[2 * i], edges[2 * i + 1]) for i in range(len(cuts) + 1)]
        pcs = [(x, y) for x, y in pcs if y - x >= 6]
        # tramos largos sin pausas: cambio de toma invisible en el final de una frase (el audio sigue continuo)
        split = []
        for x, y in pcs:
            if (y - x) / FPS <= shot_max * 1.35: split.append((x, y, False)); continue
            ends = [w["e"] for w in _WS if x / FPS + 2.5 < w["e"] < y / FPS - 2.5 and w["t"][-1] in ".?!,"]
            cur = x; first = True
            for te in ends:
                if (te - cur / FPS) >= shot_max * 0.9:
                    nx = _next_word_start(te - 0.02) or te
                    g = _gap_frame(te - 0.02, nx + 0.04)
                    if cur + 45 <= g <= y - 45: split.append((cur, g, not first)); cur = g; first = False
            split.append((cur, y, not first))
        pcs3 = split
        for pi, (fs, fe, joined) in enumerate(pcs3):
            if joined or ((pi > 0 or kind == "seg+") and (out_f - shot_start_out) / FPS >= shot_max): shot += 1; shot_start_out = out_f
            pr = pre_n if pi == 0 else 0
            items.append(dict(kind="speech", sid=sid, role=role, scene=sc, shot=shot, fs=fs, fe=fe, out=out_f, pre=pr, n=fe - fs + pr, ein=(pi == 0), eout=(pi == len(pcs3) - 1),
                               soft_in=bool(edge_db(fs) > -33.0) and not (pi == 0 and contiguous) and not joined, soft_out=bool(edge_db(fe) > -33.0), cont=bool((pi == 0 and contiguous) or joined)))
            out_f += fe - fs + pr
    for i0, i1 in zip(items, items[1:]):                                   # audio continuo entre tramos seguidos del original
        if i1.get("cont"): i0["soft_out"] = False; i0["eout"] = False; i1["ein"] = False
    speech = out_f
    end_n = TARGET - speech
    items.append(dict(kind="card", name="end", out=out_f, n=end_n))
    return dict(fps=FPS, total=TARGET, speech=speech, end_n=end_n, ok=end_min <= end_n <= end_max, items=items, pause_keep=pause_keep, end_max=end_max)


# ------------------------------------------------------------------ selector automático
ANGLES = {
    "calma": dict(title="Mensaje de calma", hook="No, no hay ninguna crisis",
                  kw={"ahorros": 3, "garantizados": 3, "protegidos": 2, "calma": 3, "certeza": 3, "sólido": 2, "liquidez": 2, "tranquila": 2,
                      "intervención": 2, "crisis": 2, "fuerte": 2, "banco": 1, "central": 1, "ciudadanía": 1, "pueblo": 1, "zozobra": 2}),
    "leite": dict(title="Respuesta a Gustavo Leite", hook="vende patria",
                  kw={"leite": 3, "irresponsable": 3, "cobardía": 3, "vende": 2, "patria": 2, "zozobra": 2, "incertidumbre": 2, "doloroso": 2,
                      "ausente": 2, "embajador": 2, "dineral": 2, "ratifico": 2, "iniciaron": 1, "inició": 2, "ahorros": 1, "garantizados": 1}),
    "propuestas": dict(title="Lo que hago por el país", hook="Ahora te voy a decir qué yo hago",
                       kw={"leyes": 3, "salud": 2, "mental": 2, "propuesta": 3, "proyecto": 3, "ley": 2, "ips": 3, "jubilatorios": 3, "fondos": 2,
                           "piso": 2, "salarial": 2, "médicos": 2, "reclamo": 1, "gradual": 2, "2027": 2, "acordado": 1, "garantizar": 2}),
}


def score_unit(u, ang):
    ws = [norm(w["t"]) for w in u["words"]]
    kw = ang["kw"]
    k = sum(v for t, v in kw.items() if norm(t) in ws)
    s = k * 1.0
    if u["text"].rstrip()[-1] in ".?!": s += 0.8
    if u["dur"] < 1.6: s -= 2.0
    if u["dur"] > 16: s -= 1.0
    if u["spk"] == "R": s -= 1.0
    if re.match(r"^(Y|Eh|Bueno|Porque|Pero)\b", u["text"]) and k == 0: s -= 0.8
    return s


def pick_script(angle, target_s=60.0, end_s=2.2, hook_q=True):
    """devuelve (script, info): [(kind, sid, role, a, b)] con el gancho primero"""
    ang = ANGLES[angle]
    units = UNITS
    sc = {u["i"]: score_unit(u, ang) for u in units}
    L = [u for u in units if u["spk"] == "L" and u["dur"] >= 1.3]
    budget = target_s - end_s - 0.35 * 6
    # gancho: unidad (corta) que contiene la frase de gancho; si la precede una pregunta del periodista, se usa la pareja pregunta→respuesta
    hook = next((u for u in units if ang["hook"].lower() in u["text"].lower()), None)
    chosen = {}
    used = 0.0
    if hook is not None:
        chosen[hook["i"]] = hook; used += hook["dur"]
        if hook_q and hook["i"] > 0 and units[hook["i"] - 1]["spk"] == "R" and hook["s"] - units[hook["i"] - 1]["e"] < 1.2:
            q = units[hook["i"] - 1]; chosen[q["i"]] = q; used += q["dur"]
    cand = sorted([u for u in L if u["i"] not in chosen and sc[u["i"]] > 0.5], key=lambda u: -sc[u["i"]] / max(2.0, u["dur"]) ** 0.5)
    for u in cand:
        if used + u["dur"] <= budget: chosen[u["i"]] = u; used += u["dur"]
    order = sorted(chosen.values(), key=lambda u: u["s"])
    # gancho primero (pregunta+respuesta si la hay), luego el resto cronológico
    head = [u for u in order if hook is not None and (u["i"] == hook["i"] or (u["spk"] == "R" and u["i"] == hook["i"] - 1))]
    rest = [u for u in order if u not in head]
    seq = head + rest
    script, prev = [], None
    for k, u in enumerate(seq):
        role = "H" if (k == 0 and u["spk"] == "R") else ("Q" if u["spk"] == "R" else "A")
        if k == 0 and u["spk"] == "L" and hook is not None and len(head) == 1: role = "A"
        cont = prev is not None and u["i"] == prev["i"] + 1 and u["spk"] == prev["spk"]
        script.append(("seg+" if cont else "seg", f"u{u['i']}", role, round(u["s"], 2), round(u["e"], 2)))
        prev = u
    return script, dict(used=used, units=[u["i"] for u in seq], texts=[u["text"] for u in seq])


if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    print(len(UNITS), "unidades")
    for ang in ANGLES:
        sc_, info = pick_script(ang)
        print("==", ang, round(info["used"], 1), "s")
        for s, t in zip(sc_, info["texts"]): print("  ", s[0], s[2], f"{s[3]:.1f}-{s[4]:.1f}", t[:100])
