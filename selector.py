# Estudio de edición — selector narrativo automático: gancho + bloques coherentes (con bonus de adyacencia) + cierre, ajustado a la duración
# con realimentación del EDL real (tarjeta final entre 2.0 y 3.6 s).
import re
import numpy as np
import plan as P
from core import FPS

STYLE_HOOK = {"news": "qa", "ink": "punch", "report": "qa", "headline": "none", "fx": "qa", "call": "none", "split": "none"}
STYLE_ROLES_Q = {"call"}                                  # estilos que muestran también la voz del periodista

ANGLES = dict(P.ANGLES)
ANGLES["prensa"] = dict(title="Preguntas de la prensa", hook="Qué les dijo en esta reunión", close=["certeza de que están sus ahorros"],
                        kw={"reunión": 2, "dijeron": 2, "sumario": 3, "irregularidad": 3, "plazo": 2, "intervención": 3, "responsable": 2, "fuerte": 2, "senadores": 1,
                            "consultas": 2, "bancos": 1, "proceso": 2, "ajustar": 2})
ANGLES["calma"]["close"] = ["certeza de que están sus ahorros", "mensaje de calma"]
ANGLES["leite"]["close"] = ["certeza de que están sus ahorros"]
ANGLES["propuestas"]["close"] = ["proyecto de ley que hace garantizar"]


def _has(u, phrase): return P.norm(phrase) in P.norm(u["text"])


def score(u, ang):
    ws = [P.norm(w["t"]) for w in u["words"]]
    k = sum(v for t, v in ang["kw"].items() if P.norm(t) in ws)
    s = float(k)
    if u["text"].rstrip()[-1] in ".?!": s += 0.8
    if u["dur"] < 1.6: s -= 2.0
    if u["dur"] > 17: s -= 1.2
    if u["spk"] == "R": s -= 1.2
    if re.match(r"^(Y|Eh|Bueno|Porque|Pero)\b", u["text"]) and k == 0: s -= 0.8
    if re.search(r"gracias|senadora", u["text"].lower()) and k == 0: s -= 2.0
    return s


def build(angle, style, target=60.0, end_s=2.4, avoid=()):
    ang = ANGLES[angle]; U = P.UNITS
    sc = {u["i"]: score(u, ang) for u in U}
    hook_kind = STYLE_HOOK.get(style, "none")
    show_q = style in STYLE_ROLES_Q
    protected, chosen = set(), []
    hook_ids = []
    L_ok = lambda u: u["spk"] == "L" and u["dur"] >= 1.3
    # --- gancho
    if hook_kind in ("qa", "punch"):
        pair = None
        if hook_kind == "qa":
            best = -9
            for u in U:
                if u["spk"] == "R" and u["q"] and u["i"] + 1 < len(U):
                    a = U[u["i"] + 1]
                    if a["spk"] == "L" and a["s"] - u["e"] < 1.3 and u["dur"] <= 6.0 and a["dur"] <= 9.0:
                        v = sc[a["i"]] + (3 if _has(a, ang["hook"]) or _has(u, ang["hook"]) else 0)
                        if v > best: best, pair = v, (u, a)
            if pair is not None and best < 2.5: pair = None
        if pair is not None: hook_ids = [pair[0]["i"], pair[1]["i"]]
        else:
            cand = [u for u in U if L_ok(u) and _has(u, ang["hook"]) and u["dur"] <= 6.0] or sorted([u for u in U if L_ok(u) and u["dur"] <= 4.5], key=lambda u: -sc[u["i"]])[:1]
            if cand: hook_ids = [cand[0]["i"]]
            # un gancho "punch" de un solo enunciado: se agrega la respuesta siguiente si es contigua y corta
        protected |= set(hook_ids)
    # --- cierre
    close_id = None
    for ph in ang.get("close", []):
        c = next((u for u in U if L_ok(u) and _has(u, ph) and u["dur"] <= 9.0 and u["i"] not in hook_ids), None)
        if c: close_id = c["i"]; break
    if close_id is not None: protected.add(close_id)
    sel = set(protected)
    dur = lambda ids: sum(U[i]["dur"] for i in ids)
    budget = target - end_s - 0.17 * 6
    # --- bloques coherentes: elegir unidad con mayor (valor + bonus de adyacencia) / duración^0.6
    def val(i):
        v = sc[i] - 0.4
        for j in (i - 1, i + 1):
            if j in sel and 0 <= j < len(U) and U[j]["spk"] == U[i]["spk"] and abs(U[j]["s"] - U[i]["s"]) < 30: v += 0.8
        return v
    cand = [u["i"] for u in U if L_ok(u) and u["i"] not in sel and u["i"] not in avoid and sc[u["i"]] > 0.8]
    while True:
        best, bi = 0.0, None
        for i in cand:
            if i in sel or dur(sel) + U[i]["dur"] > budget: continue
            r = val(i) / max(2.0, U[i]["dur"]) ** 0.6
            if r > best: best, bi = r, i
        if bi is None: break
        sel.add(bi)
    # --- sin unidades aisladas muy cortas
    for i in list(sel):
        if i in protected: continue
        iso = not any(j in sel for j in (i - 1, i + 1))
        if iso and U[i]["dur"] < 2.2: sel.discard(i)
    return dict(sel=sel, protected=protected, hook=hook_ids, close=close_id, sc=sc, show_q=show_q, ang=ang)


