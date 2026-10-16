# Estudio de edición — UN SOLO COMANDO para cualquier video: lo entiende (entender.py), elige el formato y lo edita de punta a punta.
#   python auto.py <video>                       -> conferencia/discurso/mensaje: declaración (estilo redes) · TV: estilo datos ·
#                                                   reunión: prepara y pide confirmar nombres · evento/toma corta: montaje con música
#   python auto.py <carpeta>                     -> cada video suelto se edita; las tomas de un mismo evento van juntas a un montaje
#   opciones: --length auto|1min|3min|4min|completo · --tema "nombres propios" · --titulo "TÍTULO" (eventos/reunión) · --sub "fecha"
#             --gancho bn|color|no · --cifras auto|no|mas · --insertos <carpeta> · --broll <carpeta> · --fondo rosa · --no-deliver
#             --solo-plan (no prepara nada: muestra qué haría)
# La duración por defecto ("auto") sigue al equipo: si lo que ella dice dura ≤ 4 min se publica la declaración ENTERA; si es más
# largo (un discurso), lo más importante en ≈ 2 min.
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
QA_ES = {"FACE_SMALL": "cara chica (el original es de baja resolución)", "FACE_LOST": "la cara no se ve todo el tiempo",
         "FACE_BIG": "cara demasiado grande", "PACE_SLOW": "ritmo tranquilo (tomas largas)", "DARK": "imagen oscura",
         "LUFS": "volumen fuera de lo normal", "TP": "picos de audio", "MUSIC_LOW": "música casi inaudible", "MUSIC_HIGH": "música alta",
         "FREEZE": "imagen congelada", "BLACK": "cuadros negros", "MIDSENTENCE": "corte a mitad de frase", "DUR": "duración distinta a la pedida",
         "CONTRAST": "texto con poco contraste", "TEXT_ON_FACE": "texto sobre la cara", "SAFE_ZONE": "texto cerca del borde",
         "CLIPPED": "texto cortado", "MIRROR": "borde espejado", "CARD_BLEND": "tarjeta poco visible"}


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


def her_speech(name):
    """segundos de voz de ella en la fuente ya ingresada (para elegir declaración entera o resumen)"""
    out = subprocess.run([PY, "-c", "import content as C; print(sum(s['dur'] for s in C.SENT if s['spk']=='L'))"], cwd=STUDIO,
                         env=dict(os.environ, STUDIO_SOURCE=name, PYTHONIOENCODING="utf-8"), capture_output=True, text=True)
    try: return float(out.stdout.strip().splitlines()[-1])
    except Exception: return None


def ingresar(r, a, layout=None):
    """ingesta (una vez por video): nombre de la fuente, o None si falló"""
    name = a.name or slug(r["path"])
    if not os.path.exists(os.path.join(STUDIO, "sources", name, "source.json")):
        cmd = [PY, "ingest.py", r["path"], "--name", name] + (["--tema", a.tema] if a.tema else []) + (["--layout", layout] if layout else [])
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
    if sp is not None and sp < MIN_DECL and RESULTADOS[-1]["estado"] == "ok":
        RESULTADOS[-1].update(estado="ok con aviso", motivo=f"muy corto: ella habla solo {sp:.0f} s útiles")
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
    name = a.name or ("auto_evento_" + (fecha.strftime("%Y%m%d_%H%M") if fecha else str(int(time.time()))))
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
    vids = []
    for e in a.entrada:                                                   # una carpeta, uno o varios videos
        if os.path.isdir(e): vids += [os.path.join(e, f) for f in sorted(os.listdir(e)) if f.lower().endswith((".mp4", ".mov", ".m4v"))]
        else: vids.append(e)
    rs, vistos = [], set()
    for v in vids:
        k = (os.path.getsize(v), open(v, "rb").read(1 << 20))           # copias idénticas ("x (1).mp4"): una sola vez
        if k in vistos: log(f"copia repetida, se ignora: {os.path.basename(v)}"); continue
        vistos.add(k)
        r = EN.entender(v); rs.append(r)
        print(EN.ficha(r), flush=True)
    rc = 0
    # 1) se agrupa TODO por evento (misma fecha, tomas cercanas); dentro de cada evento decide como un editor:
    #    · si ella habla (declaración/discurso) -> ese video se edita, y las tomas sueltas del MISMO evento tapan sus saltos (--broll)
    #    · si solo hay tomas sueltas -> montaje con música (si hay ≥ 12 s de material)
    DECL = ("conferencia", "discurso", "mensaje")
    grupos = EN.grupos([r for r in rs if r.get("fecha")]) + [[r] for r in rs if not r.get("fecha")]
    for g in grupos:
        f = datetime.datetime.fromisoformat(g[0]["fecha"]) if g[0].get("fecha") else None
        # ella habla pero filmada de lejos (cara < 5 % del alto: mesa principal, escenario): no da para una declaración vertical ->
        # su voz va DENTRO del montaje del evento, con subtítulo, sobre las tomas (así lo resuelve un editor)
        lejos = [r for r in g if r["tipo"] in DECL and (r["video"].get("face_big") or 0) < 0.05]
        for r in lejos: log(f"{r['file']}: ella habla pero filmada de lejos (cara {100 * (r['video'].get('face_big') or 0):.0f} % del alto) -> va al montaje del evento con su voz")
        decl = [r for r in g if r["tipo"] in DECL and r not in lejos]
        sueltas = [r for r in g if r["tipo"] in ("evento", "clip")] + lejos
        # ella habla, pero casi todo es charla / pide no grabar (5-ene: 40 s de video, 16 s útiles de saludo): con otras tomas del
        # mismo evento eso no es una declaración -> va al montaje con su voz. Se mide después de la ingesta (voz útil real).
        if sueltas or len(decl) > 1:
            for r in list(decl):
                A = r.get("audio") or {}
                if r["info"]["dur"] * A.get("speech_ratio", 1) * A.get("lilian_share", 1) > 60: continue
                name = ingresar(r, a)
                if name is None: decl.remove(r); continue                # la falla ya quedó en el informe
                sp = her_speech(name)                                     # (en --solo-plan, solo si ya estaba ingresado)
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
            if t == "reunion": rc |= editar_reunion(r, a) or 0
            elif t == "tv": rc |= editar_declaracion(r, a, layout="panel") or 0
            else:
                b_ = a.broll
                if sueltas and not a.broll:
                    a.broll = [x["path"] for x in sueltas]; log(f"   tomas del mismo evento para tapar los saltos: {len(sueltas)}")
                rc |= editar_declaracion(r, a) or 0
                a.broll = b_
        if sueltas and not decl:
            util = sum(x["info"]["dur"] for x in sueltas)
            if util < 12.0:
                log(f"   solo {util:.0f} s de tomas sueltas: no alcanza para un montaje (mínimo 12 s). Sumá más tomas de ese evento.")
                RESULTADOS.append(dict(video=", ".join(x["file"] for x in sueltas)[:90], formato="tomas sueltas", estado="omitido",
                                       motivo=f"solo {util:.0f} s de material: no alcanza para un montaje (mínimo 12 s); sumá más tomas de ese día",
                                       salida=None, proyecto=None))
                continue
            rc |= editar_evento([x["path"] for x in sueltas], a, f) or 0
    informe(rs, a)
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
