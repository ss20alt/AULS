# Estudio de edición — UN SOLO COMANDO para cualquier video: lo entiende (entender.py), elige el formato y lo edita de punta a punta.
#   python auto.py <video>                       -> conferencia/discurso/mensaje: declaración (estilo redes) · TV: estilo datos ·
#                                                   reunión: prepara y pide confirmar nombres · evento/toma corta: montaje con música
#   python auto.py <carpeta>                     -> cada video suelto se edita; las tomas de un mismo evento van juntas a un montaje
#   opciones: --length auto|1min|3min|4min|completo · --tema "nombres propios" · --titulo "TÍTULO" (eventos/reunión) · --sub "fecha"
#             --gancho bn|color|no · --cifras auto|no|mas · --insertos <carpeta> · --broll <carpeta> · --fondo rosa · --no-deliver
#             --solo-plan (no prepara nada: muestra qué haría)
# La duración por defecto ("auto") sigue al equipo: si lo que ella dice dura ≤ 4 min se publica la declaración ENTERA; si es más
# largo (un discurso), lo más importante en ≈ 2 min.
# El MISMO archivo ya ingresado (con cualquier nombre) no se re-ingresa: se usa la fuente con más correcciones humanas (hablante,
# texto, mapa aprobado, datos.json) y el informe lo dice. El informe también avisa las dudas del árbitro sin revisar que quedaron
# DENTRO del video ("ok con aviso"). Un video roto o a medio copiar no frena la tanda: queda como "falla" con el motivo.
import os, sys, json, re, subprocess, time, argparse, datetime

STUDIO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDIO)
PY = sys.executable
log = lambda *a: print("[auto]", *a, flush=True)


def slug(path, info=None):
    b = os.path.splitext(os.path.basename(path))[0].lower()
    for a, c in zip("áéíóúñ", "aeioun"): b = b.replace(a, c)
    b = re.sub(r"[^a-z0-9]+", "_", b).strip("_")[:24]
    return "auto_" + (b or "video")


RESULTADOS = []                                                         # informe final: qué se hizo con cada cosa
MIN_DECL = 25.0                                                         # menos de esto de voz útil de ella no es una declaración
VID = (".mp4", ".mov", ".m4v", ".mkv")                                  # los mismos que entender.VID (antes un .mkv de la carpeta quedaba afuera)
QA_ES = {"FACE_SMALL": "cara chica (el original es de baja resolución)", "FACE_LOST": "la cara no se ve todo el tiempo",
         "FACE_BIG": "cara demasiado grande", "PACE_SLOW": "ritmo tranquilo (tomas largas)", "DARK": "imagen oscura",
         "LUFS": "volumen fuera de lo normal", "TP": "picos de audio", "MUSIC_LOW": "música casi inaudible", "MUSIC_HIGH": "música alta",
         "FREEZE": "imagen congelada", "BLACK": "cuadros negros", "MIDSENTENCE": "corte a mitad de frase", "DUR": "duración distinta a la pedida",
         "CONTRAST": "texto con poco contraste", "TEXT_ON_FACE": "texto sobre la cara", "SAFE_ZONE": "texto cerca del borde",
         "CLIPPED": "texto cortado", "MIRROR": "borde espejado", "CARD_BLEND": "tarjeta poco visible",
         "SOLAPE": "textos que se pisan (título y subtítulo)", "QA": "el control no pudo correr entero", "QA_ERR": "el control visual no pudo correr",
         "CUT_VOICE": "corte sobre una voz", "OTHER_VOICE": "voz de otra persona", "CPS": "subtítulo demasiado rápido",
         "SUB_COV": "subtítulos que no cubren lo que se dice", "SUB_SHORT": "subtítulo demasiado corto", "TXT": "texto distinto a lo dicho",
         "CARA_AJENA": "se ve la cara de otra persona mientras habla", "PLACA_CARA": "la placa de nombre va sobre otra persona",
         "PLACA_NOMBRE": "el nombre de la placa no coincide con la persona reconocida"}


