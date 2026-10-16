# Estudio de edición — GENERADOR AUTOMÁTICO: estilo + ángulo -> video de 60 s listo (selección narrativa, cortes, subtítulos, gráficos, FX, audio, QA y entrega).
#   python make_video.py --style fx --angle calma
#   python make_video.py --all                      (combinaciones recomendadas)
#   estilos: news ink report headline fx call split · ángulos: calma leite propuestas prensa
import os, sys, json, time, shutil, argparse, re
import numpy as np
from core import FPS, STUDIO
import plan as P
import selector as SEL
import selector2 as SEL2
import content as CM
import autocfg
import build
import qa

DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
EXTRA_DELIVER = [os.path.join(os.path.expanduser("~"), "Documents", "videosclaudesubir")]      # Drive del usuario (PC original)
STYLE_DEFAULTS = {
    "news": dict(style="news", pre=5, shot_max=5.0, bpm=96, seed=31, split_on_key=False),
    "ink": dict(style="ink", pre=5, shot_max=4.5, bpm=106, seed=47, split_on_key=True, chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]),
    "report": dict(style="report", pre=5, shot_max=4.8, bpm=112, seed=11, split_on_key=False),
    "headline": dict(style="headline", pre=5, shot_max=5.5, bpm=92, seed=71, split_on_key=False, chords=[[57, 60, 64], [55, 59, 62], [53, 57, 60], [52, 55, 59]]),
    "fx": dict(style="fx", pre=5, shot_max=4.5, bpm=118, seed=19, split_on_key=False, chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]),
    "call": dict(style="call", pre=0, shot_max=99.0, bpm=92, seed=23, split_on_key=False, still_t=244.0, chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]),
    "split": dict(style="split", pre=5, shot_max=4.8, bpm=100, seed=61, split_on_key=False),
    # ---- ronda de 1 minuto (estilos nuevos sobre styles/base.py)
    "karaoke": dict(style="karaoke", pre=3, shot_max=3.6, bpm=124, seed=83, split_on_key=False, max_chars=18, skip_caption_roles=[],
                    chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]),
    "doc": dict(style="doc", pre=6, shot_max=6.5, bpm=68, seed=5, split_on_key=False, max_chars=30, skip_caption_roles=[],
                chords=[[45, 52, 57, 60], [41, 48, 53, 57], [43, 50, 55, 59], [40, 47, 52, 55]]),
    "tv": dict(style="tv", pre=4, shot_max=4.6, bpm=104, seed=37, split_on_key=False, max_chars=24, skip_caption_roles=[]),
    "claves": dict(style="claves", pre=5, shot_max=4.8, bpm=100, seed=13, split_on_key=False, skip_caption_roles=[],
                   chords=[[48, 52, 55, 60], [45, 48, 52, 57], [41, 45, 48, 53], [43, 47, 50, 55]]),
    "cita": dict(style="cita", pre=5, shot_max=5.0, bpm=84, seed=29, split_on_key=False, skip_caption_roles=["H"],
                 chords=[[45, 48, 52, 57], [41, 45, 48, 53], [43, 47, 50, 55], [40, 43, 47, 52]]),
    "editorial": dict(style="editorial", pre=5, shot_max=5.2, bpm=98, seed=41, split_on_key=False, skip_caption_roles=[], max_chars=22,
                      chords=[[48, 52, 55, 59], [45, 48, 52, 55], [41, 45, 48, 52], [43, 47, 50, 53]]),
    "campana": dict(style="campana", pre=6, shot_max=5.6, bpm=76, seed=59, split_on_key=False, skip_caption_roles=[], max_chars=22,
                    chords=[[48, 55, 60, 64], [45, 52, 57, 60], [41, 48, 53, 57], [43, 50, 55, 59]]),
    "podcast": dict(style="podcast", pre=4, shot_max=5.0, bpm=90, seed=67, split_on_key=False, skip_caption_roles=[],
                    chords=[[45, 52, 57, 60], [43, 50, 55, 59], [41, 48, 53, 57], [40, 47, 52, 55]]),
    # ---- el look que el equipo publica (18 TikToks editados, STUDIO_LOG §3o): subtítulo único, gancho B/N, música baja
    "redes": dict(style="redes", pre=4, shot_max=6.0, bpm=92, seed=17, split_on_key=False, skip_caption_roles=[], max_chars=20,
                  chords=[[45, 52, 57, 60], [41, 48, 53, 57], [43, 50, 55, 59], [40, 47, 52, 55]]),
    # ---- fuentes en formato panel (TV horizontal): recuadro fijo + datos animados (styles/datos.py)
    "datos": dict(style="datos", pre=4, shot_max=99.0, bpm=76, seed=7, split_on_key=False, skip_caption_roles=[], max_chars=26,
                  chords=[[45, 48, 52, 57], [41, 45, 48, 53], [43, 47, 50, 55], [40, 43, 47, 52]]),
}
LABEL = {"news": "NOTICIERO", "ink": "TIKTOK_TINTA", "report": "REPORTAJE", "headline": "TITULARES", "fx": "ANIMADO_ROJO_FX", "call": "LLAMADA_CON_LETRA", "split": "PANTALLA_DIVIDIDA",
         "karaoke": "KARAOKE_DINAMICO", "doc": "DOCUMENTAL", "tv": "TV_NOTICIAS", "claves": "LAS_CLAVES", "cita": "LA_CITA", "editorial": "EDITORIAL", "campana": "CAMPANA", "podcast": "PODCAST", "datos": "DATOS_ANIMADOS", "redes": "REDES"}
