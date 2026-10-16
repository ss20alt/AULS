# Estudio de edición — ALINEACIÓN FORZADA (punto 4): tiempo exacto de cada palabra según el audio, no según la estimación de whisper.
# Modelo: wav2vec2-large-xlsr-53-spanish (CTC) en GPU. Para cada segmento de whisper se alinea su texto con el audio (Viterbi CTC)
# y se obtienen inicio/fin de cada palabra con resolución de 20 ms.
#   python align.py [fuente]   -> sources/<fuente>/transcript_aligned.json  (+ informe de diferencias con whisper)
import os as _os; _os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # Mac: operaciones sin MPS caen al procesador
import os, sys, json, wave, re, unicodedata, time
import numpy as np, torch

STUDIO = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(STUDIO, "models", "wav2vec2-large-xlsr-53-spanish")
SR16 = 16000
import plataforma as PL
dev = PL.DEVICE


def load_model():
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    proc = Wav2Vec2Processor.from_pretrained(MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL).eval(); model = PL.model_to(model)
    vocab = proc.tokenizer.get_vocab()
    return proc, model, vocab


def norm_word(w, vocab):
    """texto -> caracteres del vocabulario del modelo (minúsculas, sin signos; letras fuera del vocabulario se pasan a su forma base)"""
    w = w.lower()
    out = []
    for ch in w:
        if ch in vocab: out.append(ch); continue
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn")
        if base and base in vocab: out.append(base)
    return "".join(out)


def viterbi(emission, tokens, blank):
    """alineación CTC forzada: emission (T, C) log-probs, tokens (N) -> lista de (token_idx, frame) del camino más probable"""
    T, N = emission.shape[0], len(tokens)
    trellis = torch.full((T + 1, N + 1), -float("inf"), device=emission.device)
    trellis[0, 0] = 0
    trellis[1:, 0] = torch.cumsum(emission[:, blank], 0)
    tok = torch.tensor(tokens, device=emission.device)
    for t in range(T):
        stay = trellis[t, 1:] + emission[t, blank]
        move = trellis[t, :-1] + emission[t, tok]
        trellis[t + 1, 1:] = torch.maximum(stay, move)
    # retroceso
    path, j = [], N
    t = T
    tr = trellis.cpu(); em = emission.cpu()
    while j > 0 and t > 0:
        stay = tr[t - 1, j] + em[t - 1, blank]
        move = tr[t - 1, j - 1] + em[t - 1, tokens[j - 1]]
        if move >= stay: path.append((j - 1, t - 1)); j -= 1
        else: pass
        t -= 1
    return path[::-1]


def align_segment(audio, words, t0, proc, model, vocab):
    """audio 16 kHz del segmento (empieza en t0) + palabras [(texto)] -> [(s, e) | None] por palabra"""
    blank = vocab.get("<pad>", 0); sep = vocab.get("|")
    with torch.no_grad():
        x = proc(audio, sampling_rate=SR16, return_tensors="pt").input_values; x = PL.inputs_to(x)
        logits = model(x).logits[0].float()
    em = torch.log_softmax(logits, -1)
    stride = len(audio) / SR16 / em.shape[0]                        # ≈ 0.02 s por frame
    toks, owner = [], []
    for wi, w in enumerate(words):
        nw = norm_word(w, vocab)
        if not nw: continue
        if toks and sep is not None: toks.append(sep); owner.append(-1)
        for ch in nw: toks.append(vocab[ch]); owner.append(wi)
    if not toks or len(toks) > em.shape[0]: return [None] * len(words)
    path = viterbi(em, toks, blank)
    spans = {}
    for ti, fr in path:
        wi = owner[ti]
        if wi < 0: continue
        a, b = spans.get(wi, (fr, fr)); spans[wi] = (min(a, fr), max(b, fr))
    return [(t0 + spans[i][0] * stride, t0 + (spans[i][1] + 1) * stride) if i in spans else None for i in range(len(words))]


