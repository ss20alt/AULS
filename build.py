# Estudio de edición — orquestador: proyecto -> EDL -> voz/selects -> ASR+palabras -> render del estilo -> QA.
#   python build.py <proyecto> [--stills 1 5.5 ...] [--guides] [--rebuild] [--skip-render]
import os as _os; _os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")   # Mac: operaciones sin MPS caen al procesador
import os, sys, json, time, importlib, threading, queue
import numpy as np, torch
from core import *
import plan as P
import asr as A
import curated

PROJ_ROOT = os.path.join(STUDIO, "projects")


class Ctx:
    """todo lo que un estilo necesita saber del proyecto"""
    def __init__(self, cfg, pdir):
        self.cfg, self.dir = cfg, pdir
        self.J = lambda *p: os.path.join(pdir, *p)
        self.edl = json.load(open(self.J("edl.json"), encoding="utf-8"))
        self.ITEMS = self.edl["items"]; self.TOTAL = self.edl["total"]
        self.SEGS = [i for i in self.ITEMS if i["kind"] == "speech"]
        self.SC = {int(k): v for k, v in json.load(open(self.J("scenes.json"), encoding="utf-8")).items()}
        self.WORDS = json.load(open(self.J("words.json"), encoding="utf-8"))
        import content as _C
        def _spk(v):
            if "spk" in v: return v["spk"]
            try: return _C.SENT[int(str(v["sid"]).rsplit("_", 1)[1])]["spk"]
            except Exception: return "L"
        self.SPK = {k: ("R" if v["role"] == "Q" else _spk(v)) for k, v in self.SC.items()}
        self.REP_SC = {k for k, v in self.SC.items() if self.SPK[k] == "R"}
        self.CHUNKS = A.build_chunks(self.SC, self.WORDS, skip_roles=tuple(cfg.get("skip_caption_roles", ("H", "Q"))), max_chars=cfg.get("max_chars", 21), split_on_key=cfg.get("split_on_key", True),
                                     merge_scenes=self.REP_SC if cfg.get("merge_questions", True) else ())
        self.END0 = self.ITEMS[-1]["out"]
        self.SEL0, acc = {}, 0
        for i, s in enumerate(self.SEGS): self.SEL0[i] = acc; acc += s["n"]
        self._idx = {id(s): i for i, s in enumerate(self.SEGS)}
        self.cam = Camera(P.SRC["face"])
        self.selects = self.J("selects.mp4")
        self.voice = read_wav(self.J("voice_cut.wav"))
        self.hook_end = self.SC[0]["o1"]

    def item_at(self, n):
        for it in self.ITEMS:
            if it["out"] <= n < it["out"] + it["n"]: return it
        return self.ITEMS[-1]

    def shot_start(self, it): return min(s["out"] for s in self.SEGS if s["shot"] == it["shot"])

    def w_(self, sc, tok, nth=0):
        c = [w for w in self.WORDS if w["sc"] == sc and P.norm(w["t"]) == P.norm(tok)]
        return c[nth]["s"]

    def scene_of(self, sid):
        return [k for k, v in self.SC.items() if v["sid"] == sid]


def get_cfg(name):
    if name in curated.PROJECTS: return curated.PROJECTS[name]
    return json.load(open(os.path.join(PROJ_ROOT, name, "cfg.json"), encoding="utf-8"))


