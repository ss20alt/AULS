# tiras de 10 fotogramas por video (4 videos por imagen) para revisar estructura y escenario de una tanda de referencias
import os, sys, json, glob, subprocess
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
tag = sys.argv[1]; A = os.path.join("analysis", tag)
rows, names = [], []
for jp in sorted(glob.glob(os.path.join(A, "[A-Z][0-9][0-9].json"))):
    r = json.load(open(jp, encoding="utf-8")); p = r["info"]["path"]; dur = r["info"]["dur"]
    vid = os.path.basename(jp)[:3]
    tw, th = 144, 256; tiles = []
    for k in range(10):
        t = dur * (k + 0.5) / 10
        b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", "-vf", f"scale={tw}:{th}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        f = np.frombuffer(b, np.uint8); f = f.reshape(th, tw, 3).copy() if f.size == th * tw * 3 else np.zeros((th, tw, 3), np.uint8)
        cv2.putText(f, f"{t:.0f}s", (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
        tiles.append(f)
    lab = np.zeros((th, 60, 3), np.uint8)
    cv2.putText(lab, vid, (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2); cv2.putText(lab, f"{dur:.0f}s", (4, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    rows.append(np.hstack([lab] + tiles)); names.append(vid)
for i in range(0, len(rows), 4):
    cv2.imwrite(os.path.join(A, f"TIRAS_{i // 4 + 1:02d}.jpg"), np.vstack(rows[i:i + 4]), [cv2.IMWRITE_JPEG_QUALITY, 86])
print(len(rows), "videos ->", (len(rows) + 3) // 4, "imágenes")
