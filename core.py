# Estudio de edición — núcleo común: constantes, utilidades GPU, cámara con cara anclada, audio y codificación.
# Todo corre en la GPU: NVDEC (lectura) -> PyTorch CUDA (composición) -> NVENC (salida). En Mac: VideoToolbox + MPS (ver plataforma.py).
import os, sys, math, wave, subprocess, time
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
import numpy as np, cv2, torch, torch.nn.functional as F
from scipy import signal
from scipy.ndimage import gaussian_filter1d

STUDIO = os.path.dirname(os.path.abspath(__file__))
LIL = os.path.dirname(STUDIO)
sys.path.insert(0, os.path.join(STUDIO, "lib"))                   # módulos gráficos aprobados (gfx5…gfx18), dentro del estudio
sys.path.insert(0, STUDIO)
import plataforma as PL
dev, DT = PL.DEVICE, PL.DT
W, H, FPS, SR = 1080, 1920, 30, 48000
SPF = SR // FPS
SAFE = dict(top=270, bottom=1440, left=60, right=890)       # zona segura de Reels / TikTok / Shorts (contenido)
CX = 540

ease = lambda x: (lambda v: v * v * (3 - 2 * v))(min(1.0, max(0.0, x)))
easeo = lambda x: 1 - (1 - min(1.0, max(0.0, x))) ** 3
easeb = lambda x: (lambda v: 1 + 2.70158 * (v - 1) ** 3 + 1.70158 * (v - 1) ** 2)(min(1.0, max(0.0, x)))
clamp01 = lambda x: min(1.0, max(0.0, x))


# ------------------------------------------------------------------ GPU
def T(a): return torch.from_numpy(np.array(a)).to(dev)
def spr_t(a): return T(a).permute(2, 0, 1).to(DT) / 255