def to_script(S):
    """de un conjunto de unidades a [(kind,sid,role,a,b)]: gancho primero, el resto cronológico (el cierre al final)"""
    U = P.UNITS
    hook = [i for i in S["hook"] if i in S["sel"]]
    close = S["close"] if S["close"] in S["sel"] else None
    ids = [i for i in sorted(S["sel"]) if i not in hook and i != close]
    # preguntas del periodista antes de su respuesta (solo estilos que las muestran)
    if S["show_q"]:
        extra = []
        for i in ids:
            if U[i]["spk"] == "L" and i - 1 >= 0 and U[i - 1]["spk"] == "R" and U[i - 1]["q"] and U[i]["s"] - U[i - 1]["e"] < 1.3 and (i - 1) not in S["sel"]:
                extra.append(i - 1)
        ids = sorted(set(ids) | set(extra))
    order = hook + ids + ([close] if close is not None else [])
    script, prev = [], None
    for k, i in enumerate(order):
        u = U[i]
        if i in S["hook"] and S["hook"] and u["spk"] == "R": role = "H"
        elif i in S["hook"] and len(S["hook"]) == 1: role = "H"
        else: role = "Q" if u["spk"] == "R" else "A"
        # el gancho "punch" se convierte en escena H (B/N + título); el resto de estilos usa H como pregunta
        cont = prev is not None and i == prev + 1 and U[i]["spk"] == U[prev]["spk"] and role != "H" and not (prev in S["hook"])
        script.append(["seg+" if cont else "seg", f"u{i}", role, round(u["s"], 2), round(u["e"], 2)])
        prev = i
    return script


def fit(angle, style, target=60.0, end_min=60, end_max=110, log=print, avoid=(), pre=5):
    """selecciona y ajusta con el EDL real (simulando cada candidato) hasta que la tarjeta final quede entre 2.0 y 3.6 s"""
    S = build(angle, style, target, avoid=avoid)
    U = P.UNITS
    mid = (end_min + end_max) / 2
    ev = lambda SS: P.build_edl(to_script(SS), target, pre_default=pre)
    dist = lambda n: 0 if end_min <= n <= end_max else (end_min - n if n < end_min else n - end_max)
    edl = ev(S)
    for it in range(14):
        n = edl["end_n"]
        if dist(n) == 0: return to_script(S), edl, S
        moves = []
        if n > end_max:                                    # falta voz: sumar unidades (vecinas / relevantes primero)
            base = [u for u in U if u["spk"] == "L" and u["dur"] >= 1.3 and u["i"] not in S["sel"] and u["i"] not in avoid]
            nb = [u for u in base if any(j in S["sel"] for j in (u["i"] - 1, u["i"] + 1)) and S["sc"][u["i"]] > -1.0]
            rel = [u for u in base if S["sc"][u["i"]] >= 1.0]
            pool = {u["i"]: u for u in (nb + rel)}.values() or base
            need = (n - mid) / FPS
            ranked = sorted(pool, key=lambda u: abs(u["dur"] + 0.17 - need) - 1.5 * any(j in S["sel"] for j in (u["i"] - 1, u["i"] + 1)) - 0.3 * S["sc"][u["i"]])[:7]
            moves = [("add", u["i"]) for u in ranked]
        else:                                              # sobra voz: quitar la unidad menos valiosa
            rem = [i for i in S["sel"] if i not in S["protected"]]
            need = (mid - n) / FPS
            ranked = sorted(rem, key=lambda i: S["sc"][i] + 0.5 * any(j in S["sel"] for j in (i - 1, i + 1)) + 0.2 * abs(U[i]["dur"] - need))[:7]
            moves = [("del", i) for i in ranked]
        if not moves: break
        best = None
        for kind, i in moves:
            T_ = dict(S); T_["sel"] = set(S["sel"]); (T_["sel"].add if kind == "add" else T_["sel"].discard)(i)
            e2 = ev(T_); d2 = dist(e2["end_n"])
            if best is None or d2 < best[0]: best = (d2, T_, e2)
            if d2 == 0: break
        if best[0] >= dist(n) and best[0] != 0:               # ningún movimiento simple mejora: probar intercambios (sumar una + quitar otra)
            adds = [i for k, i in moves if k == "add"] or [u["i"] for u in U if u["spk"] == "L" and u["dur"] >= 1.3 and u["i"] not in S["sel"] and S["sc"][u["i"]] >= 0.8][:6]
            dels = [i for i in S["sel"] if i not in S["protected"]]
            found = None
            for ia in adds[:6]:
                for idl in dels:
                    T_ = dict(S); T_["sel"] = (set(S["sel"]) | {ia}) - {idl}
                    e2 = ev(T_)
                    if dist(e2["end_n"]) == 0: found = (T_, e2); break
                if found: break
            if found: S, edl = found; continue
            break
        S, edl = best[1], best[2]
    log("  ! no se pudo ajustar la duración exacta; tarjeta final =", round(edl["end_n"] / FPS, 2), "s")
    return to_script(S), edl, S


if __name__ == "__main__":
    import sys; sys.stdout.reconfigure(encoding="utf-8")
    for ang in ("calma", "leite", "propuestas", "prensa"):
        for st in ("news", "ink", "headline", "call"):
            sc_, edl, S = fit(ang, st)
            print(f"== {ang} / {st}: voz {edl['speech'] / FPS:.1f}s tarjeta {edl['end_n'] / FPS:.1f}s ok={edl['ok']}")
            if st in ("news", "call"):
                for s in sc_: print("  ", s[0], s[2], f"{s[3]:.1f}-{s[4]:.1f}", P.UNITS[int(s[1][1:])]["text"][:90])
