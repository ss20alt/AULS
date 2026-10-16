import os, sys, json, glob, subprocess
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
A = "analysis/" + (sys.argv[1] if len(sys.argv) > 1 else "tiktok2610")
rows = []
for jp in sorted(glob.glob(f"{A}/[A-Z][0-9][0-9].json")):
    r = json.load(open(jp, encoding="utf-8")); p = r["info"]["path"]; dur = r["info"]["dur"]
    W, H = 288, 512
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", p, "-vf", f"fps=10,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    sat, bri, capy, badge = [], [], [], []
    while True:
        b = pr.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        f = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        sat.append(float(hsv[..., 1].mean())); bri.append(float(f.mean()))
        # subtítulo blanco con borde negro: filas con muchos píxeles muy blancos pegados a píxeles muy oscuros, banda central
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        wh = (g > 238).astype(np.uint8); dk = (g < 40).astype(np.uint8)
        edge = wh & cv2.dilate(dk, np.ones((3, 3), np.uint8))
        prof = edge[:, int(W * 0.15):int(W * 0.85)].sum(1).astype(float)
        prof[:int(H * 0.25)] = 0; prof[int(H * 0.92):] = 0
        if prof.max() > 12: capy.append(int(np.argmax(np.convolve(prof, np.ones(9), "same"))) / H)
        # insignia de redes arriba a la derecha: rojo saturado en la esquina
        cz = hsv[int(H * 0.0):int(H * 0.12), int(W * 0.6):]
        red = ((cz[..., 0] < 8) | (cz[..., 0] > 170)) & (cz[..., 1] > 150) & (cz[..., 2] > 150)
        badge.append(red.mean() > 0.02)
    sat = np.array(sat); bri = np.array(bri)
    n = len(sat)
    bw = 0
    while bw < n and sat[bw] < 10: bw += 1
    # tarjeta final blanca
    wc = 0
    while wc < n and bri[n - 1 - wc] > 225: wc += 1
    # música: nivel del tramo final (sin voz) vs voz
    a = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(a, np.int16).astype(np.float32) / 32768
    def db(x): return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9) if len(x) else None
    se = r.get("speech_end") or dur
    tail = a[int((se + 0.5) * 16000):int((dur - 0.2) * 16000)]
    voice = a[int((r.get("speech_start") or 0) * 16000):int(se * 16000)]
    rows.append(dict(id=os.path.basename(jp)[:3], dur=round(dur, 1), bw_hook=round(bw / 10, 1), endcard=round(wc / 10, 1),
                     voice_db=round(db(voice), 1) if len(voice) else None,
                     tail_db=round(db(tail), 1) if len(tail) > 1600 else None, tail_s=round(len(tail) / 16000, 1),
                     cap_y=round(float(np.median(capy)), 3) if capy else None, cap_frames=round(len(capy) / max(1, n), 2),
                     badge=round(float(np.mean(badge)), 2), speech_lead=r.get("speech_start"), lufs=(r.get("audio") or {}).get("lufs")))
    print(rows[-1], flush=True)
json.dump(rows, open(f"{A}/measures.json", "w"), indent=1, default=float)
