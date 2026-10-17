# Pruebas del área GLOSARIO (rápidas, sin GPU): la ficha del cliente solo corrige nombres; lo propio de una toma va en SU fuente.
# Caso real: el glosario de la conferencia del BCP estaba en la ficha y en el Senado escribía "la mayor entidad de denuncias".
# Corren igual en el paquete del equipo (solo trae la fuente lilian_conferencia_bcp) y en un clon nuevo del repositorio (sources/ no
# se versiona): lo que necesita una fuente se prueba con las que haya; los casos inventados corren siempre.
import os, sys, json, io, contextlib

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO not in sys.path: sys.path.insert(0, STUDIO)
BCP = ("lilian_conferencia_bcp", "lilian_conf_auto", "auto_img_4572")                 # IMG_4572.MOV: la conferencia del BCP
OTRAS = ("lilian_senado_feminicidios", "auto_2026_10_14_ls1", "lilian_encarnacion_acto")
DEL_BCP = {"Ueno", "entidad", "vilo", "cobardía", "vende patria"}                      # lo que escribía el glosario de la conferencia BCP
GLOSARIO_BCP = {"filo": "vilo", "bueno": "Ueno", "cantidad": "entidad", "gobardía": "cobardía", "vendepatria": "vende patria"}   # el que estaba en la ficha
CORE = ".,¿?¡!;:"


def _jl(p): return json.load(open(p, encoding="utf-8"))


def _fuentes():
    d = os.path.join(STUDIO, "sources")
    return sorted(n for n in os.listdir(d) if os.path.exists(os.path.join(d, n, "source.json"))) if os.path.isdir(d) else []


def _palabras(name):
    """palabras crudas de whisper de una fuente (la misma transcripción que usa plan: la alineada si existe); None si no está"""
    d = os.path.join(STUDIO, "sources", name)
    try:
        sj = _jl(os.path.join(d, "source.json"))
        al = os.path.join(d, "transcript_aligned.json")
        tp = al if os.path.exists(al) else (sj["transcript"] if os.path.isabs(sj["transcript"]) else os.path.join(d, sj["transcript"]))
        return sj, [dict(t=w["w"].strip(), s=w["s"], e=w["e"]) for sg in _jl(tp) for w in sg["words"]]
    except (OSError, KeyError, ValueError): return None                     # fuente sin transcripción (o copiada a medias)


def _plan():
    """plan.py importado (carga la fuente activa); sin esa fuente (clon nuevo) se toman de plan.py solo las piezas del glosario,
    que no dependen de ninguna fuente"""
    if "plan" in sys.modules: return sys.modules["plan"]
    if os.path.exists(os.path.join(STUDIO, "sources", os.environ.get("STUDIO_SOURCE", "lilian_conferencia_bcp"), "source.json")):
        import plan as P
        return P
    import ast, re, types
    tree = ast.parse(open(os.path.join(STUDIO, "plan.py"), encoding="utf-8").read())
    keep = {"PALABRAS_COMUNES", "CONECTORES", "es_nombre", "nombres_conocidos", "glosario_cliente", "comunes_en", "_fix", "_fix_frases"}
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in keep)
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in keep for t in n.targets))]
    m = types.ModuleType("plan_glosario"); m.__dict__.update(re=re, os=os, json=json, GLOSSARY={})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), os.path.join(STUDIO, "plan.py"), "exec"), m.__dict__)
    return m


def _corregir(P, W, client, sgl):
    """mismo camino que plan.load_source + load_words: ficha (solo nombres, menos lo que esa fuente dice como palabra común) + fuente"""
    cg = P.glosario_cliente(client.get("glossary", {}), P.nombres_conocidos(client))
    for k in P.comunes_en({k: v for k, v in cg.items() if k not in sgl}, W): cg.pop(k, None)
    gl = dict(cg); gl.update(sgl)
    W = [dict(w, t=P._fix(w["t"], gl)) for w in W]
    return [w["t"] for w in P._fix_frases(W, gl)]


