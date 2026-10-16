# Guiones curados (el editor elige el hilo narrativo; el motor hace cortes, ASR, subtítulos, gráficos, audio y QA).
# ("seg", id, rol, a, b) escena nueva · ("seg+", ...) continúa la anterior · roles: H gancho (pregunta) · Q pregunta · A respuesta
from plan import ANGLES

PROJECTS = {
    # Video 1 — NOTICIERO LIMPIO (R3/R4/R5): entrevista a pantalla completa, tarjeta de pregunta, subtítulos blancos con claves doradas
    "v1_calma": dict(
        style="news", target=60.0, pre=5, shot_max=5.0, music_db=-19.5, bpm=96, split_on_key=False,
        keys=ANGLES["calma"]["kw"],
                script=[
            ("seg", "hook", "H", 75.17, 78.43),      # ¿No existe riesgo alguno de eventual crisis en el sector financiero?
            ("seg", "ans1", "A", 78.83, 82.93),      # No, no hay ninguna crisis. No hay intervención.
            ("seg", "stat", "A", 7.47, 17.62),       # A la ciudadanía... el sistema financiero paraguayo está sólido,
            ("seg+", "stat", "A", 20.54, 30.60),     # que tienen liquidez y que los ahorros de las familias paraguayas están protegidos. Es lo más resaltante para mí.
            ("seg", "pueblo", "A", 91.20, 100.90),   # Nosotros necesitamos que el pueblo paraguayo sepa que sus ahorros... están garantizados
            ("seg", "jub", "A", 174.40, 180.70),     # a los ahorristas de los distintos bancos de plaza, están garantizados sus ahorros.
            ("seg", "calma", "A", 380.47, 398.03),   # Lo que yo vengo es a dar un mensaje de calma... certeza... ahorros garantizados.
        ],
    ),

    # Video 2 — TIKTOK TINTA (R1/R6): gancho B/N con lente curva, cajas de tinta, barridos, momento rojo, final B/N
    "v2_leite": dict(
        style="ink", target=60.0, pre=5, shot_max=4.5, music_db=-19.5, bpm=106, seed=47, split_on_key=True,
        chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
        hook_text="VENDE PATRIA", red_word="irresponsable", drop_tokens=[("causa", "e"), ("causa", "doloroso.", "first"), ("embajador", "hacer.")],
        keys=ANGLES["leite"]["kw"], extra_keys=["Twitter", "vilo", "zozobra"],
        script=[
            ("seg", "hook", "H", 153.80, 156.45),     # Él que es un... vendepatria.
            ("seg", "causa", "A", 117.27, 127.02),    # han puesto en vilo a la ciudadanía en zozobra, en incertidumbre...
            ("seg+", "causa", "A", 127.40, 128.43),   # Eso fue lo más
            ("seg+", "causa", "A", 129.83, 134.10),   # irresponsable de parte de ellos. Dije y me ratifico.
            ("seg", "cobardia", "A", 134.80, 148.00), # Esto inició Gustavo Leite, que le digo, aparte de su cobardía...
            ("seg", "vos", "A", 180.90, 191.00),      # Y vos, Gustavo Leite, lo que sos es, en primer lugar, irresponsable...
            ("seg", "embajador", "A", 205.50, 217.50),# Vos, por supuesto, ¿qué te importa? Te fuiste a la de embajador...
            ("seg", "cierre", "A", 391.80, 397.90),   # Necesitan tener la certeza de que están sus ahorros garantizados.
        ],
    ),

    # Video 3 — REPORTAJE (R2/R7): globo de cómic, cards de capítulo, fotos del banco en recuadro, barridos, subtítulos en barra azul
    "v3_reporte": dict(
        style="report", target=60.0, pre=5, shot_max=4.8, music_db=-19.5, bpm=112, seed=11, split_on_key=False,
        chords=[[52, 55, 59], [48, 52, 55], [55, 59, 62], [50, 54, 57]],
        keys={"intervención": 3, "sólido": 2, "fuerte": 2, "proceso": 2, "sumario": 3, "irregularidad": 2, "proyecto": 2, "ley": 2, "IPS": 3, "fondos": 2,
              "jubilatorios": 3, "ahorros": 3, "garantizados": 3, "certeza": 2},
        script=[
            ("seg", "q", "H", 309.20, 313.43),       # ¿Qué les dijo en esta reunión sobre las dudas que hay sobre el sistema financiero?
            ("seg", "a2", "A", 322.40, 329.00),      # Y lo que dijeron es que el sistema financiero paraguayo está fuerte.
            ("seg+", "a2", "A", 331.50, 346.10),     # No hay ni habrá ninguna intervención que sí está llevando adelante un proceso sumario...
            ("seg", "irreg", "A", 348.40, 360.30),   # Admitió que hubo una irregularidad que ellos pidieron ajustar y que lo hicieron en el plazo.
            ("seg", "ley", "A", 282.90, 297.40),     # Segundo lugar, voy a presentar... un proyecto de ley que hace garantizar los fondos jubilatorios del IPS
            ("seg", "calma", "A", 377.10, 380.20),   # Eso sí le digo. Ni tampoco va a terminar acá.
            ("seg", "cierre", "A", 391.80, 397.90),  # Necesitan tener la certeza de que están sus ahorros garantizados.
        ],
                chapters=[("a2", "El sistema", "Fuerte y sin intervención"), ("irreg", "El control", "Proceso sumario al banco"),
                  ("ley", "Su trabajo", "Proyecto de ley del IPS"), ("cierre", "El mensaje", "Ahorros garantizados")],
        cutaways=[("a2", "intervención", 0, -0.20, 2.9, "logo", None, None, "warm", "Banco Central del Paraguay"),
                  ("a2", "sumario", 0, -0.25, 3.2, "p2", (330, 10, 640), (360, 30, 560), "warm", "Proceso sumario"),
                  ("irreg", "irregularidad", 0, -0.30, 3.0, "p1", (440, 190, 560), (430, 150, 480), "gloom", None),
                  ("ley", "proyecto", 0, -0.32, 2.6, "p2", (500, 0, 600), (470, 10, 520), "warm", "Proyecto de ley"),
                  ("ley", "fondos", 0, -0.12, 2.7, "p1", (640, 140, 640), (610, 120, 540), "warm", "Fondos jubilatorios del IPS")],
    ),

    # Video 4 — TITULARES (editorial): titular grande por tema, barra de progreso, cara abajo, transición de zoom
    "v4_titulares": dict(
        style="headline", target=60.0, pre=5, shot_max=5.5, music_db=-19.5, bpm=92, seed=71, split_on_key=False,
        chords=[[57, 60, 64], [55, 59, 62], [53, 57, 60], [52, 55, 59]],
        keys=ANGLES["propuestas"]["kw"],
                script=[
            ("seg", "leyes", "A", 221.13, 226.60),    # Y mira las leyes que hoy son realidades y que cambiaron la vida de la gente.
            ("seg", "salud", "A", 227.17, 237.50),    # Entre los cuales está la salud mental, que te hace posible irte a cualquier hospital público...
            ("seg", "medicos", "A", 247.10, 262.90),  # los médicos fue acompañar ese reclamo legítimo, hacer la primera y única propuesta...
            ("seg", "pago", "A", 263.80, 273.30),     # Con el piso salarial y la única diferencia fue que yo pedí que el pago sea desde este año hasta el 2027.
            ("seg", "ips", "A", 282.90, 297.40),      # Segundo lugar... un proyecto de ley que hace garantizar los fondos jubilatorios del IPS en los bancos.
            ("seg", "cierre", "A", 298.70, 305.10),   # ¿Vos dónde estás con el problema del IPS y de la salud pública? ¿Y de la educación?
        ],
        headlines={"leyes": ["LAS {LEYES} QUE", "CAMBIARON {VIDAS}"], "salud": ["{SALUD MENTAL}", "AL ALCANCE DE TODOS"], "medicos": ["{PROPUESTA} PARA", "LOS MÉDICOS"],
                   "pago": ["PISO SALARIAL", "PAGO HASTA {2027}"], "ips": ["{PROYECTO DE LEY}", "FONDOS DEL IPS"], "cierre": ["¿Y {VOS},", "DÓNDE ESTÁS?"]},
    ),

    # Video 5 — ANIMADO ROJO + FX: golpes de palabra clave, stinger rojo, karaoke, brasas
    "v5_animado": dict(
        style="fx", target=60.0, pre=5, shot_max=4.5, music_db=-19.0, bpm=118, seed=19, split_on_key=False,
        chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
        keys=ANGLES["calma"]["kw"],
        hook_text="¿HAY CRISIS FINANCIERA?",
        script=[
            ("seg", "hook", "H", 75.17, 78.43),       # ¿No existe riesgo alguno de eventual crisis en el sector financiero?
            ("seg", "ans1", "A", 78.83, 82.93),       # No, no hay ninguna crisis. No hay intervención.
            ("seg", "sumario", "A", 337.40, 346.10),  # ...sí está llevando adelante un proceso sumario al banco Ueno como lo hizo con todos los otros bancos de plaza.
            ("seg", "pueblo", "A", 91.20, 100.90),    # Nosotros necesitamos que el pueblo paraguayo sepa que sus ahorros... están garantizados, están protegidos.
            ("seg", "ley", "A", 282.90, 297.40),      # Segundo lugar... un proyecto de ley que hace garantizar los fondos jubilatorios del IPS en los bancos.
            ("seg", "calma", "A", 378.60, 398.03),    # Ni tampoco va a terminar acá. Lo que yo vengo es a dar un mensaje de calma... ahorros garantizados.
        ],
                extra_keys=["sumario", "proyecto", "ley", "IPS", "fondos", "jubilatorios", "garantizar"],
        hits=[("ans1", "crisis.", 0, "NO HAY CRISIS"), ("sumario", "sumario", 0, "PROCESO SUMARIO"),
              ("pueblo", "garantizados,", 0, "AHORROS GARANTIZADOS"), ("ley", "proyecto", 0, "PROYECTO DE LEY"), ("calma", "calma", 0, "MENSAJE DE CALMA")],
    ),

    # Video 6 — LLAMADA CON LETRA (v16/v17): foto fija arriba, panel de llamada con letra, tomas del banco abajo
    "v6_llamada": dict(
        style="call", target=60.0, pre=0, shot_max=99.0, music_db=-19.5, bpm=92, seed=23, split_on_key=False,
        chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]],
        keys={}, still_t=244.0,
        script=[
            ("seg", "q1", "Q", 309.00, 313.73),       # ¿Qué les dijo en esta reunión sobre las dudas que hay sobre el sistema financiero?
            ("seg", "a1", "A", 322.40, 329.00),       # Y lo que dijeron es que el sistema financiero paraguayo está fuerte.
            ("seg+", "a1", "A", 331.50, 346.10),      # No hay ni habrá ninguna intervención que sí está llevando adelante un proceso sumario...
            ("seg", "q2", "Q", 346.12, 348.20, {"in_exact": True}),  # ¿Admitió las irregularidades de entidad bancaria?
            ("seg", "a2", "A", 348.40, 360.30),       # Admitió que hubo una irregularidad que ellos pidieron ajustar y que lo hicieron en el plazo.
            ("seg", "q3", "Q", 360.40, 363.00),       # ¿Sobre las transacciones, préstamos, sobre qué puntualmente?
            ("seg", "a3", "A", 364.00, 372.70),       # No, no recuerdo sobre qué... ellos le reclamaron y ellos respondieron en el tiempo, ¿verdad?
            ("seg+", "a3", "A", 372.80, 375.00),      # Y hay muchas preguntas más.
            ("seg", "cierre", "A", 391.80, 397.90),   # Necesitan tener la certeza de que están sus ahorros garantizados.
        ],
        drop_tokens=[("q1", "BCP?"), ("a1", "responsable.")],
        chips=[("a1", "intervención", 0, "SIN INTERVENCIÓN", 2.4), ("a1", "sumario", 0, "PROCESO SUMARIO", 3.0), ("a2", "irregularidad", 0, "AJUSTE EN EL PLAZO", 3.0),
               ("cierre", "ahorros", 0, "AHORROS GARANTIZADOS", 2.8)],
    ),

    # Video 7 — PANTALLA DIVIDIDA: entrevista arriba, panel azul con título del tema y ventana de tomas del banco
    "v7_dividida": dict(
        style="split", target=60.0, pre=5, shot_max=4.8, music_db=-19.5, bpm=100, seed=61, split_on_key=False,
        chords=[[52, 55, 59], [48, 52, 55], [55, 59, 62], [50, 54, 57]],
        keys={"ahorros": 3, "garantizados": 3, "protegidos": 2, "calma": 3, "certeza": 3, "sólido": 2, "liquidez": 2, "intervención": 3, "crisis": 2,
              "sumario": 3, "ley": 2, "proyecto": 2, "IPS": 3, "jubilatorios": 3},
        script=[
            ("seg", "crisis", "A", 78.83, 82.93),      # No, no hay ninguna crisis. No hay intervención.
            ("seg", "solido", "A", 7.47, 17.62),       # A la ciudadanía... el sistema financiero paraguayo está sólido,
            ("seg+", "solido", "A", 20.54, 28.10),     # que tienen liquidez y que los ahorros de las familias paraguayas están protegidos.
            ("seg", "control", "A", 337.40, 346.10),   # ...proceso sumario al banco Ueno como lo hizo con todos los otros bancos de plaza.
            ("seg", "ley", "A", 282.90, 297.40),       # proyecto de ley que hace garantizar los fondos jubilatorios del IPS.
            ("seg", "calma", "A", 380.47, 398.03),     # Lo que yo vengo es a dar un mensaje de calma...
        ],
                titles={"crisis": (1, "Sin crisis", "Sin intervención del BCP"), "solido": (2, "Sistema sólido", "Con liquidez y ahorros protegidos"), "control": (3, "El control", "Proceso sumario al banco"),
                "ley": (4, "Proyecto de ley", "Fondos jubilatorios del IPS"), "calma": (5, "Mensaje de calma", "Ahorros garantizados")},
    ),
}
