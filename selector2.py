# Estudio de edición — selector por BLOQUES DE IDEA (content.py): gancho + bloques completos + cierre, duración libre hasta 2 min.
# Nunca empieza ni termina una escena a mitad de frase; si un bloque no entra entero, se recorta solo al final de una frase completa.
import re
import plan as P
import content as C
from core import FPS

STYLE_SHOW_Q = {"call", "news", "ink", "report", "headline", "fx", "split", "karaoke", "doc", "tv", "claves", "cita", "editorial", "campana", "podcast", "redes"}      # la pregunta del periodista da contexto a la respuesta
FILLER_R = ("gracias", "cómo", "senadora, solamente", "qué plazo")
MAX_S = 120.0
END_S = 2.5


def _script_from(parts, show_q):
    """parts: [(tag, [sent_ids])] -> script con una entrada por tramo contiguo de frases (seg / seg+)"""
    script = []
    for pi, (tag, ks) in enumerate(parts):
        ks = [k for k in ks if show_q or C.SENT[k]["spk"] == "L" or tag in ("hook", "qa")]
        ks = [k for k in ks if not (C.SENT[k]["spk"] == "R" and any(f in C.SENT[k]["text"].lower()[:24] for f in FILLER_R))]
        runs, cur = [], []
        for k in ks:
            if cur and (k != cur[-1] + 1 or C.SENT[k]["spk"] != C.SENT[cur[-1]]["spk"]): runs.append(cur); cur = []
            cur.append(k)
        if cur: runs.append(cur)
        for ri, run in enumerate(runs):
            spk = C.SENT[run[0]]["spk"]
            role = ("H" if spk == "R" else ("H" if tag == "hook" and len(runs) == 1 else "A")) if tag == "hook" and ri == 0 else ("Q" if spk == "R" else "A")
            kind = "seg" if (ri == 0 or C.SENT[run[0]]["spk"] != C.SENT[runs[ri - 1][-1]]["spk"]) else "seg+"
            if tag == "hook" and ri > 0: kind = "seg"
            script.append([kind, f"{tag}_{run[0]}", role, round(C.SENT[run[0]]["s"], 2), round(C.SENT[run[-1]]["e"], 2)])
    return script


def _pause_between(k0, k1):
    """¿hay un silencio real (≥ 4 fotogramas) entre el final de la frase k0 y el inicio de k1?"""
    a, b = int((C.SENT[k0]["e"] - 0.15) * FPS), int((C.SENT[k1]["s"] + 0.15) * FPS)
    return any(P._silent_run_at(f) for f in range(max(0, a), b + 1))


def _glued(k0, k1):
    """frases dichas de corrido: ni silencio real ni hueco audible (< -33 dB) entre ellas"""
    if _pause_between(k0, k1): return False
    f = P._gap_frame(C.SENT[k0]["e"] - 0.05, C.SENT[k1]["s"] + 0.05)
    return P.edge_db(f) > -33.0


def _loud_end(k):
    return P.edge_db(P.cut_out(C.SENT[k]["e"])) > -28.0


def _loud_start(k):
    return P.edge_db(P.cut_in(C.SENT[k]["s"])) > -28.0


def extend(ks, used):
    """atiende el contexto: si la frase de borde va PEGADA (sin hueco) a una frase corta de ella, el bloque la incluye"""
    ks = list(ks)
    for _ in range(2):
        k = ks[0]
        if k - 1 >= 0 and (k - 1) not in used and C.SENT[k - 1]["spk"] == "L" == C.SENT[k]["spk"] and C.SENT[k - 1]["dur"] <= 6.0 and _glued(k - 1, k): ks.insert(0, k - 1)
        else: break
    for _ in range(2):
        k = ks[-1]
        if k + 1 < len(C.SENT) and (k + 1) not in used and C.SENT[k + 1]["spk"] == "L" == C.SENT[k]["spk"] and C.SENT[k + 1]["dur"] <= 6.0 and _glued(k, k + 1): ks.append(k + 1)
        else: break
    # bordes que siguen pegados a voz: soltar la frase corta del borde para cortar donde hay pausa real
    while len(ks) >= 2 and _loud_end(ks[-1]) and C.SENT[ks[-1]]["dur"] <= 5.0 and not _loud_end(ks[-2]): ks.pop()
    while len(ks) >= 2 and _loud_start(ks[0]) and C.SENT[ks[0]]["dur"] <= 5.0 and not _loud_start(ks[1])             and not (C.SENT[ks[0]]["spk"] == "R" and "?" in C.SENT[ks[0]]["text"]): ks.pop(0)       # la pregunta del periodista es el contexto: no se suelta
    return ks


