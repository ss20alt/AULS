# Capa de CIFRAS EN PANTALLA (pedido del usuario 2026-10-16: "cifras sincronizadas con lo que ella dice, SOLO en algunos casos").
# Cuando ella dice una estadística de peso ("258 víctimas de feminicidio", "37.825 denuncias…"), aparece una tarjeta en el carril
# de los micrófonos (encima del subtítulo, sin tocarle la cara) y el número CUENTA hasta la cifra mientras lo dice. Qué cifras:
# cifras.py (estadísticas con lo que cuentan; fechas, horas, edades, leyes y números chicos no) y pocas: las más fuertes,
# separadas ≥ 12 s, ≤ 2 por minuto. Sin cifras de peso en el guion -> ninguna tarjeta.
#   cfg["cifras"] = "auto" (por defecto) | "no" | "mas" (umbral más bajo) | [ {trigger: "258", value: 258, label: "...", icon: "lazo"} ]
#   (también sources/<fuente>/cifras.json con esa misma lista: manda sobre lo automático)
import json, os
from styles.base import *
import cifras as CF
import plan as P

CW, CH = 820, 150                        # tarjeta: dentro de la zona segura (x 60–890 → centrada en 540 cabe con 820)


class Cifras:
    def __init__(self, style, y_bottom=1162, accent=RED, ink=NAVY):
        self.S, self.c = style, style.c
        self.y_bottom, self.accent, self.ink = y_bottom, accent, ink
        self.items, self.cache = [], {}
        mode = self.c.cfg.get("cifras", "auto")
        if mode == "no": return
        manual = mode if isinstance(mode, list) else None
        mj = os.path.join(P.SRC.get("dir", ""), "cifras.json")
        if manual is None and os.path.exists(mj): manual = json.load(open(mj, encoding="utf-8"))
        W_ = self.c.WORDS
        hers = lambda sc: style.scene_spk.get(sc, "L") != "R"                          # solo lo que dice ella (no la pregunta)
        if manual is not None:
            for sp in manual:
                trig = P.norm(str(sp.get("trigger", sp.get("value", ""))))
                w = next((w for w in W_ if w.get("sc") is not None and hers(w["sc"]) and P.norm(w["t"]) == trig), None)
                if w is None: print("[cifras] sin momento para", sp.get("trigger")); continue
                self.items.append(dict(value=float(sp["value"]), pct=sp.get("pct", False), label=sp["label"], icon=sp.get("icon", "documento"),
                                       t0=w["s"], tn=w["e"]))
        else:
            cands, vistas = [], set()
            for cd in CF.candidates(W_):
                if W_[cd["i0"]].get("sc") is None or not hers(W_[cd["i0"]]["sc"]): continue
                if len({W_[k].get("sc") for k in range(cd["i0"], min(cd["i1"], len(W_)))}) != 1: continue   # número y etiqueta en la misma toma
                if (cd["value"], cd["label"]) in vistas: continue         # la misma cifra repetida (gancho + contexto): una sola tarjeta
                vistas.add((cd["value"], cd["label"])); cands.append(cd)
            dur = self.c.END0 / FPS
            ms = 3.0 if mode == "mas" else 3.5
            sel = CF.pick(cands, lambda cd: cd["s"], dur=dur, min_score=ms, per_min=3.0 if mode == "mas" else 2.0)
            for cd in sel:
                self.items.append(dict(value=cd["value"], pct=cd["pct"], label=cd["label"], icon=cd["icon"], t0=W_[cd["i0"]]["s"],
                                       tn=W_[cd["i0"]]["e"], score=cd["score"]))
        self.items.sort(key=lambda s: s["t0"])
        ends = sorted(v["o1"] for v in self.c.SC.values()) + [self.c.END0 / FPS]
        for s in self.items:
            s["count_s"] = float(min(1.3, max(0.7, s["tn"] - s["t0"] + 0.45)))                # cuenta mientras lo dice
            nxt = next((e for e in ends if e > s["t0"] + 0.5), ends[-1])
            s["t1"] = min(s["t0"] + 4.2, nxt - 0.15)                                      # termina con su idea
        for a, b in zip(self.items, self.items[1:]): a["t1"] = min(a["t1"], b["t0"] - 0.2)
        self.items = [s for s in self.items if s["t1"] - s["t0"] >= 1.6]
        print("[cifras]", [(CF.fmt(s["value"], s["pct"]), s["label"], round(s["t0"], 1)) for s in self.items] or "ninguna (el guion no tiene cifras de peso)")
        try: json.dump([{k: v for k, v in s.items()} for s in self.items], open(os.path.join(self.c.dir, "cifras.json"), "w", encoding="utf-8"),
                       ensure_ascii=False, indent=1)
        except Exception: pass

    # ---------------------------------------------------------------- tarjeta
    def sprite(self, s, prog):
        key = (id(s), round(prog, 3))
        if key in self.cache: return self.cache[key]
        from styles.datos import icon
        im = rgba(CW, CH); d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, CW - 1, CH - 1), radius=22, fill=(255, 255, 255, 246))
        d.rounded_rectangle((0, 0, 132, CH - 1), radius=22, fill=tuple(self.accent) + (255,)); d.rectangle((110, 0, 132, CH - 1), fill=tuple(self.accent) + (255,))
        im.alpha_composite(Image.fromarray(icon(s.get("icon", "documento"), 84)), (24, (CH - 84) // 2))
        final = CF.fmt(s["value"], s["pct"])
        num = final if prog >= 1 else CF.fmt(s["value"] * easeo(prog), s["pct"])
        fn = font("Black", 88)
        while fn.getlength(final) > 330 and fn.size > 54: fn = font("Black", fn.size - 4)
        x = 160
        d.text((x, CH / 2 + 4), num, font=fn, fill=tuple(self.ink) + (255,), anchor="lm")
        xl = x + fn.getlength(final) + 22
        lab = s["label"].upper()
        fl = font("ExtraBold", 36)
        lines = self.wrap(lab, fl, CW - xl - 26)
        while len(lines) > 2 and fl.size > 24: fl = font("ExtraBold", fl.size - 2); lines = self.wrap(lab, fl, CW - xl - 26)
        lines = lines[:2]; lh = fl.size * 1.12
        for i, ln in enumerate(lines):
            d.text((xl, CH / 2 + (i - (len(lines) - 1) / 2) * lh), ln, font=fl, fill=(40, 46, 66, 255), anchor="lm")
        out = spr_t(np_(shadowed(im, blur=14, dy=7, alpha=0.5, pad=18)))
        if len(self.cache) > 400: self.cache.clear()
        self.cache[key] = out
        return out

    @staticmethod
    def wrap(text, f, maxw):
        lines, cur = [], ""
        for w in text.split():
            t = (cur + " " + w).strip()
            if f.getlength(t) <= maxw or not cur: cur = t
            else: lines.append(cur); cur = w
        return lines + [cur]

    def active(self, t):
        return next((s for s in self.items if s["t0"] - 0.05 <= t < s["t1"] + 0.35), None)

    def draw(self, fr, t):
        s = self.active(t)
        if s is None: return
        a = t - s["t0"]; dur = s["t1"] - s["t0"]
        p_in = easeo(a / 0.40); p_out = ease((a - dur) / 0.35) if a > dur else 0.0
        vis = min(1.0, a / 0.12) * (1 - p_out)
        prog = clamp01((a - 0.10) / s["count_s"])
        spr = self.sprite(s, prog)
        y = self.y_bottom - spr.shape[1] + 18 + 70 * (1 - p_in) + 40 * p_out
        blend(fr, spr, CX - spr.shape[2] / 2, y, vis)

    def cues(self):
        out = []
        for s in self.items:
            out.append((s["t0"] - 0.03, "swish", 0.14))
            out.append((s["t0"] + 0.10 + s["count_s"], "click", 0.12))
        return out
