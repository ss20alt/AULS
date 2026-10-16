# Estilo 6 — LLAMADA CON LETRA (layout aprobado v16/v17): foto fija de Lilian arriba, panel de llamada con la letra que se ilumina palabra a palabra
# (estilo Spotify) y, abajo, tomas del edificio / fotos del Banco Central con el escudo centrado. Su voz va por encima.
import os, sys, subprocess
from styles.common import *
import gfx16 as G16
import gfx18 as G18
import plan as P

TOP_H = 1218
BR_Y, BR_H = 1218, 702
CLIPS = os.path.join(STUDIO, "assets", "material", "bcp", "clips")      # material del tema BCP (solo fuentes con material="bcp")
# secuencia por defecto de tomas inferiores: (tipo, rect inicial, rect final, grade)
KINDS = [("v1", None, None, "warm"), ("p1", (450, 20, 880), (450, 20, 820), "warm"), ("logo", None, None, "warm"), ("v2", None, None, "warm"),
         ("v3", None, None, "warm"), ("p2", (500, 0, 560), (480, 20, 520), "warm"), ("v4", None, None, "gloom"), ("p1", (440, 200, 520), (430, 170, 470), "warm"),
         ("v5", None, None, "warm"), ("v6", None, None, "warm"), ("p1", (610, 140, 600), (590, 130, 540), "warm"), ("v7", None, None, "warm"),
         ("p2", (300, 20, 560), (330, 40, 520), "warm"), ("v8", None, None, "warm"), ("v9", None, None, "warm"), ("logo", None, None, "warm")]


class ClipPlayer:
    def __init__(self): self.p = {}

    def get(self, key, name, k):
        if key not in self.p or self.p[key][1] != k - 1:
            if key in self.p: self.p[key][0].kill()
            proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", os.path.join(CLIPS, name.upper() + ".mp4"), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, bufsize=W * BR_H * 6)
            self.p[key] = [proc, -1, None]
            for _ in range(k + 1): self._read(key)
        else: self._read(key)
        return self.p[key][2]

    def _read(self, key):
        b = self.p[key][0].stdout.read(W * BR_H * 3)
        if len(b) == W * BR_H * 3: self.p[key][2] = np.frombuffer(b, np.uint8).reshape(BR_H, W, 3)
        self.p[key][1] += 1

    def close(self):
        for v in self.p.values(): v[0].kill()


