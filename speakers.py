# Estudio de edición — QUIÉN HABLA (punto 5): verificación de voz con WavLM-SV contra la "huella de voz" del cliente.
# Cada frase se compara con la huella de Lilian; lo que no es su voz se marca como periodista (REPORTER).
#   python speakers.py build  [fuente_con_etiquetas]  -> clients/<cliente>_voiceprint.npy + umbral (calibrado con la fuente etiquetada a mano)
#   python speakers.py label  <fuente>                -> escribe "reporter" en sources/<fuente>/source.json
#   python speakers.py eval   [fuente_con_etiquetas]  -> precisión contra las etiquetas manuales
import os as _os; _os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # Mac: operaciones sin MPS caen al procesador
import os, sys, json, wave
import numpy as np, torch

STUDIO = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(STUDIO, "models", "wavlm-base-plus-sv")
SR16 = 16000
import plataforma as PL
dev = PL.DEVICE
_m = {}


def model():
    if not _m:
        from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
        _m["fe"] = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
        _m["m"] = WavLMForXVector.from_pretrained(MODEL).to(dev).eval()
    return _m["fe"], _m["m"]


def load_audio(path):
    import scipy.signal as ss
    w = wave.open(path); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    return ss.resample_poly(a, 1, 3).astype(np.float32)


def embed(a16, s, e):
    fe, m = model()
    x = a16[int(s * SR16):int(e * SR16)]
    if len(x) < int(0.4 * SR16): x = np.pad(x, (0, int(0.4 * SR16) - len(x)))
    with torch.no_grad():
        inp = fe(x, sampling_rate=SR16, return_tensors="pt").to(dev)
        v = m(**inp).embeddings[0].float().cpu().numpy()
    return v / (np.linalg.norm(v) + 1e-9)


def chunks(s, e, maxlen=3.0):
    n = max(1, int(np.ceil((e - s) / maxlen)))
    return [(s + (e - s) * i / n, s + (e - s) * (i + 1) / n) for i in range(n)]


def sentences(source):
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import importlib, plan, content
    importlib.reload(plan); importlib.reload(content)
    return plan, content.SENT


def sentence_embeddings(P, SENT):
    a16 = load_audio(P.SRC["voice"])
    out = []
    for s in SENT:
        vs = [embed(a16, a, b) for a, b in chunks(s["s"], s["e"])]
        out.append(np.mean(vs, 0))
    return np.array(out)


def build(source="lilian_conferencia_bcp"):
    P, SENT = sentences(source)
    E = sentence_embeddings(P, SENT)
    lab = np.array([s["spk"] == "L" for s in SENT])
    dur = np.array([s["dur"] for s in SENT])
    # validación "dejando uno afuera": la huella se arma sin la frase que se evalúa
    sims = []
    for i in range(len(SENT)):
        mask = lab.copy(); mask[i] = False; mask &= dur >= 1.5
        vp = E[mask].mean(0); vp /= np.linalg.norm(vp)
        sims.append(float(E[i] @ vp))
    sims = np.array(sims)
    cands = np.linspace(sims.min(), sims.max(), 400)
    acc = [((sims >= c) == lab).mean() for c in cands]
    thr = float(cands[int(np.argmax(acc))])
    vp = E[lab & (dur >= 1.5)].mean(0); vp /= np.linalg.norm(vp)
    client = P.SRC["client"]
    np.save(os.path.join(STUDIO, "clients", f"{client}_voiceprint.npy"), vp)
    meta = dict(threshold=round(thr, 4), accuracy_loo=round(float(max(acc)), 3), n_lilian=int(lab.sum()), n_otros=int((~lab).sum()),
                sim_lilian_median=round(float(np.median(sims[lab])), 3), sim_otros_median=round(float(np.median(sims[~lab])), 3))
    json.dump(meta, open(os.path.join(STUDIO, "clients", f"{client}_voiceprint.json"), "w"), indent=1)
    print("[voz] huella creada:", meta)
    for i, s in enumerate(SENT):
        ok = (sims[i] >= thr) == lab[i]
        if not ok: print(f"   ✗ {s['s']:6.1f}s {'L' if lab[i] else 'R'} sim {sims[i]:.3f}  {s['text'][:70]}")
    return meta


