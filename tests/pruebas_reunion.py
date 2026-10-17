# Pruebas rápidas del CONTROL FINAL del formato reunión (sin GPU, sin oído, sin render; ~6 s): duración vs pedida, placa con el
# nombre sobre la persona correcta y textos (titular, placa, subtítulos) en zona segura y sin tapar la cara.
# Datos: la fuente real sources/reunion_mussi (IMG_4801: Lilian / Mussi / Aarón) + una copia chica del proyecto entregado
# auto_reunion_reunion_mussi_150s en tests/reunion_mussi150 (EDL, subtítulos y la cara que sigue el recorte; sin video).
# Todo se copia a una carpeta temporal y se ROMPE a propósito (voz unida a otra cara, nombres cruzados, cara baja, textos largos):
# el control tiene que verlo; el caso real tiene que pasar limpio.
import os, sys, json, shutil, tempfile, subprocess
import numpy as np

STUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(STUDIO, "tests", "reunion_mussi150")
FUENTE = "reunion_mussi"
COPIAR = ("source.json", "people.json", "voice_face.json", "known_faces.json", "face_centroids.npy", "faces_raw.json",
          "face_windows.json", "sentences.json", "voice_emb.npy")
VIDEO_REAL = os.path.join(STUDIO, "projects", "auto_reunion_reunion_mussi_150s", "video.mp4")


def _jl(p): return json.load(open(p, encoding="utf-8"))
def _js(o, p): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def _kinds(F, sev=("media", "alta")): return sorted(f["kind"] for f in F if f.get("sev", "alta") in sev)