STOP = set("para porque entonces también ciudadanía paraguayo paraguayos paraguaya senadora tenemos tenía había hacer hecho estaba estamos estos estas todos todas nuestro nuestra nosotros ellos ahora siempre además después antes durante sobre hasta desde puede pueden quiero quieren vengo vamos tiene tienen cuando donde cualquier primero primer segundo lugar".split())




def auto_zoom(ref=0.14, max_up=3.2):
    """acercamiento según la fuente: en un acto la filman de cuerpo entero (cara 0.10 del alto vs 0.14 de una conferencia) ->
    acercar hasta la cara de referencia, pero sin agrandar el original más de `max_up` veces (más = blando). (zoom_mul, límite)"""
    try:
        import core
        f = np.load(P.SRC["face"]); fs = float(np.median(f[:, 2])) / 1920
        mp = os.path.join(P.SRC["dir"], "meta.json")
        m = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        w, h = m.get("width"), m.get("height")
        up = (max(1080 / w, 1920 / h) if h >= w else 1920 / h) if w and h else 1.0       # cuánto se agrandó ya el original
        zf = core.ZOOM_FIJO if core.ZOOM_FIJO > 0 else 1.0
        cap = max(1.0, max_up / up / zf)
        want = max(1.0, ref / max(fs, 1e-3))
        if want <= 1.04: return 1.0, None
        zm = round(min(want, cap, 1.6), 3)
        return zm, (f"original {w}×{h}, agrandado ×{up:.1f}" if want > cap + 1e-3 else None)
    except Exception:
        return 1.0, None


def auto_keys(script, base):
    """palabras clave (en dorado): las del ángulo, las de la fuente y, en fuentes nuevas, las palabras ancla de cada idea del mapa"""
    keys = dict(base)
    src_kw = P.SRC.get("keywords") or {}
    for k, v in src_kw.items(): keys.setdefault(k, v)
    if not src_kw:
        for b, tag in CM.TAGS.items():
            if tag[1] and len(tag[1]) >= 4: keys.setdefault(tag[1], 2)
    return keys


NEEDS_MATERIAL = {"split", "call"}                                       # estilos que se arman con fotos/clips del tema


# los mapas automáticos (mapper.py) usan ángulos genéricos; equivalencias con los ángulos del mapa manual
ANGLE_FALLBACK = {"sistema": "mensaje", "calma": "resumen", "leite": "confrontacion", "propuestas": "propuestas", "prensa": "prensa"}


def available_angle(angle):
    if angle in CM.STORIES: return angle
    alt = ANGLE_FALLBACK.get(angle)
    return alt if alt in CM.STORIES else "resumen"


LENGTHS = {"1min": 60.0, "3min": 180.0, "4min": 240.0}                    # duraciones exactas


