# Pruebas rápidas de entender.py (sin GPU, sin whisper, sin render: ffprobe y datos ya guardados) — las carga regress.py.
#   · un archivo roto / a medio copiar no tira error: sale como tipo "roto" con el motivo (antes: KeyError('streams') y la tanda se frenaba)
#   · agrupado por evento: tope de duración por evento, GPS (> 1 km = otro lugar), hora/fecha de los nombres de WhatsApp;
#     una grabación continua de más de 4 h no se parte ni se cae (antes: ValueError en _partir)
#   · lo que falta en la PC (ffprobe, módulos, modelos, huellas, zscale) es FallaEstudio, no un archivo "roto"
#   · los grupos reales de VIDEOSCRUDOLILIAN no empeoran (5-ene, 9-ene, 7-feb y 22-ago siguen juntos) y el GPS queda en la medida
import os, sys, json, shutil, subprocess, tempfile, datetime, hashlib

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO not in sys.path: sys.path.insert(0, STUDIO)
CRUDOS = "C:/Users/acer/Desktop/lilianclaude/skill/VIDEOSCRUDOLILIAN"
L1, L2 = [-25.2815, -57.6222], [-25.2900, -57.5750]                       # Asunción: ~4.8 km entre sí


def _toma(f, h, tipo="clip", gps=None, dur=8.0, dia="2026-10-14", fuente="nombre"):
    """ficha sintética (como la que devuelve entender) para probar el agrupado sin videos"""
    return dict(file=f, tipo=tipo, fecha=f"{dia}T{h}:00", fecha_fuente=fuente, info=dict(dur=dur, gps=gps))


def _nombres(gs): return [[r["file"] for r in g] for g in gs]
def _horas(g): return (datetime.datetime.fromisoformat(g[-1]["fecha"]) - datetime.datetime.fromisoformat(g[0]["fecha"])).total_seconds() / 3600
def _clave(p): return hashlib.md5((os.path.abspath(p) + str(os.path.getsize(p))).encode()).hexdigest()[:16]   # la de entender()