def blend(fr, spr, x, y, alpha=1.0):
    _, h, w = spr.shape
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(fr.shape[2], x + w), min(fr.shape[1], y + h)
    if x1 <= x0 or y1 <= y0 or alpha <= 0.003: return
    s = spr[:, y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[3:4] * alpha
    fr[:, y0:y1, x0:x1] = fr[:, y0:y1, x0:x1] * (1 - a) + s[:3] * a


def scaled(spr, sc):
    if abs(sc - 1) < 1e-3: return spr
    return F.interpolate(spr[None].float(), scale_factor=sc, mode="bilinear", align_corners=False, recompute_scale_factor=False, antialias=sc < 1)[0].to(DT)


def wipe_gpu(spr, p, mode):
    _, h, w = spr.shape
    ys = torch.arange(h, device=dev, dtype=torch.float32)
    jag = torch.sin(ys * 0.9) * 9 + torch.sin(ys * 0.23 + 1.0) * 16
    edge = -50 + (w + 100) * p
    xs = torch.arange(w, device=dev, dtype=torch.float32)[None, :]
    vis = (xs < (edge + jag)[:, None]) if mode == "in" else (xs >= (edge + jag)[:, None])
    o = spr.clone(); o[3:4] = o[3:4] * vis[None].to(DT)
    return o


def gblur_h(x, k):
    if k <= 1: return x
    return F.avg_pool2d(F.pad(x[None], (k // 2, k // 2, 0, 0), mode="replicate"), (1, k), stride=1)[0]


_kc = {}
def gblur(x, sigma):
    f = max(1, int(sigma / 3))
    xs = F.interpolate(x, scale_factor=1 / f, mode="area") if f > 1 else x
    s = sigma / f; r = int(3 * s) + 1
    if (s, r) not in _kc:
        k = torch.exp(-0.5 * (torch.arange(-r, r + 1, device=dev, dtype=torch.float32) / s) ** 2); _kc[(s, r)] = (k / k.sum()).to(DT)
    k = _kc[(s, r)]; C = xs.shape[1]
    xs = F.conv2d(F.pad(xs, (r, r, 0, 0), mode="replicate"), k.view(1, 1, 1, -1).repeat(C, 1, 1, 1), groups=C)
    xs = F.conv2d(F.pad(xs, (0, 0, r, r), mode="replicate"), k.view(1, 1, -1, 1).repeat(C, 1, 1, 1), groups=C)
    return F.interpolate(xs, size=x.shape[-2:], mode="bilinear", align_corners=False) if f > 1 else xs


yy_ = torch.arange(H, device=dev, dtype=torch.float32)[:, None]
xx_ = torch.arange(W, device=dev, dtype=torch.float32)[None, :]
sm = lambda a, b, v: ((v - a) / (b - a)).clamp(0, 1).pow(2) * (3 - 2 * ((v - a) / (b - a)).clamp(0, 1))


def tcolor(rgb): return torch.tensor(rgb, device=dev).view(3, 1, 1).to(DT) / 255


def make_vignette(strength=0.40):
    rr2 = ((xx_ - W / 2) / (W * 0.82)) ** 2 + ((yy_ - H * 0.40) / (H * 0.62)) ** 2
    return (1 - strength * (rr2 - 0.30).clamp(0, 1).pow(1.4))[None].to(DT)


def grade_color(x, contrast=1.07, sat=1.10):
    y = (x - 0.5) * contrast + 0.5
    g = y.mean(0, keepdim=True)
    y = g + (y - g) * sat
    lum = g.clamp(0, 1)
    y = torch.cat([y[0:1] + 0.014 * lum.pow(2), y[1:2], y[2:3] + 0.014 * (1 - lum).pow(2)], 0)
    return y.clamp(0, 1)


def to_bw(x, n, contrast=1.20):
    g = (0.299 * x[0:1] + 0.587 * x[1:2] + 0.114 * x[2:3])
    g = ((g - 0.5) * contrast + 0.5 - 0.02) * (1 + 0.035 * math.sin(n * 2.7))
    return g.clamp(0, 1).expand(3, -1, -1)


def shake(n, amp):
    return amp * (math.sin(n / 3.1) + 0.6 * math.sin(n / 1.7 + 1.3)), amp * 0.7 * (math.sin(n / 2.3 + 0.5) + 0.5 * math.sin(n / 1.3))


def whip_filter(out, k, off):
    """barrido: desenfoque horizontal + separación RGB (+ destello en el cambio)"""
    if k > 1:
        out = gblur_h(out, k)
        dxs = int(round(k / 8))
        if dxs > 0: out = torch.stack([torch.roll(out[0], dxs, 1), out[1], torch.roll(out[2], -dxs, 1)])
        if off == 0: out = out * 0.82 + 0.18
    return out


WHIP_K = {-3: .25, -2: .55, -1: .90, 0: 1.0, 1: .70, 2: .35}


def whip_k(n, whips):
    for c in whips:
        s = WHIP_K.get(n - c)
        if s: return 1 + 2 * int(round(s * 48)), n - c
    return 0, None


# ------------------------------------------------------------------ cámara: cara anclada en el punto (AX, AY)
ZOOM_FIJO = float(os.environ.get("STUDIO_ZOOM_FIJO", "1.06"))    # acercamiento fijo a la cara (la grabación no tiene más resolución: más zoom = más
                                                                  # blando). 0 = el zoom animado de cada estilo, como antes
CAMARA = os.environ.get("STUDIO_CAMARA", "fija")                 # fija = como un camarógrafo con trípode (pedido del usuario 2026-10-18:
                                                                  # "tiemblan mucho; solo los movimientos necesarios") · sigue = como antes


def temblor_fuente(work, cache=None):
    """temblor de la grabación (cámara en mano): desplazamiento de la imagen cuadro a cuadro (correlación de fase sobre el video de
    trabajo a 270×480), menos su parte lenta (los paneos de quien filma). -> (N, 2) px en el video de trabajo. Se guarda en cache"""
    if cache and os.path.exists(cache): return np.load(cache)
    aw, ah = 270, 480
    p = subprocess.Popen(["ffmpeg", "-v", "error", *PL.HWDEC, "-i", work, "-vf", f"scale={aw}:{ah}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         stdout=subprocess.PIPE)
    win = cv2.createHanningWindow((aw, int(ah * 0.62)), cv2.CV_32F); prev, d = None, [(0.0, 0.0)]
    while True:
        b = p.stdout.read(aw * ah)
        if len(b) < aw * ah: break
        g = np.frombuffer(b, np.uint8).reshape(ah, aw)[:int(ah * 0.62)].astype(np.float32)   # sin la franja de abajo (micrófonos, zócalos)
        if prev is not None:
            (dx, dy), r = cv2.phaseCorrelate(prev, g, win)
            d.append((dx, dy) if r > 0.08 and abs(dx) < 20 and abs(dy) < 20 else (0.0, 0.0))
        prev = g
    p.wait()
    S = np.cumsum(np.array(d, np.float64), 0) * (W / aw)                   # posición acumulada de la imagen (px del video de trabajo)
    J = S - gaussian_filter1d(S, 12, axis=0)                                # solo el temblor (lo lento son paneos de quien filma)
    J = np.clip(J, -60, 60).astype(np.float32)
    if cache:
        try: np.save(cache, J)
        except OSError: pass
    return J


def camino_fijo(fx, fy, zona_x, zona_y, lead=45, trans=24):
    """encuadre de trípode: el centro queda QUIETO mientras la cara está dentro de una zona; si sale, un paneo suave (trans cuadros,
    con aceleración y frenado) a la nueva posición (mediana de lo que viene). Nada de seguir cada movimiento de la cabeza"""
    n = len(fx); cx = np.zeros(n, np.float32); cy = np.zeros(n, np.float32)
    med = lambda v, i: float(np.median(v[i:min(n, i + lead)]))
    ax, ay = med(fx, 0), med(fy, 0); i = 0
    while i < n:
        if abs(fx[i] - ax) > zona_x or abs(fy[i] - ay) > zona_y:
            nx, ny = med(fx, i), med(fy, i)
            for k in range(trans):
                if i + k >= n: break
                u = (k + 1) / trans; u = u * u * (3 - 2 * u)
                cx[i + k] = ax + (nx - ax) * u; cy[i + k] = ay + (ny - ay) * u
            ax, ay = nx, ny; i += trans; continue
        cx[i], cy[i] = ax, ay; i += 1
    return cx, cy


class Camera:
    def __init__(self, face_path=None, smooth=24):
        self.zoom_mul = 1.0
        raw = np.load(face_path or os.path.join(LIL, "edicion", "face.npy")).astype(np.float32).copy()
        self.FACE = raw.copy()
        for k in range(3): self.FACE[:, k] = gaussian_filter1d(self.FACE[:, k], smooth)
        self.J = None; self.caminos = {}
        if CAMARA == "fija" and face_path:
            d = os.path.dirname(face_path); work = os.path.join(d, "work.mp4")
            try:
                if os.path.exists(work):
                    J = temblor_fuente(work, os.path.join(d, "temblor.npy"))
                    m = min(len(J), len(raw)); self.J = np.zeros((len(raw), 2), np.float32); self.J[:m] = J[:m]
            except Exception: self.J = None
            jx = self.J[:, 0] if self.J is not None else 0.0; jy = self.J[:, 1] if self.J is not None else 0.0
            self.cara_quieta = (gaussian_filter1d(raw[:, 0] - jx, 6), gaussian_filter1d(raw[:, 1] - jy, 6))   # cara sin el temblor

    def _centro(self, f, z):
        if CAMARA != "fija" or not hasattr(self, "cara_quieta"):
            fx, fy, _ = self.FACE[min(f, len(self.FACE) - 1)]; return fx, fy
        k = round(z, 2)
        if k not in self.caminos:                                          # zona de tolerancia: 9 % del ancho y 6 % del alto de lo que se ve
            self.caminos[k] = camino_fijo(*self.cara_quieta, zona_x=0.09 * W / z, zona_y=0.06 * H / z)
        cx, cy = self.caminos[k]; f = min(f, len(cx) - 1)
        jx, jy = (self.J[f] if self.J is not None else (0.0, 0.0))
        return cx[f] + jx, cy[f] + jy                                        # el recorte acompaña el temblor -> la imagen queda quieta

    def theta(self, f, z, ax=540.0, ay=690.0, ext_x=0.0, ext_y=260.0):       # ext_x=0: nunca relleno espejado a los costados (QA visual MIRROR)
        if ZOOM_FIJO > 0: z = ZOOM_FIJO                                # zoom fijo sobre la cara: sin entrar y salir (pedido del usuario 2026-10-14)
        z = max(1.0, z * self.zoom_mul)
        fx, fy = self._centro(f, z)
        x0 = min(max(fx - ax / z, -ext_x / z), W - W / z + ext_x / z)
        y0 = min(max(fy - ay / z, -ext_y / z), H - H / z + ext_y / z)
        cw, ch = W / z, H / z
        return torch.tensor([[cw / W, 0, 2 * (x0 + cw / 2) / W - 1], [0, ch / H, 2 * (y0 + ch / 2) / H - 1]], dtype=torch.float32, device=dev).view(1, 2, 3)

    def face_size(self, f): return float(self.FACE[min(f, len(self.FACE) - 1)][2])


def warp_src(src_f, theta, ext_bg=None, dx=0.0, dy=0.0, fade_top=True, fade=(0.90, 0.14)):
    """muestrea la fuente: en X el borde se extiende por reflejo; en Y (arriba) se funde al color de fondo"""
    th = theta.clone()
    th[0, 0, 2] += theta[0, 0, 0] * 2 * dx / W
    th[0, 1, 2] += theta[0, 1, 1] * 2 * dy / H
    grid = F.affine_grid(th, (1, 3, H, W), align_corners=False)
    gx, gy = grid[0, ..., 0], grid[0, ..., 1]
    u = torch.remainder(gx + 1, 4.0); u = torch.where(u > 2, 4 - u, u)
    g2 = torch.stack([u - 1, gy], -1)[None]
    out = F.grid_sample(src_f, g2, mode="bicubic", padding_mode="border", align_corners=False).clamp(0, 1).to(DT)[0]   # bicúbico: con zoom conserva más detalle que bilineal
    if not fade_top or ext_bg is None: return out
    ay = ((gy.abs() - fade[0]) / fade[1]).clamp(0, 1); m = (ay * ay * (3 - 2 * ay)).to(DT)[None]
    return out * (1 - m) + ext_bg * m


class Reader:
    """lee frames de un mp4 con NVDEC (rgb24). step > 1: entrega solo los cuadros 0, step, 2·step… (los controles que revisan
    1 de cada N cuadros no pagan la conversión y el traspaso de los demás, que era el 70 % de su tiempo)"""
    def __init__(self, path, k0=0, step=1):
        ss = ["-ss", f"{k0 / FPS:.4f}"] if k0 else []
        sel = ["-vf", f"select=not(mod(n\\,{step}))", "-fps_mode", "passthrough"] if step > 1 else []
        self.p = subprocess.Popen(["ffmpeg", "-v", "error"] + PL.HWDEC + ss + ["-i", path] + sel + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE, bufsize=W * H * 6)

    def get(self): return np.frombuffer(self.p.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)
    def close(self): self.p.kill()


def to_np(fr):
    """cuadro de la GPU -> imagen HxWx3 en la CPU. Se ordena en la GPU antes de bajarlo: bajar el tensor permutado
    (no contiguo) obligaba a reordenar 6 MB en la CPU y costaba ~30 ms por cuadro (la mitad del render)"""
    return (fr.clamp(0, 1) * 255).byte().permute(1, 2, 0).contiguous().cpu().numpy()


def guides(im):
    o = im.astype(np.float32); m = np.zeros((H, W), np.float32)
    m[:SAFE["top"], :] = 1; m[SAFE["bottom"]:, :] = 1; m[:, :SAFE["left"]] = 1; m[:, SAFE["right"]:] = 1
    o = o * (1 - 0.35 * m[..., None]) + np.array([255, 0, 40], np.float32) * 0.35 * m[..., None]
    o = o.astype(np.uint8); cv2.rectangle(o, (SAFE["left"], SAFE["top"]), (SAFE["right"], SAFE["bottom"]), (0, 200, 110), 3)
    return o


# ------------------------------------------------------------------ audio
def read_wav(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a.reshape(-1, w.getnchannels())


def write_wav(path, st):
    w = wave.open(path, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()


def midi(m): return 440 * 2 ** ((m - 69) / 12)
def lpf(x, fc, o=4): return signal.sosfilt(signal.butter(o, fc, "low", fs=SR, output="sos"), x)
def hpf(x, fc, o=4): return signal.sosfilt(signal.butter(o, fc, "high", fs=SR, output="sos"), x)


def music_pulse(N, whips=(), bpm=100, chords=None, seed=31, hat=True):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm; bar = 4 * beat
    mus = np.zeros(N, np.float32)
    CHD = chords or [[52, 55, 59], [48, 52, 55], [55, 59, 62], [50, 54, 57]]
    for ci in range(int(N / SR / bar) + 2):
        s0 = int(ci * bar * SR)
        if s0 >= N: break
        e0 = min(N, s0 + int(bar * SR) + int(0.6 * SR))
        tt = np.arange(s0, e0) / SR
        env = np.minimum(1, (tt - s0 / SR) / 0.5) * np.minimum(1, (e0 / SR - tt) / 0.6)
        seg = np.zeros(len(tt), np.float32)
        for m in CHD[ci % 4]:
            for det in (-0.06, 0.06):
                f = midi(m + 12) * 2 ** (det / 12)
                seg += (2 * ((tt * f) % 1) - 1) * 0.035 + np.sin(2 * np.pi * f * tt) * 0.03
        mus[s0:e0] += lpf(seg, 1300) * env
    for k in range(int(N / SR / (beat / 2))):
        o = int(k * beat / 2 * SR); root = midi(CHD[(k // 8) % 4][0] - 12)
        bt = np.arange(int(0.30 * SR)) / SR
        bass = (np.sin(2 * np.pi * root * bt) + 0.35 * np.sin(2 * np.pi * 2 * root * bt)) * np.exp(-bt * 9) * 0.20
        if o + len(bass) < N: mus[o:o + len(bass)] += bass
    if hat:
        for k in range(int(N / SR / (beat / 4))):
            o = int(k * beat / 4 * SR)
            nz = hpf(rng.normal(0, 1, int(0.03 * SR)), 7000, 2) * np.exp(-np.arange(int(0.03 * SR)) / SR * 140) * (0.07 if k % 4 else 0.12)
            if o + len(nz) < N: mus[o:o + len(nz)] += nz.astype(np.float32)
    for c in whips:
        te = c / FPS; n0, n1 = int(max(0, te - 0.9) * SR), int(te * SR)
        if n1 > n0 + 100:
            mus[n0:n1] += hpf(rng.normal(0, 1, n1 - n0).astype(np.float32), 900, 2) * (np.linspace(0, 1, n1 - n0) ** 2.2) * 0.12
    mus /= np.sqrt(np.mean(mus ** 2)) + 1e-9
    sos = signal.butter(2, [500, 3200], "bandstop", fs=SR, output="sos")             # hueco en la banda de la voz
    return (0.4 * mus + 0.6 * signal.sosfilt(sos, mus)).astype(np.float32)


def make_duck(voice, floor=0.16):
    hop = SR // 100
    e = np.sqrt(np.convolve((voice.mean(1)) ** 2, np.ones(hop) / hop, "same"))[::hop]
    if not (e > 1e-4).any(): return np.ones(len(voice), np.float32)       # sin voz (montaje de evento sin que ella hable): música sin bajar
    thr = 0.08 * np.percentile(e[e > 1e-4], 90)
    act = (e > thr).astype(np.float32)
    act = np.maximum.reduce([np.roll(act, k) for k in range(0, 30)])
    act = np.maximum(act, np.maximum(np.roll(act, -6), np.roll(act, -12)))
    d = np.ones(len(act), np.float32); cur = floor if act[0] > 0.5 else 1.0
    for i, a in enumerate(act):
        tgt = floor if a > 0.5 else 1.0
        cur += (tgt - cur) * (0.45 if tgt < cur else 0.03)
        d[i] = cur
    return np.interp(np.arange(len(voice)) / SR, np.arange(len(d)) / 100.0, d).astype(np.float32)


SFX = os.path.join(STUDIO, "assets", "audio")
_sfx = {}
def sfx(name):
    if name not in _sfx: _sfx[name] = read_wav(os.path.join(SFX, f"sfx_{name}.wav"))
    return _sfx[name]


def mix_audio(voice, total_frames, whips, cues, out, music_db=-24.0, bpm=100, speech_mask=None, chords=None, seed=31):
    """voice: (N,2) ya alineada al video · cues: [(t_seg, nombre_sfx, vol)]"""
    N = total_frames * SPF
    v = np.zeros((N, 2), np.float32); v[:min(N, len(voice))] += voice[:N]
    mus = music_pulse(N, whips, bpm=bpm, chords=chords, seed=seed)
    m = mus * make_duck(v) * 10 ** (music_db / 20)
    m[:int(0.4 * SR)] *= np.linspace(0, 1, int(0.4 * SR)); m[-int(1.4 * SR):] *= np.linspace(1, 0, int(1.4 * SR)) ** 1.5
    mus_st = np.stack([m, np.concatenate([np.zeros(300), m[:-300]])], 1)
    mix = v + mus_st
    for t0, name, vol in cues:
        x = sfx(name); x = x if x.ndim == 2 else np.repeat(x[:, None], 2, 1)
        o = max(0, int(t0 * SR)); k = min(len(x), N - o)
        if k > 0: mix[o:o + k] += x[:k] * vol
    sp = speech_mask if speech_mask is not None else np.arange(N)
    sp = sp[sp < N]
    rv = 20 * np.log10(np.sqrt(np.mean(v[sp] ** 2)) + 1e-9); rm = 20 * np.log10(np.sqrt(np.mean(mus_st[sp] ** 2)) + 1e-9)
    info = dict(rms_voz=round(rv, 1), rms_musica=round(rm, 1), dif=round(rv - rm, 1), pico=round(20 * np.log10(np.abs(mix).max() + 1e-9), 2))
    write_wav(out, mix)
    return info


# ------------------------------------------------------------------ codificación (NVENC)
def start_encoder(out, audio, dur, cq=21, maxrate="18M", lufs=-14):
    return subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-i", audio, "-map", "0:v", "-map", "1:a",
                             *PL.venc(cq, maxrate, "36M", 60, 2), "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
                             "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=9", "-ar", "48000", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-shortest", "-t", f"{dur:.3f}", out],
                            stdin=subprocess.PIPE)


def make_lite(src, dst, kbps=None):
    """versión liviana para WhatsApp (720x1280, < 15 MB aunque dure 2 min)"""
    if kbps is None:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip() or 60)
        kbps = int(min(1650, 14.2e6 * 8 / dur / 1000 - 140))
    r = PL.run_ffmpeg(["ffmpeg", "-v", "error", "-y", *PL.HWDEC, "-i", src, "-vf", "scale=720:1280:flags=lanczos", *PL.venc_bitrate(kbps), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", dst])
    if r.returncode: raise RuntimeError(r.stderr[-500:])
