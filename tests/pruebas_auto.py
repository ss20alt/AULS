# Pruebas rápidas de auto.py (sin GPU, sin whisper, sin render: fuentes sintéticas en una carpeta temporal + datos ya guardados) —
# las carga regress.py.
#   · el MISMO archivo ya ingresado y corregido a mano se reutiliza (por el archivo original, no por el nombre armado del archivo)
#   · ingest._register trae las correcciones de otra fuente del mismo archivo cuando entra con otro nombre
#   · las dudas del árbitro sin revisar que caen DENTRO del video editado pasan al informe ("ok con aviso")
#   · un video roto no frena la tanda (fila "falla" con el motivo) y las carpetas aceptan .mkv y .m4v
#   · el mismo archivo MOVIDO de carpeta (fuente vieja sin huella) se reusa: no vuelve a ingresar como <nombre>_2 (GPU, minutos)
#   · un borrador del mapa corregido a mano y sin aprobar no se pisa al rehacer borradores con el mapper de hoy
import os, sys, json, shutil, tempfile, argparse, time, types

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO not in sys.path: sys.path.insert(0, STUDIO)
LS1 = r"C:\Users\acer\Downloads\2026-10-14-LS1.mp4"


def _fuente(src_dir, name, original, dur, panel=False, extra=None, archivos=True, **sj):
    """fuente sintética: source.json + meta.json (+ archivos de trabajo vacíos y extras como content.json)"""
    d = os.path.join(src_dir, name); os.makedirs(d, exist_ok=True)
    s = dict(name=name, client="lilian", original=original, video="work.mp4", voice="voice.wav", transcript="transcript.json", face="face.npy",
             glossary={}, reporter=[], bad=[], delete=[[10.0, 10.02, "auto"]], created="2026-10-16 12:00", tema="")
    if panel: s.update(layout="panel", panel=[0, 400, 1080, 840])
    s.update(sj)
    json.dump(s, open(os.path.join(d, "source.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(dict(duration=dur), open(os.path.join(d, "meta.json"), "w"))
    for f in (("work.mp4", "voice.wav", "transcript.json", "face.npy") if archivos else ()): open(os.path.join(d, f), "wb").close()
    for f, txt in (extra or {}).items():
        os.makedirs(os.path.dirname(os.path.join(d, f)), exist_ok=True); open(os.path.join(d, f), "w", encoding="utf-8").write(txt)
    return d


def _escenario(tmp):
    """un video y 4 fuentes: 'auto_video' (nombre armado, sin correcciones), 'corregida' (hablante, texto, mapa aprobado, datos),
    'vertical' (mismo archivo, otro formato), 'otro_video' (misma ruta pero otra duración: el teléfono repitió el nombre)"""
    vid = os.path.join(tmp, "video.mp4"); open(vid, "wb").write(os.urandom(1 << 20) + b"x" * 5000)
    S = os.path.join(tmp, "sources")
    _fuente(S, "auto_video", vid, 100.0, panel=True, created="2026-10-16 16:32")
    _fuente(S, "corregida", vid, 100.0, panel=True, created="2026-10-14 12:58", tema="Senado, Bachi Núñez",
            speaker_fix=[[229.26, 247.7, "L", "es Lilian"]], fixes=[{"t0": 1.0, "t1": 2.0, "text": "Ahí", "words": [["Ahí", 1.2, 1.4]]}],
            nocut=[[5.0, 6.0, "c1"]], extra={"content.json": "{}", "datos.json": '{"datos": [], "fondos": [{"img": "material/a.png"}]}',
                                             "material/a.png": "png"})
    _fuente(S, "vertical", vid, 100.0, speaker_fix=[[1.0, 2.0, "L", "x"]])
    _fuente(S, "otro_video", vid, 42.0, speaker_fix=[[1.0, 2.0, "R", "x"]] * 5, extra={"content.json": "{}"})
    return vid, S


def _reuso(AU, IG, tmp):
    vid, S = _escenario(tmp)
    viejo = IG.SOURCES; IG.SOURCES = S
    try:
        cs = [c["name"] for c in IG.fuentes_del_original(vid, 100.0)]
        a = argparse.Namespace(name=None, tema="", solo_plan=True)
        r = dict(path=vid, info=dict(dur=100.0))
        tv = AU.ingresar(r, a, "panel")                                   # TV (panel): la corregida, no la del nombre armado
        ve = AU.fuente_previa(vid, None, 100.0)["name"]                   # declaración vertical: la del formato vertical
        sin = AU.fuente_previa(os.path.join(tmp, "nunca.mp4"), "panel", 10.0)["name"]
    finally: IG.SOURCES = viejo
    real = None
    if os.path.isdir(os.path.join(STUDIO, "sources", "lilian_senado_feminicidios")):       # el caso real (si están las fuentes en esta PC)
        try: dur = json.load(open(os.path.join(STUDIO, "sources", "lilian_senado_feminicidios", "meta.json")))["duration"]
        except Exception: dur = None
        real = AU.fuente_previa(LS1, "panel", dur)["name"]
    ok = (cs[:1] == ["corregida"] and "otro_video" not in cs and set(cs) == {"corregida", "vertical", "auto_video"} and tv == "corregida"
          and "corregida" in r.get("fuente_nota", "") and ve == "vertical" and sin is None and real in (None, "lilian_senado_feminicidios"))
    return ok, dict(candidatas=cs, tv=tv, nota=r.get("fuente_nota"), vertical=ve, sin=sin, ls1_real=real)


def _hereda(IG, tmp):
    vid, S = _escenario(tmp)
    viejo = IG.SOURCES; IG.SOURCES = S
    try:
        d = os.path.join(S, "nueva_ingesta"); os.makedirs(d)
        json.dump(dict(duration=100.0), open(os.path.join(d, "meta.json"), "w"))      # (ingest escribe meta.json antes de registrar)
        IG._register(d, "nueva_ingesta", "lilian", vid, tema="", layout="panel", tipo="tv")
        s1 = json.load(open(os.path.join(d, "source.json"), encoding="utf-8"))
        IG._register(d, "nueva_ingesta", "lilian", vid, tema="", layout="panel")      # re-ingesta con el mismo nombre: no se pierde nada
        s2 = json.load(open(os.path.join(d, "source.json"), encoding="utf-8"))
    finally: IG.SOURCES = viejo
    det = dict(heredado_de=s1.get("heredado_de"), speaker_fix=s1.get("speaker_fix"), tema=s1.get("tema"), nocut=s1.get("nocut"),
               archivos=sorted(os.listdir(d)), huella=bool(s1.get("huella")), igual_2da=all(s2.get(k) == s1.get(k) for k in ("speaker_fix", "fixes", "tema", "nocut")))
    ok = (s1.get("heredado_de") == "corregida" and s1.get("speaker_fix") == [[229.26, 247.7, "L", "es Lilian"]] and len(s1.get("fixes") or []) == 1
          and s1.get("tema") == "Senado, Bachi Núñez" and s1.get("nocut") and bool(s1.get("huella"))
          and os.path.exists(os.path.join(d, "datos.json")) and os.path.exists(os.path.join(d, "material", "a.png"))
          and not os.path.exists(os.path.join(d, "content.json")) and det["igual_2da"])
    return ok, det


def _dudas(AU, AR, tmp):
    src = "fuente_dudas"
    os.makedirs(os.path.join(tmp, "sources", src))
    it = lambda i, t0, t1, sev, dec=None: dict(id=i, t0=t0, t1=t1, sev=sev, quien="ella", tipo="distinta", whisper="w", dudosas=f"d{i}", oye="o",
                                               **({"decision": dec} if dec else {}))
    json.dump(dict(items=[it(0, 709.17, 709.5, 2.7),                     # «hubo» dentro del gancho (caso real de LS1)
                          it(1, 431.68, 432.94, 20.0),                    # 1.12 s de 1.26 adentro
                          it(2, 398.08, 399.56, 10.4),                    # roza el borde del tramo 0.05 s: NO está dentro
                          it(3, 500.0, 501.0, 9.0, dec=dict(action="ok")),  # ya revisada
                          it(4, 900.0, 901.0, 30.0),                      # fuera del video
                          it(5, 600.02, 600.1, 1.0)]),                    # muy corta pero entera adentro
              open(os.path.join(tmp, "sources", src, "arbitro.json"), "w", encoding="utf-8"))
    pd = os.path.join(tmp, "proyecto"); os.makedirs(pd)
    sp = lambda a, b, pre=0: dict(kind="speech", fs=int(round(a * 30)) + pre, fe=int(round(b * 30)), pre=pre)
    json.dump(dict(fps=30, items=[sp(706.93, 713.0), sp(431.07, 432.8, 4), sp(396.0, 398.13), sp(499.0, 502.0), sp(599.9, 600.5),
                                  dict(kind="card", name="end", out=0, n=60)]), open(os.path.join(pd, "edl.json"), "w"))
    json.dump(dict(source=src, script=[["seg", "x", "A", 0.0, 1.0]]), open(os.path.join(pd, "cfg.json"), "w"))
    viejo = AR.STUDIO; AR.STUDIO = tmp
    try:
        fu, du = AU.dudas_en_video(pd)
        x = dict(estado="ok", motivo="ritmo tranquilo (tomas largas)"); AU.aviso_dudas(x, pd, None)
        y = dict(estado="no entregado", motivo="✗ HALLAZGOS"); AU.aviso_dudas(y, pd, None)
        os.remove(os.path.join(pd, "edl.json"))                           # sin EDL: el guion de cfg.json
        sin_edl = AU.tramos_usados(pd)
    finally: AR.STUDIO = viejo
    ids = [d["id"] for d in du]
    ok = (fu == src and ids == [1, 0, 5] and x["estado"] == "ok con aviso"
          and x["motivo"].startswith(f"3 dudas de transcripción sin revisar (python arbitro.py review {src})") and "ritmo tranquilo" in x["motivo"]
          and len(x.get("dudas", [])) == 3 and y["estado"] == "no entregado" and "3 dudas" in y["motivo"] and sin_edl == [(0.0, 1.0)])
    return ok, dict(ids=ids, x=x["motivo"], y=y["motivo"], sin_edl=sin_edl)


def _roto(AU, tmp):
    d = os.path.join(tmp, "tanda"); os.makedirs(d)
    for f, b in (("a_roto.mp4", b"esto no es un video" * 40), ("b_bueno.mkv", b"x" * 3000), ("c_clip.m4v", b"y" * 3000), ("d_tv.MOV", b"z" * 3000),
                 ("notas.txt", b"t"), ("._b_bueno.mkv", b"basura de la Mac"), ("e_vacio.mp4", b""), ("f_ilegible.mp4", b"w" * 3000)):
        open(os.path.join(d, f), "wb").write(b)

    class EN:                                                             # entender falso: lo que hace el real con un archivo roto
        @staticmethod
        def entender(p):
            f = os.path.basename(p)
            if f.startswith("a_"): raise KeyError("streams")              # ffprobe da '{}' (antes: la tanda entera se frenaba acá)
            if f.startswith("f_"): return dict(file=f, path=p, tipo="roto", info=dict(dur=0.0, roto="el archivo no terminó de grabarse"))
            return dict(file=f, path=p, tipo="clip", info=dict(dur=8.0), fecha=None)
        @staticmethod
        def ficha(r): return f"■ {r['file']}"

    antes = list(AU.RESULTADOS); AU.RESULTADOS.clear()
    try:
        vids = AU.listar([d])
        rs = AU.leer(vids, EN)
        rc = AU.seguro("x.mp4", "video", lambda: 1 / 0)                   # un error de Python en una edición tampoco frena la tanda
        filas = [(x["video"], x["estado"], x["motivo"][:60]) for x in AU.RESULTADOS]
    finally: AU.RESULTADOS[:] = antes
    nom = sorted(os.path.basename(v) for v in vids)
    ok = (nom == ["a_roto.mp4", "b_bueno.mkv", "c_clip.m4v", "d_tv.MOV", "e_vacio.mp4", "f_ilegible.mp4"]
          and sorted(r["file"] for r in rs) == ["b_bueno.mkv", "c_clip.m4v", "d_tv.MOV"]
          and sorted(f[0] for f in filas if f[1] == "falla") == ["a_roto.mp4", "e_vacio.mp4", "f_ilegible.mp4", "x.mp4"]
          and all("no se pudo leer" in f[2] for f in filas if f[0] != "x.mp4") and rc == 1)
    return ok, dict(listados=nom, leidos=[r["file"] for r in rs], filas=filas)


def _movido(AU, IG, tmp):
    """el MISMO video ya ingresado (fuentes viejas, sin huella) ahora está en otra carpeta: antes del arreglo la carpeta con el nombre
    armado se tomaba por «otro archivo con el mismo nombre» y volvía a ingresar como auto_img_9999_2, sin sus correcciones"""
    S = os.path.join(tmp, "sources")
    viejo = os.path.join(tmp, "Descargas", "IMG_9999.MOV")              # donde estaba cuando entró (ya no está ahí)
    vid = os.path.join(tmp, "Drive", "IMG_9999.MOV"); os.makedirs(os.path.dirname(vid))
    open(vid, "wb").write(os.urandom(1 << 20) + b"x" * 999)
    _fuente(S, "auto_img_9999", viejo, 100.0, created="2026-10-16 15:00")                       # nombre armado, sin correcciones
    _fuente(S, "img_9999_corregida", viejo, 100.0, created="2026-10-14 12:00", speaker_fix=[[1.0, 2.0, "L", "x"]],
            extra={"content.json": "{}"})                                                        # la corregida a mano (caso LS1)
    _fuente(S, "otro_9999", os.path.join(tmp, "Viejo", "IMG_9999.MOV"), 42.0, speaker_fix=[[1.0, 2.0, "R", "x"]] * 9)  # otro video, mismo nombre
    _fuente(S, "auto_img_7777", os.path.join(tmp, "x", "img-7777.mov"), 100.0)                   # mismo nombre armado, nombre escrito distinto
    v7 = os.path.join(tmp, "Drive", "IMG_7777.MOV"); open(v7, "wb").write(os.urandom(1 << 20))
    v8 = os.path.join(tmp, "Drive", "IMG_7777b.MOV")                     # (para la prueba de duración distinta)
    sj = lambda n: open(os.path.join(S, n, "source.json"), encoding="utf-8").read()
    antes = {n: sj(n) for n in os.listdir(S)}
    vs, vi = AU.STUDIO, IG.SOURCES; AU.STUDIO, IG.SOURCES = tmp, S
    try:
        a = argparse.Namespace(name=None, tema="", solo_plan=True)
        usa = AU.ingresar(dict(path=vid, info=dict(dur=100.0)), a, None)                         # -> la corregida, no *_2
        intacto = all(sj(n) == antes[n] for n in antes)                                          # --solo-plan no escribe nada
        shutil.rmtree(os.path.join(S, "img_9999_corregida"))
        solo = AU.ingresar(dict(path=vid, info=dict(dur=100.0)), a, None)                       # solo la del nombre armado: se reusa
        u7 = AU.ingresar(dict(path=v7, info=dict(dur=100.0)), a, None)                          # nombre armado igual, misma duración
        shutil.copy(v7, v8); os.rename(os.path.join(S, "auto_img_7777"), os.path.join(S, "auto_img_7777b"))
        u8 = AU.ingresar(dict(path=v8, info=dict(dur=55.0)), a, None)                           # otra duración: sí es otro archivo
        sel = [c["name"] for c in IG.fuentes_del_original(vid, 100.0, sellar=True)]              # corrida real: se guarda la huella
        hue = all(json.loads(sj(n)).get("huella") == IG.huella(vid) for n in sel)
        otro = os.path.join(tmp, "Mac", "lilian senado.mov"); os.makedirs(os.path.dirname(otro)); shutil.move(vid, otro)
        luego = [(c["name"], c["por"]) for c in IG.fuentes_del_original(otro, 100.0)]            # movido Y renombrado: por la huella
    finally: AU.STUDIO, IG.SOURCES = vs, vi
    ok = (usa == "img_9999_corregida" and intacto and solo == "auto_img_9999" and u7 == "auto_img_7777" and u8 == "auto_img_7777b_2"
          and sel == ["auto_img_9999"] and hue and luego == [("auto_img_9999", "huella")] and "otro_9999" not in sel)
    return ok, dict(usa=usa, intacto=intacto, solo=solo, u7=u7, u8=u8, selladas=sel, huella_ok=hue, luego=luego)


def _borrador(AU, IG, tmp):
    """borrador del mapa (sin aprobar) y mapper.py más nuevo: se rehace SOLO si es tal cual lo escribió mapper.py; el corregido a mano
    (más nuevo que content_review.html) no se toca y cuenta como corrección humana; sin la página, no se sabe -> no se toca"""
    S = os.path.join(tmp, "sources"); hace = time.time() - 3600
    open(os.path.join(tmp, "mapper.py"), "w").write("# reglas de hoy")
    for n, dr_t, html in (("a_mano", hace + 600, True), ("maquina", hace, True), ("sin_pagina", hace, False)):
        d = _fuente(S, n, os.path.join(tmp, n + ".mp4"), 100.0, extra={"content_draft.json": '{"blocks": "' + n + '"}'})
        if html: open(os.path.join(d, "content_review.html"), "w").write("<p>Para corregir: editar content_draft.json</p>"); os.utime(os.path.join(d, "content_review.html"), (hace, hace))
        os.utime(os.path.join(d, "content_draft.json"), (dr_t, dr_t))
    llamadas = []
    def run(cmd, **kw):                                                   # mapper.draft falso: borrador de hoy + su página (como el real)
        n = cmd[-1]; llamadas.append(n)
        open(os.path.join(S, n, "content_draft.json"), "w").write('{"blocks": "hoy"}')
        open(os.path.join(S, n, "content_review.html"), "w").write("<p>revisar</p>")
        return types.SimpleNamespace(returncode=0, stderr="")
    vs, sp = AU.STUDIO, AU.subprocess; AU.STUDIO, AU.subprocess = tmp, types.SimpleNamespace(run=run)
    try:
        for n in ("a_mano", "maquina", "sin_pagina"): AU.refrescar_borrador(n)
    finally: AU.STUDIO, AU.subprocess = vs, sp
    lee = lambda n: json.load(open(os.path.join(S, n, "content_draft.json")))["blocks"]
    _, det = IG.correcciones(os.path.join(S, "a_mano"), {})
    _, det_m = IG.correcciones(os.path.join(S, "maquina"), {})
    ok = (lee("a_mano") == "a_mano" and lee("maquina") == "hoy" and lee("sin_pagina") == "sin_pagina" and llamadas == ["maquina"]
          and "borrador del mapa corregido a mano" in det and "borrador del mapa corregido a mano" not in det_m
          and os.path.exists(os.path.join(S, "maquina", "content_draft.prev.json")))
    return ok, dict(a_mano=lee("a_mano"), maquina=lee("maquina"), sin_pagina=lee("sin_pagina"), llamadas=llamadas, det=det)


def pruebas(check):
    import auto as AU, ingest as IG, arbitro as AR
    for nombre, fn, args in (("auto: el MISMO archivo ya corregido a mano se reutiliza (por el original, no por el nombre; la más corregida "
                              "del formato pedido; otra duración = otro archivo)", _reuso, (AU, IG)),
                             ("ingest: otra ingesta del mismo archivo con otro nombre trae hablante, texto, zonas sin corte, tema y datos.json "
                              "(no el mapa aprobado) y la huella queda guardada", _hereda, (IG,)),
                             ("auto: dudas del árbitro sin revisar DENTRO del video -> 'ok con aviso' con el comando de revisión "
                              "(roces de borde y dudas revisadas no cuentan)", _dudas, (AU, AR)),
                             ("auto: un video roto no frena la tanda (fila 'falla' con el motivo); carpetas con .mkv/.m4v y sin '._' de la Mac",
                              _roto, (AU,)),
                             ("auto: el mismo archivo MOVIDO de carpeta (fuente vieja sin huella) se reusa, la más corregida, sin re-ingresar "
                              "como <nombre>_2; en una corrida real se le guarda la huella (después se reconoce aunque se renombre)", _movido, (AU, IG)),
                             ("auto: un borrador del mapa corregido a mano y sin aprobar NO se rehace con el mapper nuevo (y cuenta como "
                              "corrección); el que quedó tal cual lo escribió mapper.py sí", _borrador, (AU, IG))):
        tmp = tempfile.mkdtemp(prefix="pr_auto_")
        try: ok, det = fn(*args, tmp)
        except Exception as e: ok, det = False, repr(e)
        finally: shutil.rmtree(tmp, ignore_errors=True)
        check(nombre, ok, det)
