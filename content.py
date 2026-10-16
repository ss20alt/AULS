# Estudio de edición — MAPA DE CONTENIDO de la fuente: frases completas (por puntuación, nunca por pausas) agrupadas en BLOQUES de idea
# que no se separan, con tema, tipo e importancia. El selector arma los videos con bloques enteros: así nunca se corta una idea a la mitad
# ni se empieza una frase por el medio ("los médicos fue…", "sí está llevando…").
import re
import numpy as np
import plan as P
from core import FPS

# --------------------------------------------------------------- frases completas
def voiced_word(w, thr=-36.0):
    f0, f1 = int((w["s"] - 0.12) * FPS), int((w["e"] + 0.12) * FPS) + 1
    return bool((P.R[max(0, f0):f1] > thr).any())


def build_sentences():
    W = [w for w in P.WORDS if not any(a <= w["s"] <= b for a, b in P.BAD)]          # sin palabras inexistentes (silencio)
    sents, cur = [], []
    for w in W:
        cur.append(w)
        if w["t"][-1] in ".?!": sents.append(cur); cur = []
    if cur: sents.append(cur)
    # un "fragmento" de 1-2 palabras pegado a la frase anterior es su final ("…en los bancos. De plaza.")
    out = []
    for s in sents:
        cont = P.norm(s[0]["t"]) in ("de", "del", "en", "a", "al", "y", "que", "para", "por", "con", "e", "o")
        if out and cont and len(s) <= 3 and s[0]["s"] - out[-1][-1]["e"] < 0.35 and P.speaker_at(s[0]["s"]) == P.speaker_at(out[-1][-1]["s"]):
            out[-1][-1] = dict(out[-1][-1], t=out[-1][-1]["t"].rstrip("."))
            s = [dict(s[0], t=s[0]["t"][:1].lower() + s[0]["t"][1:])] + s[1:]
            out[-1] = out[-1] + s
        else: out.append(s)
    # whisper a veces deja tramos largos SIN puntuación (discurso en un acto: 593–672 s quedaba como UNA frase de 78 s). Una
    # "frase" de más de 30 s (las bien puntuadas no pasan de ~28 s) se parte en sus pausas reales hasta trozos ≤ 22 s: la pausa
    # más larga cuya palabra siguiente arranca idea (mayúscula, "entonces", "y", "pero"…), nunca antes de "de / que / para…",
    # con trozos de ≥ 3 s
    SOFT = {"de", "del", "a", "al", "que", "con", "en", "para", "por", "como", "la", "el", "los", "las", "un", "una", "su", "sus", "lo", "le", "se"}
    START = {"entonces", "y", "pero", "porque", "también", "hoy", "acá", "aca", "ahí", "ahi", "finalmente", "gracias", "nosotros", "yo"}
    def split_long(s, lim=30.0):
        if s[-1]["e"] - s[0]["s"] <= lim or len(s) < 8: return [s]
        best, bi = -1e9, None
        for i in range(2, len(s) - 2):
            a, b = s[i - 1], s[i]
            if b["s"] - s[0]["s"] < 3.0 or s[-1]["e"] - a["e"] < 3.0: continue
            nxt = P.norm(b["t"]).strip(".,;:¿?¡!")
            if nxt in SOFT: continue
            gap = b["s"] - a["e"]
            sc = gap + (0.25 if b["t"][:1].isupper() else 0) + (0.2 if nxt in START else 0) + (0.3 if a["t"][-1:] in ",;:" else 0)
            if sc > best: best, bi = sc, i
        if bi is None: return [s]
        return split_long(s[:bi], 22.0) + split_long(s[bi:], 22.0)
    soft = set()                                                     # trozos partidos que arrancan a mitad de frase (minúscula / "de…")
    pieces = []
    for s in out:
        ps = split_long(s)
        for j, p in enumerate(ps):
            if j > 0 and (p[0]["t"][:1].islower() or P.norm(p[0]["t"]).strip(".,;:") in SOFT): soft.add(len(pieces))
            pieces.append(p)
    out = pieces
    S = []
    for k, s in enumerate(out):
        a, b = s[0]["s"], s[-1]["e"]
        S.append(dict(k=k, s=a, e=b, dur=b - a, words=s, text=" ".join(w["t"] for w in s), spk=P.speaker_at((a + b) / 2),
                      ghosts=[w["t"] for w in s if not voiced_word(w)], soft_start=k in soft))
    return S


SENT = build_sentences()
WORD_SPK = {round(w["s"], 3): s["spk"] for s in SENT for w in s["words"]}              # hablante de cada palabra según SU frase (no según el reloj)


