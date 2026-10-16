# Estudio de edición — enriquecimiento automático por estilo: a partir de las palabras clave y las escenas genera titulares, golpes (hits),
# capítulos, recuadros de fotos, chips y textos de gancho. Todo ligado al contenido real del video.
import re
import numpy as np
import plan as P
from core import FPS


def _w(cfg, t):
    keys = {P.norm(k): v for k, v in cfg.get("keys", {}).items()}
    return keys.get(P.norm(t), 0)


def scene_ids(ctx, roles=("A",)):
    return [sc for sc in sorted(ctx.SC) if ctx.SC[sc]["role"] in roles]


def key_words(cfg, ctx, sc):
    """[(idx_en_escena, palabra, peso)] de las palabras clave de la escena"""
    ws = [w for w in ctx.WORDS if w["sc"] == sc]
    out = []
    for i, w in enumerate(ws):
        wt = _w(cfg, w["t"]) or (2 if w.get("key") else 0)
        if w.get("key") or wt: out.append((i, w, max(wt, 2)))
    return ws, out


def phrase(ws, i, maxw=3):
    """grupo de palabras clave consecutivas alrededor de ws[i]"""
    a = i
    while a > 0 and ws[a - 1].get("key") and i - a < maxw - 1: a -= 1
    b = i
    while b + 1 < len(ws) and ws[b + 1].get("key") and b - a < maxw - 1: b += 1
    return ws[a:b + 1]


def clean(t): return re.sub(r"[¿?¡!.,;:]", "", t).strip()


def nth_of(ws, i):
    n = P.norm(ws[i]["t"])
    return sum(1 for w in ws[:i] if P.norm(w["t"]) == n)


def title_case(s): return s[:1].upper() + s[1:]


FUNC_W = {"a", "de", "del", "la", "el", "en", "y", "que", "los", "las", "un", "una", "unos", "unas", "con", "por", "para", "se", "su", "sus", "al", "lo", "no", "es", "e", "o", "u",
          "mi", "tu", "te", "me", "le", "les", "nos", "como", "si", "ya", "ni", "eso", "esto", "mira", "fue", "son", "hay", "ha", "han", "está", "están", "era", "ser", "yo", "vos"}


def content_words(ws, n=3):
    toks = [clean(w["t"]) for w in ws]
    i = 0
    while i < len(toks) and P.norm(toks[i]) in FUNC_W: i += 1
    out = toks[i:i + n]
    while out and P.norm(out[-1]) in FUNC_W: out.pop()
    return " ".join(out)


def scene_title(cfg, ctx, sc, used=None):
    """(título, subtítulo) del tema; no repite títulos entre escenas"""
    used = used if used is not None else set()
    ws, kws = key_words(cfg, ctx, sc)
    ordered = sorted(kws, key=lambda k: (-k[2], k[0]))
    title, tph = None, []
    for i, w, wt in ordered:
        ph = phrase(ws, i, 3); txt = " ".join(clean(x["t"]) for x in ph)
        if P.norm(txt) not in used: title, tph = txt, ph; break
    if title is None:
        title = content_words(ws, 3) or (clean(ws[0]["t"]) if ws else "Tema")
    used.add(P.norm(title))
    sub = ""
    for i, w, wt in ordered:
        ph = phrase(ws, i, 3); txt = " ".join(clean(x["t"]) for x in ph)
        if P.norm(txt) != P.norm(title) and not (set(P.norm(x["t"]) for x in ph) & set(P.norm(x["t"]) for x in tph)): sub = txt; break
    if not sub: sub = content_words(ws[len(tph):] if tph else ws, 5)
    sub = " ".join(sub.split()[:4]); sub = " ".join(sub.split()[:-1]) if sub.split() and P.norm(sub.split()[-1]) in FUNC_W and len(sub.split()) > 1 else sub
    return (title.upper() if len(title) < 14 else title_case(title)), title_case(sub.lower())


def pick_hits(cfg, ctx, n_max=6, gap=1.9, t_min=1.2):
    hits, last = [], -9.0
    cands = []
    for sc in scene_ids(ctx):
        ws, kws = key_words(cfg, ctx, sc)
        for i, w, wt in kws: cands.append((wt, w["s"], sc, i, ws))
    for wt, t, sc, i, ws in sorted(cands, key=lambda c: (-c[0], c[1])):
        if len(hits) >= n_max: break
        if t < t_min or t > ctx.END0 / FPS - 3.0 or any(abs(t - h[0]) < gap for h in hits): continue
        ph = phrase(ws, i, 3)
        txt = " ".join(clean(x["t"]) for x in ph).upper()
        FUNC_ = {"a", "de", "del", "la", "el", "en", "y", "que", "los", "las", "un", "una", "con", "por", "para", "se", "su", "sus", "al", "lo", "no", "es"}
        if len(txt) < 8 and i + 1 < len(ws) and P.norm(ws[i + 1]["t"]) not in FUNC_ and ws[i + 1]["t"][-1] not in ".?!": txt = (txt + " " + clean(ws[i + 1]["t"]).upper()).strip()
        if len(txt) < 5: continue
        hits.append((t, ctx.SC[sc]["sid"], ws[i]["t"], nth_of(ws, i), txt))
    return [(sid, tok, nth, txt) for t, sid, tok, nth, txt in sorted(hits)]