def run(cmd, env=None):
    """corre un paso mostrando su salida en vivo y guardándola (para el informe: qué salió, qué no y por qué)"""
    log("→", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    e = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    p = subprocess.Popen(cmd, cwd=STUDIO, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    lines = []
    for ln in p.stdout:
        lines.append(ln.rstrip("\n"))
        if not any(x in ln.lower() for x in ("warning", "warn(", "loading weights", "key_padding_mask")): print(ln, end="", flush=True)
    p.wait()
    run.last = lines
    return p.returncode
run.last = []


def resultado(video, formato, rc, proyecto=None):
    """resume la corrida recién hecha: estado, archivo y motivo (leído de la salida del paso)"""
    L = run.last; txt = "\n".join(L)
    estado, motivo, salida = "ok", "", None
    for ln in L:
        if "listo en" in ln and "->" in ln: salida = ln.split("->")[-1].strip()
        if "entregado en" in ln or "también en" in ln: pass
    if "Traceback" in txt:
        estado = "falla"; motivo = next((l for l in reversed(L) if l.strip() and not l.startswith(" ")), "error")[:200]
    elif rc and not motivo:
        estado = "falla"
        motivo = next((l.strip() for l in L if "✗" in l), f"código {rc}")[:200]
    else:
        fr = [l.strip() for l in L if "✗" in l or "HALLAZGOS" in l or "no se entrega" in l]
        if fr: estado = "no entregado"; motivo = fr[-1][:200]
        av = [l.strip() for l in L if l.strip().startswith("! ") or "AVISO" in l]
        if av and estado == "ok": estado = "ok con aviso"; motivo = av[-1][:200]
        qj = os.path.join(STUDIO, "projects", proyecto or "-", "qa.json")
        if estado in ("ok", "ok con aviso") and proyecto and os.path.exists(qj):   # hallazgos del control final, dichos en palabras
            try:
                F = json.load(open(qj, encoding="utf-8"))["findings"]
                med = [QA_ES.get(f[1], f[1]) for f in F if f[0] in ("media", "alta")]
                baj = [QA_ES.get(f[1], f[1]) for f in F if f[0] == "baja"]
                if med: estado = "ok con aviso"; motivo = "; ".join(med + baj)[:200]
                elif baj and not motivo: motivo = "detalles menores: " + "; ".join(baj)
            except Exception: pass
    RESULTADOS.append(dict(video=video, formato=formato, estado=estado, motivo=motivo, salida=salida, proyecto=proyecto))
    return rc


def avisar(x, texto, primero=False):
    """suma un aviso al detalle de una fila del informe (primero = lo que hay que hacer va adelante: la consola corta a 90 letras)"""
    if not texto: return
    m = x.get("motivo") or ""
    x["motivo"] = (texto + ("; " + m if m else "")) if primero else ((m + " · " if m else "") + texto)


# ------------------------------------------------------------------ dudas del árbitro DENTRO del video editado
# arbitro.json se genera en cada ingesta (whisper escribió una cosa y el modelo acústico oye otra) y nadie lo leía: un video podía
# entregarse con «2025 hubo 258» dudoso en el gancho. Se cruzan las dudas SIN revisar con los tramos de la fuente que entraron.
def tramos_usados(proyecto):
    """tramos de la FUENTE (segundos) que entran en el video editado: edl.json (fs/fe en cuadros de la fuente, con la respiración
    previa 'pre'); si no hay EDL, el guion de cfg.json (["seg", id, rol, desde, hasta])"""
    pd = proyecto if os.path.isabs(proyecto) else os.path.join(STUDIO, "projects", proyecto)
    try:
        e = json.load(open(os.path.join(pd, "edl.json"), encoding="utf-8")); fps = float(e.get("fps") or 30)
        T = [((it["fs"] - it.get("pre", 0)) / fps, it["fe"] / fps) for it in e["items"] if it.get("kind") == "speech"]
        if T: return T
    except Exception: pass
    try: return [(float(s[3]), float(s[4])) for s in json.load(open(os.path.join(pd, "cfg.json"), encoding="utf-8"))["script"] if str(s[0]).startswith("seg")]
    except Exception: return []


def dudas_en_video(proyecto, fuente=None):
    """dudas del árbitro SIN revisar que caen dentro del video editado -> (fuente, [ítems], la más grave primero)"""
    pd = proyecto if os.path.isabs(proyecto) else os.path.join(STUDIO, "projects", proyecto)
    if fuente is None:
        try: fuente = json.load(open(os.path.join(pd, "cfg.json"), encoding="utf-8")).get("source")
        except Exception: fuente = None
    T = tramos_usados(pd)
    if not fuente or not T: return fuente, []
    import arbitro as AR
    return fuente, AR.pendientes(fuente, T)


def aviso_dudas(x, proyecto, fuente):
    """fila del informe: 'ok' -> 'ok con aviso' si hay dudas de transcripción sin revisar dentro del video (y cuáles, en el .json)"""
    try: fuente, du = dudas_en_video(proyecto, fuente)
    except Exception as e: log(f"(no se pudieron leer las dudas del árbitro: {e!r})"); return
    if not du: return
    x["dudas"] = [dict(t=d["t0"], quien=d.get("quien"), sev=d.get("sev"), texto=d.get("dudosas") or d.get("whisper"), oye=d.get("oye")) for d in du]
    n = len(du)
    msg = f"{n} {'duda' if n == 1 else 'dudas'} de transcripción sin revisar (python arbitro.py review {fuente})"
    d0 = du[0]
    log(f"! {msg} — la más grave en {int(d0['t0'] // 60)}:{d0['t0'] % 60:04.1f}: «{(d0.get('dudosas') or d0.get('whisper') or '').strip()}»"
        f" (el modelo oye «{d0.get('oye', '')}»)")
    if x["estado"] in ("ok", "ok con aviso"): x["estado"] = "ok con aviso"; avisar(x, msg, primero=True)
    else: avisar(x, msg)


def historias(name):
    """historias (ángulos) del mapa de la fuente: un mapa aprobado a mano puede no tener 'resumen' (el del Senado: juzgados, …)"""
    out = subprocess.run([PY, "-c", "import content as C; print('|'.join(C.STORIES))"], cwd=STUDIO,
                         env=dict(os.environ, STUDIO_SOURCE=name, PYTHONIOENCODING="utf-8"), capture_output=True, text=True)
    try: return [x for x in out.stdout.strip().splitlines()[-1].split("|") if x]
    except Exception: return []


def her_speech(name):
    """segundos de voz de ella en la fuente ya ingresada (para elegir declaración entera o resumen)"""
    out = subprocess.run([PY, "-c", "import content as C; print(sum(s['dur'] for s in C.SENT if s['spk']=='L'))"], cwd=STUDIO,
                         env=dict(os.environ, STUDIO_SOURCE=name, PYTHONIOENCODING="utf-8"), capture_output=True, text=True)
    try: return float(out.stdout.strip().splitlines()[-1])
    except Exception: return None


def fuente_previa(path, layout=None, dur=None, nombre=None, sellar=False):
    """¿este MISMO archivo ya entró como fuente, con cualquier nombre? (por el ARCHIVO ORIGINAL: huella, o ruta + duración, o nombre
    de archivo + duración si cambió de carpeta; antes solo por el nombre armado del archivo, y LS1 ya corregido a mano en
    lilian_senado_feminicidios volvió a entrar como auto_2026_10_14_ls1 sin sus correcciones). `nombre`: el nombre armado (slug) de
    este archivo; `sellar`: guardar la huella en las fuentes viejas reconocidas (solo en una corrida real)
    -> dict(name=la más corregida que sirve para este formato o None, aviso, tema, todas)"""
    import ingest as IG
    cs = IG.fuentes_del_original(path, dur, propio=nombre, sellar=sellar)
    if not cs: return dict(name=None, aviso="", tema="", todas=[])
    panel = layout == "panel"
    sirven = [c for c in cs if c["usable"] and (c["layout"] == "panel") == panel]     # mismo formato de video de trabajo (panel TV o no)
    tema = next((c["tema"] for c in cs if c["tema"]), "")
    if not sirven:
        por = "le faltan archivos de trabajo" if not any(c["usable"] for c in cs) else f"no está en formato {'panel' if panel else 'vertical'}"
        return dict(name=None, tema=tema, todas=cs, aviso=f"este archivo ya entró como {', '.join('sources/' + c['name'] for c in cs)}, pero {por}: "
                                                          f"se ingresa de nuevo y se le traen sus correcciones")
    c = sirven[0]
    det = f" ({', '.join(c['detalle'])})" if c["detalle"] else ""
    if len(cs) > 1:
        aviso = (f"este archivo ya entró {len(cs)} veces ({', '.join(x['name'] for x in cs)}): se usa la más corregida a mano, "
                 f"sources/{c['name']}{det}")
    else: aviso = f"fuente ya ingresada: sources/{c['name']}{det}"
    if cs[0] is not c:                                                   # la más corregida no sirve acá (otra PC sin sus archivos, otro formato)
        aviso += (f" — sources/{cs[0]['name']} tiene más correcciones ({', '.join(cs[0]['detalle'])}) pero "
                  + ("le faltan archivos de trabajo" if not cs[0]["usable"] else "está en otro formato"))
    if c.get("por") == "nombre": aviso += " (reconocida por el nombre del archivo y su duración: el video cambió de carpeta)"
    return dict(name=c["name"], aviso=aviso, tema=tema, todas=cs, corregida=bool(c["detalle"]), detalle=c["detalle"])


def refrescar_borrador(name):
    """fuente reutilizada SIN mapa aprobado: el borrador automático se rehace con las reglas de hoy (mapper.py mejora seguido: un
    borrador viejo conserva titulares que hoy el control rechaza, como «CABALLERO LEVANTÓ» de §3w). Solo texto, segundos. El mapa
    aprobado (content.json) no se toca. El viejo se aparta antes (content.py lo leería al importarse) y vuelve si algo falla.
    NUNCA se rehace un borrador corregido a mano (la página de revisión pide «editar content_draft.json» para corregir): antes
    bastaba con editar mapper.py, o descomprimir el paquete en otra PC, para pisar sin aviso esas correcciones todavía sin aprobar.
    Si no se puede saber (falta content_review.html), tampoco se toca"""
    import ingest as IG
    d = os.path.join(STUDIO, "sources", name)
    if os.path.exists(os.path.join(d, "content.json")): return
    dr = os.path.join(d, "content_draft.json"); bk = os.path.join(d, "content_draft.prev.json")
    if os.path.exists(dr):
        ed = IG.borrador_editado(d)
        if ed: log(f"   el borrador del mapa de sources/{name} está corregido a mano y sin aprobar: se usa tal cual (no se rehace). "
                   f"Para aprobarlo: python mapper.py approve {name}"); return
        if ed is None: return                                           # sin content_review.html no se sabe si alguien lo corrigió
        try: cl = json.load(open(os.path.join(d, "source.json"), encoding="utf-8")).get("client", "lilian")
        except Exception: cl = "lilian"
        ref = [os.path.join(STUDIO, "mapper.py"), os.path.join(STUDIO, "clients", f"{cl}.json")]   # reglas o glosario de la ficha más nuevos:
        if os.path.getmtime(dr) >= max(os.path.getmtime(x) for x in ref if os.path.exists(x)): return   # el texto cambió -> se rehace
    try:
        if os.path.exists(dr): os.replace(dr, bk)
        out = subprocess.run([PY, "-c", "import sys, mapper; mapper.draft(sys.argv[1])", name], cwd=STUDIO, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=dict(os.environ, STUDIO_SOURCE=name, PYTHONIOENCODING="utf-8"))
        ok = out.returncode == 0 and os.path.exists(dr)
        log(f"   borrador del mapa rehecho con las reglas de hoy (sources/{name})" if ok
            else f"   (no se pudo rehacer el borrador del mapa: {(out.stderr or '').strip().splitlines()[-1:]}; queda el anterior)")
    except OSError as e: ok = False; log(f"   (no se pudo rehacer el borrador del mapa: {e})")
    if not ok and os.path.exists(bk): os.replace(bk, dr)               # se vuelve al borrador anterior: nunca queda la fuente sin mapa


def ingresar(r, a, layout=None):
    """ingesta (una vez por ARCHIVO): nombre de la fuente, o None si falló. Si el mismo archivo ya entró (con cualquier nombre) se
    usa la fuente con más correcciones humanas y el log lo dice; r["fuente_nota"] queda para el informe"""
    name = a.name or slug(r["path"])
    tema, hacer = a.tema, not os.path.exists(os.path.join(STUDIO, "sources", name, "source.json"))
    if not a.name:                                                       # --name manda: el usuario pidió esa fuente
        # (sources/<nombre armado> sin huella y con la misma duración es ESTE archivo aunque se haya movido de carpeta: se reusa como
        # antes, sin re-ingresar como <nombre>_2; en una corrida real se le guarda la huella a las fuentes viejas reconocidas)
        pv = fuente_previa(r["path"], layout, (r.get("info") or {}).get("dur"), nombre=name, sellar=not a.solo_plan)
        if pv["aviso"]: log(pv["aviso"])
        if pv["name"]:
            if pv.get("corregida") and pv["name"] != name: r["fuente_nota"] = f"se usó la fuente corregida {pv['name']} ({', '.join(pv['detalle'])})"
            if a.tema: log(f"   (--tema no se vuelve a aplicar: la transcripción de sources/{pv['name']} ya está hecha)")
            if not a.solo_plan: refrescar_borrador(pv["name"])
            return pv["name"]
        tema = a.tema or pv["tema"]                                      # los nombres que ya se dieron para este mismo archivo (mejoran la transcripción)
        mio = next((c for c in pv["todas"] if c["name"] == name), None)
        if mio and not mio["usable"]: hacer = True                       # este archivo, con este nombre, sin sus archivos de trabajo: se rehace (las correcciones quedan)
        elif not hacer:                                                  # ese nombre es de OTRO archivo (IMG_4572 de otro teléfono) o de este en otro formato
            k = 2
            while os.path.exists(os.path.join(STUDIO, "sources", f"{name}_{k}")): k += 1
            log(f"sources/{name} es {'de este archivo en otro formato' if mio else 'de otro archivo con el mismo nombre'}: este entra como sources/{name}_{k}")
            name, hacer = f"{name}_{k}", True
    if hacer:
        cmd = [PY, "ingest.py", r["path"], "--name", name] + (["--tema", tema] if tema else []) + (["--layout", layout] if layout else [])
        if a.solo_plan: log(f"(solo plan) ingresaría: {' '.join(cmd[1:])}")
        elif run(cmd): log("✗ la ingesta falló"); resultado(os.path.basename(r["path"]), "ingesta", 1); return None
    else: log(f"fuente ya ingresada: sources/{name}")
    return name


def editar_declaracion(r, a, layout=None):
    name = ingresar(r, a, layout)
    if name is None: return 1
    sp = None
    style = "datos" if layout == "panel" else (a.estilo or "redes")
    length, angle = a.length, a.angle
    if not angle:
        if length in ("completo", "auto"):
            sp = her_speech(name)                                       # (en --solo-plan, solo si ya estaba ingresado)
            if length == "completo" or (sp is not None and sp <= 240): angle, length = "completo", "auto"
            else: angle, length = "resumen", "auto"
            log(f"duración: {'declaración entera' if angle == 'completo' else 'lo más importante (≈ 2 min)'}"
                + (f" — ella habla {sp:.0f} s" if sp else ""))
        else: angle = "resumen"
        hs = historias(name)
        if hs and angle not in hs:                                       # el mapa no tiene ese ángulo: el más parecido que sí tenga
            otras = [x for x in hs if x != "completo"]                    # discurso largo (> 4 min de su voz): la historia del editor, no
            alt = next((x for x in ("resumen", "mensaje") if x in hs), None) or (   # la declaración entera de 6 min
                "completo" if "completo" in hs and ((sp or 0) <= 240 or not otras) else (otras or hs)[0])
            log(f"   el mapa de sources/{name} no tiene la historia '{angle}': se usa '{alt}' (historias: {', '.join(hs)})"); angle = alt
    cmd = [PY, "make_video.py", "--style", style, "--angle", angle, "--name", f"{name}_{style}_{angle}"]
    if length and length != "auto": cmd += ["--length", length]
    for k in ("gancho", "cifras", "fondo"):
        if getattr(a, k): cmd += [f"--{k}", getattr(a, k)]
    for k in ("insertos", "broll"):
        if getattr(a, k): cmd += [f"--{k}"] + getattr(a, k)
    if a.no_deliver: cmd.append("--no-deliver")
    if a.solo_plan: log(f"(solo plan) editaría: STUDIO_SOURCE={name} {' '.join(cmd[1:])}"); return 0
    rc = run(cmd, env=dict(STUDIO_SOURCE=name))
    rc = resultado(os.path.basename(r["path"]), f"{style} · {'declaración entera' if angle == 'completo' else angle}", rc, f"{name}_{style}_{angle}")
    x = RESULTADOS[-1]; x["fuente"] = name
    if sp is not None and sp < MIN_DECL and x["estado"] == "ok":
        x.update(estado="ok con aviso", motivo=f"muy corto: ella habla solo {sp:.0f} s útiles")
    if x["estado"] != "falla": aviso_dudas(x, f"{name}_{style}_{angle}", name)    # dudas de transcripción sin revisar DENTRO del video
    avisar(x, r.get("fuente_nota"))                                     # «se usó la fuente corregida …» (el mismo archivo ya estaba corregido)
    return rc


def editar_reunion(r, a):
    name = a.name or slug(r["path"])
    prev = reunion_previa(r["path"])
    if prev:                                                            # ya preparada y aprobada: se edita ESA (nombres y caras confirmados)
        name, tprev = prev
        log(f"REUNIÓN: este mismo video ya está preparado y con nombres aprobados (sources/{name}) -> se edita con eso")
        conocidos = ([], tprev)
    else:
        cmd = [PY, "reunion.py", "ingest", r["path"], "--name", name] + (["--tema", a.tema] if a.tema else [])
        if a.solo_plan: log(f"(solo plan) {' '.join(cmd[1:])}"); return 0
        rc = run(cmd)
        if rc: return resultado(os.path.basename(r["path"]), "reunión", rc)
        conocidos = reunion_conocida(name, r["path"])
    if a.solo_plan: log(f"(solo plan) reunion.py edit {name}"); return 0
    if conocidos:                                                       # personas ya confirmadas (voz + cara) o reunión ya aprobada: se edita
        nombres, titulo_prev = conocidos
        titulo = a.titulo or titulo_prev
        if not titulo:                                                  # título descriptivo (no inventa lo que pasó): pasá --titulo
            pj_ = os.path.join(STUDIO, "sources", name, "reunion", "people.json")
            invit = [n for n in nombres if n] or [v.get("name") for k, v in json.load(open(pj_, encoding="utf-8"))["people"].items() if k != "L"]
            titulo = "REUNIÓN DE TRABAJO|CON " + " Y ".join(x.upper() for x in invit) if invit else "REUNIÓN DE TRABAJO"
            if len(titulo.split("|")[-1]) > 40: titulo = "REUNIÓN DE TRABAJO|CON " + " Y ".join(x.split()[-1].upper() for x in invit)
        if nombres:
            log(f"REUNIÓN: todas las personas ya fueron confirmadas antes y se reconocen por voz y cara ({', '.join(nombres)}) -> se edita directo")
            run([PY, "reunion.py", "people", name, "approve"])
        log(f"   título «{titulo}»")
        L = {"1min": 60, "3min": 180, "4min": 240, "completo": 240}.get(a.length, 150)
        cmd = [PY, "reunion.py", "edit", name, "--length", str(L), "--titulo", titulo, "--proj", f"auto_reunion_{name}_{L}s"] + (["--no-deliver"] if a.no_deliver else [])
        rc = run(cmd)
        out = next((ln.split("->")[-1].strip() for ln in run.last if "listo en" in ln and "->" in ln), None)
        rc = resultado(os.path.basename(r["path"]), "reunión", rc, None)
        x = RESULTADOS[-1]
        if out: x["salida"] = out
        if any("CON HALLAZGOS" in ln for ln in run.last): x.update(estado="no entregado", motivo="el control final encontró problemas (ver qa del proyecto)")
        elif not a.titulo and not titulo_prev and x["estado"] == "ok": x.update(estado="ok con aviso", motivo="título descriptivo genérico: pasá --titulo")
        return rc
    RESULTADOS.append(dict(video=os.path.basename(r["path"]), formato="reunión", estado="espera nombres",
                           motivo=f"confirmar nombres: python reunion.py people {name} … approve, luego reunion.py edit", salida=None, proyecto=name))
    log("REUNIÓN preparada. Antes de editar hay que CONFIRMAR los nombres (no se adivinan):")
    log(f"  python reunion.py people {name}                      (ver people.png)")
    log(f'  python reunion.py people {name} set S1 "Nombre" "Cargo"   …   python reunion.py people {name} approve')
    log(f'  python reunion.py edit {name} --length 150 --titulo "LÍNEA 1|LÍNEA 2"')
    return 0


def reunion_previa(path):
    """el MISMO archivo ya preparado y con nombres aprobados en otra fuente -> (fuente, título) o None (se edita esa, no se re-adivina)"""
    for d in sorted(os.listdir(os.path.join(STUDIO, "sources"))):
        sj = os.path.join(STUDIO, "sources", d, "reunion", "source.json"); pp = os.path.join(STUDIO, "sources", d, "reunion", "people.json")
        if not (os.path.exists(sj) and os.path.exists(pp)): continue
        try:
            src = json.load(open(sj, encoding="utf-8"))
            if os.path.abspath(src.get("original", "")) == os.path.abspath(path) and json.load(open(pp, encoding="utf-8")).get("approved"):
                return d, src.get("titulo")
        except Exception: continue
    return None


def reunion_conocida(name, path):
    """¿todas las personas de la reunión las confirmó el usuario antes Y se reconocen por VOZ y por CARA a la vez? (la cara sola
    no alcanza: en IMG_4801 la sincronía de labios asignó la voz de Mussi a la cara de Aarón) -> (nombres, None) o None"""
    pj = os.path.join(STUDIO, "sources", name, "reunion", "people.json")
    if not os.path.exists(pj): return None
    ppl = json.load(open(pj, encoding="utf-8"))["people"]
    nombres = []
    for spk, x in ppl.items():
        if spk == "L": continue
        if not x.get("source", "").startswith("reconocido por su voz y su cara"): return None
        nombres.append(x.get("name", ""))
    return (nombres, None) if nombres else None


def editar_evento(paths, a, fecha=None):
    titulo = a.titulo or "UN DÍA CON LA GENTE"
    sub = a.sub or (fecha.strftime("%d de %B").lstrip("0") if fecha else "")
    for en, es in (("January", "enero"), ("February", "febrero"), ("March", "marzo"), ("April", "abril"), ("May", "mayo"), ("June", "junio"),
                   ("July", "julio"), ("August", "agosto"), ("September", "septiembre"), ("October", "octubre"), ("November", "noviembre"), ("December", "diciembre")):
        sub = sub.replace(en, es)
    name = a.name or ("auto_evento_" + (fecha.strftime("%Y%m%d_%H%M") if fecha else str(int(time.time())))   # + huella de las tomas:
                       + "_" + __import__("hashlib").md5("|".join(sorted(os.path.abspath(x) for x in paths)).encode()).hexdigest()[:5])   # dos grupos del mismo minuto no comparten carpeta
    cmd = [PY, "evento.py"] + paths + ["--titulo", titulo, "--name", name] + (["--sub", sub] if sub else []) + (["--tema", a.tema] if a.tema else [])
    if a.no_deliver: cmd.append("--no-deliver")
    if a.solo_plan: cmd.append("--no-render"); log(f"(solo plan) montaje de {len(paths)} tomas: título «{titulo}» {sub}")
    if not a.titulo: log("AVISO: sin --titulo; se usa uno genérico. Pasá el nombre del evento (p. ej. --titulo \"CUMPLEAÑOS DE ARNALDO\").")
    rc = run(cmd)
    if a.solo_plan: return rc
    out = os.path.join(STUDIO, "projects", name, f"{name}.mp4")
    rc = resultado(", ".join(os.path.basename(x) for x in paths)[:90], f"montaje de evento ({len(paths)} tomas)", rc, name)
    if RESULTADOS and RESULTADOS[-1]["salida"] is None and os.path.exists(out): RESULTADOS[-1]["salida"] = out
    if not a.titulo and RESULTADOS[-1]["estado"] == "ok": RESULTADOS[-1].update(estado="ok con aviso", motivo="título genérico: pasá --titulo")
    return rc


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada", nargs="+"); ap.add_argument("--length", default="auto", choices=["auto", "1min", "3min", "4min", "completo"])
    ap.add_argument("--angle"); ap.add_argument("--estilo"); ap.add_argument("--tema", default=""); ap.add_argument("--name")
    ap.add_argument("--titulo", default=""); ap.add_argument("--sub", default="")
    ap.add_argument("--gancho", choices=["bn", "color", "no"]); ap.add_argument("--cifras", choices=["auto", "no", "mas"])
    ap.add_argument("--fondo"); ap.add_argument("--insertos", nargs="+"); ap.add_argument("--broll", nargs="+")
    ap.add_argument("--no-deliver", action="store_true"); ap.add_argument("--solo-plan", action="store_true")
    a = ap.parse_args()
    import entender as EN
    if not a.solo_plan:                                                   # lo que falta en ESTA PC (ffmpeg, modelos, huellas) se dice UNA vez
        try: EN.revisar_estudio(hdr=False)                                # y corta la tanda: no son videos "rotos" (zscale lo pide cada HDR)
        except EN.FallaEstudio as e:
            log(f"✗ falta algo en esta PC (no es culpa de los videos): {e}")
            RESULTADOS.append(dict(video="(instalación)", formato="estudio", estado="falla", motivo=str(e)[:200], salida=None, proyecto=None))
            informe([], a); return 2
    try: rs = leer(listar(a.entrada), EN)                                 # un video roto no frena la tanda: queda como "falla" en el informe
    except EN.FallaEstudio as e:                                          # pero si falta algo en la PC a mitad de la lectura, se corta ahí
        log(f"✗ falta algo en esta PC (no es culpa de los videos): {e}")
        RESULTADOS.append(dict(video="(instalación)", formato="estudio", estado="falla", motivo=str(e)[:200], salida=None, proyecto=None))
        informe([], a); return 2
    rc = int(any(x["estado"] == "falla" for x in RESULTADOS))            # (y la salida lo dice: código 1)
    # 1) se agrupa TODO por evento (misma fecha, tomas cercanas); dentro de cada evento decide como un editor:
    #    · si ella habla (declaración/discurso) -> ese video se edita, y las tomas sueltas del MISMO evento tapan sus saltos (--broll)
    #    · si solo hay tomas sueltas -> montaje con música (si hay ≥ 12 s de material)
    try: grupos = EN.grupos([r for r in rs if r.get("fecha")]) + [[r] for r in rs if not r.get("fecha")]
    except Exception as e: log(f"✗ no se pudieron agrupar por evento ({e!r}): cada video va solo"); grupos = [[r] for r in rs]
    for g in grupos:                                                      # un error en un evento no frena los demás
        rc |= seguro(", ".join(r["file"] for r in g), "evento" if len(g) > 1 else "video", editar_grupo, g, a, EN)
    informe(rs, a)
    return rc


def listar(entradas):
    """videos de las entradas (carpetas o archivos): .mp4 .mov .m4v .mkv; sin los '._x' que deja la Mac al copiar a un disco"""
    vids = []
    for e in entradas:                                                    # una carpeta, uno o varios videos
        if os.path.isdir(e): vids += [os.path.join(e, f) for f in sorted(os.listdir(e)) if f.lower().endswith(VID) and not f.startswith("._")]
        else: vids.append(e)
    return vids


class Ilegible(Exception):
    """entender lo marcó como 'roto' (o sin duración): el mensaje ya es el motivo en palabras"""


def motivo_lectura(e):
    """por qué no se pudo leer un video, en palabras (para el informe)"""
    if isinstance(e, Ilegible): return f"no se pudo leer: {e}"[:200]
    if isinstance(e, FileNotFoundError): return "no se encontró el archivo"
    if isinstance(e, PermissionError): return "el archivo está en uso o bloqueado (¿se está copiando o sincronizando?)"
    return f"no se pudo leer el video (archivo incompleto, dañado o todavía sincronizándose): {type(e).__name__}: {e}"[:200]


def leer(vids, EN):
    """entiende cada video. Uno roto (grabación cortada por batería, archivo de Drive a medio bajar: ffprobe devuelve '{}' y
    entender saltaba con KeyError('streams'); ahora entender lo devuelve como tipo 'roto' con el motivo) NO frena la tanda y NO se
    edita: queda en el informe como 'falla' con el motivo y se sigue con los demás"""
    rs, vistos = [], set()
    for v in vids:
        try:
            if not os.path.isfile(v): raise FileNotFoundError(v)
            if os.path.getsize(v) == 0: raise Ilegible("archivo vacío (0 bytes): todavía se está copiando o sincronizando")
            with open(v, "rb") as fh: k = (os.path.getsize(v), fh.read(1 << 20))      # copias idénticas ("x (1).mp4"): una sola vez
            if k in vistos: log(f"copia repetida, se ignora: {os.path.basename(v)}"); continue
            vistos.add(k)
            r = EN.entender(v)
            ro = (r.get("info") or {}).get("roto")
            if r.get("tipo") == "roto" or ro: raise Ilegible(ro or "archivo roto o incompleto")
            if not ((r.get("info") or {}).get("dur") or 0) > 0: raise Ilegible("sin duración: el archivo quedó incompleto")
        except Exception as e:
            if isinstance(e, getattr(EN, "FallaEstudio", ())): raise   # falta algo en la PC: no se culpa a cada video
            m = motivo_lectura(e)
            log(f"✗ {os.path.basename(v)}: {m} -> se sigue con los demás")
            RESULTADOS.append(dict(video=os.path.basename(v), formato="entender", estado="falla", motivo=m, salida=None, proyecto=None))
            continue
        rs.append(r)
        try: print(EN.ficha(r), flush=True)
        except Exception as e: log(f"(ficha de {r.get('file')}: {e!r})")
    return rs


def seguro(nombre, formato, fn, *args):
    """corre la edición de un video o evento; un error de Python (no de un paso, que ya queda en el informe) no frena la tanda:
    queda como 'falla' con el motivo y se sigue con lo demás"""
    try: return fn(*args) or 0
    except Exception as e: return falla_inesperada(nombre, formato, e)


def falla_inesperada(nombre, formato, e):
    import traceback; traceback.print_exc(file=sys.stdout)                 # (en la salida de la tanda, junto al resto del registro)
    log(f"✗ error con {nombre[:80]}: {e!r} -> se sigue con lo demás")
    RESULTADOS.append(dict(video=nombre[:90], formato=formato, estado="falla", motivo=f"error del autoeditor: {type(e).__name__}: {e}"[:200],
                           salida=None, proyecto=None))
    return 1


DECL = ("conferencia", "discurso", "mensaje")


def editar_grupo(g, a, EN):
    """un evento (o un video solo): decide qué se edita y cómo, como un editor"""
    rc = 0
    f = datetime.datetime.fromisoformat(g[0]["fecha"]) if g[0].get("fecha") else None
    # ella habla pero filmada de lejos (cara < 5 % del alto: mesa principal, escenario): no da para una declaración vertical ->
    # su voz va DENTRO del montaje del evento, con subtítulo, sobre las tomas (así lo resuelve un editor)
    lejos = [r for r in g if r["tipo"] in DECL and ((r.get("video") or {}).get("face_big") or 0) < 0.05]
    for r in lejos: log(f"{r['file']}: ella habla pero filmada de lejos (cara {100 * (r['video'].get('face_big') or 0):.0f} % del alto) -> va al montaje del evento con su voz")
    decl = [r for r in g if r["tipo"] in DECL and r not in lejos]
    sueltas = [r for r in g if r["tipo"] in ("evento", "clip")] + lejos
    # ella habla, pero casi todo es charla / pide no grabar (5-ene: 40 s de video, 16 s útiles de saludo): con otras tomas del
    # mismo evento eso no es una declaración -> va al montaje con su voz. Se mide después de la ingesta (voz útil real).
    if sueltas or len(decl) > 1:
        for r in list(decl):
            A = r.get("audio") or {}
            if r["info"]["dur"] * A.get("speech_ratio", 1) * A.get("lilian_share", 1) > 60: continue
            try: name = ingresar(r, a)
            except Exception as e: name = None; falla_inesperada(r["file"], "ingesta", e)     # (no frena las otras tomas del evento)
            if name is None: decl.remove(r); continue                    # la falla ya quedó en el informe
            sp = her_speech(name)                                         # (en --solo-plan, solo si ya estaba ingresado)
            if sp is not None and sp < MIN_DECL:
                log(f"{r['file']}: ella habla solo {sp:.0f} s útiles (lo demás es charla o pide no grabar): no da para una declaración "
                    f"-> va al montaje del evento con su voz")
                decl.remove(r); sueltas.append(r)
    if len(g) > 1 or sueltas:
        log(f"== EVENTO" + (f" {f:%d/%m/%Y %H:%M}" if f else "") + f" · {len(g)} videos: "
            + ", ".join(f"{r['file']} ({r['tipo']})" for r in g))
    for r in g:
        t = r["tipo"]
        if t in ("evento", "clip") or r in sueltas: continue
        if t == "editado": log(f"{r['file']}: ya está editado, no se re-edita (sirve como REFERENCIA: python analyze_batch.py refs …)"); continue
        log(f"== {r['file']} → {EN.TIPOS[t][0]}")
        if t == "reunion": rc |= seguro(r["file"], "reunión", editar_reunion, r, a)
        elif t == "tv": rc |= seguro(r["file"], "datos (TV)", editar_declaracion, r, a, "panel")
        else:
            b_ = a.broll
            if sueltas and not a.broll:
                a.broll = [x["path"] for x in sueltas]; log(f"   tomas del mismo evento para tapar los saltos: {len(sueltas)}")
            rc |= seguro(r["file"], "declaración", editar_declaracion, r, a)
            a.broll = b_
    if sueltas and not decl:
        util = sum(x["info"]["dur"] for x in sueltas)
        if util < 12.0:
            log(f"   solo {util:.0f} s de tomas sueltas: no alcanza para un montaje (mínimo 12 s). Sumá más tomas de ese evento.")
            RESULTADOS.append(dict(video=", ".join(x["file"] for x in sueltas)[:90], formato="tomas sueltas", estado="omitido",
                                   motivo=f"solo {util:.0f} s de material: no alcanza para un montaje (mínimo 12 s); sumá más tomas de ese día",
                                   salida=None, proyecto=None))
            return rc
        rc |= seguro(", ".join(x["file"] for x in sueltas), "montaje de evento", editar_evento, [x["path"] for x in sueltas], a, f)
    return rc


def informe(rs, a):
    """tabla final (también en projects/_informes/auto_<fecha>.md): cada video, qué formato, si salió y por qué no"""
    ign = [r for r in rs if r["tipo"] == "editado"]
    for r in ign: RESULTADOS.append(dict(video=r["file"], formato="ya editado", estado="sin cambios", motivo="sirve como referencia", salida=None, proyecto=None))
    if not RESULTADOS: return
    ic = {"ok": "✓", "ok con aviso": "✓!", "no entregado": "✗", "falla": "✗✗", "espera nombres": "…", "sin cambios": "·", "omitido": "–"}
    print("\n" + "=" * 100 + "\nINFORME", flush=True)
    for x in RESULTADOS:
        print(f" {ic.get(x['estado'], '?'):3s} {x['video'][:46]:46s} {x['formato'][:28]:28s} {x['estado']:15s} {x['motivo'][:90]}", flush=True)
    d = os.path.join(STUDIO, "projects", "_informes"); os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, "auto_" + time.strftime("%Y%m%d_%H%M") + ".md")
    with open(fn, "w", encoding="utf-8") as f:
        f.write("# Informe del autoeditor\n\n| | video | formato | estado | detalle | archivo |\n|---|---|---|---|---|---|\n")
        for x in RESULTADOS: f.write(f"| {ic.get(x['estado'], '?')} | {x['video']} | {x['formato']} | {x['estado']} | {x['motivo']} | {x['salida'] or ''} |\n")
    json.dump(RESULTADOS, open(fn.replace(".md", ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"informe: {fn}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