def find_sent(prefix):
    """frase que empieza con ese texto; tolera pequeñas diferencias entre transcripciones (otra pasada de whisper)"""
    import difflib
    p = P.norm(prefix)
    for s in SENT:
        if P.norm(s["text"]).startswith(p): return s["k"]
    for s in SENT:                                                      # la otra transcripción unió frases: buscar dentro
        if p in P.norm(s["text"]): return s["k"]
    pw = [P.norm(x) for x in prefix.split() if P.norm(x)]                 # por palabras: tolera palabras agregadas u omitidas
    best, bk = 0.0, None
    for s in SENT:
        sw = [P.norm(x) for x in s["text"].split() if P.norm(x)][:len(pw) + 5]
        r = difflib.SequenceMatcher(None, pw, sw, autojunk=False).ratio()
        if r > best: best, bk = r, s["k"]
    if best >= 0.6: return bk
    raise KeyError(prefix)


# El mapa de contenido de cada fuente vive en sources/<fuente>/content.json (bloques de idea, titulares, historias).
# Si la fuente todavía no tiene mapa, se arma uno automático provisorio (ver auto_map).
import json, os


def _load_map():
    p = os.path.join(P.SRC["dir"], "content.json")                         # aprobado por el editor / cliente
    if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
    d = os.path.join(P.SRC["dir"], "content_draft.json")                   # borrador automático (mapper.py) sin aprobar
    if os.path.exists(d):
        print(f"[mapa] {P.SOURCE_NAME}: usando el borrador automático (sin aprobar: python mapper.py approve {P.SOURCE_NAME})")
        return json.load(open(d, encoding="utf-8"))
    return None


def auto_map():
    """mapa provisorio: bloques = frases seguidas del mismo hablante hasta una pausa larga o ~25 s; titular = frase clave"""
    blocks, cur = [], []
    for s in SENT:
        if cur and (s["spk"] != cur[-1]["spk"] or s["s"] - cur[-1]["e"] > 1.2 or sum(x["dur"] for x in cur) > 25):
            blocks.append(cur); cur = []
        cur.append(s)
    if cur: blocks.append(cur)
    out = []
    for i, b in enumerate(blocks):
        out.append(dict(id=f"b{i:02d}", firsts=[b[0]["text"][:40]], topic=b[0]["text"][:60], kind="pregunta" if b[0]["spk"] == "R" else "mensaje",
                        imp=3, extra=len(b) - 1, tag=["", "", ""]))
    return dict(blocks=out, stories={})


MAP = _load_map() or auto_map()
BEATS = []
for e in MAP["blocks"]:
    ks = [find_sent(f) for f in e["firsts"]]
    ks = list(range(min(ks), max(ks) + 1 + e.get("extra", 0)))           # bloque contiguo: todas las frases entre la primera y la última (+ extra)
    ss = [SENT[k] for k in ks]
    BEATS.append(dict(id=e["id"], sents=ks, topic=e["topic"], kind=e["kind"], imp=e["imp"], s=ss[0]["s"], e=ss[-1]["e"],
                      dur=sum(x["dur"] for x in ss), q=ss[0]["spk"] == "R", text=" ".join(x["text"] for x in ss)))
BEAT = {b["id"]: b for b in BEATS}
TAGS = {e["id"]: tuple(e["tag"]) for e in MAP["blocks"] if e.get("tag") and e["tag"][0]}
STORIES = MAP.get("stories", {})
# DECLARACIÓN COMPLETA (referencias 2026-10-16: la mayoría publica la declaración casi entera, 1–4 min, en una toma, solo
# limpiando el principio y el final): todos los bloques en su orden real, sin gancho; si no entran en 6 min, los más
# importantes (igual en orden real). `make_video.py --angle completo`
if BEATS and "completo" not in STORIES:
    _last = max(BEATS, key=lambda b: b["s"])
    STORIES["completo"] = dict(title="Declaración completa", body=[b["id"] for b in sorted(BEATS, key=lambda b: -b["imp"]) if b is not _last],
                               close=_last["id"], max_s=360.0)


def report():
    for b in BEATS:
        gh = [g for k in b["sents"] for g in SENT[k]["ghosts"]]
        print(f"{b['id']:14s} imp{b['imp']} {b['kind']:9s} {b['s']:6.1f}-{b['e']:6.1f} ({b['dur']:5.1f}s) {b['topic']}" + (f"  <<sin voz: {gh}>>" if gh else ""))


if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    report()