def enrich(cfg, ctx):
    """completa cfg (in situ) según el estilo; devuelve cfg"""
    st = cfg["style"]
    A_ = scene_ids(ctx)
    if st == "news":
        h = [w["t"] for w in ctx.WORDS if w["sc"] == 0]
        cfg.setdefault("hook_tag", "PREGUNTA" if any("?" in t for t in h) else "LILIAN SAMANIEGO")
    elif st == "ink":
        h = [clean(w["t"]) for w in ctx.WORDS if w["sc"] == 0]
        ws0, kws0 = key_words(cfg, ctx, 0)
        txt = " ".join(clean(w["t"]) for w in phrase(ws0, max(kws0, key=lambda k: k[2])[0], 3)) if kws0 else " ".join(h[:3])
        if len(txt) < 8: txt = " ".join(h[:3])
        cfg["hook_text"] = txt.upper()[:26]
        mids = [sc for sc in A_ if sc not in (A_[0], A_[-1])] or A_
        best = None
        for sc in mids:
            ws, kws = key_words(cfg, ctx, sc)
            for i, w, wt in kws:
                if wt >= 3 and ctx.SC[sc]["o0"] + 1.0 < w["s"] < ctx.SC[sc]["o1"] - 1.0 and (best is None or wt > best[0]): best = (wt, clean(w["t"]))
        cfg["red_word"] = best[1] if best else "ahorros"
    elif st == "fx":
        h = [clean(w["t"]) for w in ctx.WORDS if w["sc"] == 0]
        ws0, kws0 = key_words(cfg, ctx, 0)
        if kws0 and ctx.SC[0]["role"] == "H":
            ph = phrase(ws0, max(kws0, key=lambda k: k[2])[0], 3)
            cfg["hook_text"] = ("¿HAY " + " ".join(clean(w["t"]) for w in ph[-1:]).upper() + "?")[:28] if any("?" in w["t"] for w in ws0) else " ".join(clean(w["t"]) for w in ph).upper()[:26]
        else: cfg["hook_text"] = ""
        cfg["hits"] = pick_hits(cfg, ctx, n_max=max(6, int(ctx.END0 / FPS / 11)), gap=2.4)
    elif st == "report":
        scs = [sc for sc in A_ if ctx.SC[sc]["o1"] - ctx.SC[sc]["o0"] > 4.0][:6]
        used = set(); cfg["chapters"] = [(ctx.SC[sc]["sid"],) + scene_title(cfg, ctx, sc, used) for sc in scs]
        cuts, last_e = [], -9.0
        kinds = [("logo", None, None, "warm"), ("p2", (330, 10, 640), (360, 30, 560), "warm"), ("p1", (440, 190, 560), (430, 150, 480), "gloom"),
                 ("p2", (500, 0, 600), (470, 10, 520), "warm"), ("p1", (640, 140, 640), (610, 120, 540), "warm")]
        ki = 0
        cands = []
        for sc in A_:
            ws, kws = key_words(cfg, ctx, sc)
            for i, w, wt in kws: cands.append((w["s"], wt, sc, i, ws))
        for t, wt, sc, i, ws in sorted(cands):
            if len(cuts) >= max(5, int(ctx.END0 / FPS / 14)): break
            if t - 0.3 < max(last_e + 6.0, 4.5) or t > ctx.END0 / FPS - 6.0: continue
            kd = kinds[ki % len(kinds)]; ki += 1
            tag = "Banco Central del Paraguay" if kd[0] == "logo" else title_case(" ".join(clean(x["t"]) for x in phrase(ws, i, 3)).lower())
            dur = 2.9
            cuts.append([ctx.SC[sc]["sid"], ws[i]["t"], nth_of(ws, i), -0.25, dur, kd[0], kd[1], kd[2], kd[3], tag if kd[0] != "p1" else None])
            last_e = t - 0.25 + dur
        cfg["cutaways"] = cuts
    elif st == "headline":
        hl, used = {}, set()
        for sc in A_[:10]:
            t, s = scene_title(cfg, ctx, sc, used)
            ws, _ = key_words(cfg, ctx, sc)
            lines = ["{" + t.upper() + "}"]
            if s and P.norm(s) != P.norm(t): lines.append(s.upper())
            hl[ctx.SC[sc]["sid"]] = lines
        cfg["headlines"] = hl
    elif st == "call":
        chips, last = [], -9.0
        for sc in A_:
            ws, kws = key_words(cfg, ctx, sc)
            for i, w, wt in sorted(kws, key=lambda k: -k[2])[:1]:
                if w["s"] - last >= 6.0 and w["s"] > 3.0 and w["s"] < ctx.END0 / FPS - 3.0:
                    chips.append([ctx.SC[sc]["sid"], w["t"], nth_of(ws, i), " ".join(clean(x["t"]) for x in phrase(ws, i, 3)).upper(), 2.8]); last = w["s"]
        cfg["chips"] = chips[:8]
    elif st == "split":
        titles, used = {}, set()
        for k, sc in enumerate(A_[:10]):
            t, s = scene_title(cfg, ctx, sc, used); titles[ctx.SC[sc]["sid"]] = [k + 1, t, s]
        cfg["titles"] = titles
    return cfg


