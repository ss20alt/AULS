# Estudio de edición — ÁRBITRO DE LA TRANSCRIPCIÓN: compara lo que ESCRIBIÓ whisper con lo que OYE el modelo acústico (wav2vec2,
# lectura letra por letra, sin diccionario). Donde no coinciden puede haber un error de whisper ("El trato de sicaria" cuando el audio
# dice "le trató de sicaria") o una palabra que whisper no escribió. Cada desacuerdo queda en una lista con su minuto para que el
# equipo lo escuche y lo confirme con un clic; una corrección se re-alinea con el audio y queda como prueba permanente.
#   python arbitro.py scan   <fuente>   -> sources/<fuente>/arbitro.json (desacuerdos ordenados por gravedad)
#   python arbitro.py review <fuente>   -> página local http://127.0.0.1:8765 para escuchar y decidir
import os, sys, json, re, io, wave, time, difflib
import numpy as np

STUDIO = os.path.dirname(os.path.abspath(__file__))
SR16 = 16000


def _load(source):
    os.environ["STUDIO_SOURCE"] = source
    sys.path.insert(0, STUDIO)
    import importlib, plan as P
    importlib.reload(P)
    import content as C
    importlib.reload(C)
    return P, C


def _audio16(P):
    import scipy.signal as ss
    w = wave.open(P.SRC["voice"]); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32).mean(1) / 32768
    return ss.resample_poly(a, 1, 3).astype(np.float32)


def greedy(seg, t0, proc, model, inv):
    """lectura del modelo acústico: [(letra, tiempo)] (sin repetidos ni silencios)"""
    import torch
    with torch.no_grad():
        import plataforma as PL
        x = PL.inputs_to(proc(seg, sampling_rate=SR16, return_tensors="pt").input_values)
        am = model(x).logits[0].float().argmax(-1).tolist()
    st = len(seg) / SR16 / max(1, len(am))
    out, prev = [], None
    for i, k in enumerate(am):
        ch = inv[k]
        if k != prev and ch not in ("<pad>", "<s>", "</s>", "<unk>"): out.append((ch, t0 + i * st))
        prev = k
    return out


