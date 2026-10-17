# Pruebas del formato EVENTO (evento.py): ningún corte dentro de una palabra (tomas de ambiente y frases de ella) y controles del
# montaje (QA sin render). Rápidas (sin GPU ni render) y SIN depender de projects/: usan tests/evento_fixtures/<caso>/, copias
# congeladas del plan ENTREGADO (antes de los arreglos) y del análisis de cada toma (clips/c*.json, con el VAD de su audio ya
# calculado) + los 9 cuadros que mira YuNet bajo el título del cumpleaños. Re-renderizar o borrar un proyecto no las cambia.
# (las armó un script con evento.vad_de/cuadro sobre projects/* el 2026-10-16; cada plan.json dice de qué proyecto salió)
#   pruebas(check)  ->  check(nombre, ok_bool, detalle)
import os, sys, json, glob

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STUDIO)
FX = os.path.join(STUDIO, "tests", "evento_fixtures")
# los 3 casos medidos en la auditoría: su voz cortada dentro de una toma de ambiente (5-ene; 9-ene «corazón»; Arnaldo «le») y,
# en el 9-ene (Epi Centurión entregado), sus frases que entraban dentro de «hacer.» y salían dentro de «Entonces»
CASOS = [("arnaldo_20260105_ingesta", 1), ("epi_20260109", 1), ("arnaldo_20260105_whisper", 1)]


def _cargar(caso):
    fd = os.path.join(FX, caso)
    P = json.load(open(os.path.join(fd, "plan.json"), encoding="utf-8"))
    A = {c["k"]: json.load(open(os.path.join(fd, "clips", f"c{c['k']}.json"), encoding="utf-8")) for c in P["clips"]}
    return fd, P, A


def _su_voz(A):
    """su voz medida aparte (huella de voz + sus palabras), sin usar el código que se prueba"""
    return [tuple(x) for x in A.get("her", [])] + [(w["s"], w["e"]) for w in A.get("words", [])]


def _ajenas(x, ws):
    """palabras suyas que NO son de la frase de una toma 'habla' y que suenan (aunque sea 0.01 s) dentro de la toma"""
    s0, e0 = x["words"][0]["s"], x["words"][-1]["e"]
    return [w["t"] for w in ws if not (s0 - 1e-6 <= w["s"] and w["e"] <= e0 + 1e-6) and min(w["e"], x["b"]) - max(w["s"], x["a"]) > 0.005]


def _cuadros(fd):
    """leer_cuadro para qa_montaje: los cuadros guardados (cuadros/c<k>_<t>.jpg), el más cercano a t (± 0.02 s)"""
    import cv2
    hay = []
    for f in glob.glob(os.path.join(fd, "cuadros", "*.jpg")):
        n, t = os.path.splitext(os.path.basename(f))[0].rsplit("_", 1); hay.append((n, float(t), f))
    def leer(video, t):
        n = os.path.splitext(os.path.basename(video))[0]
        d, f = min(((abs(tt - t), f) for nn, tt, f in hay if nn == n), default=(1.0, None))
        return cv2.imread(f) if d < 0.02 else None
    return leer