# ------------------------------------------------------------------ enriquecimiento con el MAPA DE CONTENIDO (titulares editoriales por bloque)
def beat_of_sid(sid):
    import content as C
    try: k = int(str(sid).rsplit("_", 1)[1])
    except Exception: return None
    for b in C.BEATS:
        if k in b["sents"]: return b["id"]
    return None


def beat_scenes(ctx):
    """[(beat_id, [scenes en orden])] según aparecen en el video"""
    order, seen = [], {}
    for sc in sorted(ctx.SC):
        b = beat_of_sid(ctx.SC[sc]["sid"])
        if b is None: continue
        if b not in seen: seen[b] = []; order.append(b)
        seen[b].append(sc)
    return [(b, seen[b]) for b in order]


def anchor_in(ctx, scenes, anchor, roles=("A",)):
    """(sid, token, nth, t) de la primera aparición de la palabra ancla en esas escenas"""
    for sc in scenes:
        if ctx.SC[sc]["role"] not in roles: continue
        ws = [w for w in ctx.WORDS if w["sc"] == sc]
        for i, w in enumerate(ws):
            if P.norm(clean(w["t"])).startswith(P.norm(anchor)):
                return ctx.SC[sc]["sid"], w["t"], nth_of(ws, i), w["s"]
    return None


def video_tags(ctx):
    """titulares del video SIN repetir: si dos ideas tienen el mismo titular (p. ej. IRRESPONSABLE), la segunda usa su bajada"""
    import content as C
    out, used = {}, set()
    for b, scs in beat_scenes(ctx):
        if b not in C.TAGS: continue
        t, anc, sub = C.TAGS[b]
        if t.strip().upper() in used:
            if sub and sub.strip().upper() not in used: t, sub = sub.upper(), ""
            else: continue
        used.add(t.strip().upper()); out[b] = (t, anc, sub)
    return out


def beat_timeline(ctx):
    """línea de tiempo de ideas del video: [{b, kind, title, sub, o0, o1, role, anchor_t}] en tiempo de SALIDA"""
    import content as C
    out = []
    VT = video_tags(ctx)
    runs = []                                                             # tramos SEGUIDOS de cada idea: si la frase del gancho vuelve después
    for sc in sorted(ctx.SC):                                             # en su contexto (videos de 2–4 min), esa idea tiene su propio tramo
        b = beat_of_sid(ctx.SC[sc]["sid"])                                # (si no, el titular anterior quedaba puesto sobre otra idea)
        if b is None: continue
        if runs and runs[-1][0] == b: runs[-1][1].append(sc)
        else: runs.append((b, [sc]))
    for ri, (b, scs) in enumerate(runs):
        tag = VT.get(b, ("", "", ""))
        if all(ctx.SC[sc]["role"] == "H" for sc in scs) and any(b2 == b for b2, _ in runs[ri + 1:]):
            tag = ("", tag[1], "")                                        # el gancho adelanta la idea: el titular va cuando la idea llega
        a = anchor_in(ctx, scs, tag[1], roles=("A", "Q", "H")) if tag[1] else None
        spk = getattr(ctx, "SPK", {})
        a0 = next((ctx.SC[sc]["o0"] for sc in scs if spk.get(sc, "L") == "L"), ctx.SC[scs[0]]["o0"])     # cuando ELLA empieza a responder
        out.append(dict(b=b, kind=C.BEAT[b]["kind"], title=tag[0], sub=tag[2], o0=round(ctx.SC[scs[0]]["o0"], 3), o1=round(ctx.SC[scs[-1]]["o1"], 3), a0=round(a0, 3),
                        role=ctx.SC[scs[0]]["role"], anchor_t=round(a[3], 3) if a else None, anchor=clean(a[1]) if a else ""))
    return out