def _roto(EN, tmp):
    """basura con extensión .mp4, archivo de 0 bytes y un mp4 'faststart' cortado a la mitad (ffprobe lo lee 'entero')"""
    bas = os.path.join(tmp, "Dji 20261014101500 0001 D.mp4"); open(bas, "wb").write(b"esto no es un video" * 50)
    vac = os.path.join(tmp, "vacio.mp4"); open(vac, "wb").close()
    res = {}
    for p in (bas, vac):
        try: res[os.path.basename(p)] = EN.probe(p).get("roto")
        except Exception as e: res[os.path.basename(p)] = f"ERROR {e!r}"
    fs = os.path.join(tmp, "fs.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=2:r=25", "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "8", "-movflags", "+faststart", fs], capture_output=True)
    if os.path.exists(fs) and os.path.getsize(fs) > 0:
        cut = os.path.join(tmp, "fs_cortado.mp4"); open(cut, "wb").write(open(fs, "rb").read()[: os.path.getsize(fs) // 2])
        res["fs.mp4 (entero)"] = EN.probe(fs).get("roto"); res["fs_cortado.mp4"] = EN.probe(cut).get("roto")
    try:
        r = EN.entender(bas); txt = EN.ficha(r)
        ent = (r["tipo"], r["fecha"], r.get("fecha_fuente"), bool(r["avisos"]), "NO SE PUDO LEER" in txt)
    except Exception as e: ent = f"ERROR {e!r}"
    ok = all(isinstance(v, str) and not v.startswith("ERROR") for k, v in res.items() if k != "fs.mp4 (entero)")
    return ok and res.get("fs.mp4 (entero)") is None and ent == ("roto", "2026-10-14T10:15:00", "nombre", True, True) and "roto" in EN.TIPOS, (res, ent)


def _tope(EN, tmp):
    """un día de actividades a las 8, 11, 14, 17 y 20 h no es un evento; tomas parejas cada 1.5 h de 8 a 20 h se parten en eventos de
    ≤ 4 h (sin quedar una por una); un acto de 1 h con 4 tomas sigue junto"""
    dia = EN.grupos([_toma(f"t{h}.mp4", f"{h:02d}:00") for h in (8, 11, 14, 17, 20)])
    par = EN.grupos([_toma(f"p{i}.mp4", (datetime.datetime(2026, 10, 14, 8) + datetime.timedelta(minutes=90 * i)).strftime("%H:%M")) for i in range(9)])
    acto = EN.grupos([_toma(f"a{i}.mp4", h) for i, h in enumerate(("19:00", "19:20", "19:45", "20:05"))])
    return len(dia) == 5 and max(map(_horas, par)) <= 4 and 2 <= len(par) <= 5 and len(acto) == 1, (_nombres(dia), _nombres(par), _nombres(acto))


def _gps(EN, tmp):
    """dos tomas a 20 min pero a ~5 km (otro lugar) van aparte; la DJI sin GPS se junta con la más cercana en hora; dos tomas en el
    mismo lugar (20 m) siguen juntas"""
    g1 = EN.grupos([_toma("iphone_a.mov", "10:00", gps=L1), _toma("android_b.mp4", "10:20", gps=L2), _toma("dji_c.mp4", "10:30")])
    g2 = EN.grupos([_toma("x.mp4", "10:00", gps=L1), _toma("y.mp4", "10:20", gps=[-25.2816, -57.6224])])
    d = EN.km(L1, L2)
    return _nombres(g1) == [["iphone_a.mov"], ["android_b.mp4", "dji_c.mp4"]] and len(g2) == 1 and 4 < d < 6, (_nombres(g1), _nombres(g2), round(d, 2))


def _whatsapp(EN, tmp):
    """hora de "at 10.23.45" (también reloj de 12 h con PM), día de "VID-20261014-WA0012"; metadato 1970 = vacío; hora con zona del
    iPhone. Las de solo-día van juntas por día, aparte de las de hora conocida, y el grupo queda marcado como dudoso"""
    f1 = EN.fecha_y_fuente("WhatsApp Video 2026-10-14 at 10.23.45.mp4", {})
    f2 = EN.fecha_y_fuente("WhatsApp Video 2026-10-14 at 3.45.12 PM.mp4", {})
    f3 = EN.fecha_y_fuente("VID-20261014-WA0012.mp4", {"created": "1970-01-01T00:00:00.000000Z"})
    f4 = EN.fecha_y_fuente("IMG_8553.MOV", {"creada_local": "2026-01-10T17:48:52-0300", "created": "2026-01-10T20:48:52.000000Z"})
    wa = EN.grupos([_toma("VID-20261014-WA0012.mp4", "12:00", fuente="dia"), _toma("VID-20261014-WA0013.mp4", "12:00", fuente="dia"),
                    _toma("dji.mp4", "12:10")])
    return (f1 == (datetime.datetime(2026, 10, 14, 10, 23, 45), "whatsapp") and f2[0] == datetime.datetime(2026, 10, 14, 15, 45, 12)
            and f3 == (datetime.datetime(2026, 10, 14, 12, 0), "dia") and f4 == (datetime.datetime(2026, 1, 10, 17, 48, 52), "metadatos")
            and sorted(map(len, wa)) == [1, 2] and any(EN.dudas(g) for g in wa if len(g) == 2)), (f1, f2, f3, f4, _nombres(wa))


def _continua(EN, tmp):
    """grabación CONTINUA de más de 4 h (sin ni 1 min de corte): un solo evento, sin caerse. Antes: ValueError('min() iterable
    argument is empty') con huecos ≤ 0 (toma corta dentro de una larga; trozos DJI que se solapan) y entender/evento se cortaban"""
    T0 = datetime.datetime(2026, 10, 14, 8)
    fk = lambda f, ini, dur: dict(file=f, tipo="evento", fecha=ini.isoformat(), fecha_fuente="nombre", info=dict(dur=dur, gps=None))
    a = EN.grupos([fk("larga.mp4", T0, 4 * 3600 + 600), fk("corta.mov", T0 + datetime.timedelta(minutes=245), 30)])
    b = EN.grupos([fk(f"dji{i}.mp4", T0 + datetime.timedelta(hours=i), 3600.5) for i in range(6)])             # se solapan 0.5 s
    c = EN.grupos([fk(f"djs{i}.mp4", T0 + datetime.timedelta(seconds=3601 * i), 3600.0) for i in range(6)])    # nombre al segundo: +1 s
    ok = [len(x) for x in (a, b, c)] == [1, 1, 1] and any("continua" in d for d in EN.dudas(b[0]))
    return ok, (_nombres(a), _nombres(b), _nombres(c), EN.dudas(b[0]))


def _sano(tmp):
    """video sano de 2 s sin audio (ffmpeg testsrc), para probar entender sin medir nada pesado"""
    p = os.path.join(tmp, "sano 20261014101500.mp4")
    if not os.path.exists(p):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=2:r=25", "-c:v", "libx264", "-preset",
                        "ultrafast", p], capture_output=True, stdin=subprocess.DEVNULL)
    return p


def _estudio(EN, tmp):
    """lo que falta en la PC NO sale como archivo 'roto' (con 'copialo de nuevo desde la cámara' y TODOS los videos rotos): sale
    FallaEstudio con lo que falta. Sin ffprobe, sin la huella de cara, un módulo que no carga, cv2.error de un modelo, ffmpeg sin
    zscale con un HDR. Un error que sí es del archivo sigue siendo 'roto' (y el sano se lee). Antes: todos 'roto'"""
    fs = _sano(tmp)
    if not os.path.exists(fs): return None
    import cv2
    F = getattr(EN, "FallaEstudio", None)
    if F is None: return False, "no existe EN.FallaEstudio (los errores de la PC salen como 'roto')"
    sale = {}
    def corre(nombre, fn):
        try: v = fn(); sale[nombre] = ("roto: " + v["info"]["roto"]) if isinstance(v, dict) and (v.get("info") or {}).get("roto") else (v.get("tipo") if isinstance(v, dict) else v)
        except F as e: sale[nombre] = "FALLA_ESTUDIO: " + str(e)
        except Exception as e: sale[nombre] = f"OTRA {e!r}"
    path0, cache0, clients0, av0, vf0 = os.environ.get("PATH", ""), EN.CACHE, EN.CLIENTS, EN.audio_features, EN.video_features
    V = dict(faces_mean=1.0, faces_multi=0.0, face_big=0.2, face_rate=1.0, lilian_face=0.0, motion=0.0, motion_p90=0.0, captions=0.0,
             cuts_per_min=0.0, end_white=False, tv_band=False, band_edges=0.0, band_still=1.0)
    def lanza(e):
        def f(*a, **k): raise e
        return f
    try:
        EN.CACHE = tmp; EN._ESTUDIO.clear()                                      # caché de prueba: nada se escribe en la real
        EN.audio_features = EN.video_features = lanza(AssertionError("no debería medir: faltaba algo"))
        os.environ["PATH"] = tempfile.mkdtemp(dir=tmp)                           # sin ffmpeg/ffprobe
        corre("sin ffprobe: probe", lambda: EN.probe(fs))
        corre("sin ffprobe: entender", lambda: EN.entender(fs, use_cache=False))
        os.environ["PATH"] = path0; EN._ESTUDIO.clear()
        EN.CLIENTS = tempfile.mkdtemp(dir=tmp)                                   # sin la huella de cara
        corre("sin huella de cara", lambda: EN.entender(fs, use_cache=False))
        EN.CLIENTS = clients0
        EN.video_features = lanza(ModuleNotFoundError("No module named 'faster_whisper'"))
        corre("módulo que falta", lambda: EN.entender(fs, use_cache=False))
        EN.video_features = lanza(cv2.error("yunet.onnx: can't read ONNX"))
        corre("cv2.error de un modelo", lambda: EN.entender(fs, use_cache=False))
        EN.video_features = lanza(ValueError("cuadro con tamaño raro"))          # esto sí puede ser del archivo: sigue 'roto'
        corre("error del archivo", lambda: EN.entender(fs, use_cache=False))
        EN.video_features = lambda *a, **k: dict(V)                              # sano: se lee (toma de 2 s -> clip)
        corre("sano", lambda: EN.entender(fs, use_cache=False))
        EN._ESTUDIO.update(ffprobe=True, ffmpeg=True, zscale=False)              # ffmpeg sin zscale: el HDR falla, el SDR no
        corre("HDR sin zscale", lambda: EN.revisar_estudio(audio=False, hdr=True))
        corre("SDR sin zscale", lambda: EN.revisar_estudio(audio=False, hdr=False) or "bien")
    finally:
        os.environ["PATH"] = path0; EN.CACHE, EN.CLIENTS, EN.audio_features, EN.video_features = cache0, clients0, av0, vf0
        EN._ESTUDIO.clear()
    fe = lambda k, txt="": sale.get(k, "").startswith("FALLA_ESTUDIO") and txt in sale.get(k, "")
    ok = (fe("sin ffprobe: probe", "ffprobe") and fe("sin ffprobe: entender") and fe("sin huella de cara", "lilian_faceprint.npy")
          and fe("módulo que falta", "faster_whisper") and fe("cv2.error de un modelo") and sale.get("error del archivo", "").startswith("roto")
          and sale.get("sano") == "clip" and fe("HDR sin zscale", "zscale") and sale.get("SDR sin zscale") == "bien")
    return ok, sale


def _reales(EN, tmp):
    """archivos reales: solo ffprobe y la caché ya guardada (si falta la caché de alguno NO se mide: sería pesado -> None = se salta)"""
    if not os.path.isdir(CRUDOS): return None
    ps = [os.path.join(CRUDOS, f) for f in sorted(os.listdir(CRUDOS)) if f.lower().endswith(EN.VID)]
    if not ps or not all(os.path.exists(os.path.join(EN.CACHE, _clave(p) + ".json")) for p in ps): return None
    # caché VIEJA (sin GPS): se completa con ffprobe barato al cargar y queda guardada (en una caché de prueba, no la real)
    i8, vieja = os.path.join(CRUDOS, "IMG_8553.MOV"), None
    if os.path.exists(i8):
        c0, EN.CACHE = EN.CACHE, tmp
        try:
            r0 = json.load(open(os.path.join(c0, _clave(i8) + ".json"), encoding="utf-8"))
            for k in ("gps", "creada_local"): r0["info"].pop(k, None)
            json.dump(r0, open(os.path.join(tmp, _clave(i8) + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
            r1 = EN.entender(i8)
            vieja = (r1["info"].get("gps"), json.load(open(os.path.join(tmp, _clave(i8) + ".json"), encoding="utf-8"))["info"].get("gps"))
        finally: EN.CACHE = c0
    rs = [EN.entender(p) for p in ps]
    gs = [sorted(r["file"] for r in g) for g in EN.grupos(rs)]
    junto = {d: sorted(r["file"] for r in rs if d in r["file"].replace(" ", "")) for d in ("20260105", "20260109", "20260207", "20260822")}
    gps = {r["file"]: r["info"].get("gps") for r in rs if r["file"] in ("IMG_8553.MOV", "VID_20260822_120059.mp4", "Dji 20260109213309 0042 D.mp4")}
    ok_vieja = vieja is None or bool(vieja[0] and abs(vieja[0][0] + 25.2839) < 1e-3 and vieja[1] == vieja[0])
    return (all(len(v) >= 2 and v in gs for v in junto.values()) and not any(r["tipo"] == "roto" for r in rs) and ok_vieja
            and (gps.get("VID_20260822_120059.mp4") or [0])[0] == -25.2815 and (gps.get("IMG_8553.MOV") or [0, 0])[1] == -57.5041
            and "Dji 20260109213309 0042 D.mp4" in gps and gps["Dji 20260109213309 0042 D.mp4"] is None), (gs, junto, gps, vieja)


CASOS = [
    ("entender: un archivo roto o a medio copiar NO frena la tanda (tipo 'roto' con el motivo; el entero se lee bien)", _roto),
    ("eventos: un día de actividades (8, 11, 14, 17, 20 h) no es un solo evento; tope de 4 h por evento", _tope),
    ("eventos: con GPS, a más de 1 km = otro lugar (otro evento); en el mismo lugar siguen juntas", _gps),
    ("fecha: hora de 'WhatsApp Video … at 10.23.45', día de 'VID-20261014-WA0012' (sin hora: aparte de las de hora conocida)", _whatsapp),
    ("eventos: una grabación continua de más de 4 h (toma corta adentro, trozos DJI que se solapan) es UN evento y no se cae", _continua),
    ("entender: lo que falta en la PC (ffprobe, huella, módulo, modelo, zscale) es FallaEstudio, no un archivo 'roto'", _estudio),
    ("entender: GPS en la medida (iPhone ISO6709 / Android location; caché vieja completada) y los grupos reales no empeoran "
     "(5-ene, 9-ene, 7-feb, 22-ago juntos)", _reales),
]


def pruebas(check):
    import entender as EN
    tmp = tempfile.mkdtemp(prefix="pruebas_entender_")
    try:
        for nombre, fn in CASOS:                                          # cada caso falla solo (una excepción no tapa a los demás)
            try: res = fn(EN, tmp)
            except Exception as e: res = (False, f"excepción: {e!r}")
            if res is not None: check(nombre, res[0], res[1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
