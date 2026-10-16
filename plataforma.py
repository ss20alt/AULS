# Estudio de edición — CAPA DE PLATAFORMA: el mismo estudio corre en Windows con NVIDIA (CUDA/NVDEC/NVENC), en Mac con Apple Silicon
# (MPS/VideoToolbox) o, como último recurso, solo con el procesador. Todo lo que depende de la máquina vive acá.
#   STUDIO_DEVICE=cuda|mps|cpu   fuerza un dispositivo (para probar el camino de Mac en una PC sin usar la NVIDIA: STUDIO_DEVICE=cpu)
#   python plataforma.py         informe de la máquina (dispositivo, codificadores de ffmpeg, fuentes)
import os, sys, platform, subprocess, shutil

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")       # en Mac, las pocas operaciones que MPS no tiene caen al procesador
STUDIO = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(STUDIO, "lib")
ASSETS = os.path.join(STUDIO, "assets")
IS_MAC = sys.platform == "darwin"
IS_WIN = os.name == "nt"


def _pick_device():
    want = os.environ.get("STUDIO_DEVICE")
    import torch
    if want: return want
    if torch.cuda.is_available(): return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available(): return "mps"
    return "cpu"


DEVICE = _pick_device()
import torch
DT = torch.half if DEVICE == "cuda" else torch.float32          # media precisión solo en NVIDIA (en MPS/CPU, float32: estable y sin sorpresas)


def model_to(m):
    """modelos de voz (wav2vec2, WavLM): media precisión en NVIDIA, float32 en el resto"""
    m = m.to(DEVICE)
    return m.half() if DEVICE == "cuda" else m.float()


def inputs_to(x):
    x = x.to(DEVICE)
    return x.half() if DEVICE == "cuda" and x.is_floating_point() else x


# ------------------------------------------------------------------ ffmpeg: lectura y escritura de video
def _ffmpeg_has(kind, name):
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", f"-{kind}"], capture_output=True, text=True).stdout
        return f" {name} " in out
    except Exception:
        return False


def _encoder():
    want = os.environ.get("STUDIO_ENCODER")
    if want: return want
    if DEVICE == "cuda" and _ffmpeg_has("encoders", "h264_nvenc"): return "nvenc"
    if IS_MAC and _ffmpeg_has("encoders", "h264_videotoolbox"): return "videotoolbox"
    return "x264"


ENCODER = _encoder()
HWDEC = {"cuda": ["-hwaccel", "cuda"], "mps": ["-hwaccel", "videotoolbox"]}.get(DEVICE, []) if ENCODER != "x264" or DEVICE == "cuda" else []


def venc(cq=18, maxrate="9M", bufsize="28M", gop=60, bframes=2, tune_hq=True, rc=True, profile=True):
    """argumentos de codificación H.264 equivalentes en cada máquina (calidad pareja: cq de NVENC ≈ crf de x264)"""
    if ENCODER == "nvenc":
        a = ["-c:v", "h264_nvenc", "-preset", "p5"] + (["-tune", "hq"] if tune_hq else []) + (["-rc", "vbr"] if rc else []) +             ["-cq", str(cq), "-b:v", "0", "-maxrate", maxrate, "-bufsize", bufsize]
        if gop: a += ["-g", str(gop), "-bf", str(bframes)]
        return a + (["-profile:v", "high"] if profile else [])
    if ENCODER == "videotoolbox":                                # VideoToolbox: por tasa de bits (el modo de calidad constante no está en todas las versiones)
        mr = maxrate
        return ["-c:v", "h264_videotoolbox", "-b:v", mr, "-maxrate", mr, "-bufsize", bufsize, "-profile:v", "high", "-allow_sw", "1"] + (["-g", str(gop)] if gop else [])
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(cq), "-maxrate", maxrate, "-bufsize", bufsize, "-profile:v", "high"] + \
           (["-g", str(gop), "-bf", str(bframes)] if gop else [])


