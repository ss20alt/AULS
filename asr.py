# Estudio de edición — voz recortada, selects (NVDEC/NVENC), ASR por escena (Whisper GPU) y tiempos de palabra anclados a las ráfagas de voz.
import os, sys, json, wave, subprocess, re
import numpy as np
from core import LIL, FPS, SR, SPF, read_wav, write_wav
import plan as P

def domain_prompt():
    """vocabulario para whisper: el de la fuente, o el de la ficha del cliente + el tema del video (nombres propios, siglas)"""
    if P.SRC.get("prompt"): return P.SRC["prompt"]
    return (P.CLIENT.get("whisper_prompt", "Conferencia de prensa.") + " " + P.SRC.get("tema", "")).strip()


# ------------------------------------------------------------------ voz recortada (frame-exacta, micro-fundidos de 8 ms)
def build_voice_cut(edl, path):
    V = np.stack([P.VOICE, P.VOICE], 1)
    _wf = wave.open(P.SRC["voice"])
    V = np.frombuffer(_wf.readframes(_wf.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    N = edl["total"] * SPF
    out = np.zeros((N, 2), np.float32)
    FD = 384
    sp = [s for s in edl["items"] if s["kind"] == "speech"]
    for j, s in enumerate(sp):
        x = V[s["fs"] * SPF:s["fe"] * SPF].copy()
        nxt_cont = j + 1 < len(sp) and sp[j + 1].get("cont") and sp[j + 1]["fs"] == s["fe"]
        fi = 0 if (s.get("cont") and j > 0 and sp[j - 1]["fe"] == s["fs"]) else (1680 if s.get("soft_in") else FD)       # audio continuo: sin fundido en la unión
        fo = 0 if nxt_cont else (2400 if s.get("soft_out") else FD)                                                      # corte sobre voz: fundido de 35-50 ms
        if fi: x[:fi] *= np.linspace(0, 1, fi)[:, None] ** 1.5
        if fo: x[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
        o = (s["out"] + s.get("pre", 0)) * SPF; out[o:o + len(x)] += x
    write_wav(path, out)
    return out


def build_selects(edl, path, filt_path):
    sp = [i for i in edl["items"] if i["kind"] == "speech"]
    parts, names = [], []
    for i, s in enumerate(sp):
        if s.get("pre", 0) > 0:                                         # respiración: primer cuadro congelado
            parts.append(f"[0:v]trim=start_frame={s['fs']}:end_frame={s['fs'] + 1},setpts=PTS-STARTPTS,loop=loop={s['pre'] - 1}:size=1:start=0,setpts=N/(30*TB)[p{i}]")
            names.append(f"[p{i}]")
        parts.append(f"[0:v]trim=start_frame={s['fs']}:end_frame={s['fe']},setpts=PTS-STARTPTS[v{i}]")
        names.append(f"[v{i}]")
    fc = ";".join(parts) + ";" + "".join(names) + f"concat=n={len(names)}:v=1:a=0[out]"
    open(filt_path, "w").write(fc)
    import plataforma as PL
    r = PL.run_ffmpeg(["ffmpeg", "-v", "error", "-y", *PL.HWDEC, "-i", P.SRC["video"], "-/filter_complex", filt_path, "-map", "[out]",
                       *PL.venc(14, "40M", "80M", gop=0, tune_hq=False, rc=False, profile=False), "-pix_fmt", "yuv420p", "-r", "30", path])
    if r.returncode: raise RuntimeError(r.stderr[-800:])
    return sum(s["n"] for s in sp)


# ------------------------------------------------------------------ ASR (large-v3, GPU)
def transcribe(voice_cut_path, out_json):
    import scipy.signal as ss, plataforma as PL
    a = read_wav(voice_cut_path).mean(1)
    a16 = ss.resample_poly(a, 1, 3).astype(np.float32)
    m = PL.whisper_model("large-v3")
    segs, _ = m.transcribe(a16, language="es", word_timestamps=True, vad_filter=False, beam_size=5, condition_on_previous_text=False, initial_prompt=domain_prompt())
    words = [dict(t=w.word.strip(), s=round(w.start, 3), e=round(w.end, 3)) for s in segs for w in s.words]
    json.dump(words, open(out_json, "w", encoding="utf-8"), ensure_ascii=False)
    del m
    return words


# ------------------------------------------------------------------ escenas en la línea de tiempo recortada
def scenes_of(edl):
    sp = [i for i in edl["items"] if i["kind"] == "speech"]
    SC = {}
    for sc in sorted(set(s["scene"] for s in sp)):
        g = [s for s in sp if s["scene"] == sc]
        SC[sc] = dict(sid=g[0]["sid"], role=g[0]["role"], o0=min(s["out"] for s in g) / FPS, o1=max(s["out"] + s["n"] for s in g) / FPS)
    return SC


def syl(w):
    w = re.sub(r"[^a-záéíóúüñ]", "", w.lower())
    return max(1, len(re.findall(r"[aeiouáéíóúü]+", w))) + 0.12 * len(w)


def fix_token(t):
    core = t.strip(".,¿?¡!")
    if core in P.GLOSSARY: t = t.replace(core, P.GLOSSARY[core])
    return t


def _sim(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def source_words(edl, hyp=None):
    """texto = transcripción de la fuente (contexto completo + glosario) · est = tiempo en la línea recortada.
    Cada palabra va a la toma con la que más se solapa; las 2 palabras de cada extremo de la toma se verifican con el ASR del audio ya recortado
    (whisper desfasa ~0.2 s y puede dejar en la toma una palabra que el corte ya no contiene)."""
    import content as C
    per, other = {}, []
    sp = [i for i in edl["items"] if i["kind"] == "speech"]
    for w in P.WORDS:
        if any(a <= w["s"] <= b for a, b in P.BAD): continue
        foreign = C.WORD_SPK.get(round(w["s"], 3)) == "R"                    # palabra de una frase de otra persona (periodista)
        dur = max(0.05, w["e"] - w["s"])
        mid_w = (w["s"] + w["e"]) / 2
        holders = [it for it in sp if it["fs"] / FPS <= mid_w < it["fe"] / FPS]
        # una misma frase puede sonar DOS veces (gancho = avance y después en su contexto): la palabra va a cada toma que la contiene
        groups = [[h] for h in holders] if holders else [sp]
        for cand in groups:
            best, bov, bsc = None, 0.0, 0.0
            for it in cand:
                ov = min(w["e"] + 0.25, it["fe"] / FPS) - max(w["s"], it["fs"] / FPS)             # +0.25 s: whisper acaba las palabras cortas antes de tiempo
                ov0 = min(w["e"], it["fe"] / FPS) - max(w["s"], it["fs"] / FPS)
                sc_ = ov0 + 0.25 * ov
                if (ov > 0 and sc_ > bsc) or (holders and best is None): best, bov, bsc = it, max(ov, 0.12), max(sc_, 1e-6)
            if best is None or bov < min(0.12, 0.45 * (dur + 0.25)): continue
            if foreign and best.get("role") == "A": other.append(w["t"]); continue        # nunca en el subtítulo de ella
            f0, f1 = int(max(w["s"], best["fs"] / FPS) * FPS), int(min(w["e"] + 0.25, best["fe"] / FPS) * FPS) + 1
            if not (P.R[f0:f1] > -40.0).any(): continue                     # sin voz real dentro de la toma
            t = max(w["s"], best["fs"] / FPS)
            per.setdefault(id(best), (best, []))[1].append(dict(t=w["t"], s=(best["out"] + best.get("pre", 0)) / FPS + (t - best["fs"] / FPS), e=0, w0=w["s"], w1=w["e"]))
    out, dropped, unsure = {}, [], []
    STARTERS = {"y", "yo", "de", "lo", "eso", "por", "pero", "porque", "es", "en", "un", "una", "si", "ahora", "entonces", "sí", "no", "que", "la", "el", "los", "las", "a", "con", "para", "se", "su", "mi", "esto", "ese", "esa", "como", "cuando", "también", "ni", "o", "e"}
    for it, L in per.values():
        if len(L) >= 1:
            fe_s, fs_s = it["fe"] / FPS, it["fs"] / FPS
            # reglas automáticas de borde (aprendidas de las decisiones editoriales):
            #  fin: palabra con mayúscula que abre frase (Y, Por, Eso, De, Lo…) = principio de la frase siguiente que el corte ya no contiene
            #  inicio: palabra que cierra frase (termina en . ? !) = cola de la frase anterior
            #  ambos: si menos del 35 % de la palabra (según whisper) cae dentro de la toma, se descarta
            def mid(tok): return (tok["w0"] + tok["w1"]) / 2
            ein, eout = it.get("ein", True), it.get("eout", True)           # solo en los bordes del guion (no en pausas internas)
            while eout and len(L) >= 1:                                        # extremo final
                t_ = L[-1]["t"].strip("¿?¡!.,")
                if t_[:1].isupper() and t_.lower() in STARTERS and L[-1]["t"][-1] not in ".?!": dropped.append(L.pop()["t"]); continue
                if len(L) >= 2 and L[-2]["t"][-1] in ".?!" and L[-1]["t"][-1] not in ".?!" and it.get("last_of_unit", True): dropped.append(L.pop()["t"]); continue   # abre la frase siguiente
                if len(L) >= 2 and mid(L[-1]) > fe_s + 0.05: dropped.append(L.pop()["t"]); continue
                break
            while ein and len(L) >= 1:                                         # extremo inicial
                if L[0]["t"][-1] in ".?!": dropped.append(L.pop(0)["t"]); continue
                if len(L) >= 2 and mid(L[0]) < fs_s - 0.15: dropped.append(L.pop(0)["t"]); continue
                break
        if hyp is not None and len(L) > 2:
            def heard(tok):                                                # cerca en tiempo, o la MISMA palabra algo corrida (whisper adelanta palabras tras una pausa)
                return any(abs(h["s"] - tok["s"]) < 0.6 or (abs(h["s"] - tok["s"]) < 1.5 and _sim(P.norm(h["t"]), P.norm(tok["t"])) >= 0.7) for h in hyp)
            def match(tok): return any(abs(h["s"] - tok["s"]) < 2.0 and _sim(P.norm(h["t"]), P.norm(tok["t"])) >= 0.7 for h in hyp)
            while it.get("eout", True) and len(L) > 2 and not heard(L[-1]): dropped.append(L.pop()["t"])   # solo en un corte real (no en pausas recortadas)
            for tok, pos in ((L[0], "inicio"), (L[-1], "fin")):
                if not match(tok): unsure.append((it["sid"], pos, tok["t"]))
        out.setdefault(it["scene"], []).extend(L)
    for sc in out:
        out[sc].sort(key=lambda w: w["s"])
        for a_, b_ in zip(out[sc], out[sc][1:]):                         # mayúscula al empezar una oración ("…patria. Eso es.")
            if a_["t"][-1:] in ".?!" and b_["t"][:1].islower(): b_["t"] = b_["t"][:1].upper() + b_["t"][1:]
        w = out[sc][0] if out[sc] else None                # si el corte dejó afuera solo una conjunción inicial ("Y vos" -> "vos"), se capitaliza
        if w is not None and w["t"][:1].islower():
            st = [x for x in P.WORDS if x["s"] <= w["w0"] + 0.01 and not any(a_ <= x["s"] <= b_ for a_, b_ in P.BAD)]
            k = len(st) - 1
            while k > 0 and st[k - 1]["t"][-1] not in ".?!": k -= 1
            if k >= 0 and w["w0"] - st[k]["s"] <= 0.7: w["t"] = w["t"][:1].upper() + w["t"][1:]
    if dropped: print("[words] bordes descartados por reglas automáticas:", dropped)
    if other: print("[words] palabras de otra voz fuera del subtítulo:", other)
    if unsure: print("[words] bordes dudosos que quedan (ASR escribe otra cosa):", unsure)
    return out


def align_words(edl, voice_cut, keyset, hyp=None):
    """tokens = texto de la fuente (con glosario) · tiempos = DP sobre las ráfagas de voz reales de cada escena"""
    SC = scenes_of(edl)
    SRCW = source_words(edl, hyp)
    m = voice_cut.mean(1)
    R10 = np.array([20 * np.log10(np.sqrt(np.mean(m[i:i + 480] ** 2)) + 1e-9) for i in range(0, len(m) - 480, 480)])

    def bursts_in(a, b, thr=-38.0, gap=0.10, minlen=0.12):
        i0, i1 = int(a * 100), int(b * 100)
        act = R10[i0:i1] > thr
        out, i = [], 0
        while i < len(act):
            if act[i]:
                j = i
                while j + 1 < len(act) and act[j + 1]: j += 1
                out.append([a + i / 100, a + (j + 1) / 100]); i = j + 1
            else: i += 1
        merged = []
        for s, e in out:
            if merged and s - merged[-1][1] < gap: merged[-1][1] = e
            else: merged.append([s, e])
        return [(s, e) for s, e in merged if e - s >= minlen]

    words = []
    for sc, S in SC.items():
        o0, o1 = S["o0"], S["o1"]
        hw = SRCW.get(sc, [])
        toks = []
        for h in hw:
            for piece in h["t"].split():
                toks.append((piece, h["s"], P.norm(piece) in keyset, h.get("w0")))
        N = len(toks)
        if N == 0: continue
        cw = np.concatenate([[0], np.cumsum([syl(tk[0]) for tk in toks])])
        est = [min(max(tk[1], o0), o1) for tk in toks]
        bs = bursts_in(o0, o1) or [(o0, o1)]
        while len(bs) > N:
            gaps = [bs[k + 1][0] - bs[k][1] for k in range(len(bs) - 1)]
            k = int(np.argmin(gaps)); bs = bs[:k] + [(bs[k][0], bs[k + 1][1])] + bs[k + 2:]
        K = len(bs); D = sum(e - s for s, e in bs); rbar = cw[-1] / D
        INF = 1e18

        def cost(k, i0, i1):
            dk = bs[k][1] - bs[k][0]; wk = cw[i1] - cw[i0]
            c = 0.5 * dk * abs(wk / dk - rbar) / rbar
            if k > 0:
                c += 0.5 * abs(est[i0] - bs[k][0])
                gp = bs[k][0] - bs[k - 1][1]
                if toks[i0 - 1][0][-1] in ".,?!;": c -= 0.6 * min(gp, 0.7)
            return c
        f = [[INF] * (N + 1) for _ in range(K + 1)]; bp = [[0] * (N + 1) for _ in range(K + 1)]
        f[0][0] = 0.0
        for k in range(K):
            for i1 in range(k + 1, N - (K - 1 - k) + 1):
                for i0 in range(k, i1):
                    if f[k][i0] >= INF: continue
                    v = f[k][i0] + cost(k, i0, i1)
                    if v < f[k + 1][i1]: f[k + 1][i1] = v; bp[k + 1][i1] = i0
        bc, i1 = [], N
        for k in range(K, 1, -1):
            i0 = bp[k][i1]; bc.append(i0); i1 = i0
        idx = [0] + bc[::-1] + [N]
        for k in range(K):
            a, b = bs[k]; i0, i1 = idx[k], idx[k + 1]; tw = cw[i1] - cw[i0]
            for i in range(i0, i1):
                s = a + (b - a) * (cw[i] - cw[i0]) / tw; e = a + (b - a) * (cw[i + 1] - cw[i0]) / tw
                words.append(dict(t=toks[i][0], s=s, e=e, sc=sc, key=toks[i][2], i=i, w0=toks[i][3] if len(toks[i]) > 3 else None))
    for i in range(1, len(words)):                         # mayúscula al abrir frase (whisper a veces la omite)
        if words[i]["sc"] == words[i - 1]["sc"] and words[i - 1]["t"][-1] in ".?!" and words[i]["t"][:1].islower():
            words[i]["t"] = words[i]["t"][:1].upper() + words[i]["t"][1:]
    return SC, words


# ------------------------------------------------------------------ subtítulos: fragmentos de 2-3 palabras
FUNC = {"de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "a", "al", "en", "y", "o", "u", "e", "que", "con", "por", "para", "se", "su", "sus", "lo", "mi", "tu", "es", "no", "si", "como", "ni", "hay", "ha", "han", "ese", "esa", "esta", "este", "eso"}


def _core(t): return P.norm(t)


def build_chunks(SC, WORDS, skip_roles=("H", "Q"), max_chars=21, split_on_key=True, merge_scenes=()):
    """fragmentos de 2-4 palabras con sentido (programación dinámica): no terminan en artículo/preposición, no dejan palabras sueltas,
    cortan en comas y puntos; las frases clave van aparte"""
    out = []
    for sc in SC:
        if SC[sc]["role"] in skip_roles: continue
        ws0 = [w for w in WORDS if w["sc"] == sc]
        if sc in merge_scenes and ws0:                                    # voz de otra persona (pregunta): la frase entera en un bloque de 2 líneas
            sents, cur = [], []
            for w in ws0:
                cur.append(w)
                if w["t"][-1] in ".?!": sents.append(cur); cur = []
            if cur: sents.append(cur)
            groups = []
            def _split(c):
                if sum(len(x["t"]) + 1 for x in c) <= 95 or len(c) < 4: groups.append(c); return
                mid = sum(len(x["t"]) + 1 for x in c) / 2; acc, best = 0, None
                for j in range(1, len(c)):
                    acc += len(c[j - 1]["t"]) + 1
                    sc = abs(acc - mid) - (25 if c[j - 1]["t"][-1] in ",;" else 0) - (12 if _core(c[j]["t"]) in ("sobre", "que", "y", "porque", "para", "de") else 0)
                    if best is None or sc < best[0]: best = (sc, j)
                _split(c[:best[1]]); _split(c[best[1]:])
            for c in sents: _split(c)
            for gi, c in enumerate(groups):
                s0 = c[0]["s"] - 0.03
                nxt_w = min((w["s"] for w in WORDS if w["s"] > c[-1]["s"] + 0.01 and w not in c), default=1e9)   # nunca tapa la respuesta
                e0 = min(groups[gi + 1][0]["s"] - 0.03 if gi + 1 < len(groups) else c[-1]["e"] + 0.45, SC[sc]["o1"] + 0.35, nxt_w - 0.03)
                out.append(dict(sc=sc, s=max(SC[sc]["o0"], s0), e=e0, words=[w["t"] for w in c], flags=[False] * len(c), ts=[w["s"] for w in c], key=False, merged=True,
                                hold=0.9 if gi == len(groups) - 1 else 0.0))      # la pregunta queda 0.9 s más, chica y arriba de la respuesta
            continue
        ws = []
        for w in ws0:                                                     # tartamudeos: "que que" -> "que"
            if ws and _core(ws[-1]["t"]) == _core(w["t"]) and len(_core(w["t"])) <= 4 and ws[-1]["t"][-1] not in ".?!": 
                ws[-1] = dict(ws[-1], e=w["e"]); continue
            ws.append(w)
        n = len(ws)
        INF = 1e9

        def cost(i, j):
            c = ws[i:j]; m = len(c)
            if split_on_key and len({x["key"] for x in c}) > 1: return INF
            wd = sum(len(x["t"]) + 1 for x in c) - 1
            key = any(x["key"] for x in c)
            dur = (ws[j]["s"] if j < n else c[-1]["e"] + 0.22) - c[0]["s"]
            fast = dur < 0.27 * m                                           # habla rápida: se permiten fragmentos algo más largos
            if m > 1 and wd > max_chars + (6 if key else 0) + (7 if fast else 0): return INF
            if m > (4 if key else 4): return INF
            v = 1.0 + 0.04 * abs(wd - 14)
            cps = (wd + 1) / max(0.1, dur)                                  # velocidad de lectura: > 21 car/s no se alcanza a leer
            if cps > 21: v += 0.5 * (cps - 21)
            if m == 1 and not key: v += 1.8
            if m == 4 and not key: v += 0.5
            last = c[-1]["t"]
            if j < n and _core(last) in FUNC and last[-1] not in ".,?!;": v += 3.5
            if any(x["t"][-1] in ",;" for x in c[:-1]): v += 4.0
            if any(x["t"][-1] in ".?!" for x in c[:-1]): v += 6.0
            if last[-1] in ".?!": v -= 1.0
            elif last[-1] in ",;": v -= 0.6
            return v
        best = [INF] * (n + 1); prv = [0] * (n + 1); best[0] = 0.0
        for j in range(1, n + 1):
            for i in range(max(0, j - 5), j):
                if best[i] >= INF: continue
                v = best[i] + cost(i, j)
                if v < best[j]: best[j] = v; prv[j] = i
        cuts, j = [], n
        while j > 0: cuts.append((prv[j], j)); j = prv[j]
        ch = [ws[i:j] for i, j in cuts[::-1]]
        for k, c in enumerate(ch):
            s0 = c[0]["s"] - 0.03
            nxt = ch[k + 1][0]["s"] - 0.03 if k + 1 < len(ch) else None
            e0 = c[-1]["e"] + 0.22
            if nxt is not None and nxt - e0 < 0.30: e0 = nxt
            e0 = min(e0, SC[sc]["o1"])
            out.append(dict(sc=sc, s=max(SC[sc]["o0"], s0), e=e0, words=[w["t"] for w in c], flags=[w["key"] for w in c], ts=[w["s"] for w in c], key=any(w["key"] for w in c)))
    # un fragmento de menos de 0.3 s no se alcanza a leer: se une al siguiente (o al anterior) de la misma escena ("Vos," + "por supuesto,")
    i = 0
    while i < len(out):
        c = out[i]
        if c.get("merged") or c["e"] - c["s"] >= 0.30: i += 1; continue
        nb = [j for j in (i + 1, i - 1) if 0 <= j < len(out) and out[j]["sc"] == c["sc"] and not out[j].get("merged")
              and len(" ".join(out[j]["words"] + c["words"])) <= max_chars + 8]
        if not nb: i += 1; continue
        j = nb[0]; a, b = (c, out[j]) if j > i else (out[j], c)
        m = dict(a, e=b["e"], words=a["words"] + b["words"], flags=a["flags"] + b["flags"], ts=a["ts"] + b["ts"], key=a["key"] or b["key"])
        out[min(i, j)] = m; del out[max(i, j)]
        i = min(i, j)
    return out