def make(style, angle, target=60.0, name=None, deliver=True, fix_loop=True, log=print, length="auto", prepare_only=False, force=False, cifras=None, broll=None, fondo=None, insertos=None, gancho=None):
    """PILOTO AUTOMÁTICO: guion -> espectador (guion) -> preparar -> espectador + QA visual sobre fotogramas de prueba ->
    correcciones automáticas -> render SOLO si todo está limpio -> QA final -> entrega SOLO sin hallazgos medios/altos"""
    t0 = time.time()
    tag = "" if P.SOURCE_NAME == "lilian_conferencia_bcp" else f"__{P.SOURCE_NAME}"         # proyectos de otras fuentes no pisan los existentes
    name = name or ({"auto": f"auto2_{style}_{angle}", "1min": f"m1_{style}_{angle}", "3min": f"m3_{style}_{angle}", "4min": f"m4_{style}_{angle}"}.get(length, f"auto_{style}_{angle}") + tag)
    pdir = os.path.join(build.PROJ_ROOT, name); os.makedirs(pdir, exist_ok=True)
    log(f"== {name}")
    import espectador as ESP
    if style in NEEDS_MATERIAL and not P.SRC.get("material"):
        log(f"  ✗ el estilo {style} se arma con fotos/clips del tema y esta fuente no tiene material (ver SKILL.md · material del tema)")
        return dict(name=name, findings=["SIN_MATERIAL"], ok=False)
    if length == "auto" or length in LENGTHS:                             # bloques de idea completos, hasta 2 min (o duración exacta)
        max_s = LENGTHS.get(length, CM.STORIES.get(angle, {}).get("max_s", SEL2.MAX_S))   # una historia armada a mano puede pedir otro largo
        script, edl, parts = SEL2.build(angle, style, max_s=max_s, log=log, exact=length in LENGTHS, hook=gancho != "no")
        target = round(edl["total"] / FPS, 3)
        sf = ESP.script_checks(parts)                                     # 1.ª verificación: el guion, antes de preparar nada
        log("  ✓ guion: " + ("sin problemas" if not sf else f"PROBLEMAS {sf}"))
        if sf and not force: log("  ✗ guion con problemas: no se prepara (revisar historia en el mapa)"); return dict(name=name, findings=[f[0] for f in sf], ok=False)
        if length in LENGTHS and abs(target - max_s) > 1e-3:
            fa = edl.get("falta") or {}
            log(f"  ! duración {target}s (pedida {max_s}s): {fa.get('motivo', 'no encaja')} (el mapa tiene {fa.get('mapa', '?')} s de ideas de ella)"
                + (" → aprobá más bloques en el mapa (content_review.html) o pedí una duración menor" if "no tiene ideas" in fa.get("motivo", "") else ""))
    else:
        script, edl, S = SEL.fit(angle, style, target, log=log)
    cfg = dict(STYLE_DEFAULTS[style]); cfg.update(target=target, music_db=-19.5, angle=angle, auto=True, script=script, source=P.SOURCE_NAME)
    if cifras: cfg["cifras"] = cifras                               # cifras en pantalla (estilo redes): auto | no | mas
    if insertos:                                                     # noticias / documentos / infografías que aparecen cuando ella nombra el tema
        fs_ = []
        for b_ in insertos:
            fs_ += [os.path.join(b_, f) for f in sorted(os.listdir(b_)) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))] if os.path.isdir(b_) else [b_]
        cfg["insertos"] = fs_
    if fondo: cfg["fondo"] = fondo
    if gancho: cfg["gancho"] = gancho                               # bn (blanco y negro, por defecto en redes) | color | no                                  # fuentes de TV/Senado (estilo datos): fondo liso rosa | rosa_fuerte | #RRGGBB
    if broll:                                                        # tomas del público del MISMO acto para tapar los saltos (estilo redes)
        fs_ = []
        for b_ in broll:
            fs_ += [os.path.join(b_, f) for f in sorted(os.listdir(b_)) if f.lower().endswith((".mp4", ".mov", ".m4v"))] if os.path.isdir(b_) else [b_]
        cfg["broll"] = fs_
    zm, lim = auto_zoom()
    if zm != 1.0: cfg["zoom_mul"] = zm
    if lim: cfg["zoom_limit"] = lim
    if zm != 1.0 or lim: log(f"  encuadre: zoom ×{zm:.2f}" + (f" (tope por resolución: {lim})" if lim else ""))
    if length == "auto" or length in LENGTHS:
        cfg.setdefault("skip_caption_roles", ["H"])                       # las preguntas del periodista también llevan subtítulo
        cfg.update(pause_keep=edl.get("pause_keep"), end_max=edl.get("end_max", 110))
    base_kw = {}
    if P.SRC.get("legacy_angles"):                                       # ángulos manuales de la conferencia BCP (solo esa fuente)
        base_kw = dict(SEL.ANGLES[angle]["kw"]) if angle in SEL.ANGLES else {}
        for a_ in ("calma", "leite", "propuestas", "prensa"):             # en 2 min se tocan más temas: claves de todos los ángulos (peso menor)
            for k, v in SEL.ANGLES[a_]["kw"].items(): base_kw.setdefault(k, min(v, 2))
    cfg["keys"] = auto_keys(script, base_kw)
    cfg["split_on_key"] = cfg.get("split_on_key", False)
    cfgp = os.path.join(pdir, "cfg.json")
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in ("edl.json", "voice_cut.wav", "selects.mp4", "hyp.json", "words.json", "scenes.json"):
        if os.path.exists(os.path.join(pdir, k)): os.remove(os.path.join(pdir, k))
    build.prepare(name, rebuild=True)
    # enriquecimiento por estilo (necesita palabras y escenas)
    ctx = build.Ctx(cfg, pdir)
    (autocfg.enrich_beats if (length == "auto" or length in LENGTHS) else autocfg.enrich)(cfg, ctx)
    if style == "cita": cfg["face_hidden_s"] = round(ctx.hook_end, 2)      # el gancho tipográfico desenfoca la imagen a propósito
    if style == "doc": cfg["letterbox"] = [372, 1560]                       # franjas negras de cine (diseño, no exposición)
    json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 2.ª verificación ANTES del render: el espectador (sentido) + QA visual sobre fotogramas de prueba (se componen sin renderizar).
    # Revisa 1 de cada 15 cuadros, igual que el control final, que después la reutiliza si nada cambió (no se repite el trabajo)
    import qa_visual
    for attempt in range(3):
        pre = ESP.check(name, log=log) + qa_visual.run(name, step=15, log=log, firmar=True)   # misma densidad que el control final: lo que él vería se corrige ANTES del render
        serious = [f for f in pre if f[0] != "baja"]
        codes = {f[1] for f in serious}
        if not serious: log("  ✓ verificación previa: sin problemas"); break
        changed = False                                                   # correcciones automáticas conocidas
        if "TEXT_ON_FACE" in codes: cfg["zoom_mul"] = round(cfg.get("zoom_mul", 1.0) / 1.06, 3); changed = True
        if not changed: break
        log("  ↻ corrección previa:", {k: cfg[k] for k in ("zoom_mul",) if k in cfg})
        json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(dict(pre=pre), open(os.path.join(pdir, "verificacion_previa.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if serious and not force:
        log(f"  ✗ verificación previa con problemas: NO se renderiza → {[f[2] for f in serious]}")
        return dict(name=name, findings=sorted(codes), ok=False, pre=pre)
    if prepare_only: log(f"  preparado y verificado (sin render): projects/{name}"); return dict(name=name, findings=None, pre=pre)
    out = build.render(name, lite_async=True)                         # la versión liviana se hace mientras corre el control final
    M, F = qa.run(name)
    F += [f for f in ESP.check(name, log=lambda *a: None) if f not in F]
    findings = {f[1] for f in F}
    for it in range(1 if fix_loop else 0):                                # un ciclo de corrección automática (cara/zoom)
        changed = False
        if "FACE_SMALL" in findings and not cfg.get("zoom_limit"): cfg["zoom_mul"] = round(cfg.get("zoom_mul", 1.0) * 1.07, 3); changed = True
        if "FACE_BIG" in findings: cfg["zoom_mul"] = round(cfg.get("zoom_mul", 1.0) / 1.07, 3); changed = True
        if not changed: break
        log("  ↻ corrección automática:", {k: cfg[k] for k in ("zoom_mul",) if k in cfg})
        json.dump(cfg, open(cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out = build.render(name, lite_async=True); M, F = qa.run(name); findings = {f[1] for f in F}
    build.wait_lite(name)                                                 # la versión liviana tiene que estar terminada
    # entrega (solo si el QA final no tiene hallazgos medios o altos)
    final = None
    blocking = [f for f in F if f[0] in ("media", "alta")]
    if blocking and not force:
        log(f"  ✗ QA final con hallazgos: no se entrega → {[f[1] for f in blocking]}"); deliver = False
    if deliver:
        who = re.sub(r"\W+", "", P.CLIENT.get("short", P.CLIENT.get("name", "Cliente").split()[0]))
        base = f"{who}_AUTO_{LABEL[style]}_{angle}_" + (f"{int(round(target))}s" if length == "auto" else length) + tag
        shutil.copy(out, os.path.join(DOWNLOADS, base + ".mp4"))
        lite = out.replace(".mp4", "_liviano.mp4")
        if os.path.exists(lite): shutil.copy(lite, os.path.join(DOWNLOADS, base + "_liviano.mp4"))
        final = os.path.join(DOWNLOADS, base + ".mp4")
        for d_ in EXTRA_DELIVER:                                        # carpeta sincronizada con Google Drive (si existe en esta máquina)
            if os.path.isdir(d_):
                shutil.copy(out, os.path.join(d_, base + ".mp4"))
                if os.path.exists(lite): shutil.copy(lite, os.path.join(d_, base + "_liviano.mp4"))
                log(f"  ✓ también en {d_}")
    # informe
    texts = []
    for s in cfg["script"]:
        a_, b_ = s[3], s[4]
        texts.append(" ".join(x["text"] for x in CM.SENT if a_ - 0.05 <= x["s"] and x["e"] <= b_ + 0.05))
    md = [f"# {name}", f"estilo **{style}** · ángulo **{angle}** · {time.time() - t0:.0f}s de producción", "", "## Guion elegido (automático)"]
    md += [f"- `{s[2]}` {s[3]:.1f}–{s[4]:.1f}s: {t}" for s, t in zip(cfg["script"], texts)]
    md += ["", "## QA", *( [f"- [{s}] {c}: {t}" for s, c, t, a in F] or ["- sin hallazgos"] ), "", f"mezcla: {M.get('mezcla')}", f"audio: {M.get('audio')}"]
    open(os.path.join(pdir, "REPORT.md"), "w", encoding="utf-8").write("\n".join(md))
    log(f"   listo en {time.time() - t0:.0f}s · hallazgos: {sorted(findings) or 'ninguno'} -> {final or out}")
    return dict(name=name, out=out, final=final, findings=sorted(findings), metrics=M, ok=not blocking)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=list(STYLE_DEFAULTS)); ap.add_argument("--angle", choices=sorted(set(SEL.ANGLES) | set(CM.STORIES)))
    ap.add_argument("--target", type=float, default=60.0); ap.add_argument("--name"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-deliver", action="store_true"); ap.add_argument("--prepare-only", action="store_true"); ap.add_argument("--length", default="auto", choices=["auto", "60", "1min", "3min", "4min"]); ap.add_argument("--force", action="store_true")
    ap.add_argument("--gancho", choices=["bn", "color", "no"], help="gancho (frase fuerte al inicio): bn = en blanco y negro (redes), color, no = arranca directo")
    ap.add_argument("--insertos", nargs="+", help="imágenes (noticias, documentos, tablas, infografías): aparecen cuando ella dice el nombre del archivo (estilo redes)")
    ap.add_argument("--fondo", help="estilo datos (TV/Senado): fondo liso — rosa, rosa_fuerte, bordo, azul, rojo, blanco o #RRGGBB")
    ap.add_argument("--broll", nargs="+", help="videos o carpeta con tomas del público del MISMO acto (tapan los saltos, estilo redes)")
    ap.add_argument("--cifras", choices=["auto", "no", "mas"], help="cifras en pantalla sincronizadas con la voz (estilo redes): auto = solo estadísticas de peso")
    a = ap.parse_args()
    if a.all:
        combos = [("fx", "sistema"), ("ink", "leite"), ("report", "prensa"), ("headline", "propuestas"), ("news", "calma"), ("call", "prensa"), ("split", "calma")]
        combos = [(s, available_angle(g)) for s, g in combos]
        res = [make(s, g, a.target, deliver=not a.no_deliver, length=a.length) for s, g in combos]
        print("\nRESUMEN"); [print(" ", r["name"], r["findings"]) for r in res]
    else:
        make(a.style, a.angle, a.target, a.name, deliver=not a.no_deliver, length=a.length, prepare_only=a.prepare_only, force=a.force, cifras=a.cifras, broll=a.broll, fondo=a.fondo, insertos=a.insertos, gancho=a.gancho)