_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince",
      "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco",
      "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_D = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_C = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def spell(n):
    """número -> palabras en castellano (lo que realmente se oye: '2027' -> 'dos mil veintisiete')"""
    if n < 30: return _U[n]
    if n < 100: return _D[n // 10] + ("" if n % 10 == 0 else " y " + _U[n % 10])
    if n == 100: return "cien"
    if n < 1000: return _C[n // 100] + ("" if n % 100 == 0 else " " + spell(n % 100))
    if n < 1000000:
        m, r = divmod(n, 1000)
        return ("mil" if m == 1 else spell(m) + " mil") + ("" if r == 0 else " " + spell(r))
    return str(n)


def spoken(w):
    return re.sub(r"\d+", lambda m: " " + spell(int(m.group())) + " ", w)


def run(source):
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import plan as P
    tr = json.load(open(P.SRC["raw_transcript"], encoding="utf-8"))
    w = wave.open(P.SRC["voice"]); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    import scipy.signal as ss
    a16 = ss.resample_poly(a, 1, 3).astype(np.float32)
    proc, model, vocab = load_model()
    t0 = time.time(); n_ok = n_tot = 0; shifts = []
    # cada segmento de whisper se alinea por separado (probado: alinear tramos largos juntos es PEOR — el texto de una voz
    # lejana que el modelo no oye, p. ej. "Gracias, senadora" de una periodista sin micrófono, empuja a las palabras vecinas al silencio)
    W = [(si, x) for si, sg in enumerate(tr) for x in sg["words"]]
    res = []
    for sg in tr:
        ws = sg["words"]
        if not ws: continue
        s0 = max(0.0, min(sg["start"], ws[0]["s"]) - 0.35); e0 = max(sg["end"], ws[-1]["e"]) + 0.35
        seg = a16[int(s0 * SR16):int(e0 * SR16)]
        res += align_segment(seg, [spoken(x["w"].strip()) for x in ws], s0, proc, model, vocab)
    # palabras sin alinear (sin letras): se reparten entre sus vecinas alineadas, nunca se solapan
    for i, r in enumerate(res):
        if r is not None: continue
        pe = next((res[j][1] for j in range(i - 1, -1, -1) if res[j] is not None), None)
        ns = next((res[j][0] for j in range(i + 1, len(res)) if res[j] is not None), None)
        x = W[i][1]
        s, e = x["s"], x["e"]
        if pe is not None: s = max(s, pe)
        if ns is not None and ns > s: e = min(e, ns)
        if e <= s: e = s + 0.05
        res[i] = (s, e, "whisper")
    out = [dict(sg, words=[]) for sg in tr]
    for (si, x), r in zip(W, res):
        n_tot += 1
        if len(r) == 3: out[si]["words"].append(dict(x, s=round(r[0], 3), e=round(r[1], 3), ws=x["s"], we=x["e"], src="whisper")); continue
        n_ok += 1; shifts.append(r[0] - x["s"])
        out[si]["words"].append(dict(w=x["w"], s=round(r[0], 3), e=round(r[1], 3), p=x.get("p"), ws=x["s"], we=x["e"], src="ctc"))
    dst = os.path.join(P.SRC["dir"], "transcript_aligned.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sh = np.array(shifts)
    rep = dict(words=n_tot, aligned=n_ok, secs=round(time.time() - t0, 1), shift_median=round(float(np.median(sh)), 3),
               shift_abs_p90=round(float(np.percentile(np.abs(sh), 90)), 3), shift_abs_max=round(float(np.abs(sh).max()), 3))
    print("[align]", rep)
    return dst, rep


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STUDIO_SOURCE", "lilian_conferencia_bcp"))


def ghosts(source, write=True):
    """palabras que whisper escribió sin voz real debajo:
       1) racha de ≥ 2 palabras con confianza de whisper muy baja (repeticiones inventadas sobre un silencio)
       2) palabra que la alineación tuvo que estirar sobre un silencio (duración absurda para sus sílabas y poca voz)"""
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import importlib, plan as P
    importlib.reload(P)
    tr = json.load(open(os.path.join(P.SRC["dir"], "transcript_aligned.json"), encoding="utf-8"))
    W = [w for sg in tr for w in sg["words"]]
    p = [w.get("p") if w.get("p") is not None else 1.0 for w in W]
    bad = set()
    i = 0
    while i < len(W):                                                   # regla 1
        if p[i] < 0.3:
            j = i
            while j + 1 < len(W) and p[j + 1] < 0.6: j += 1
            k0 = i
            while k0 - 1 >= 0 and p[k0 - 1] < 0.6: k0 -= 1
            if j - k0 + 1 >= 2:
                run = [re.sub(r"[^a-záéíóúüñ]", "", W[k]["w"].lower()) for k in range(k0, j + 1)]
                prev = [re.sub(r"[^a-záéíóúüñ]", "", W[k]["w"].lower()) for k in range(max(0, k0 - len(run) - 2), k0)]
                repeated = sum(1 for x in run if x in prev) >= max(2, int(0.6 * len(run)))      # repite lo que se acaba de decir
                seg = P.R10[max(0, int(W[k0]["s"] * 100)):int(W[j]["e"] * 100) + 1]
                silent = len(seg) == 0 or float((seg > -36).mean()) < 0.4                       # o cae sobre silencio
                if repeated or silent: bad.update(range(k0, j + 1))
            i = j + 1
        else: i += 1
    for i, w in enumerate(W):                                           # regla 2
        dur = w["e"] - w["s"]
        nsyl = max(1, len(re.findall(r"[aeiouáéíóúü]+", w["w"].lower())))
        seg = P.R10[max(0, int(w["s"] * 100)):int(w["e"] * 100) + 1]
        vfrac = float((seg > -36).mean()) if len(seg) else 0.0
        if dur > max(1.2, 0.45 * nsyl) and vfrac < 0.5 and p[i] < 0.97: bad.add(i)          # estirada sobre silencio y whisper dudoso
    out = [[round(W[i].get("ws", W[i]["s"]) - 0.01, 3), round(W[i].get("ws", W[i]["s"]) + 0.01, 3), W[i]["w"].strip()] for i in sorted(bad)]
    if write:
        sp = os.path.join(P.SRC["dir"], "source.json")
        sj = json.load(open(sp, encoding="utf-8"))
        keep = [d for d in sj.get("delete", []) if len(d) < 3 or d[2] != "auto"]
        sj["delete"] = keep + [[a, b, "auto"] for a, b, _ in out]
        json.dump(sj, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[fantasmas] {source}: {[(x[2], x[0]) for x in out]}")
    return out