def pruebas(check):
    client = _jl(os.path.join(STUDIO, "clients", "lilian.json"))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            P = _plan()
            cg = P.glosario_cliente(client.get("glossary", {}), P.nombres_conocidos(client))
        # 1. la ficha (vale para TODOS los videos) pasa entera el filtro de nombres y ninguna fuente dice sus claves como palabras comunes
        W = {nm: _palabras(nm) for nm in _fuentes()}
        comunes = {nm: P.comunes_en(cg, w[1]) for nm, w in W.items() if w}
        malas = sorted(set(client.get("glossary", {})) - set(cg)) + [f"{nm}: {ks}" for nm, ks in comunes.items() if ks]
        check("glosario: la ficha del cliente no cambia palabras comunes", not malas, malas)

        # 2. aunque alguien vuelva a poner palabras comunes en la ficha, plan no las deja pasar: ni solas ("cantidad") ni en frase
        #    ("mayor cantidad"→"Mayor Entidad"); una frase que solo pone mayúsculas pasa si el nombre está en la ficha
        pr = {"cantidad": "entidad", "bueno": "Ueno", "Bueno": "Ueno", "filo": "vilo", "Carvalho": "Carvallo", "Juana Fara": "Juan Afara",
              "la cantidad": "la entidad", "la cantidad ": "La Entidad", "peña": "Peña", "Banco": "Ueno", "Banco Bueno": "Banco Ueno",
              "mayor cantidad": "Mayor Entidad", "de denuncias": "De Denuncias", "muchas gracias": "Muchas Gracias",
              "causa republicana": "Causa Republicana"}
        with contextlib.redirect_stdout(io.StringIO()):
            con = set(P.glosario_cliente(pr, "Senadora Lilian Samaniego. Causa Republicana, Partido Colorado."))
            sin = set(P.glosario_cliente(pr))                                # sin nombres conocidos: "causa republicana" tampoco pasa
        check("glosario: de la ficha solo pasan nombres (palabras y frases)",
              con == {"Carvalho", "Juana Fara", "causa republicana"} and sin == {"Carvalho", "Juana Fara"}, dict(con=sorted(con), sin=sorted(sin)))

        # 3. un texto del Senado no cambia ni con la ficha de hoy ni con el glosario del BCP puesto en la ficha (corre siempre); con
        #    las fuentes que haya: el BCP sigue con "Ueno"/"entidad"/"vilo"; Senado y Encarnación sin ningún reemplazo del BCP
        sen = "la mayor cantidad de denuncias, muchas gracias.".split()
        Ws = [dict(t=t, s=i * 0.3, e=i * 0.3 + 0.25) for i, t in enumerate(sen)]
        with contextlib.redirect_stdout(io.StringIO()):
            inv = [_corregir(P, Ws, cl, {}) for cl in (client, dict(client, glossary=dict(client.get("glossary", {}), **GLOSARIO_BCP)))]
            T = {nm: _corregir(P, W[nm][1], client, W[nm][0].get("glossary", {})) for nm in BCP + OTRAS if W.get(nm)}
        cnt = lambda nm, x: sum(1 for t in T[nm] if t.strip(CORE) == x)
        bcp = {nm: (cnt(nm, "entidad"), cnt(nm, "vilo")) for nm in BCP if nm in T}
        ueno = cnt("lilian_conferencia_bcp", "Ueno") if "lilian_conferencia_bcp" in T else 2
        ajeno = {nm: [t for t in T[nm] if t.strip(CORE) in DEL_BCP] for nm in OTRAS if nm in T}
        cantidad = {nm: cnt(nm, "cantidad") for nm in ("lilian_senado_feminicidios", "auto_2026_10_14_ls1") if nm in T}   # 185, 488 y 531 s
        ok3 = (all(x == sen for x in inv) and ueno == 2 and all(v == (1, 1) for v in bcp.values())
               and not any(ajeno.values()) and all(v == 3 for v in cantidad.values()))
        check("glosario: BCP con Ueno/entidad/vilo; Senado y Encarnación sin reemplazos del BCP", ok3,
              dict(inventado=inv, ueno=ueno, bcp=bcp, ajeno={k: v for k, v in ajeno.items() if v}, cantidad=cantidad))

        # 4. entradas de varias palabras: misma cantidad -> palabra por palabra (tiempos y puntuación intactos); distinta -> una sola
        W4 = [dict(t=t, s=i * 0.5, e=i * 0.5 + 0.4) for i, t in enumerate(["la", "de", "Juana", "Fara,", "¿causa", "republicana?"])]
        a = [w["t"] for w in P._fix_frases(W4, {"Juana Fara": "Juan Afara", "causa republicana": "Causa Republicana"})]
        b = P._fix_frases(W4, {"juana fara": "Afara"})
        ok4 = (a == ["la", "de", "Juan", "Afara,", "¿Causa", "Republicana?"] and [w["t"] for w in b][2] == "Afara," and b[2]["e"] == W4[3]["e"])
        check("glosario: frases de varias palabras (Juan Afara, Causa Republicana)", ok4, (a, [w["t"] for w in b]))

        # 5. segunda red: lo que ESA fuente dice como palabras comunes no se aplica ahí: una palabra en minúscula ("un franco
        #    deterioro") o una frase escrita como nombre cuyas palabras dice sueltas en minúscula ("muchas veces… gracias"); la frase
        #    misma no cuenta ("senador juana fara" se corrige) y las que solo ponen mayúsculas ("causa republicana") se aplican
        W5 = [dict(t=t) for t in "un franco deterioro. Carlos Carvalho? muchas veces, gracias. Muchas Gracias. senador juana fara, "
                                  "a causa de causa republicana".split()]
        got = P.comunes_en({"Franco": "Franko", "Carvalho": "Carvallo", "Juana Fara": "Juan Afara", "Muchas Gracias": "Muchas Grasias",
                            "causa republicana": "Causa Republicana"}, W5)
        check("glosario: palabra o frase que la fuente usa como común no se toca", got == ["Franco", "Muchas Gracias"], got)
    except Exception as e:
        check("glosario: funciones del glosario en plan.py", False, repr(e))