def pruebas(check):
    import numpy as np
    import evento as E
    if not os.path.isdir(FX): return                                              # paquete sin datos congelados: no aplica
    falta = [c for c in ("arnaldo_20260105_ingesta", "arnaldo_20260105_whisper", "epi_20260109", "jovenes_20260822", "cumple_20260207")
             if not os.path.exists(os.path.join(FX, c, "plan.json"))]
    if falta:                                                                       # nunca saltear en silencio: el banco perdería cobertura
        check("evento: están los datos congelados de las pruebas (tests/evento_fixtures/)", False, falta)
        return
    # 1) ninguna toma corta una palabra: ambiente sin su voz (ni 0.1 s antes/después) y cada borde en silencio o con fundido
    #    largo (voz de otros); 'habla' (su frase) sin ningún pedazo de una palabra suya que no sea de la frase
    mal, n_amb, n_hab = [], 0, 0
    for caso, k in CASOS:
        fd, P, A = _cargar(caso)
        c = next(c for c in P["clips"] if c["k"] == k)
        ella = _su_voz(A[k])
        _, voz = E.voces(c, A[k])
        for x in E.candidates(c, A[k]):
            if x["kind"] == "habla":
                n_hab += 1
                aj = _ajenas(x, A[k]["words"])
                if aj: mal.append((caso, round(x["a"], 2), round(x["b"], 2), "habla con", aj[:3]))
                continue
            n_amb += 1
            if any(min(x["b"] + 0.1, e) > max(x["a"] - 0.1, s) for s, e in ella): mal.append((caso, round(x["a"], 2), round(x["b"], 2), "su voz"))
            for t, f in ((x["a"], x.get("fa", 0.03)), (x["b"], x.get("fb", 0.03))):
                if any(s + 0.05 < t < e - 0.05 for s, e in voz) and f < 0.3: mal.append((caso, round(t, 2), "borde en voz sin fundido"))
    check("evento: ninguna toma corta una palabra: ambiente sin su voz y en pausas (o con fundido), sus frases sin pedazos de "
          "«hacer.»/«Entonces» (3 casos: 5-ene, 9-ene «corazón», Arnaldo «le»)", not mal and n_amb > 100 and n_hab >= 6, (mal[:4], n_amb, n_hab))
    # 2) QA del montaje: ve los cortes de su voz en los 3 planes entregados (en el Epi: «corazón» en una toma de ambiente y su
    #    frase que entra en «hacer.» y sale en «Entonces») y los planes nuevos (misma selección, código nuevo) no tienen ninguno
    viejos, nuevos = {}, {}
    for caso, _ in CASOS:
        fd, P, A = _cargar(caso)
        viejos[caso] = [f for f in E.qa_montaje(fd, titulo="", caras=False) if f[1] == "MIDSENTENCE" and f[0] == "alta"]
        cands = [x for c in P["clips"] for x in E.candidates(c, A[c["k"]])]
        plan = dict(chosen=E.select(P["clips"], cands, float(np.clip(0.45 * sum(c["dur"] for c in P["clips"]), 12.0, 45.0))), clips=P["clips"])
        nuevos[caso] = [f for f in E.qa_montaje(fd, titulo="", caras=False, plan=plan) if f[1] == "MIDSENTENCE"]
    epi = " ".join(f[2] + " " + f[3] for f in viejos["epi_20260109"])
    check("evento: el QA marca los cortes de su voz de los planes entregados («corazón» en ambiente; «hacer.» y «Entonces» en su "
          "frase) y los planes nuevos no tienen ninguno",
          all(viejos.values()) and all(w in epi for w in ("«corazón»", "«hacer.»", "«Entonces»")) and not any(nuevos.values()),
          ({k: [f[2] for f in v] for k, v in viejos.items()}, nuevos))
    # 3) duración contra la pedida (jóvenes: 8.8 s armados para 12 s pedidos con 18 s de material)
    F = E.qa_montaje(os.path.join(FX, "jovenes_20260822"), titulo="", caras=False)
    check("evento: el QA compara la duración armada con la pedida (8.8 s de 12 s)", any(f[1] == "DUR" and "8.8" in f[2] for f in F), F)
    # 4) título dentro de la zona segura (2 líneas + fecha: antes 28 % bajo la barra de la app) y el control lo ve si se pone mal
    cum, P, A = _cargar("cumple_20260207")
    tit, sub = P["titulo"], P["sub"]
    tl = E.linea_de_tiempo(P["chosen"]); im = E.title_sprite(tit, sub)
    ty = E.titulo_y(tl, A, im, E.subtitulos(tl, A))
    tope = ty - im.shape[0] / 2 + E.tinta(im)[1]
    bien = E.qa_montaje(cum, titulo=tit, sub=sub, ty=ty, caras=False)
    mal = E.qa_montaje(cum, titulo=tit, sub=sub, ty=330.0, caras=False)
    _, Pe, Ae = _cargar("epi_20260109")                                             # sus frases del Epi: 14 subtítulos seguidos
    caps = E.subtitulos(E.linea_de_tiempo(Pe["chosen"]), Ae)                        # (con la cola de +0.15 s se pisaban 0.1 s)
    pisados = [(a["text"], b["text"]) for a, b in zip(caps, caps[1:]) if a["e"] > b["s"] + 1e-6]
    check("evento: título y subtítulos dentro de la zona segura y del cuadro, sin dos subtítulos a la vez (y el control marca el "
          "título viejo en y=330)",
          tope >= 250 and not [f for f in bien if f[1] in ("SAFE_ZONE", "CLIPPED", "SOLAPE")] and any(f[1] == "SAFE_ZONE" for f in mal)
          and len(caps) > 5 and not pisados, (round(tope), bien, mal, len(caps), pisados[:3]))
    # 5) el título no tapa caras: YuNet sobre los cuadros reales guardados (en el cumpleaños hay caras en la franja de abajo)
    if glob.glob(os.path.join(cum, "cuadros", "*.jpg")) and os.path.exists(os.path.join(STUDIO, "models", "yunet.onnx")):
        leer = _cuadros(cum)                                                       # (cuadros con caras de invitados: solo en esta PC)
        abajo = E.qa_montaje(cum, titulo=tit, sub=sub, ty=1180.0, leer_cuadro=leer)
        elegido = E.qa_montaje(cum, titulo=tit, sub=sub, ty=ty, leer_cuadro=leer)
        check("evento: el QA ve (YuNet) un título que tapa caras y la altura elegida no las tapa",
              any(f[1] == "TEXT_ON_FACE" for f in abajo) and not any(f[1] == "TEXT_ON_FACE" for f in elegido), (abajo, elegido))
    # 6) una frase con su voz pero SIN su cara no cuenta como suya (el umbral de voz deja pasar a un animador)
    n = 100
    ws = [dict(t=w, s=2.0 + 0.4 * i, e=2.0 + 0.4 * i + 0.3) for i, w in enumerate("Muchas gracias a todos por venir hoy.".split())]
    base = dict(sharp=[5.0] * n, mot=[0.5] * n, bri=[120.0] * n, nf=[1] * n, fsz=[0.1] * n, fcx=[540.0] * n, fcy=[700.0] * n,
                her=[(1.9, 4.9)], words=ws, vad=[(1.9, 4.9)])
    c0 = dict(k=0, dur=10.0, audio="", file="x.mp4")
    sin = [x for x in E.candidates(c0, dict(base, lil=[0.1] * n)) if x["kind"] == "habla"]
    con = [x for x in E.candidates(c0, dict(base, lil=[0.6] * n)) if x["kind"] == "habla"]
    check("evento: una frase con su voz pero sin su cara en pantalla no se da por suya (con su cara, sí)", not sin and len(con) == 1,
          ([x["text"] for x in sin], [x["text"] for x in con]))
