# Estudio de edición — EL ESPECTADOR: control editorial ANTES del render. Revisa el proyecto preparado (guion, cortes, subtítulos,
# titulares) como lo revisa un editor mirando: lo que el QA técnico y el visual no miden porque es de sentido, no de píxeles.
#   DANGLING     una escena arranca con "Por lo tanto…", "Como lo…", "Entre los cuales…" sin la frase anterior (falta el antecedente)
#   MIDSENTENCE  una escena termina a mitad de oración (sin punto) y lo que sigue no la continúa
#   UNANSWERED   una pregunta del periodista sin la respuesta de ella a continuación
#   HOOK_ECHO    la frase del gancho vuelve a sonar enseguida (< 20 s): se nota repetida
#   TITLE_TWICE  el mismo titular dos veces en el video
#   TITLE_EARLY  el titular de la respuesta aparece mientras todavía pregunta el periodista
#   CAP_SPLIT    subtítulo que termina en artículo o preposición ("sobre el" | "sistema financiero?")
#   EDGE_LOST    se perdió una palabra con contenido de ella en el borde de una escena (no una conjunción)
#   python espectador.py <proyecto>
import os, sys, json, re

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO)
STRONG = re.compile(r"^(por lo tanto|entre (los|las) cuales|como lo|como la|como los|que |de (?!\d)|del (?!\d)|con (el|la|los|las) |o sea|es decir|incluso)", re.I)   # "Del 2020 al 2025 hubo…" se entiende solo
FUNC_END = {"el", "la", "los", "las", "un", "una", "de", "del", "a", "al", "en", "con", "por", "para", "sobre", "que", "y", "o", "su", "sus", "mi", "lo"}
SKIP_EDGE = {"y", "e", "o", "u", "pero", "que", "eso", "es", "porque", "entonces", "bueno", "sí", "no", "ni", "a", "de", "en", "el", "la", "los", "las"}


def _core(t): return re.sub(r"[^a-záéíóúüñ0-9]", "", t.lower())