class Style:
    uses_video = False

    def __init__(self, ctx):
        self.c = ctx

    def setup(self):
        c = self.c; cfg = c.cfg
        self.end = Endcard()
        self.cp = ClipPlayer()
        # --- foto fija arriba
        still_t = cfg.get("still_t", 244.0)
        sp = c.J("still.png")
        if not os.path.exists(sp):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{still_t}", "-i", P.SRC["video"], "-frames:v", "1", sp], check=True)
        img = cv2.cvtColor(cv2.imread(sp), cv2.COLOR_BGR2RGB)
        src = (T(img).permute(2, 0, 1).float() / 255)[None]
        f = int(round(still_t * FPS))
        z, ax, ay = cfg.get("still_zoom", 1.32), 500.0, 455.0
        th = c.cam.theta(f, z, ax, ay, ext_y=0.0)
        top = warp_src(src, th, ext_bg=None, fade_top=False)[:, :TOP_H]
        self.top = grade_color(top, 1.08, 1.10) * make_vignette(0.30)[:, :TOP_H]
        # --- panel de llamada
        words = sorted(c.WORDS, key=lambda w: w["s"])
        self.lines = G16.build_lines([dict(t=w["t"], s=w["s"], e=w["e"]) for w in words])
        self.PH, self.PW = G16.PH, G16.PW
        pbg = G16.panel_bg()
        self.pbg = T(pbg[..., :3]).permute(2, 0, 1).to(DT) / 255; self.pmask = T(pbg[..., 3]).to(DT)[None] / 255
        psh, self.pshpad = G16.panel_shadow(); self.pshadow = spr_t(psh)
        import brand as B; self.hdr = spr_t(B.call_header(G16.PW, G16.HDR_H, G16.TXT_X, G16.NAVY)); self.handset = spr_t(G16.handset_icon(52))
        self.tcodes = [spr_t(a) for a in G16.timecodes(int(c.TOTAL / FPS) + 2)]
        self.navyt = tcolor(G16.NAVY)
        vr = np.sqrt(np.convolve(c.voice.mean(1) ** 2, np.ones(SPF) / SPF, "same"))[::SPF]
        self.env = np.clip(vr / (np.percentile(vr[vr > 1e-4], 90) + 1e-9), 0, 1.2)
        self.ls = {}
        self.setup_broll(sorted({ln["t0"] for ln in self.lines}))
        # chips de palabras clave
        self.chips = []
        for sid, tok, nth, text, dur in cfg.get("chips", []):
            sc = c.scene_of(sid)[0]; s = c.w_(sc, tok, nth) - 0.08
            sp_, pad = G13.chip_sprite(text); self.chips.append(dict(s=s, e=s + dur, spr=spr_t(sp_), pad=pad))
        import brand as B; self.wmark = spr_t(B.watermark())
        self.end0 = c.END0

    def setup_broll(self, starts):
        c = self.c; cfg = c.cfg
        # --- tomas inferiores
        self.photos = {}
        for nm, fl, kind in (("p1", "banco1.webp", "normal"), ("p2", "banco2.webp", "hazy")):
            up, (w, h) = G18.load_photo(fl, kind)
            self.photos[nm] = dict(t=T(up).permute(2, 0, 1).to(DT)[None] / 255, w=w, h=h)
        logo, bg = G18.logo_canvas()
        self.logo = T(logo).permute(2, 0, 1).to(DT)[None] / 255
        self.logo_bg = torch.tensor(bg, device=dev).view(3, 1, 1).to(DT) / 255
        self.xb = torch.arange(W, device=dev, dtype=torch.float32)[None, :]; self.yb = torch.arange(BR_H, device=dev, dtype=torch.float32)[:, None]
        rb2 = ((self.xb - W / 2) / (W * 0.80)) ** 2 + ((self.yb - BR_H * 0.30) / (BR_H * 0.75)) ** 2
        self.vig_br = (1 - 0.30 * (rb2 - 0.30).clamp(0, 1).pow(1.4))[None].to(DT)
        self.dist = torch.sqrt((self.xb - W / 2) ** 2 + (self.yb - BR_H / 2) ** 2)[None].to(DT)
        self.br_shade = (0.45 * sm(190.0, 320.0, self.yb) + 0.38 * (1 - sm(0.0, 30.0, self.yb))).expand(BR_H, W)[None].to(DT)
        self.br_shade_top = (0.38 * (1 - sm(0.0, 30.0, self.yb))).expand(BR_H, W)[None].to(DT)
        # plan de tomas: corte cada ≈3.4 s alineado al inicio de un subtítulo/línea
        self.shots = [(0.0,) + KINDS[0]]
        kinds = cfg.get("broll_kinds", KINDS); ki = 1; last = 0.0
        speech_end = c.END0 / FPS - 0.5
        for s in starts:
            if s - last >= 3.3 and s < speech_end - 2.0:
                kd = kinds[ki % len(kinds)]; ki += 1
                self.shots.append((s - 0.10,) + kd); last = s
        self.shot_f = [int(round(s[0] * FPS)) for s in self.shots] + [c.END0]

    # ---- tomas
    def shot_at(self, n):
        for i in range(len(self.shots)):
            if self.shot_f[i] <= n < self.shot_f[i + 1]: return i
        return len(self.shots) - 1

    def photo_frame(self, name, r0, r1, u):
        p = self.photos[name]
        cx = r0[0] + (r1[0] - r0[0]) * u; top = r0[1] + (r1[1] - r0[1]) * u; w = r0[2] + (r1[2] - r0[2]) * u
        h = w * BR_H / W
        cx = min(max(cx, w / 2), p["w"] - w / 2); top = min(max(top, 0), p["h"] - h)
        cy = top + h / 2
        th = torch.tensor([[w / p["w"], 0, 2 * cx / p["w"] - 1], [0, h / p["h"], 2 * cy / p["h"] - 1]], dtype=torch.float32, device=dev).view(1, 2, 3)
        grid = F.affine_grid(th, (1, 3, BR_H, W), align_corners=False)
        return F.grid_sample(p["t"].float(), grid, mode="bilinear", padding_mode="border", align_corners=False).to(DT)[0]

    def logo_frame(self, u, t):
        z = 1.0 + 0.08 * u
        lw, lh = self.logo.shape[3], self.logo.shape[2]
        sc = 520.0 / lw * z
        sx, sy = W / (lw * sc), BR_H / (lh * sc)
        th = torch.tensor([[sx, 0, 0], [0, sy, 0]], dtype=torch.float32, device=dev).view(1, 2, 3)
        grid = F.affine_grid(th, (1, 3, BR_H, W), align_corners=False)
        out = F.grid_sample(self.logo.float(), grid, mode="bilinear", padding_mode="border", align_corners=False).to(DT)[0]
        inside = ((grid[0, ..., 0].abs() <= 1) & (grid[0, ..., 1].abs() <= 1)).to(DT)[None]
        gl = torch.exp(-((((self.xb - W / 2) / 440) ** 2) + (((self.yb - BR_H / 2) / 300) ** 2)))[None].to(DT)
        img = (out * inside + self.logo_bg * (1 - inside)) * (1 + 0.20 * gl)
        for k in range(3):
            ph = (t * 0.45 + k / 3) % 1.0
            r = 300 * 0.82 + 300 * ph
            img = img + torch.exp(-((self.dist - r) / 2.6) ** 2) * (1 - ph) * 0.20
        return img.clamp(0, 1)

    def grade_br(self, x, mode):
        g = x.mean(0, keepdim=True)
        if mode == "gloom":
            y = g + (x - g) * 0.48
            y = y * torch.tensor([0.92, 0.97, 1.06], device=dev).view(3, 1, 1).to(DT) * 0.90
            y = (y - 0.5) * 1.10 + 0.5
        else:
            y = (x - 0.5) * 1.07 + 0.5
            y = g + (y - g) * 1.10
        return (y * self.vig_br).clamp(0, 1)

    def broll(self, n):
        i = self.shot_at(n); s = self.shots[i]
        k = n - self.shot_f[i]
        u = ease(k / max(1, self.shot_f[i + 1] - self.shot_f[i] - 1))
        kind = s[1]
        if kind == "logo": return self.logo_frame(u, n / FPS) * self.vig_br
        if kind.startswith("v"):
            rgb = self.cp.get(i, kind, min(k, 69))
            return self.grade_br((T(rgb).permute(2, 0, 1).to(DT) / 255), s[4])
        return self.grade_br(self.photo_frame(kind, s[2], s[3], u), s[4])

    # ---- panel de llamada
    def line_spr(self, i, k, mode):
        key = (i, k, mode)
        if key not in self.ls:
            sp, pad = G16.line_sprite(self.lines[i], k, mode); self.ls[key] = (spr_t(sp), pad)
        return self.ls[key]

    def lyrics_state(self, t):
        cur = 0
        for i, ln in enumerate(self.lines):
            if t >= ln["t0"] - 0.05: cur = i
        tc = self.lines[cur]["t0"] - 0.05
        return cur, (1.0 if cur == 0 else ease((t - tc) / 0.26))

    def draw_lyrics(self, fr, t, n):
        c = self.c
        pin = easeo((t - 0.12) / 0.50); pout = ease((t - (c.END0 / FPS - 0.30)) / 0.22)
        vis = pin * (1 - pout)
        if vis <= 0.003: return
        dy = int(round(120 * (1 - pin)))
        X0, Y0 = G16.PX0, G16.PANEL_Y0 + dy
        blend(fr, self.pshadow, X0 - self.pshpad, Y0 - self.pshpad, vis)
        reg = fr[:, Y0:Y0 + self.PH, X0:X0 + self.PW].clone()
        pan = self.pbg.clone()
        blend(pan, self.handset, G16.TXT_X, (G16.HDR_H - 52) / 2 + 2)
        blend(pan, self.hdr, 0, 0)
        tcs = self.tcodes[min(len(self.tcodes) - 1, int(t))]
        tx = G16.RIGHT - tcs.shape[2]
        blend(pan, tcs, tx, 21)
        e_ = float(self.env[min(len(self.env) - 1, n)])
        for i in range(5):                                                       # barras que laten con su voz
            hh = int(6 + 30 * e_ * (0.35 + 0.65 * abs(math.sin(t * (9.0 + 2.3 * i) + i * 1.7))))
            x1 = int(tx - 26 - (4 - i) * 14); y0 = 41 - hh // 2
            pan[:, y0:y0 + hh, x1:x1 + 8] = self.navyt * 0.88
        cur, e = self.lyrics_state(t)
        lw = pan[:, G16.LIN_Y0:G16.LIN_Y0 + G16.NROWS * G16.ROW_H, :]
        for i in range(max(0, cur - 4), cur + 1):
            r = 3 + (i - cur) + (1 - e)
            y = r * G16.ROW_H
            al = 1.0 if r >= 0 else max(0.0, 1 + r)
            if al <= 0.003: continue
            nsp = sum(1 for w in self.lines[i]["words"] if t >= w["s"] - 0.02)
            if i == cur:
                sp, pad = self.line_spr(i, nsp, "active"); fu, _ = self.line_spr(i, 0, "future")
                blend(lw, fu, G16.TXT_X - pad, y, al * (1 - e)); blend(lw, sp, G16.TXT_X - pad, y, al * e)
            elif i == cur - 1:
                sp, pad = self.line_spr(i, len(self.lines[i]["words"]) + 1, "active"); pa, _ = self.line_spr(i, 0, "past")
                blend(lw, sp, G16.TXT_X - pad, y, al * (1 - e)); blend(lw, pa, G16.TXT_X - pad, y, al * e)
            else:
                pa, pad = self.line_spr(i, 0, "past"); blend(lw, pa, G16.TXT_X - pad, y, al)
        fr[:, Y0:Y0 + self.PH, X0:X0 + self.PW] = reg * (1 - self.pmask * vis) + pan * (self.pmask * vis)

    def draw_chips(self, fr, t):
        for ch in self.chips:
            if not (ch["s"] <= t < ch["e"] + 0.30): continue
            w = ch["spr"].shape[2]
            if t < ch["e"]: p = easeb((t - ch["s"]) / 0.40); off = -(w + 40) * (1 - p); al = min(1.0, (t - ch["s"]) / 0.10)
            else: q = ease((t - ch["e"]) / 0.28); off = -(w + 40) * q; al = 1 - q
            blend(fr, ch["spr"], SAFE["left"] - ch["pad"] + off, 1380 - ch["pad"], al)

    def compose(self, n, it, rd):
        c = self.c; t = n / FPS
        if it["kind"] == "card": return self.end.frame((n - c.END0) / FPS)
        fr = torch.zeros(3, H, W, device=dev, dtype=DT)
        fr[:, :TOP_H] = self.top
        br = self.broll(n)
        for cf in self.shot_f[1:-1]:                                              # barrido de las tomas inferiores en cada cambio
            sw = {-1: 0.45, 0: 1.0, 1: 0.40}.get(n - cf)
            if sw: br = gblur_h(br, 1 + 2 * int(round(sw * 44)))
        sh = self.br_shade_top if self.shots[self.shot_at(n)][1] == "logo" else self.br_shade
        br = br * (1 - sh) + self.navyt * sh
        fr[:, BR_Y:] = br.clamp(0, 1)
        blend(fr, self.wmark, SAFE["right"] - self.wmark.shape[2], 276, ease((t - 0.3) / 0.4))
        self.draw_lyrics(fr, t, n)
        self.draw_chips(fr, t)
        return exit_to_white(fr, c.END0 - n)

    def whips(self): return []

    def cues(self):
        c = self.c; out = [(0.05, "chime", 0.30), (0.10, "click", 0.40)]
        for cf in self.shot_f[1:-1]: out.append((cf / FPS - 0.12, "swish", 0.30))
        for ch in self.chips: out.append((ch["s"], "click", 0.24))
        out.append((c.END0 / FPS - 0.12, "whoosh", 0.32)); out.append((c.END0 / FPS + 0.28, "chime", 0.32))
        return out
