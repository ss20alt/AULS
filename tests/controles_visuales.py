# Estudio de edición — CONTROLES VISUALES PLANTADOS: se meten a propósito errores que antes vi a ojo y el QA visual tiene que encontrarlos.
# Corren sobre el proyecto de prueba incluido en el paquete (projects/_prueba), vestido con el estilo de cada control.
#   python tests/controles_visuales.py redbox|mirror|face|emblem|clipped|widecap
import sys, os
STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, STUDIO); os.chdir(STUDIO)
sys.stdout.reconfigure(encoding="utf-8")
import qa_visual as V, doctor
which = sys.argv[1]
P = doctor.PRUEBA

if which == "redbox":                       # caja roja sobre el saco rojo (karaoke v1)
    import styles.karaoke as K
    K.GOLD = K.RED
    cfg, _ = doctor.style_ctx("karaoke")
    print(which, V.run(P, 15, log=lambda *a: None, cfg=cfg))
elif which == "mirror":                     # relleno por reflejo visible (200 px)
    import styles.base as B
    B.Base.ext_x = 200.0
    cfg, _ = doctor.style_ctx("tv")
    print(which, V.run(P, 15, log=lambda *a: None, cfg=cfg))
elif which == "face":                       # texto del gancho de "la cita" sobre la cara (si no se desenfocara)
    import styles.cita as Ci
    Ci.Style.hook_y = 860                    # el encuadre de la prueba cambió (cara más abajo): el error se planta a la altura de la cara
    cfg, _ = doctor.style_ctx("cita")
    cfg["face_hidden_s"] = 0.0
    print(which, V.run(P, 5, log=lambda *a: None, cfg=cfg))
elif which == "emblem":                     # rótulo crema sobre el escudo dorado (documental v1)
    import styles.doc as D
    orig = D.Style.decorate
    def deco(self, x, n, it, t):
        x = orig(self, x, n, it, t)
        D.blend(x, self.name_s, 60, 420, 1.0)
        return x
    D.Style.decorate = deco
    cfg, _ = doctor.style_ctx("doc")
    print(which, V.run(P, 15, log=lambda *a: None, cfg=cfg))
elif which == "clipped":                    # placa que se sale del cuadro por la derecha
    import styles.campana as Cm
    orig = Cm.Style.decorate
    def deco(self, x, n, it, t):
        x = orig(self, x, n, it, t)
        Cm.blend(x, self.name_s, 760, 600, 1.0)
        return x
    Cm.Style.decorate = deco
    cfg, _ = doctor.style_ctx("campana")
    print(which, V.run(P, 30, log=lambda *a: None, cfg=cfg))
elif which == "widecap":                    # subtítulo de una sola línea más ancho que el cuadro (pregunta entera en titulares 4 min)
    import styles.campana as Cm, styles.common as Co
    orig = Cm.Style.decorate
    wide = []
    def deco(self, x, n, it, t):
        x = orig(self, x, n, it, t)
        if not wide:
            f = Co.font("ExtraBold", 58); txt = "¿No existe riesgo alguno de eventual crisis en el sector financiero paraguayo?"
            im = Co.Image.new("RGBA", (int(f.getlength(txt)) + 40, 110), (0, 0, 0, 0)); d = Co.ImageDraw.Draw(im)
            d.text((20, 20), txt, font=f, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=(8, 10, 14, 255))
            wide.append(Co.spr_t(Co.np_(im)))
        Cm.blend(x, wide[0], 495 - wide[0].shape[2] / 2, 1100, 1.0)
        return x
    Cm.Style.decorate = deco
    cfg, _ = doctor.style_ctx("campana")
    print(which, V.run(P, 30, log=lambda *a: None, cfg=cfg))