def scan(source, write=True):
    """comparación por TIEMPO: (1) voz que el modelo oye donde whisper no escribió nada -> "falta texto";
    (2) cada palabra contra lo que el modelo oye exactamente en su tramo -> "texto distinto"."""
    import align as A
    P, C = _load(source)
    a16 = _audio16(P)
    proc, model, vocab = A.load_model()
    inv = {v: k for k, v in vocab.items()}
    W = [w for w in P.WORDS if not any(a <= w["s"] <= b for a, b in P.BAD)]
    T = len(a16) / SR16
    # ventanas que cubren TODO el audio (cortadas en el medio de las pausas largas), para oír también lo que whisper salteó
    cuts, last = [0.0], 0.0
    for w0, w1 in zip(W, W[1:]):
        gap = w1["s"] - w0["e"]
        m = (w0["e"] + w1["s"]) / 2
        if (gap > 0.6 and m - last > 4.0) or m - last > 20.0: cuts.append(m); last = m
    cuts.append(T)
    G = []
    for s0, e0 in zip(cuts, cuts[1:]):
        if e0 - s0 < 0.3: continue
        G += greedy(a16[int(s0 * SR16):int(e0 * SR16)], s0, proc, model, inv)
    letters = [(c, t) for c, t in G if c.isalpha()]
    spans = [(w["s"] - 0.12, w["e"] + 0.12) for w in W]
    items = []
    # (1) letras oídas fuera de toda palabra escrita
    free = [(c, t) for c, t in letters if not any(a <= t <= b for a, b in spans)]
    grp = []
    for c, t in free:
        if grp and t - grp[-1][1] > 0.35:
            items += _missing(grp, W, P); grp = []
        grp.append((c, t))
    if grp: items += _missing(grp, W, P)
    # (2) cada palabra contra lo oído en su propio tramo
    bad = []
    for i, w in enumerate(W):
        nw = re.sub(r"[^a-záéíóúüñ]", "", A.norm_word(A.spoken(w["t"]).replace(" ", ""), vocab))
        if len(nw) < 4: continue
        heard = "".join(c for c, t in letters if w["s"] - 0.08 <= t <= w["e"] + 0.08)
        r = difflib.SequenceMatcher(None, _plain(nw), _plain(heard), autojunk=False).ratio()
        if r < 0.5: bad.append((i, r, heard))
    groups = []
    for i, r, h in bad:
        if groups and i - groups[-1][-1][0] <= 2: groups[-1].append((i, r, h))
        else: groups.append([(i, r, h)])
    for g in groups:
        i0, i1 = g[0][0], g[-1][0]
        t0, t1 = W[i0]["s"], W[i1]["e"]
        items.append(dict(t0=round(t0, 2), t1=round(t1, 2), whisper=" ".join(w["t"] for w in W[max(0, i0 - 1):i1 + 2]),
                          dudosas=" ".join(W[i]["t"] for i in range(i0, i1 + 1)), oye=_reading(G, t0 - 0.2, t1 + 0.2),
                          sev=round(sum((1 - r) * len(W[i]["t"]) for i, r, h in g), 1), tipo="distinta"))
    for it in items:
        mid = (it["t0"] + it["t1"]) / 2
        it["quien"] = "periodista" if P.speaker_at(mid) == "R" else "ella"
        if it["quien"] == "periodista": it["sev"] = round(it["sev"] * 0.4, 1)                # lo de los periodistas importa menos
    items.sort(key=lambda x: -x["sev"])
    for k, it in enumerate(items): it["id"] = k
    prev = {}
    pth = os.path.join(P.SRC["dir"], "arbitro.json")
    if os.path.exists(pth):                                                               # conservar decisiones ya tomadas
        for it in json.load(open(pth, encoding="utf-8")).get("items", []):
            if it.get("decision"): prev[(it["t0"], it["t1"])] = it["decision"]
    for it in items:
        if (it["t0"], it["t1"]) in prev: it["decision"] = prev[(it["t0"], it["t1"])]
    out = dict(source=source, date=time.strftime("%Y-%m-%d %H:%M"), items=items)
    if write: json.dump(out, open(pth, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[árbitro] {source}: {len(items)} desacuerdos ({sum(1 for i in items if i['quien'] == 'ella')} en su voz)")
    for it in items[:14]:
        print(f"  {int(it['t0'] // 60)}:{it['t0'] % 60:05.2f} [{it['quien']:10s}] {it['tipo']:8s} sev {it['sev']:5.1f}  whisper: «{it['whisper']}»  ·  oye: «{it['oye']}»")
    return out


def _plain(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _missing(grp, W, P):
    """voz oída sin texto: solo si son ≥ 5 letras y hay voz real (no ruido) en ese tramo"""
    if len(grp) < 5: return []
    a, b = grp[0][1], grp[-1][1] + 0.06
    seg = P.R10[int(a * 100):int(b * 100) + 1]
    if not len(seg) or float((seg > -34).mean()) < 0.5: return []
    prv = max((w for w in W if w["e"] <= a + 0.12), key=lambda w: w["e"], default=None)
    nxt = min((w for w in W if w["s"] >= b - 0.12), key=lambda w: w["s"], default=None)
    txt = "".join(c for c, t in grp)
    return [dict(t0=round(a, 2), t1=round(b, 2), whisper=(prv["t"] if prv else "") + "  [ … nada … ]  " + (nxt["t"] if nxt else ""),
                 dudosas="", oye=txt, sev=round(1.5 * len(grp), 1), tipo="falta")]


def _reading(g, a, b):
    return re.sub(r"\|+", " ", "".join(c for c, t in g if a <= t <= b)).strip()


# ---------------------------------------------------------------- revisión con un clic (página local)
PAGE = """<!doctype html><meta charset=utf-8><title>Árbitro de la transcripción</title>
<style>
:root{--bg:#0b1530;--card:#13214a;--fg:#e8ecf6;--mute:#9aa6c4;--ok:#3ccf8e;--warn:#ffc93c;--red:#ff4a55}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif;padding:24px 16px}
main{max-width:860px;margin:auto;display:flex;flex-direction:column;gap:14px}
h1{font-size:22px;margin:0}.sub{color:var(--mute)}
.it{background:var(--card);border-radius:14px;padding:14px 16px;display:grid;gap:8px}
.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.t{font-variant-numeric:tabular-nums;font-weight:700}
.tag{font-size:12px;padding:2px 8px;border-radius:99px;background:#24356a;color:var(--mute)}
.sev{color:var(--warn);font-size:12px}.w b{color:var(--warn)}.o{color:var(--mute)}
input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid #2c3d73;background:#0e1838;color:var(--fg);font:inherit}
.btns{display:flex;gap:8px;flex-wrap:wrap}button{border:0;border-radius:8px;padding:8px 14px;font:inherit;font-weight:600;cursor:pointer}
.ok{background:var(--ok);color:#06210f}.fix{background:var(--warn);color:#2a1d00}.done{opacity:.55}.st{font-weight:700}
audio{width:100%;height:34px}
</style><main><h1>Árbitro de la transcripción — %SRC%</h1>
<div class=sub>Whisper escribió una cosa y el modelo acústico oye otra. Escuchá cada fragmento y decidí: <b>Está bien</b> deja el texto como está;
<b>Corregir</b> guarda tu texto, lo alinea con el audio y queda como prueba permanente del estudio.</div><div id=list></div></main>
<script>
const items=%ITEMS%;
const mm=t=>Math.floor(t/60)+":"+(t%60).toFixed(1).padStart(4,"0");
function row(it){const d=document.createElement("div");d.className="it"+(it.decision?" done":"");d.id="it"+it.id;
d.innerHTML=`<div class=top><span class=t>${mm(it.t0)}</span><span class=tag>${it.quien}</span><span class=tag>${it.tipo=="falta"?"falta texto":"texto distinto"}</span><span class=sev>gravedad ${it.sev}</span><span class=st>${it.decision?("✓ "+it.decision.action):""}</span></div>
<div class=w>Whisper: «${it.whisper.replace(it.dudosas,"<b>"+it.dudosas+"</b>")}»</div><div class=o>El modelo oye: «${it.oye}»</div>
<audio controls preload=none src="/clip?t0=${it.t0}&t1=${it.t1}"></audio>
<input value="${(it.decision&&it.decision.text)||(it.tipo=="falta"?"":it.dudosas)}" placeholder="texto correcto de ese tramo">
<div class=btns><button class=ok>Está bien</button><button class=fix>Corregir</button></div>`;
d.querySelector(".ok").onclick=()=>send(it,"ok",null,d);d.querySelector(".fix").onclick=()=>send(it,"corregir",d.querySelector("input").value,d);return d}
async function send(it,action,text,d){d.querySelector(".st").textContent="guardando…";
const r=await fetch("/decide",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:it.id,action,text})});
const j=await r.json();d.querySelector(".st").textContent=j.ok?("✓ "+action+(j.msg?" — "+j.msg:"")):("error: "+j.msg);if(j.ok)d.classList.add("done")}
const L=document.getElementById("list");items.forEach(it=>L.appendChild(row(it)));
</script>"""


def review(source, port=8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs
    P, C = _load(source)
    pth = os.path.join(P.SRC["dir"], "arbitro.json")
    data = json.load(open(pth, encoding="utf-8"))
    w = wave.open(P.SRC["voice"]); sr = w.getframerate(); ch = w.getnchannels(); raw = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, ch)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _send(self, code, body, ctype):
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                html = PAGE.replace("%SRC%", source).replace("%ITEMS%", json.dumps(data["items"], ensure_ascii=False))
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/clip":
                q = parse_qs(u.query); t0 = float(q["t0"][0]) - 0.6; t1 = float(q["t1"][0]) + 0.6
                seg = raw[max(0, int(t0 * sr)):int(t1 * sr)]
                bio = io.BytesIO(); ww = wave.open(bio, "wb"); ww.setnchannels(ch); ww.setsampwidth(2); ww.setframerate(sr); ww.writeframes(seg.tobytes()); ww.close()
                return self._send(200, bio.getvalue(), "audio/wav")
            self._send(404, b"no", "text/plain")

        def do_POST(self):
            if urlparse(self.path).path != "/decide": return self._send(404, b"no", "text/plain")
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            it = next(i for i in data["items"] if i["id"] == req["id"])
            msg = ""
            try:
                if req["action"] == "corregir":
                    text = (req.get("text") or "").strip()
                    if not text: raise ValueError("escribí el texto correcto")
                    import feedback as FB
                    pad = 0.0 if it["tipo"] == "distinta" else 0.05
                    FB.fix_source(source, it["t0"] - pad, it["t1"] + pad, text, note=f"árbitro: «{it['whisper']}» -> «{text}»", win=(it["t0"] - 0.05, it["t1"] + 0.1))
                    msg = "corregido y alineado"
                it["decision"] = dict(action=req["action"], text=req.get("text"), date=time.strftime("%Y-%m-%d %H:%M"))
                json.dump(data, open(pth, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                self._send(200, json.dumps(dict(ok=True, msg=msg)).encode(), "application/json")
            except Exception as e:
                self._send(200, json.dumps(dict(ok=False, msg=str(e))).encode(), "application/json")

    print(f"[árbitro] revisión en http://127.0.0.1:{port}  (Ctrl+C para terminar)")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, src = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "lilian_conferencia_bcp")
    if cmd == "scan": scan(src)
    elif cmd == "review": review(src, int(sys.argv[3]) if len(sys.argv) > 3 else 8765)