VOCATIVE = __import__("re").compile(r"(^\W*|gracias,?\s+)senadora\b|\bsenadora\W*$")      # "senadora" como vocativo (ella nunca se llama así)


def _label_monologo(source, P, SENT, E, sims, thr, write):
    """DISCURSO / MENSAJE: en un acto con parlantes su voz suena distinta a la huella (0.78–0.94 en vez de ≥ 0.85) y ella dice
    "ustedes" todo el tiempo (no es la prensa). Se agrupan las voces DEL PROPIO video; la voz de ella = el grupo con más tiempo
    entre los que se parecen a la huella; otra voz = grupo lejos de la huella y lejos de ella (el locutor que la presenta)"""
    from scipy.cluster.hierarchy import linkage, fcluster
    dur = np.array([s_["dur"] for s_ in SENT])
    idx = [i for i in range(len(SENT)) if dur[i] >= 1.0]
    spk = ["L"] * len(SENT)
    if len(idx) >= 3:
        lab = fcluster(linkage(E[idx], "average", metric="cosine"), t=0.30, criterion="distance")
        groups = {}
        for i, g in zip(idx, lab): groups.setdefault(g, []).append(i)
        cen = {g: (lambda c: c / np.linalg.norm(c))(E[m].mean(0)) for g, m in groups.items()}
        vp = E[0] * 0 + np.load(os.path.join(STUDIO, "clients", f"{P.SRC['client']}_voiceprint.npy"))
        cand = [g for g in groups if float(cen[g] @ vp) >= thr - 0.10] or list(groups)
        main = max(cand, key=lambda g: dur[groups[g]].sum())
        for g, m in groups.items():
            if g == main: continue
            far_vp = float(cen[g] @ vp) < thr - 0.06; far_main = float(cen[g] @ cen[main]) < 0.80
            for i in m:
                if far_vp and far_main and sims[i] < thr - 0.04: spk[i] = "R"
        for i, s_ in enumerate(SENT):                                      # frases muy cortas: heredan de la vecina
            if dur[i] < 1.0:
                nb = [j for j in (i - 1, i + 1) if 0 <= j < len(SENT) and dur[j] >= 1.0]
                if nb: spk[i] = spk[min(nb, key=lambda j: min(abs(SENT[j]["s"] - s_["e"]), abs(s_["s"] - SENT[j]["e"])))]
    rep, cur = [], None
    for s_, k in zip(SENT, spk):
        if k == "R":
            if cur and s_["s"] - cur[1] < 1.0: cur[1] = s_["e"] + 0.2
            else:
                if cur: rep.append(cur)
                cur = [round(s_["s"] - 0.2, 2), round(s_["e"] + 0.2, 2)]
    if cur: rep.append(cur)
    if write:
        sp = os.path.join(P.SRC["dir"], "source.json")
        sj = json.load(open(sp, encoding="utf-8")); sj["reporter"] = rep; sj["reporter_auto"] = True
        json.dump(sj, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[voz] {source} ({P.SRC.get('tipo')}: decide la voz del propio video): {sum(1 for k in spk if k == 'R')} frases de otras voces -> tramos {rep}")
    return spk, sims, rep


def label(source, write=True):
    P, SENT = sentences(source)
    client = P.SRC["client"]
    vp = np.load(os.path.join(STUDIO, "clients", f"{client}_voiceprint.npy"))
    thr = json.load(open(os.path.join(STUDIO, "clients", f"{client}_voiceprint.json")))["threshold"]
    E = sentence_embeddings(P, SENT)
    sims = E @ vp
    if P.SRC.get("tipo") in ("discurso", "mensaje"):                   # una sola persona habla (acto / a cámara): solo la voz decide
        return _label_monologo(source, P, SENT, E, sims, thr, write)
    import re as _re
    def qrule(s_, v):
        w_ = set(_re.findall(r"[a-záéíóúñü]+", s_["text"].lower()))
        return s_["text"].lstrip().startswith("¿") and not (w_ & {"vos", "te", "tu", "tus"}) and v < thr + 0.07
    def decide(s_, v):
        t = s_["text"].lower()
        words = set(_re.findall(r"[a-záéíóúñü]+", t))
        if v < thr: return "R"
        if VOCATIVE.search(t): return "R"                                                      # "Gracias, senadora." / "Senadora, ¿…?": le hablan a ella
        if words & {"senadora", "usted", "ustedes"} and v < 0.93: return "R"                # la prensa se dirige a ella
        if qrule(s_, v): return "R"                                                              # pregunta de periodista
        return "L"
    spk = [decide(s_, v) for s_, v in zip(SENT, sims)]
    # adaptación a cada video: perfiles locales de "Lilian" y "prensa" con las frases claras; los casos dudosos se deciden contra ambos
    cue0 = lambda s_: bool(set(_re.findall(r"[a-záéíóúñü]+", s_["text"].lower())) & {"senadora", "usted", "ustedes"}) or bool(VOCATIVE.search(s_["text"].lower()))
    dur = np.array([s_["dur"] for s_ in SENT])
    confL = (sims >= 0.93) & (dur >= 1.5)
    confR = np.array([(v < thr - 0.03 or cue0(s_)) and s_["dur"] >= 1.0 for s_, v in zip(SENT, sims)])
    if confR.sum() >= 2 and confL.sum() >= 3:
        cL = E[confL].mean(0); cL /= np.linalg.norm(cL)
        cR = E[confR].mean(0); cR /= np.linalg.norm(cR)
        for i, s_ in enumerate(SENT):
            if confL[i] or cue0(s_) or qrule(s_, sims[i]): continue
            spk[i] = "L" if float(E[i] @ cL) - float(E[i] @ cR) > 0 else "R"
    cue = lambda s_: bool(set(_re.findall(r"[a-záéíóúñü]+", s_["text"].lower())) & {"senadora", "usted", "ustedes"})
    for i in range(1, len(SENT)):                                     # serie de preguntas retóricas de ella ("¿Vos dónde estás…? ¿Y de la educación?")
        a, b = SENT[i - 1], SENT[i]
        if spk[i] == "R" and spk[i - 1] == "L" and a["text"].rstrip().endswith("?") and b["text"].lstrip().startswith("¿") and b["s"] - a["e"] < 1.2 and not cue(b) and sims[i] >= thr:
            spk[i] = "L"
    # frases muy cortas (< 1 s): el embedding es poco fiable -> heredan el hablante de la frase vecina más cercana
    for i, s in enumerate(SENT):
        if s["dur"] < 1.0 and not cue(s):
            nb = [j for j in (i - 1, i + 1) if 0 <= j < len(SENT) and SENT[j]["dur"] >= 1.0]
            if nb: spk[i] = spk[min(nb, key=lambda j: min(abs(SENT[j]["s"] - s["e"]), abs(s["s"] - SENT[j]["e"])))]
    rep, cur = [], None
    for s, k in zip(SENT, spk):
        if k == "R":
            if cur and s["s"] - cur[1] < 1.0: cur[1] = s["e"] + 0.2
            else:
                if cur: rep.append(cur)
                cur = [round(s["s"] - 0.2, 2), round(s["e"] + 0.2, 2)]
    if cur: rep.append(cur)
    if write:
        sp = os.path.join(P.SRC["dir"], "source.json")
        sj = json.load(open(sp, encoding="utf-8")); sj["reporter"] = rep; sj["reporter_auto"] = True
        json.dump(sj, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[voz] {source}: {sum(1 for k in spk if k == 'R')} frases de otras voces -> tramos {rep}")
    return spk, sims, rep


def evaluate(source="lilian_conferencia_bcp"):
    spk, sims, rep = label(source, write=False)
    P, SENT = sentences(source)
    MAN = [tuple(x[:2]) for x in json.load(open(os.path.join(STUDIO, "sources", "lilian_conferencia_bcp", "source.json"), encoding="utf-8"))["reporter"]]
    lab = ["R" if any(a <= (s["s"] + s["e"]) / 2 <= b for a, b in MAN) else "L" for s in SENT]
    acc = np.mean([a == b for a, b in zip(spk, lab)])
    print(f"[voz] precisión contra etiquetas manuales: {acc * 100:.1f}% ({sum(a == b for a, b in zip(spk, lab))}/{len(lab)})")
    for s, a, b, v in zip(SENT, spk, lab, sims):
        if a != b: print(f"   ✗ {s['s']:6.1f}s manual {b} auto {a} sim {v:.3f}  {s['text'][:70]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    src = sys.argv[2] if len(sys.argv) > 2 else "lilian_conferencia_bcp"
    {"build": build, "label": label, "eval": evaluate}[cmd](src)