def enrich_beats(cfg, ctx):
    import content as C
    st = cfg["style"]
    cfg["beats"] = beat_timeline(ctx)
    TG = video_tags(ctx)
    bs = [(b, scs) for b, scs in beat_scenes(ctx) if b in TG]
    if not bs: return enrich(cfg, ctx)
    end_t = ctx.END0 / FPS
    first_scene = lambda scs: next((sc for sc in scs if ctx.SC[sc]["role"] != "H"), scs[0])
    if st == "news":
        h = [w["t"] for w in ctx.WORDS if w["sc"] == 0]
        cfg["hook_tag"] = "PREGUNTA" if any("?" in t for t in h) else "LILIAN SAMANIEGO"
    elif st == "ink":
        hb = beat_of_sid(ctx.SC[0]["sid"])
        cfg["hook_text"] = TG[hb][0] if hb in TG else " ".join(clean(w["t"]) for w in ctx.WORDS if w["sc"] == 0)[:24].upper()
        red = None
        for b, scs in bs[1:-1]:
            if C.BEAT[b]["kind"] in ("ataque", "denuncia"):
                a = anchor_in(ctx, scs, TG[b][1])
                if a and 2.0 < a[3] < end_t - 8: red = clean(a[1]); break
        cfg["red_word"] = red or "ahorros"
    elif st == "fx":
        hb = beat_of_sid(ctx.SC[0]["sid"])
        cfg["hook_text"] = (("¿" + TG[hb][0].replace("NO HAY ", "HAY ").strip("¿?") + "?") if C.BEAT.get(hb, {}).get("kind") == "pregunta" else TG[hb][0]) if hb in TG and ctx.SC[0]["role"] == "H" else ""
        hits, last = [], -9.0
        for b, scs in bs:
            a = anchor_in(ctx, scs, TG[b][1])
            if a and a[3] - last >= 2.4 and 1.2 < a[3] < end_t - 3.0:
                hits.append((a[0], a[1], a[2], TG[b][0])); last = a[3]
        cfg["hits"] = hits
    elif st == "report":
        cfg["chapters"] = [(ctx.SC[first_scene(scs)]["sid"], title_case(TG[b][0].lower()) if len(TG[b][0]) > 13 else TG[b][0], TG[b][2]) for b, scs in bs if ctx.SC[first_scene(scs)]["role"] != "H"][:7]
        kinds = [("logo", None, None, "warm"), ("p2", (330, 10, 640), (360, 30, 560), "warm"), ("p1", (440, 190, 560), (430, 150, 480), "gloom"),
                 ("p2", (500, 0, 600), (470, 10, 520), "warm"), ("p1", (640, 140, 640), (610, 120, 540), "warm")]
        cuts, last_e, ki = [], -9.0, 0
        if not P.SRC.get("material"): bs_photo = []                         # sin material del tema: reportaje sin recuadros de fotos
        else: bs_photo = bs
        gap = 6.0 if end_t <= 130 else 20.0                                # videos largos: los recuadros de fotos más espaciados (solo hay 3 fotos)
        for b, scs in bs_photo:
            a = anchor_in(ctx, scs, TG[b][1])
            if len(cuts) >= (5 if end_t <= 130 else 8): break
            if not a or a[3] - 0.3 < max(last_e + gap, 4.5) or a[3] > end_t - 6.0: continue
            kd = kinds[ki % len(kinds)]; ki += 1
            tag = "Banco Central del Paraguay" if kd[0] == "logo" else title_case(TG[b][0].lower().strip("¿?"))
            cuts.append([a[0], a[1], a[2], -0.25, 2.9, kd[0], kd[1], kd[2], kd[3], tag])
            last_e = a[3] - 0.25 + 2.9
        cfg["cutaways"] = cuts
    elif st == "headline":
        hl = {}
        for b, scs in bs:
            sc = scs[0]
            lines = ["{" + TG[b][0] + "}"] + ([TG[b][2].upper()] if TG[b][2] else [])
            hl[ctx.SC[sc]["sid"]] = lines
        cfg["headlines"] = hl
    elif st == "call":
        chips, last = [], -9.0
        for b, scs in bs:
            a = anchor_in(ctx, scs, TG[b][1], roles=("A", "Q", "H"))
            if a and a[3] - last >= 5.0 and 2.0 < a[3] < end_t - 3.0:
                chips.append([a[0], a[1], a[2], TG[b][0], 2.8]); last = a[3]
        cfg["chips"] = chips
    elif st == "split":
        titles = {}
        for n, (b, scs) in enumerate(bs):
            titles[ctx.SC[scs[0]]["sid"]] = [n + 1, TG[b][0].strip("¿?") if len(TG[b][0]) < 18 else title_case(TG[b][0].lower()), TG[b][2]]
        cfg["titles"] = titles
    return cfg