def venc_bitrate(kbps):
    """codificación por tasa de bits (versión liviana)"""
    if ENCODER == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.15)}k", "-bufsize", f"{kbps * 2}k", "-profile:v", "high"]
    if ENCODER == "videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.15)}k", "-bufsize", f"{kbps * 2}k", "-profile:v", "high", "-allow_sw", "1"]
    return ["-c:v", "libx264", "-preset", "medium", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.15)}k", "-bufsize", f"{kbps * 2}k", "-profile:v", "high"]


def run_ffmpeg(cmd, **kw):
    """ejecuta ffmpeg; si falla con decodificación por hardware (algún video raro en VideoToolbox), reintenta por procesador"""
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode and HWDEC:
        for i in range(len(cmd) - len(HWDEC) + 1):
            if cmd[i:i + len(HWDEC)] == HWDEC:
                r = subprocess.run(cmd[:i] + cmd[i + len(HWDEC):], capture_output=True, text=True, **kw); break
    return r


# ------------------------------------------------------------------ whisper (faster-whisper)
def whisper_model(name="large-v3"):
    """large-v3 en la placa NVIDIA (int8_float16) o en el procesador (int8; en Mac usa Accelerate)"""
    if DEVICE == "cuda" and IS_WIN:                              # Windows: las DLL de cuBLAS/cuDNN vienen con torch
        lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        try: os.add_dll_directory(lib)
        except Exception: pass
        os.environ["PATH"] = lib + os.pathsep + os.environ.get("PATH", "")
    from faster_whisper import WhisperModel
    if DEVICE == "cuda": return WhisperModel(name, device="cuda", compute_type="int8_float16")
    return WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(1, (os.cpu_count() or 4)))


# ------------------------------------------------------------------ fuentes del sistema
_SUP = "/System/Library/Fonts/Supplemental/"
FONTS = {
    "georgia": ["C:/Windows/Fonts/georgia.ttf", _SUP + "Georgia.ttf", "/Library/Fonts/Georgia.ttf"],
    "georgiab": ["C:/Windows/Fonts/georgiab.ttf", _SUP + "Georgia Bold.ttf", "/Library/Fonts/Georgia Bold.ttf"],
    "georgiai": ["C:/Windows/Fonts/georgiai.ttf", _SUP + "Georgia Italic.ttf", "/Library/Fonts/Georgia Italic.ttf"],
    "georgiaz": ["C:/Windows/Fonts/georgiaz.ttf", _SUP + "Georgia Bold Italic.ttf", "/Library/Fonts/Georgia Bold Italic.ttf"],
    "impact": ["C:/Windows/Fonts/impact.ttf", _SUP + "Impact.ttf"],
    "bahnschrift": ["C:/Windows/Fonts/bahnschrift.ttf", _SUP + "DIN Alternate Bold.ttf", _SUP + "DIN Condensed Bold.ttf"],
    "seguisym": ["C:/Windows/Fonts/seguisym.ttf", "/System/Library/Fonts/Apple Symbols.ttf"],
}
FALLBACK = os.path.join(ASSETS, "fonts", "Montserrat-Bold.ttf")


def sysfont(name):
    """ruta de una fuente del sistema por su nombre de Windows; si no existe, la equivalente de Mac; si tampoco, Montserrat"""
    for p in FONTS.get(name, []) + ([f"C:/Windows/Fonts/{name}.ttf"] if name not in FONTS else []):
        if os.path.exists(p): return p
    return FALLBACK


def has_font(name):
    return any(os.path.exists(p) for p in FONTS.get(name, []))


def report():
    import json
    r = dict(sistema=f"{platform.system()} {platform.machine()}", python=sys.version.split()[0], torch=torch.__version__, dispositivo=DEVICE,
             precision=str(DT).replace("torch.", ""), codificador=ENCODER, decodificacion=" ".join(HWDEC) or "procesador",
             ffmpeg=shutil.which("ffmpeg") or "NO ENCONTRADO", zscale=_ffmpeg_has("filters", "zscale"),
             fuentes={k: os.path.basename(sysfont(k)) for k in FONTS})
    return r


if __name__ == "__main__":
    import json
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report(), ensure_ascii=False, indent=1))
