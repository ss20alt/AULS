# Estudio de edición — EMPAQUETAR el autoeditor como skill para el equipo de Lilian (Mac o Windows).
# Arma una carpeta autocontenida: código, gráficos, material, ficha y huella de voz de Lilian, la fuente de la conferencia BCP,
# el proyecto y las referencias de prueba, la skill para Claude Code, el instalador de Mac y la guía para la persona.
#   python empaquetar.py [destino] [--sin-video] [--con-invitados]      (por defecto: ~/Documents/AutoeditorLilian)
#   --con-invitados: incluye las huellas de voz/cara de invitados aprobados (datos biométricos de terceros: por defecto NO)
import os, sys, json, shutil, glob, time, hashlib

STUDIO = os.path.dirname(os.path.abspath(__file__))
CODE_DIRS = ["styles", "lib"]
SKIP_PY = set()


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def build(dest, with_video=True, log=print, con_invitados=False):
    if os.path.exists(dest): shutil.rmtree(dest)
    S = os.path.join(dest, "studio")
    os.makedirs(S)
    # código
    for f in glob.glob(os.path.join(STUDIO, "*.py")):
        if os.path.basename(f) not in SKIP_PY: copy(f, os.path.join(S, os.path.basename(f)))
    for d in CODE_DIRS:
        for f in glob.glob(os.path.join(STUDIO, d, "*.py")): copy(f, os.path.join(S, d, os.path.basename(f)))
    for f in ("STUDIO_LOG.md", "requirements.txt", "requirements-libre.txt"): copy(os.path.join(STUDIO, f), os.path.join(S, f))
    # gráficos, sonidos, material del tema BCP
    shutil.copytree(os.path.join(STUDIO, "assets"), os.path.join(S, "assets"), ignore=shutil.ignore_patterns("*.zip", "animados"))   # sin comprimidos sueltos ni los logos ya exportados (están en Drive; se rehacen con logo_estilos.py)
    # ficha + huella de voz de Lilian
    for f in glob.glob(os.path.join(STUDIO, "clients", "lilian*")):        # + huella de cara de Lilian
        if f.lower().endswith(".zip"): continue                            # (un .zip suelto puede traer huellas de invitados)
        if os.path.isdir(f):                                               # huellas de voz/cara de INVITADOS (reunión): datos biométricos de
            if con_invitados: shutil.copytree(f, os.path.join(S, "clients", os.path.basename(f)))   # terceros -> solo si se pide
        else: copy(f, os.path.join(S, "clients", os.path.basename(f)))
    for f in ("yunet.onnx", "sface.onnx"):                                # detector y reconocedor de caras (formato reunión, ≈ 37 MB)
        if os.path.exists(os.path.join(STUDIO, "models", f)): copy(os.path.join(STUDIO, "models", f), os.path.join(S, "models", f))
    # ADN de las referencias (para el QA)
    for f in glob.glob(os.path.join(STUDIO, "analysis", "*.json")):           # (no los resúmenes de entender: GPS y fechas de las tomas)
        if os.path.basename(f).startswith("entender_") and os.path.basename(f) != "entender_verdad.json": continue
        copy(f, os.path.join(S, "analysis", os.path.basename(f)))
    copy(os.path.join(STUDIO, "models", "download_models.py"), os.path.join(S, "models", "download_models.py"))
    # fuente: conferencia BCP (archivos sueltos de la máquina original -> dentro de la fuente, rutas relativas)
    src_dir = os.path.join(STUDIO, "sources", "lilian_conferencia_bcp")
    D = os.path.join(S, "sources", "lilian_conferencia_bcp")
    sj = json.load(open(os.path.join(src_dir, "source.json"), encoding="utf-8"))
    os.makedirs(D)
    for k, name in (("voice", "voice.wav"), ("transcript", "transcript_vad.json"), ("face", "face.npy")) + ((("video", "fuente.mp4"),) if with_video else ()):
        p = sj[k] if os.path.isabs(sj[k]) else os.path.join(src_dir, sj[k])   # rutas relativas = dentro de la fuente (fuente_colorA.mp4)
        copy(p, os.path.join(D, name)); sj[k] = name
    if not with_video: sj["video"] = "fuente.mp4"                       # se puede agregar después (copiar el archivo con ese nombre)
    sj["original"] = os.path.basename(sj.get("original", ""))
    json.dump(sj, open(os.path.join(D, "source.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for f in ("content.json", "transcript_aligned.json", "arbitro.json", "feedback.json"):
        if os.path.exists(os.path.join(src_dir, f)): copy(os.path.join(src_dir, f), os.path.join(D, f))
    # pruebas: proyecto de prueba, referencias de los 15 estilos, controles plantados, ingesta de referencia
    shutil.copytree(os.path.join(STUDIO, "projects", "_prueba"), os.path.join(S, "projects", "_prueba"),
                    ignore=shutil.ignore_patterns("stills", "qa_visual.json", "espectador.json"))
    shutil.copytree(os.path.join(STUDIO, "tests", "referencia"), os.path.join(S, "tests", "referencia"))
    copy(os.path.join(STUDIO, "tests", "controles_visuales.py"), os.path.join(S, "tests", "controles_visuales.py"))
    for f in glob.glob(os.path.join(STUDIO, "tests", "pruebas_*.py")) + [os.path.join(STUDIO, "tests", "cara_perfil.mp4")]:   # pruebas por área
        if os.path.exists(f): copy(f, os.path.join(S, "tests", os.path.basename(f)))
    fx = os.path.join(STUDIO, "tests", "evento_fixtures")                 # datos congelados de las pruebas de evento, SIN los cuadros con
    if os.path.isdir(fx): shutil.copytree(fx, os.path.join(S, "tests", "evento_fixtures"), ignore=shutil.ignore_patterns("cuadros"))   # caras
    ref = os.path.join(STUDIO, "sources", "lilian_conf_auto")
    for f in ("transcript.json", "face.npy", "source.json"): copy(os.path.join(ref, f), os.path.join(S, "tests", "ingesta_referencia", f))
    # skill + instalador + guía
    P = os.path.join(STUDIO, "paquete")
    copy(os.path.join(P, "SKILL.md"), os.path.join(dest, ".claude", "skills", "autoeditor-lilian", "SKILL.md"))
    copy(os.path.join(P, "instalar_mac.sh"), os.path.join(dest, "instalar_mac.sh"))
    copy(os.path.join(P, "LEEME_PRIMERO.md"), os.path.join(dest, "LEEME_PRIMERO.md"))
    with open(os.path.join(dest, "instalar_mac.sh"), "rb") as fh: data = fh.read().replace(b"\r\n", b"\n")
    with open(os.path.join(dest, "instalar_mac.sh"), "wb") as fh: fh.write(data)
    # versión
    tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(dest) for f in fs)
    try:                                                                  # versión del código (control de versiones del estudio)
        import subprocess
        rev = subprocess.run(["git", "-C", STUDIO, "log", "-1", "--format=%h %cd", "--date=format:%Y-%m-%d %H:%M"], capture_output=True, text=True).stdout.strip()
    except Exception: rev = ""
    json.dump(dict(fecha=time.strftime("%Y-%m-%d %H:%M"), con_video=with_video, tamano_mb=round(tot / 1e6), version_codigo=rev, con_invitados=con_invitados),
              open(os.path.join(dest, "VERSION.json"), "w", encoding="utf-8"), indent=1)
    log(f"[paquete] {dest} · {tot / 1e9:.2f} GB")
    return dest


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    dest = a[0] if a else os.path.join(os.path.expanduser("~"), "Documents", "AutoeditorLilian")
    build(dest, with_video="--sin-video" not in sys.argv, con_invitados="--con-invitados" in sys.argv)