def prepare(name, rebuild=False):
    cfg = get_cfg(name)
    pdir = os.path.join(PROJ_ROOT, name); os.makedirs(pdir, exist_ok=True)
    J = lambda *p: os.path.join(pdir, *p)
    log = lambda *a: print("[build]", *a, flush=True)
    if rebuild or not os.path.exists(J("edl.json")):
        edl = P.build_edl(cfg["script"], cfg["target"], pre_default=cfg.get("pre", 5), shot_max=cfg.get("shot_max", 5.0),
                          pause_keep=cfg.get("pause_keep"), end_max=cfg.get("end_max", 110))
        json.dump(edl, open(J("edl.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"EDL: voz {edl['speech'] / FPS:.2f}s + tarjeta {edl['end_n'] / FPS:.2f}s = {edl['total'] / FPS:.2f}s  ok={edl['ok']}")
        for k in ("voice_cut.wav", "selects.mp4", "hyp.json", "words.json", "scenes.json"):
            if os.path.exists(J(k)): os.remove(J(k))
    edl = json.load(open(J("edl.json"), encoding="utf-8"))
    if not edl["ok"]: log("!! duración de la tarjeta final fuera de rango:", edl["end_n"] / FPS, "s")
    if not os.path.exists(J("voice_cut.wav")):
        A.build_voice_cut(edl, J("voice_cut.wav")); log("voz recortada")
    if not os.path.exists(J("selects.mp4")):
        t0 = time.time(); n = A.build_selects(edl, J("selects.mp4"), J("selects_filter.txt")); log(f"selects ({n} fr) {time.time() - t0:.0f}s")
    if not os.path.exists(J("hyp.json")):
        t0 = time.time(); A.transcribe(J("voice_cut.wav"), J("hyp.json")); log(f"ASR {time.time() - t0:.0f}s")
    if not os.path.exists(J("words.json")):
        hyp = json.load(open(J("hyp.json"), encoding="utf-8"))
        vc = read_wav(J("voice_cut.wav"))
        keyset = {P.norm(k) for k, v in cfg.get("keys", {}).items() if v >= 2} | {P.norm(k) for k in cfg.get("extra_keys", [])}
        SC, words = A.align_words(edl, vc, keyset, hyp)
        for d in cfg.get("drop_tokens", []):                       # decisiones del editor sobre bordes dudosos: (sid, palabra, 'first'|'last'|n)
            which = d[2] if len(d) > 2 else "first"
            for sc in SC:
                if SC[sc]["sid"] == d[0]:
                    ix = [i for i, w in enumerate(words) if w["sc"] == sc and P.norm(w["t"]) == P.norm(d[1])]
                    if ix: words.pop(ix[0] if which == "first" else ix[-1] if which == "last" else ix[which])
        import content as _C
        for k, v in SC.items():                                          # quién habla en cada escena, guardado con el proyecto
            try: v["spk"] = "R" if v["role"] == "Q" else _C.SENT[int(str(v["sid"]).rsplit("_", 1)[1])]["spk"]
            except Exception: v["spk"] = "L"
        json.dump({str(k): v for k, v in SC.items()}, open(J("scenes.json"), "w"), indent=1)
        json.dump(words, open(J("words.json"), "w", encoding="utf-8"), ensure_ascii=False)
        log("palabras alineadas:", len(words))
        for sc in SC: log(f"  sc{sc} {SC[sc]['sid']} {SC[sc]['role']}: " + " ".join(("*" if w["key"] else "") + w["t"] for w in words if w["sc"] == sc))
    return cfg, pdir


_LITE = {}


def _lite(src, dst, box):
    try:
        make_lite(src, dst); print("[lite]", round(os.path.getsize(dst) / 1e6, 1), "MB", flush=True)
    except Exception as e: box.append(e)


def wait_lite(name):
    """espera la versión liviana que se hace en paralelo con el control final (si falló, avisa igual que antes)"""
    th = _LITE.pop(name, None)
    if th is None: return
    th[0].join()
    if th[1]: raise th[1][0]


class _Prefetch:
    """lee los cuadros de selects.mp4 por adelantado en otro hilo: el armado de cada cuadro no espera al decodificador"""
    def __init__(self, rd, depth=6):
        self.rd, self.q, self.stop = rd, queue.Queue(depth), False
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def _run(self):
        nb = W * H * 3
        while not self.stop:
            b = self.rd.p.stdout.read(nb)
            x = np.frombuffer(b, np.uint8).reshape(H, W, 3) if len(b) == nb else None
            while not self.stop:
                try: self.q.put(x, timeout=0.2); break
                except queue.Full: continue
            if x is None: return

    def get(self):
        x = self.q.get()
        if x is None: raise RuntimeError("selects.mp4 terminó antes que el video")
        return x

    def close(self):
        self.stop = True; self.rd.close()


class _Writer:
    """baja cada cuadro a la CPU y lo manda al codificador en otro hilo mientras se arma el siguiente.
    En NVIDIA: copia asíncrona a memoria fija (anillo de búferes) + evento por cuadro; sin NVIDIA, igual que antes (to_np)"""
    def __init__(self, enc, depth=4):
        self.enc, self.q, self.err, self.k = enc, queue.Queue(depth), None, 0
        self.cuda = getattr(dev, "type", str(dev)) == "cuda"
        self.bufs = [torch.empty((H, W, 3), dtype=torch.uint8).pin_memory() for _ in range(depth + 2)] if self.cuda else None
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def put(self, fr):
        if self.err: raise self.err
        if self.cuda:
            host = self.bufs[self.k % len(self.bufs)]; self.k += 1     # depth en la cola + 1 escribiéndose + 1 llenándose: nunca se pisa
            host.copy_((fr.clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous(), non_blocking=True)
            ev = torch.cuda.Event(); ev.record()
            self.q.put((host, ev))
        else:
            self.q.put((to_np(fr), None))

    def _run(self):
        while True:
            item = self.q.get()
            if item is None: return
            if self.err: continue
            a, ev = item
            try:
                if ev is not None: ev.synchronize(); a = a.numpy()
                self.enc.stdin.write(a.data)
            except Exception as e: self.err = e

    def close(self):
        self.q.put(None); self.t.join()
        if self.err: raise self.err


def render(name, stills=None, guides_on=False, lite_async=False, pipeline=True):
    """lite_async: la versión liviana se codifica en paralelo (lo siguiente, el control final, casi no usa la placa); wait_lite(name) la espera.
    pipeline: leer el cuadro siguiente y codificar el anterior mientras se arma el actual (mismos bytes que en serie)"""
    wait_lite(name)                                             # nunca pisar el video mientras la liviana anterior lo está leyendo
    cfg, pdir = prepare(name)
    ctx = Ctx(cfg, pdir)
    ctx.cam.zoom_mul = cfg.get("zoom_mul", 1.0)
    mod = importlib.import_module("styles." + cfg["style"])
    S = mod.Style(ctx)
    S.setup()
    TOTAL = ctx.TOTAL
    if stills is not None:
        os.makedirs(ctx.J("stills"), exist_ok=True)
        for ts in stills:
            n = min(TOTAL - 1, int(round(ts * FPS))); it = ctx.item_at(n)
            if it["kind"] == "speech":
                if getattr(S, "uses_video", True):
                    i = ctx._idx[id(it)]; rd = Reader(ctx.selects, ctx.SEL0[i] + (n - it["out"]))
                    fr = S.compose(n, it, rd); rd.close()
                else: fr = S.compose(n, it, None)
            else: fr = S.compose(n, it, None)
            im = to_np(fr)
            if guides_on: im = guides(im)
            cv2.imwrite(ctx.J("stills", f"s_{ts:06.2f}{'_g' if guides_on else ''}.png"), cv2.cvtColor(cv2.resize(im, (540, 960), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR))
        return
    spk = np.concatenate([np.arange(s["out"] * SPF, (s["out"] + s["n"]) * SPF) for s in ctx.SEGS])
    mdb = cfg.get("music_db", -19.5)
    for _try in range(4):                                       # nivel de música automático: 15–19 dB bajo la voz
        info = mix_audio(ctx.voice, TOTAL, S.whips(), S.cues(), ctx.J("mix.wav"), music_db=mdb, bpm=cfg.get("bpm", 100), speech_mask=spk, chords=cfg.get("chords"), seed=cfg.get("seed", 31))
        if 15.0 <= info["dif"] <= 19.0: break
        mdb += float(info["dif"]) - 17.0
    info["music_db"] = round(mdb, 1)
    print("[audio]", info, flush=True)
    json.dump({k: float(v) for k, v in info.items()}, open(ctx.J("mix_info.json"), "w"))
    out_path = ctx.J(f"{name}.mp4")
    enc = start_encoder(out_path, ctx.J("mix.wav"), TOTAL / FPS, cq=cfg.get("cq", 18), lufs=cfg.get("lufs", -14))
    rd = Reader(ctx.selects) if getattr(S, "uses_video", True) else None; t0 = time.time()
    if pipeline and rd is not None: rd = _Prefetch(rd)
    wr = _Writer(enc) if pipeline else None
    try:
        for n in range(TOTAL):
            it = ctx.item_at(n)
            fr = S.compose(n, it, rd if it["kind"] == "speech" else None)
            if wr is not None: wr.put(fr)
            else: enc.stdin.write(to_np(fr).tobytes())
            if n % 300 == 0: print(f"{n}/{TOTAL}  {n / max(1e-6, time.time() - t0):.1f} fps", flush=True)
        if wr is not None: wr.close()
    finally:
        if rd is not None: rd.close()
        if wr is not None and wr.t.is_alive(): wr.q.put(None)          # si algo falló a mitad, el hilo del codificador termina igual
    if hasattr(S, "cp"): S.cp.close()
    enc.stdin.close(); enc.wait()
    print("[render] listo en", round(time.time() - t0), "s ->", out_path)
    lite = ctx.J(f"{name}_liviano.mp4")
    if lite_async:
        box = []; th = threading.Thread(target=_lite, args=(out_path, lite, box)); th.start(); _LITE[name] = (th, box)
    else:
        make_lite(out_path, lite); print("[lite]", round(os.path.getsize(lite) / 1e6, 1), "MB")
    return out_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a: print("uso: build.py <proyecto> [--stills t ...] [--guides] [--rebuild] [--prepare]"); sys.exit(1)
    name = a[0]
    if "--rebuild" in a: prepare(name, rebuild=True)
    if "--prepare" in a: prepare(name); sys.exit(0)
    if "--stills" in a:
        ts = [float(x) for x in a[a.index("--stills") + 1:] if not x.startswith("--")]
        render(name, stills=ts, guides_on="--guides" in a)
    else:
        render(name)