def build(angle, style, max_s=MAX_S, log=print, exact=None, hook=True):
    """exact: duración exacta = max_s (1 min y 3 min). Por defecto, exacta si max_s <= 75 (compatibilidad)."""
    exact = (max_s <= 75) if exact is None else exact
    long_ = max_s > 75
    st = C.STORIES[angle]
    show_q = style in STYLE_SHOW_Q
    hook_style = hook and style not in ("headline", "call", "split")   # estos estilos (o --gancho no) abren directo con el tema
    parts, used = [], set()
    if hook_style:
        if st.get("hook"):
            b = C.BEAT[st["hook"]]; parts.append(("hook", list(b["sents"]))); used |= set(b["sents"])
        elif st.get("hook_sent"):
            k = C.find_sent(st["hook_sent"]); parts.append(("hook", [k])); used.add(k)
    hook_ks = set(parts[0][1]) if parts and st.get("hook_sent") else set()
    # 3 min: la frase del gancho (avance) puede volver más tarde EN SU CONTEXTO, si no queda pegada al gancho
    free = lambda k, b: k not in used or (long_ and k in hook_ks and k != b["sents"][0])
    close = C.BEAT[st["close"]]
    body = [C.BEAT[b] for b in st["body"]]
    budget = max_s - END_S - 0.5

    def total(pp):
        sc = _script_from(pp + [("close", [k for k in close["sents"] if k not in used])], show_q)
        e = P.build_edl(sc, 999.0)
        return e["speech"] / FPS, sc
    cks = extend([k for k in close["sents"] if k not in used], used)
    close = dict(close, sents=cks)
    for b in body:
        ks = [k for k in b["sents"] if free(k, b) and k not in cks]
        if not ks: continue
        run = [ks[0]]                                         # un bloque nunca con huecos: solo el primer tramo seguido
        for k in ks[1:]:
            if k != run[-1] + 1: break
            run.append(k)
        if len(run) < len(ks):
            anc = P.norm(C.TAGS.get(b["id"], ("", "", ""))[1] or "")
            txt = " ".join(P.norm(w) for k in run for w in C.SENT[k]["text"].split())
            if not (anc and anc in txt): continue              # el tramo que queda no tiene la idea del bloque: se descarta
            ks = run
        ks = [k for k in extend(ks, used | set(cks)) if k not in cks]
        t_with, _ = total(parts + [(b["id"], ks)])
        if t_with <= budget:
            parts.append((b["id"], ks)); used |= set(ks); continue
        # no entra entero: probar recortarlo al final de una frase (mínimo 2 frases y ≥ 60 % del bloque)
        for n in range(len(ks) - 1, 1, -1):
            sub = ks[:n]
            if sum(C.SENT[k]["dur"] for k in sub) < 0.6 * sum(C.SENT[k]["dur"] for k in ks): break
            t_sub, _ = total(parts + [(b["id"], sub)])
            if t_sub <= budget: parts.append((b["id"], sub)); used |= set(sub); log(f"  · bloque {b['id']} recortado a {n} frases"); break
    # relleno (videos cortos, p. ej. 1 min): si sobra presupuesto, sumar otros bloques — primero los del mismo tipo que la
    # historia, luego por importancia — enteros o recortados al final de una frase completa (≥ 3 s de voz de ella)
    fill_ids = set()
    if exact:
        kinds = {C.BEAT[b]["kind"] for b in st["body"] if b in C.BEAT}
        taken = {p[0] for p in parts}
        body_ids = [b for b in st["body"] if b in C.BEAT]
        coherent = lambda b: b["id"] in body_ids or b["kind"] in kinds or not kinds
        # 1 min: solo bloques coherentes con la historia. 3 min: después de esos, el resto de la conferencia por importancia
        pool = sorted([b for b in C.BEATS if b["id"] not in taken and b["id"] != close["id"] and (not b["q"] or (long_ and show_q))
                       and (coherent(b) or long_)],
                      key=lambda b: (b["id"] not in body_ids, body_ids.index(b["id"]) if b["id"] in body_ids else 0, not coherent(b), b["kind"] not in kinds, -b["imp"], b["s"]))
        budget = max_s - 2.0 - 0.15                       # duración exacta: la tarjeta final puede bajar a 2 s
        for b in pool:
            t_now, _ = total(parts)
            if budget - t_now < 2.0: break
            qblock = b["q"] and long_ and show_q             # bloque de prensa: la pregunta va con su respuesta
            ks = [k for k in b["sents"] if free(k, b) and k not in cks and (C.SENT[k]["spk"] == "L" or qblock)
                  and not re.search(r"agradezco|gracias|martina|ustedes le preguntan", C.SENT[k]["text"], re.I)]   # sin agradecimientos ni nombres de periodistas
            if qblock and ks and C.SENT[ks[0]]["spk"] != "R": continue
            if not ks: continue
            for n in range(len(ks), 0, -1):
                sub = ks[:n]
                if any(sub[i + 1] != sub[i] + 1 for i in range(len(sub) - 1)): continue
                if sum(C.SENT[k]["dur"] for k in sub) < 2.0: break
                if C.SENT[sub[-1]]["spk"] != "L" or not any(C.SENT[k]["spk"] == "L" for k in sub): continue   # una pregunta siempre con su respuesta
                anc = P.norm(C.TAGS.get(b["id"], ("", "", ""))[1] or "")
                txt = " ".join(P.norm(w) for k in sub for w in C.SENT[k]["text"].split())
                if n < len(b["sents"]) and not ((anc and anc in txt) or sum(C.SENT[k]["dur"] for k in sub) >= 0.6 * sum(C.SENT[k]["dur"] for k in b["sents"])):
                    continue                                       # un trozo suelto tiene que contener la idea del bloque
                t_sub, _ = total(parts + [(b["id"], sub)])
                if t_sub <= budget: parts.append((b["id"], sub)); used |= set(sub); fill_ids.add(b["id"]); log(f"  · relleno: bloque {b['id']} ({n} frases)"); break
        # discurso (frases largas, sin pausas para estirar): si quedan > 4.5 s que la tarjeta final no absorbe, se ALARGA una idea
        # ya elegida con la frase que la sigue en su mismo bloque (continúa la idea; nunca una frase suelta de otro lado)
        for _ in range(6):
            t_now, _ = total(parts)
            if budget + 2.0 - t_now <= 4.5: break
            best = None
            for pi, (bid, ks) in enumerate(parts):
                if bid in ("hook", "close") or bid not in C.BEAT: continue
                k = ks[-1] + 1
                if k not in C.BEAT[bid]["sents"] or k in used or k in cks or C.SENT[k]["spk"] != "L": continue
                t_k, _ = total(parts[:pi] + [(bid, ks + [k])] + parts[pi + 1:])
                if t_k <= budget and (best is None or t_k > best[0]): best = (t_k, pi, k)
            if best is None: break
            t_k, pi, k = best; bid, ks = parts[pi]
            parts[pi] = (bid, ks + [k]); used.add(k); log(f"  · relleno: se completa la idea {bid} con la frase siguiente ({C.SENT[k]['dur']:.1f} s)")
    # orden: gancho, cuerpo cronológico, relleno (después del cuerpo, nunca intercalado), cierre al final
    hook = [p for p in parts if p[0] == "hook"]
    if long_:                                                 # 3 min: todo en el orden natural de la conferencia
        rest = sorted([p for p in parts if p[0] != "hook"], key=lambda p: C.SENT[p[1][0]]["s"])
    else:
        rest = sorted([p for p in parts if p[0] != "hook" and p[0] not in fill_ids], key=lambda p: C.SENT[p[1][0]]["s"])
        rest += sorted([p for p in parts if p[0] in fill_ids], key=lambda p: C.SENT[p[1][0]]["s"])
    if st.get("orden") == "historia":                         # la historia la armó el editor: se respeta su orden (no el de la conferencia)
        rest = sorted(rest, key=lambda p: st["body"].index(p[0]) if p[0] in st["body"] else len(st["body"]))
    elif hook:                                                # el gancho anuncia algo ("Ahora te voy a decir qué yo hago"): lo que sigue en el original va primero
        nxt = next((p for p in rest if p[1][0] == hook[0][1][-1] + 1 and p[0] not in fill_ids), None)
        if nxt: rest = [nxt] + [p for p in rest if p is not nxt]
    if hook and rest:                                         # la frase del gancho vuelve en su contexto: nunca enseguida (< 20 s)
        hk = set(hook[0][1])
        i_e = next((i for i, p in enumerate(rest) if hk & set(p[1])), None)
        if i_e is not None and sum(C.SENT[k]["dur"] for p in rest[:i_e] for k in p[1]) < 20.0:
            pe = rest.pop(i_e); acc, j = 0.0, 0
            while j < len(rest) and acc < 20.0: acc += sum(C.SENT[k]["dur"] for k in rest[j][1]); j += 1
            if acc >= 20.0: rest.insert(j, pe)                # después de ≥ 20 s de otras ideas
            else:                                             # no hay 20 s antes del cierre: la frase no se repite (sin dejar huecos:
                ks2 = [k for k in pe[1] if k not in hk]       # solo si estaba en un borde del bloque)
                if ks2 and all(ks2[i + 1] == ks2[i] + 1 for i in range(len(ks2) - 1)): rest.insert(j, (pe[0], ks2))
                elif not ks2: pass
                else: rest.insert(j, pe)
    parts = hook + rest + [("close", [k for k in close["sents"] if k not in used])]
    script = _script_from(parts, show_q)
    e0 = P.build_edl(script, 999.0)
    target = round((e0["speech"] + int(END_S * FPS)) / FPS, 3); pk, end_max = None, 110
    if exact:                                             # duración EXACTA (1 o 3 min): tarjeta final de 2–4.7 s y, si falta, respiraciones más largas
        end_max = 140
        for pk_ in (None, 6, 7, 8, 9, 10) + ((12, 14) if long_ else ()):   # 3–4 min con frases largas (discurso): pausas de hasta 0.47 s
            e0 = P.build_edl(script, 999.0, pause_keep=pk_)
            if 60 <= max_s * FPS - e0["speech"] <= end_max: target, pk = float(max_s), pk_; break
            if max_s * FPS - e0["speech"] < 60: break
        pre = 5
        if target != float(max_s) and long_:                  # 3–4 min con frases largas: respiración un poco más larga ANTES de
            for pre_ in (8, 11, 14, 18, 24):                  # cada idea (ella en cuadro, en silencio, 0.27–0.8 s) + tarjeta ≤ 6 s
                sp_ = P.build_edl(script, 999.0, pre_default=pre_)["speech"]
                if 60 <= max_s * FPS - sp_ <= 180: target, pk, pre, end_max = float(max_s), None, pre_, 180; break
                if max_s * FPS - sp_ < 60: break
        if target != float(max_s):                            # discurso de frases largas: ni la tarjeta (≤ 4.7 s) ni las pausas
            sp0 = P.build_edl(script, 999.0)["speech"]         # alcanzan -> tarjeta final de hasta 6 s antes que cortar una idea
            if 60 <= max_s * FPS - sp0 <= 180: target, pk, end_max = float(max_s), None, 180
    else: pre = 5
    edl = P.build_edl(script, target, end_max=end_max, pause_keep=pk, pre_default=pre)
    if exact and edl["total"] / FPS < max_s - 1e-3:
        disp = sum(C.SENT[k]["dur"] for b in C.BEATS for k in b["sents"] if C.SENT[k]["spk"] == "L")
        edl["falta"] = dict(pedido=max_s, logrado=round(edl["total"] / FPS, 2), mapa=round(disp, 1),
                            motivo="el mapa de contenido no tiene ideas suficientes" if disp < max_s * 0.95 else "las ideas que quedan no encajan en el tiempo")
    return script, edl, parts


if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    for ang in C.STORIES:
        for st in ("news", "call"):
            sc, edl, parts = build(ang, st)
            print(f"== {ang} / {st}: {edl['total'] / FPS:.1f}s (voz {edl['speech'] / FPS:.1f}s) bloques: {[p[0] for p in parts]}")