def pruebas(check):
    for p in (STUDIO, os.path.join(STUDIO, "lib")):
        if p not in sys.path: sys.path.insert(0, p)
    import reunion as RU
    import reunion_render as RR
    src = os.path.join(RU.SOURCES, FUENTE, "reunion")
    falta = [f for f in COPIAR if not os.path.exists(os.path.join(src, f))]
    if not os.path.isdir(FIX): return                   # paquete del equipo: no lleva la reunión (huellas de cara y voz de terceros)
    if falta:
        check("reunión QA: datos de prueba (sources/reunion_mussi)", False, f"faltan {falta}"); return
    tmp = tempfile.mkdtemp(prefix="qa_reunion_")
    old = RU.SOURCES, RU.CLIENTS
    try:
        sd = os.path.join(tmp, "sources", FUENTE, "reunion"); os.makedirs(sd)
        for f in COPIAR: shutil.copy(os.path.join(src, f), os.path.join(sd, f))
        pd = os.path.join(tmp, "auto_reunion_reunion_mussi_150s"); shutil.copytree(FIX, pd)
        # registro de personas propio (como 'people approve'): cara = grupo de huellas unido a su voz, voz = promedio de sus frases;
        # la ficha de la cliente y su huella de cara, las reales
        cd = os.path.join(tmp, "clients"); kp = os.path.join(cd, "lilian_people"); os.makedirs(kp)
        for f in ("lilian.json", "lilian_faceprint.npy"): shutil.copy(os.path.join(old[1], f), os.path.join(cd, f))
        ppl = _jl(os.path.join(sd, "people.json"))["people"]; vf = _jl(os.path.join(sd, "voice_face.json"))
        cent = np.load(os.path.join(sd, "face_centroids.npy"), allow_pickle=True).item()
        S_ = _jl(os.path.join(sd, "sentences.json")); E_ = np.load(os.path.join(sd, "voice_emb.npy"))
        for spk in ("S1", "S2"):
            np.save(os.path.join(kp, ppl[spk]["name"] + ".npy"), cent[vf[spk]])
            m = E_[[k for k, s in enumerate(S_) if s["spk"] == spk and s["e"] - s["s"] >= 1.0]].mean(0)
            np.save(os.path.join(kp, ppl[spk]["name"] + ".voz.npy"), (m / np.linalg.norm(m)).astype(np.float32))
        RU.SOURCES, RU.CLIENTS = os.path.join(tmp, "sources"), cd
        E = _jl(os.path.join(pd, "edl.json"))
        MZ, FACES, aprox = RU.caras_encuadradas(FUENTE, pd, E)

        def placas(): return RU.control_placas(FUENTE, E, MZ, FACES)[0]

        def textos(faces=FACES): return RU.control_textos(FUENTE, pd, E, MZ, faces)[0]

        def con(paths, cambio, fn):                                                 # rompe archivos, corre el control y los deja como estaban
            orig = {p: open(p, "rb").read() for p in paths}
            try: cambio(); return fn()
            finally:
                for p, b in orig.items(): open(p, "wb").write(b)

        # 1) duración: el render dura lo que el plan (±0.3 s: si no, no se entrega) y lo pedido: exacto ±max(1.5 s, 2 %); MÁS CORTO =
        #    aviso siempre (faltaron ideas: "completo" = 240 s con ~120 s buenos se entrega, como el evento); más largo que
        #    max(6 s, 10 %) no se entrega. El pedido sale del EDL o, en proyectos viejos, SOLO de los nombres de auto.py
        e1 = dict(total=4495)                                                        # 149.83 s
        d_ok = RU.control_duracion(149.83, e1, 150.0)
        d_180 = RU.control_duracion(149.83, e1, 180.0)                               # 30 s corto: aviso
        d_240 = RU.control_duracion(120.0, dict(total=3600), 240.0)                  # la mitad de lo pedido: aviso (antes: no se entregaba)
        d_155 = RU.control_duracion(149.83, e1, 155.0)
        d_140 = RU.control_duracion(149.83, e1, 140.0)                               # +9.8 s ≤ 10 %: aviso
        d_120 = RU.control_duracion(149.83, e1, 120.0)                               # +29.8 s: se pasó, no se entrega
        d_rot = RU.control_duracion(152.0, e1, 150.0)
        ped = RU._pedido(pd, E)
        mano = []                                                                   # --frases/--ideas sin --proj: nombre por defecto y
        for nom in ("reunion_reunion_mussi_150s", "Mussi_Causa_Republicana_1min10"):  # «(pedido 150 s)» en el plan -> sin pedido
            q = os.path.join(tmp, nom); os.makedirs(q); shutil.copy(os.path.join(FIX, "plan.txt"), os.path.join(q, "plan.txt"))
            mano.append(RU._pedido(q, E))
        ok1 = (not d_ok and _kinds(d_180) == [] and _kinds(d_180, ("baja",)) == ["DUR"] and _kinds(d_240) == [] and _kinds(d_240, ("baja",)) == ["DUR"]
               and _kinds(d_155) == [] and _kinds(d_155, ("baja",)) == ["DUR"] and _kinds(d_140) == [] and _kinds(d_140, ("baja",)) == ["DUR"]
               and _kinds(d_120) == ["DUR"] and _kinds(d_rot) == ["DUR"] and ped == 150.0 and mano == [None, None]
               and RU._pedido(pd, dict(E, pedido=None)) is None and RU._pedido(os.path.join(tmp, "x"), dict(E, pedido=90)) == 90.0)
        check("reunión QA: duración comparada con la pedida (y con el plan)", ok1, (d_ok, d_180, d_240, d_155, d_140, d_120, d_rot, ped, mano))

        # 2) caso real (Mussi 2:30 entregado): sin hallazgos; la geometría de las piezas coincide con el video renderizado (si está)
        F2, met2 = RU.qa_formato(FUENTE, pd, dur=149.83)
        det2 = [f["texto"] for f in F2]
        ok2 = not F2 and not aprox and met2["pedido"] == 150.0 and all(v >= 0.9 for v in met2["bloques_cara_de_la_voz"].values()) \
            and len(met2["bloques_cara_de_la_voz"]) == 6 and met2["muestras_texto"] > 400
        if ok2 and os.path.exists(VIDEO_REAL):
            n = 60                                                                   # 2.0 s: titular, placa de Lilian y "Muy contenta de recibirle"
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{n / 30:.4f}", "-i", VIDEO_REAL, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                               capture_output=True, timeout=30)
            fr = np.frombuffer(r.stdout[:1080 * 1920 * 3], np.uint8).reshape(1920, 1080, 3).astype(int)
            cap = next(c for c in _jl(os.path.join(pd, "captions.json")) if c["s"] <= n / 30 < c["e"])
            m, x, y = RR.mascara_subtitulo(cap["t"])
            from PIL import Image, ImageDraw
            fill = Image.new("L", (m.shape[1], m.shape[0]), 0)
            ImageDraw.Draw(fill).text((20, 10), cap["t"], font=RR.font("ExtraBold", 52), fill=255)
            import cv2
            fl = cv2.erode((np.asarray(fill) > 200).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            ring = (m > 200) & ~(cv2.dilate((np.asarray(fill) > 30).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
            yy, xx = np.nonzero(fl); blanco = float((fr[yy + y, xx + x].min(1) > 200).mean())
            yy, xx = np.nonzero(ring); borde = float((fr[yy + y, xx + x].max(1) < 110).mean())
            px0, py0, px1, py1 = RR.caja_placa(ppl["L"]["name"], ppl["L"]["role"])
            franja = fr[py0 + 20:py1 - 20, px0 + 2:px0 + 8]; afuera = fr[py0 + 20:py1 - 20, px0 - 12:px0 - 6]
            roja = float(((franja[..., 2] > 150) & (franja[..., 1] < 90)).mean()); roja_afuera = float(((afuera[..., 2] > 150) & (afuera[..., 1] < 90)).mean())
            tx0, ty0, tx1, ty1 = [int(v) for v in RR.cajas_titular(_jl(os.path.join(sd, "source.json"))["titulo"])[1]]
            chip = fr[ty0 + 8:ty1 - 8, tx0 + 4:tx0 + 10]; chip_af = fr[ty0 + 20:ty1 - 8, tx0 - 12:tx0 - 6]
            rojo_chip = float(((chip[..., 2] > 150) & (chip[..., 1] < 90)).mean()); rojo_chip_af = float(((chip_af[..., 2] > 150) & (chip_af[..., 1] < 90)).mean())
            ok2 = blanco > 0.9 and borde > 0.8 and roja > 0.9 and roja_afuera < 0.2 and rojo_chip > 0.9 and rojo_chip_af < 0.2
            det2 = dict(blanco=round(blanco, 2), borde=round(borde, 2), franja=round(roja, 2), afuera=round(roja_afuera, 2), chip=round(rojo_chip, 2), chip_afuera=round(rojo_chip_af, 2))
        check("reunión QA: caso real sin hallazgos (y piezas donde las dibuja el render)", ok2, det2)

        # 3) la voz de Mussi unida a la cara de Aarón (voice_face): el bloque y la placa muestran a otra persona
        vfp = os.path.join(sd, "voice_face.json"); cfp = os.path.join(sd, "face_centroids.npy")
        F3 = con([vfp], lambda: _js(dict(vf, S1=vf["S2"]), vfp), placas)
        aj = sorted(f["bloque"] for f in F3 if f["kind"] == "CARA_AJENA" and f["sev"] == "alta")
        #    lo mismo cuando los grupos de Mussi y Aarón no tienen centroide (grupos chicos): decide la ventana de cara de la fuente
        sin_c = lambda: np.save(cfp, {k: v for k, v in cent.items() if k not in (vf["S1"], vf["S2"])}, allow_pickle=True)
        F3b = con([vfp, cfp], lambda: (_js(dict(vf, S1=vf["S2"]), vfp), sin_c()), placas)
        F3c = con([cfp], sin_c, placas)
        aj_b = sorted(f["bloque"] for f in F3b if f["kind"] == "CARA_AJENA" and f["sev"] == "alta")
        #    caso REAL (reunion_prueba10, 14/10, el QA de entonces dio OK): mientras habla Lilian el recorte siguió el REFLEJO de Mussi
        #    en la mesa de vidrio (cara de ella apenas en el borde). Misma toma (f0 = 3): se usa esa pista de cara en el bloque b0
        rf = np.load(os.path.join(FIX, "reflejo_b0.npy")); f3 = dict(FACES)
        f3["b0"] = np.vstack([rf, np.repeat(rf[-1:], max(0, len(FACES["b0"]) - len(rf)), 0)])
        F3d = RU.control_placas(FUENTE, E, MZ, f3)[0]
        #    y NO es error: la voz de Aarón unida a su OTRO grupo de huellas (el agrupado lo partió en dos: centroides 0.57). Con su
        #    cara registrada (mismo nombre) y sin registro (solo centroides): antes salía CARA_AJENA b3–b5 + PLACA_CARA y no se entregaba
        u = lambda x: x / np.linalg.norm(x)
        otro = max((k for k in cent if k != vf["S2"]), key=lambda k: float(u(cent[k]) @ u(cent[vf["S2"]])))
        sim_otro = float(u(cent[otro]) @ u(cent[vf["S2"]]))
        vac = os.path.join(tmp, "clients_vacio"); os.makedirs(vac)
        def sin_registro():
            RU.CLIENTS = vac
            try: return placas()
            finally: RU.CLIENTS = cd
        F3e = con([vfp], lambda: _js(dict(vf, S2=otro), vfp), placas)
        F3f = con([vfp], lambda: _js(dict(vf, S2=otro), vfp), sin_registro)
        partida = [f["texto"] for f in F3e + F3f if f["kind"] in ("CARA_AJENA", "PLACA_CARA", "PLACA_NOMBRE")]
        ok3 = (aj == ["b1", "b2"] and any(f["kind"] == "PLACA_CARA" and f["spk"] == "S1" for f in F3) and aj_b == ["b1", "b2"]
               and not [f for f in F3c if f["kind"] in ("CARA_AJENA", "PLACA_CARA")]
               and [(f["bloque"], f["sev"]) for f in F3d if f["kind"] == "CARA_AJENA"] == [("b0", "alta")]
               and [f["spk"] for f in F3d if f["kind"] == "PLACA_CARA"] == ["L"]
               and sim_otro >= 0.5 and not partida)
        check("reunión QA: cara encuadrada que no es la de la voz (y la misma persona partida en dos grupos no lo es)", ok3,
              ([f["texto"] for f in F3], aj_b, [f["texto"] for f in F3c], [f["texto"] for f in F3d], (otro, round(sim_otro, 2)), partida))

        # 4) placa con el nombre de otra persona: (a) el error de IMG_4801 (encuadre coherente con la voz, pero la cara es la registrada
        #    de OTRO invitado) -> PLACA_NOMBRE sin PLACA_VOZ; (b) nombres cruzados en people.json -> la voz tampoco coincide (PLACA_VOZ)
        a_ = os.path.join(kp, ppl["S1"]["name"] + ".npy"); b_ = os.path.join(kp, ppl["S2"]["name"] + ".npy")
        def cruza_caras(): ca, cb = np.load(a_), np.load(b_); np.save(a_, cb); np.save(b_, ca)
        F4a = con([a_, b_], cruza_caras, placas)
        pj = os.path.join(sd, "people.json"); P = _jl(pj)
        def cruza_nombres():
            q = json.loads(json.dumps(P)); q["people"]["S1"]["name"], q["people"]["S2"]["name"] = P["people"]["S2"]["name"], P["people"]["S1"]["name"]; _js(q, pj)
        F4b = con([pj], cruza_nombres, placas)
        ok4 = (sorted(f["spk"] for f in F4a if f["kind"] == "PLACA_NOMBRE" and f["sev"] == "alta") == ["S1", "S2"]
               and not [f for f in F4a if f["kind"] in ("PLACA_VOZ", "CARA_AJENA")]
               and sorted(f["spk"] for f in F4b if f["kind"] == "PLACA_VOZ") == ["S1", "S2"]
               and sorted(f["spk"] for f in F4b if f["kind"] == "PLACA_NOMBRE" and f["sev"] == "alta") == ["S1", "S2"])
        check("reunión QA: nombre de la placa = registro de caras y voces", ok4, ([f["texto"] for f in F4a], [f["texto"] for f in F4b]))

        # 5) texto sobre la cara: la cara de Mussi (bloque b1) baja en la imagen -> el recorte no puede subirla y el titular la tapa
        f5 = dict(FACES); f5["b1"] = FACES["b1"].copy(); f5["b1"][:, 1] = 950.0; f5["b1"][:, 2] = 260.0
        F5, F5ok = textos(f5), textos()
        ok5 = [f["pieza"] for f in F5 if f["kind"] == "TEXT_ON_FACE"] == ["titular"] and not F5ok
        check("reunión QA: texto sobre la cara", ok5, [f["texto"] for f in F5 + F5ok])

        # 6) zona segura / texto cortado / titular vacío: subtítulo larguísimo y cargo larguísimo se salen del cuadro; sin título ni tema
        cp = os.path.join(pd, "captions.json"); CP = _jl(cp)
        def textos_largos():
            q = json.loads(json.dumps(P)); q["people"]["S2"]["role"] = "Presidente del Movimiento MOVER y ex convencional constituyente por Guairá"; _js(q, pj)
            _js(CP[:3] + [dict(CP[3], t="y eso es lo que venimos a decirles a todos los correligionarios")] + CP[4:], cp)
        F6 = con([pj, cp], textos_largos, textos)
        sj = os.path.join(sd, "source.json"); SJ = _jl(sj)
        F6b = con([sj], lambda: _js(dict(SJ, titulo="", tema=""), sj), textos)
        cl = [f for f in F6 if f["kind"] == "CLIPPED"]
        ok6 = bool(cl) and cl[0]["n"] == 2 and cl[0]["sev"] == "media" and _kinds(F6b) == ["TITULAR_VACIO"]
        check("reunión QA: textos fuera del cuadro y titular vacío", ok6, ([f["texto"] for f in F6], [f["texto"] for f in F6b]))
    finally:
        RU.SOURCES, RU.CLIENTS = old
        shutil.rmtree(tmp, ignore_errors=True)