def check(name, log=print):
    import build, plan as P, content as C
    cfg = build.get_cfg(name)
    pdir = os.path.join(STUDIO, "projects", name)
    ctx = build.Ctx(cfg, pdir)
    SC = ctx.SC
    F = {k: [] for k in ("DANGLING", "MIDSENTENCE", "UNANSWERED", "HOOK_ECHO", "TITLE_TWICE", "TITLE_EARLY", "CAP_SPLIT", "EDGE_LOST")}
    # escenas -> frases de la fuente
    def k_of(sid):
        try: return int(str(sid).rsplit("_", 1)[1])
        except Exception: return None
    seq, sc = [], -1                                                      # [(escena, [frases])] en el orden del video, desde el guion
    for entry in cfg["script"]:
        kind, sid, role, a, b = entry[:5]
        ks = [s["k"] for s in C.SENT if a - 0.05 <= s["s"] and s["e"] <= b + 0.05]
        if kind == "seg" or not seq: sc += 1; seq.append((sc, ks or [k_of(sid)]))
        else: seq[-1] = (seq[-1][0], seq[-1][1] + ks)
    prev_last = None
    for i, (sc, ks) in enumerate(seq):
        v = SC[sc]; first = C.SENT[ks[0]]
        spk = ctx.SPK.get(sc, "L")
        # antecedente: arranca con un conector fuerte y la frase anterior de la fuente no es lo que se vio justo antes
        if spk == "L" and STRONG.match(first["text"].lstrip("¿¡ ")) and prev_last != ks[0] - 1:
            F["DANGLING"].append((round(v["o0"], 1), first["text"][:50]))
        # pregunta sin respuesta
        if spk == "R":
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            if not nxt or ctx.SPK.get(nxt[0], "L") != "L" or nxt[1][0] > ks[-1] + 3:
                F["UNANSWERED"].append((round(v["o0"], 1), first["text"][:50]))
        prev_last = ks[-1]
    # termina a mitad de oración
    words = ctx.WORDS
    for i, (sc, ks) in enumerate(seq):
        ws = [w for w in words if w["sc"] == sc]
        if not ws or ctx.SPK.get(sc, "L") != "L": continue
        last = ws[-1]["t"]
        nxt_cont = i + 1 < len(seq) and seq[i + 1][1][0] == ks[-1] + 1 and C.SENT[ks[-1]]["text"].rstrip()[-1:] not in ".?!"
        if last[-1:] not in ".?!…" and not nxt_cont:                       # también la última escena (el cierre)
            F["MIDSENTENCE"].append((round(SC[sc]["o1"], 1), " ".join(w["t"] for w in ws[-4:])))
    # gancho repetido enseguida
    if seq and SC[seq[0][0]]["role"] == "H":
        hk = set(seq[0][1])
        for sc, ks in seq[1:]:
            if hk & set(ks) and SC[sc]["o0"] - SC[seq[0][0]]["o1"] < 20: F["HOOK_ECHO"].append((round(SC[sc]["o0"], 1), C.SENT[min(hk)]["text"][:40]))
    beats = cfg.get("beats", [])
    # titulares que el estilo MUESTRA: repetidos y antes de la respuesta
    try:
        import importlib
        mod = importlib.import_module("styles." + cfg["style"])
        S = mod.Style(ctx); S.setup()
        tl = S.qa_titles() if hasattr(S, "qa_titles") else []
        seen = set()
        for t, txt in tl:
            u = (txt or "").strip().upper().strip("¿?")
            if u and u in seen: F["TITLE_TWICE"].append((round(t, 1), txt))
            seen.add(u)
        for b in beats:
            if b.get("kind") != "pregunta" or b.get("a0") is None or b["a0"] - b["o0"] < 0.8: continue
            for t, txt in tl:
                if txt and txt.strip().upper() == (b.get("title") or "").strip().upper() and b["o0"] - 0.05 <= t < b["a0"] - 0.05:
                    F["TITLE_EARLY"].append((round(t, 1), txt))
    except Exception as e:
        log(f"[espectador] no se pudo revisar titulares del estilo: {e}")
    # subtítulos que terminan en artículo/preposición (corte de frase)
    ch = ctx.CHUNKS
    for a, b in zip(ch, ch[1:]):
        if a["sc"] == b["sc"] and _core(a["words"][-1]) in FUNC_END and a["words"][-1][-1:] not in ",.;?!" and not a.get("merged"):
            F["CAP_SPLIT"].append((round(a["s"], 1), " ".join(a["words"]) + " | " + " ".join(b["words"][:2])))
    # palabra con contenido perdida en el borde
    for sc, ks in seq:
        if ctx.SPK.get(sc, "L") != "L": continue
        ws = [w for w in words if w["sc"] == sc]
        if not ws: continue
        src = [w for k in ks for w in C.SENT[k]["words"]]
        if not src: continue
        first_src = src[0]
        got = {round(w.get("w0", -1), 2) for w in ws}
        if round(first_src["s"], 2) not in got and _core(first_src["t"]) not in SKIP_EDGE and ws[0].get("w0", 0) > first_src["s"] + 0.05:
            F["EDGE_LOST"].append((round(SC[sc]["o0"], 1), first_src["t"]))
    SEV = dict(DANGLING="media", MIDSENTENCE="media", UNANSWERED="alta", HOOK_ECHO="media", TITLE_TWICE="media", TITLE_EARLY="media",
               CAP_SPLIT="baja", EDGE_LOST="baja")
    TXT = dict(DANGLING="escena sin su antecedente", MIDSENTENCE="escena que termina a mitad de oración", UNANSWERED="pregunta sin respuesta",
               HOOK_ECHO="el gancho se repite enseguida", TITLE_TWICE="titular repetido", TITLE_EARLY="titular antes de que ella responda",
               CAP_SPLIT="subtítulo cortado en artículo/preposición", EDGE_LOST="palabra perdida en el borde")
    out = []
    for k, v in F.items():
        if not v: continue
        if k == "CAP_SPLIT" and len(v) <= 2: continue                         # uno o dos en minutos de video: aceptable
        out.append((SEV[k], k, f"{TXT[k]}: {len(v)} (ej. {v[:3]})", ""))
    json.dump({k: v for k, v in F.items()}, open(os.path.join(pdir, "espectador.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"[espectador] {name}: " + (", ".join(f"{k}×{len(v)}" for k, v in F.items() if v) or "sin problemas"))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for f in check(sys.argv[1]): print(" ", f)


def script_checks(parts):
    """controles del GUION (antes de preparar nada): parts = [(etiqueta, [frases])] en el orden del video"""
    import content as C
    out = []
    for i, (tag, ks) in enumerate(parts):
        first = C.SENT[ks[0]]
        prev = parts[i - 1][1][-1] if i > 0 else None
        if tag != "hook" and first["spk"] == "L" and STRONG.match(first["text"].lstrip("¿¡ ")) and prev != ks[0] - 1:
            out.append(("DANGLING", tag, first["text"][:40]))
        if C.SENT[ks[-1]]["spk"] != "L": out.append(("UNANSWERED", tag, C.SENT[ks[-1]]["text"][:40]))
        if any(ks[j + 1] != ks[j] + 1 for j in range(len(ks) - 1)): out.append(("HOLE", tag, ks))
    if parts and parts[0][0] == "hook" and len(parts) > 1 and set(parts[0][1]) & set(parts[1][1]):
        out.append(("HOOK_ECHO", parts[1][0], C.SENT[parts[0][1][0]]["text"][:40]))
    return out
