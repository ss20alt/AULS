# Estudio de edición — análisis cuantitativo de los videos de referencia.
# Por video: cortes (ritmo), movimiento por zonas 3x3, zoom/paneo de cámara, color/contraste, tamaño y posición de la cara,
# loudness/silencios del audio y hoja de contacto. Salida: studio/analysis/<id>.json + <id>_sheet.png + REPORTE.md
import os, sys, json, subprocess, glob
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(os.path.dirname(HERE), "referencias")
OUT = os.path.join(HERE, "analysis"); os.makedirs(OUT, exist_ok=True)
FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def audio_stats(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true,silencedetect=n=-38dB:d=0.35", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    t = r.stderr
    if "Audio" not in t and "Stream #0:1" not in t: return None
    import re
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", t); LRA = re.findall(r"LRA:\s+(-?[\d.]+) LU", t); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", t)
    sil = re.findall(r"silence_duration: ([\d.]+)", t)
    return dict(lufs=float(I[-1]) if I else None, lra=float(LRA[-1]) if LRA else None, true_peak=float(TP[-1]) if TP else None,
                silence_total=round(sum(map(float, sil)), 2), silence_n=len(sil))


def _frames(path, small):
    """cuadros del video. Referencias: tamaño completo con OpenCV. QA de cada video (small): 270×480 desde ffmpeg con la placa;
    la reducción la hace ffmpeg en paralelo y el control final no decodifica el video dos veces a tamaño completo"""
    if not small:
        cap = cv2.VideoCapture(path)
        while True:
            ok, fr = cap.read()
            if not ok: break
            yield fr
        cap.release(); return
    if HERE not in sys.path: sys.path.insert(0, HERE)
    import plataforma as PL
    # tomar píxeles (neighbor) y convertir el color con BT.601, como hace OpenCV: brillo/saturación/contraste/cara quedan dentro de
    # décimas de lo que medía la pasada a tamaño completo (con 'area' y BT.709 el brillo subía ~2 y las franjas negras daban saturación)
    p = subprocess.Popen(["ffmpeg", "-v", "error", *PL.HWDEC, "-i", path, "-vf", "scale=270:480:flags=neighbor:in_color_matrix=bt601",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE, bufsize=270 * 480 * 3 * 8)
    nb = 270 * 480 * 3
    try:
        while True:
            b = p.stdout.read(nb)
            if len(b) < nb: break
            yield np.frombuffer(b, np.uint8).reshape(480, 270, 3)
    finally:
        p.kill(); p.wait()


def analyze(path, small=False):
    """small=True (QA de cada video): una sola pasada a 270×480 que además mide congelados y negros (res['freezes'], res['blacks'])"""
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); dur = N / fps
    cap.release()
    prev2 = None; frun = 0; freezes = []; blacks = []
    prev = None; prevg = None; hp = None
    cuts = []; zone = np.zeros((3, 3)); zn = 0
    zoom_s, pan_x, pan_y = [], [], []
    bright, sat, contrast = [], [], []
    faces = []
    thumbs = []; step_thumb = max(1, int(round(fps * 2.5)))
    diffs = []
    i = 0
    for fr in _frames(path, small):
        sm = cv2.resize(fr, (144, 256), interpolation=cv2.INTER_AREA)
        if small:                                                    # congelados y negros (antes: qa.freeze_and_black, otra pasada)
            g2 = cv2.cvtColor(cv2.resize(fr, (108, 192)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev2 is not None:
                if float(np.abs(g2 - prev2).mean()) < 0.12: frun += 1
                else:
                    if frun >= 18: freezes.append((round((i - frun) / fps, 2), round(frun / fps, 2)))
                    frun = 0
            if g2.mean() < 6: blacks.append(round(i / fps, 2))
            prev2 = g2
        g = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([sm], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3).ravel(); hist /= hist.sum()
        if hp is not None:
            d = 0.5 * np.abs(hist - hp).sum()                       # distancia de histograma (0..1)
            diffs.append(d)
            ad = np.abs(g.astype(np.float32) - prevg.astype(np.float32))
            if d > 0.28 and ad.mean() > 14: cuts.append(round(i / fps, 3))
            zone += np.array([[ad[r * 85:(r + 1) * 85, c * 48:(c + 1) * 48].mean() for c in range(3)] for r in range(3)]); zn += 1
            if i % 3 == 0:
                fl = cv2.calcOpticalFlowFarneback(prevg, g, None, 0.5, 2, 15, 2, 5, 1.1, 0)
                H_, W_ = g.shape
                yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32); xx -= W_ / 2; yy -= H_ / 2
                fx, fy = fl[..., 0].ravel(), fl[..., 1].ravel()
                A = np.stack([xx.ravel() ** 2 + yy.ravel() ** 2, np.ones_like(fx)], 1)
                zoom_s.append(float((xx.ravel() * fx + yy.ravel() * fy).sum() / (xx.ravel() ** 2 + yy.ravel() ** 2).sum()))
                pan_x.append(float(np.median(fx))); pan_y.append(float(np.median(fy)))
        hp, prevg = hist, g
        if i % 6 == 0:
            hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
            bright.append(float(g.mean())); sat.append(float(hsv[..., 1].mean())); contrast.append(float(g.std()))
        if i % 15 == 0:
            gg = cv2.cvtColor(cv2.resize(fr, (270, 480)), cv2.COLOR_BGR2GRAY)
            fc = FACE.detectMultiScale(gg, 1.15, 5, minSize=(40, 40))
            if len(fc):
                x, y, w, h = max(fc, key=lambda b: b[2] * b[3]); faces.append((x + w / 2, y + h / 2, h))
        if i % step_thumb == 0: thumbs.append(cv2.resize(fr, (162, 288), interpolation=cv2.INTER_AREA))
        i += 1
    if small and i == 0: return analyze(path, small=False)            # sin decodificación por hardware: el camino de siempre
    # cortes duros: colapsar los muy próximos
    cl = []
    for c in cuts:
        if not cl or c - cl[-1] > 0.25: cl.append(c)
    bounds = [0.0] + cl + [dur]
    shots = np.diff(bounds)
    zone = zone / max(1, zn)
    zs = np.array(zoom_s); px = np.array(pan_x); py = np.array(pan_y)
    fa = np.array(faces) if faces else np.zeros((0, 3))
    res = dict(file=os.path.basename(path), dur=round(dur, 2), fps=round(fps, 2), size=[int(cap.get(3)), int(cap.get(4))] if False else None,
               n_cuts=len(cl), cuts=cl, asl=round(float(shots.mean()), 2), shot_median=round(float(np.median(shots)), 2),
               shot_min=round(float(shots.min()), 2), shot_max=round(float(shots.max()), 2), cuts_per_min=round(len(cl) / dur * 60, 1),
               zone_motion=np.round(zone, 2).tolist(),
               zoom_events=int((np.abs(zs) > 0.0035).sum() / max(1, len(zs)) * 100), zoom_mean=round(float(zs.mean()), 5) if len(zs) else 0,
               pan_energy=round(float(np.abs(px).mean() + np.abs(py).mean()), 3),
               brightness=round(float(np.mean(bright)), 1), saturation=round(float(np.mean(sat)), 1), contrast=round(float(np.mean(contrast)), 1),
               face_rate=round(len(faces) / max(1, len(thumbs) * 2.5 / 0.5), 2),
               face_h_frac=round(float(np.median(fa[:, 2]) / 480), 3) if len(fa) else None,
               face_cx_frac=round(float(np.median(fa[:, 0]) / 270), 3) if len(fa) else None,
               face_cy_frac=round(float(np.median(fa[:, 1]) / 480), 3) if len(fa) else None,
               audio=audio_stats(path))
    if small:
        if frun >= 18: freezes.append((round((i - frun) / fps, 2), round(frun / fps, 2)))
        res.update(freezes=freezes, blacks=blacks)
    cols = 8
    tl = thumbs[:cols * 8]
    while len(tl) % cols: tl.append(np.zeros_like(tl[0]))
    sheet = np.vstack([np.hstack(tl[r:r + cols]) for r in range(0, len(tl), cols)])
    return res, sheet


def main():
    files = sorted(glob.glob(os.path.join(REFS, "*.mp4")) + glob.glob(os.path.join(REFS, "ref01", "*.mp4")))
    allr = []
    for k, f in enumerate(files):
        rid = f"R{k + 1}"
        print(rid, os.path.basename(f), flush=True)
        res, sheet = analyze(f)
        res["id"] = rid
        json.dump(res, open(os.path.join(OUT, rid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        cv2.imwrite(os.path.join(OUT, rid + "_sheet.png"), sheet)
        allr.append(res)
        print({k_: v for k_, v in res.items() if k_ not in ("cuts", "zone_motion")}, flush=True)
    json.dump(allr, open(os.path.join(OUT, "all.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
