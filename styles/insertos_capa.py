# Capa de INSERTOS DE CONTEXTO (referencias N04, N15, N17, N18, N25, N26 · T02, T04, T10): captura de una noticia, nota del
# diario, documento, tabla o infografía a pantalla completa cuando ella NOMBRA el tema, mientras su voz sigue y el subtítulo
# continúa. La imagen va nítida al centro, sobre ella misma desenfocada y oscurecida, con un acercamiento lento (como el equipo:
# zoom a la cifra de la tabla, al titular de la nota).
#   cfg["insertos"] = [rutas de imágenes]  (make_video.py --insertos <carpeta|imágenes>)
#   Disparador = el NOMBRE del archivo ("piso_salarial.png" -> "piso salarial"), o insertos.json en la carpeta:
#   [{"archivo": "nota_abc.jpg", "cuando": "huelga médica", "dur": 5}]
import os, json, re
import numpy as np
from PIL import Image, ImageFilter
from styles.base import *
import plan as P

DUR = 4.2


def trigger_of(path):
    b = os.path.splitext(os.path.basename(path))[0]
    b = re.sub(r"[_\-.]+", " ", b); b = re.sub(r"\b\d+\b", " ", b)
    return " ".join(b.split())


class Insertos:
    def __init__(self, style, avoid=()):
        self.S, self.c = style, style.c
        self.items, self.cache = [], {}
        paths = self.c.cfg.get("insertos") or []
        if not paths: return
        spec = {}
        for d in {os.path.dirname(p) for p in paths}:
            jp = os.path.join(d, "insertos.json")
            if os.path.exists(jp):
                for e in json.load(open(jp, encoding="utf-8")): spec[os.path.join(d, e["archivo"])] = e
        W_ = [w for w in self.c.WORDS if w.get("sc") is not None and style.scene_spk.get(w["sc"], "L") != "R"]
        toks = [P.norm(w["t"]) for w in W_]
        hook_end = getattr(style, "hook_end_t", getattr(style, "bw_end", 0.0)); end_t = self.c.END0 / FPS
        used_t = []
        for p in paths:
            e = spec.get(p, {})
            trig = [P.norm(x) for x in (e.get("cuando") or trigger_of(p)).split() if len(P.norm(x)) > 2 or P.norm(x).isdigit()]   # "hubo 37": el número cuenta
            if not trig: continue
            hit = None
            for i in range(len(toks)):                                         # la frase del disparador (o sus 2 primeras palabras)
                n = min(len(trig), 3)
                if toks[i:i + n] == trig[:n]:
                    t = W_[i]["s"]
                    if t < hook_end + 0.5 or t > end_t - 3.0: continue
                    if any(a - 0.5 <= t <= b + 0.5 for a, b in list(avoid) + used_t): continue
                    hit = t; break
            if hit is None:
                print("[insertos] no se dice:", " ".join(trig), "->", os.path.basename(p)); continue
            dur = float(e.get("dur", DUR))
            ends = sorted(v["o1"] for v in self.c.SC.values()) + [end_t]
            t1 = min(hit + dur, next((x for x in ends if x > hit + 1.0), end_t) - 0.15, end_t - 0.5)
            if t1 - hit < 2.0: continue
            self.items.append(dict(path=p, t0=hit - 0.15, t1=t1)); used_t.append((hit - 0.15, t1))
        self.items.sort(key=lambda x: x["t0"])
        print("[insertos]", [(os.path.basename(x["path"])[:24], round(x["t0"], 1), round(x["t1"] - x["t0"], 1)) for x in self.items] or "ninguno")
        declarar_tramos(self.c.dir, "insertos", [(x["t0"], x["t1"]) for x in self.items], quietos=True)   # imagen fija a propósito

    def spans(self): return [(x["t0"], x["t1"]) for x in self.items]

    def _prep(self, x):
        if x["path"] in self.cache: return self.cache[x["path"]]
        im = Image.open(x["path"]).convert("RGB")
        # fondo: la misma imagen, cubriendo el cuadro, desenfocada y oscura
        sc = max(W / im.width, H / im.height)
        bg = im.resize((int(im.width * sc) + 2, int(im.height * sc) + 2)).filter(ImageFilter.GaussianBlur(28))
        l, t = (bg.width - W) // 2, (bg.height - H) // 2
        bg = np.asarray(bg.crop((l, t, l + W, t + H))).astype(np.float32) / 255 * 0.45
        # frente: la imagen entera, nítida, a lo ancho (máx. 1000×1300) con un borde blanco fino
        fs = min(1000 / im.width, 1300 / im.height)
        fg = im.resize((int(im.width * fs), int(im.height * fs)), Image.LANCZOS)
        fr = Image.new("RGB", (fg.width + 12, fg.height + 12), (255, 255, 255)); fr.paste(fg, (6, 6))
        out = (torch.from_numpy(bg).permute(2, 0, 1).to(dev).to(DT),
               torch.from_numpy(np.asarray(fr).astype(np.float32) / 255).permute(2, 0, 1).to(dev).to(DT))
        self.cache[x["path"]] = out
        return out

    def draw(self, fr, t):
        x = next((x for x in self.items if x["t0"] <= t < x["t1"]), None)
        if x is None: return fr
        bg, fg = self._prep(x)
        a = t - x["t0"]; d = x["t1"] - x["t0"]
        k = min(1.0, a / 0.25, max(0.0, (d - a) / 0.25))
        u = a / d; z = 1.0 + 0.07 * u                                          # acercamiento lento
        h, w = fg.shape[1:]
        hs, ws = int(h * z), int(w * z)
        fgz = torch.nn.functional.interpolate(fg[None].float(), size=(hs, ws), mode="bilinear", align_corners=False)[0].to(DT)
        out = bg.clone()
        y0 = int(700 - hs / 2) if hs < 1300 else int(110 - (hs - 1300) * 0.0)
        y0 = max(60, min(H - hs - 60, y0)) if hs < H - 120 else (H - hs) // 2
        x0 = (W - ws) // 2
        ya, yb = max(0, y0), min(H, y0 + hs); xa, xb = max(0, x0), min(W, x0 + ws)
        out[:, ya:yb, xa:xb] = fgz[:, ya - y0:yb - y0, xa - x0:xb - x0]
        return fr * (1 - k) + out * k
