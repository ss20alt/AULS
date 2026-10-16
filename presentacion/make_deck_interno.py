# Presentación "Cómo funciona por dentro" del sistema de edición (16:9, sin nombre de marca ni logo) -> PDF con Chrome headless.
#   python make_deck_interno.py            -> Sistema_de_edicion_como_funciona.pdf
#   python make_deck_interno.py --shots    -> capturas PNG de cada diapositiva (revisión)
import os, sys, json, base64, subprocess, html, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_deck as MD                                   # paleta, tipografías y piezas aprobadas
J = lambda *p: os.path.join(HERE, *p)
OUT_PDF = "Sistema_de_edicion_como_funciona.pdf"


def foot(n, total):
    """pie de página sin marca: solo el tema y el número"""
    return f'<div class="foot"><span>Cómo funciona por dentro</span><span>{n:02d} / {total:02d}</span></div>'
OUT_HTML = J("deck_interno.html")


def b64(p): return "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()


STY = [("news", "Noticiero"), ("ink", "TikTok tinta"), ("report", "Reportaje"), ("headline", "Titulares"), ("fx", "Animado FX"),
       ("call", "Llamada con letra"), ("split", "Pantalla dividida"), ("karaoke", "Karaoke"), ("doc", "Documental"), ("tv", "TV noticias"),
       ("claves", "Las claves"), ("cita", "La cita"), ("editorial", "Editorial"), ("campana", "Campaña"), ("podcast", "Podcast")]
IMG = {k: b64(J(f"{k}.jpg") if os.path.exists(J(f"{k}.jpg")) else J("estilos", f"{k}.jpg")) for k, _ in STY}

# ---------------------------------------------------------------- datos reales de la conferencia (para los diagramas)
sys.path.insert(0, STUDIO)
_cwd = os.getcwd(); os.chdir(STUDIO)
import plan as P, content as C
os.chdir(_cwd)
WORDS = [(w["t"], w["s"], w["e"], C.WORD_SPK.get(round(w["s"], 3))) for w in P.WORDS if 75.0 < w["s"] < 83.0]
BEATS = [(b["kind"], b["s"], b["e"]) for b in C.BEATS]
SRC_DUR = 434.0


def wave_bars(t0, t1, step=0.03):
    w = wave.open(P.SRC["voice"]); sr = w.getframerate(); ch = w.getnchannels()
    w.setpos(int(t0 * sr)); a = np.frombuffer(w.readframes(int((t1 - t0) * sr)), np.int16).reshape(-1, ch).astype(np.float32).mean(1) / 32768
    n = int((t1 - t0) / step); h = int(step * sr)
    db = np.array([20 * np.log10(np.sqrt(np.mean(a[i * h:(i + 1) * h] ** 2)) + 1e-9) for i in range(n)])
    return np.clip((db + 52) / 40, 0.02, 1.0)


CSS = MD.CSS + """
/* recorrido */
.flow { display: grid; grid-template-columns: 170px repeat(5, 1fr) 170px; gap: 18px; align-items: stretch; margin-top: 10px; }
.flow .io { border: 2px dashed var(--muted); border-radius: 18px; display: grid; place-items: center; text-align: center; padding: 18px;
            font-family: var(--display); font-stretch: 78%; font-weight: 800; font-size: 28px; color: var(--muted); }
.flow .io.out { border: 3px solid var(--signal); color: var(--ink); }
.flow .io:first-child { position: relative; }
.flow .io:first-child::after { content: "→"; position: absolute; right: -19px; top: 50%; transform: translateY(-50%); color: var(--signal); font-size: 26px; font-weight: 700; }
.node { background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 26px 24px; display: grid; gap: 14px; align-content: start; position: relative; }
.node::after { content: "→"; position: absolute; right: -19px; top: 50%; transform: translateY(-50%); color: var(--signal); font-size: 26px; font-weight: 700; z-index: 2; }
.flow > :nth-child(6)::after { content: "→"; }
.node .num { width: 46px; height: 46px; border-radius: 50%; background: var(--signal); color: var(--signal-ink); display: grid; place-items: center;
             font-family: var(--mono); font-weight: 700; font-size: 20px; }
.node h3 { font-size: 36px; }
.node p { font-size: 22px; line-height: 1.4; color: var(--muted); }
.loop { margin-top: 28px; display: flex; align-items: center; gap: 22px; border: 1px solid var(--line); border-radius: 18px; padding: 22px 28px; background: var(--surface); }
.loop .num { width: 46px; height: 46px; border-radius: 50%; border: 3px solid var(--signal); color: var(--signal); display: grid; place-items: center; font-family: var(--mono); font-weight: 700; font-size: 20px; flex: none; }
.loop b { font-family: var(--display); font-stretch: 80%; font-size: 32px; }
.loop span { font-size: 23px; color: var(--muted); }
.loop .arc { margin-left: auto; font-family: var(--mono); font-size: 18px; color: var(--signal); }

/* dos columnas genéricas */
.cols { display: grid; grid-template-columns: 1fr 1.15fr; gap: 80px; align-items: center; }
.points { margin: 0; padding: 0; list-style: none; border-top: 3px solid var(--ink); }
.points li { display: grid; grid-template-columns: 48px 1fr; gap: 18px; padding: 24px 0; border-bottom: 1px solid var(--line); align-items: start; }
.points .k { font-family: var(--mono); font-size: 20px; color: var(--signal); font-weight: 700; padding-top: 4px; }
.points b { display: block; font-size: 29px; margin-bottom: 6px; }
.points span { font-size: 23px; line-height: 1.42; color: var(--muted); }

/* transcripción */
.script { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 34px 38px; display: grid; gap: 26px; }
.line { display: grid; grid-template-columns: 150px 1fr; gap: 20px; align-items: start; }
.who { font-family: var(--mono); font-size: 17px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; padding: 8px 12px; border-radius: 8px; text-align: center; }
.who.r { background: rgba(120, 160, 255, .18); color: #a9c2ff; }
.who.l { background: rgba(255, 74, 88, .18); color: var(--signal); }
.words { display: flex; flex-wrap: wrap; gap: 10px 8px; }
.w { display: grid; gap: 2px; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--line); background: var(--paper); }
.w b { font-size: 25px; font-weight: 600; }
.w i { font-style: normal; font-family: var(--mono); font-size: 14px; color: var(--muted); }
.script .note { font-family: var(--mono); font-size: 17px; color: var(--muted); border-top: 1px dashed var(--line); padding-top: 14px; }

/* mapa de ideas */
.map { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 34px 40px; display: grid; gap: 22px; }
.map .bar { height: 84px; }
.map .blk { top: 10px; bottom: 10px; border: 0; }
.legend { display: flex; flex-wrap: wrap; gap: 14px 30px; font-size: 21px; color: var(--muted); }
.legend span { display: inline-flex; align-items: center; gap: 10px; }
.legend i { width: 22px; height: 22px; border-radius: 6px; display: inline-block; }
.ex { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.ex div { border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px; display: grid; gap: 8px; background: var(--paper); }
.ex .t { font-family: var(--mono); font-size: 16px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.ex b { font-family: var(--display); font-stretch: 78%; font-weight: 850; font-size: 34px; }
.ex p { font-size: 19px; color: var(--muted); }

/* estructura del guion */
.arc3 { display: grid; grid-template-columns: 1.35fr 2.6fr 1.25fr; gap: 10px; }
.arc3 div { border-radius: 14px; padding: 22px 24px; display: grid; gap: 8px; align-content: start; }
.arc3 .g { background: var(--signal); color: var(--signal-ink); }
.arc3 .d { background: var(--surface); border: 1px solid var(--line); }
.arc3 .c { background: var(--ink); color: var(--paper); }
.arc3 b { font-family: var(--display); font-stretch: 80%; font-weight: 850; font-size: 34px; }
.arc3 span { font-size: 20px; opacity: .85; }
.durs { display: flex; gap: 14px; margin-top: 26px; align-items: center; flex-wrap: wrap; }
.durs .chip { font-family: var(--mono); font-size: 22px; font-weight: 700; border: 2px solid var(--ink); border-radius: 999px; padding: 10px 22px; }
.durs .lbl { font-size: 22px; color: var(--muted); margin-right: 6px; }

/* onda y cortes */
.wavebox { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 40px 44px 30px; display: grid; gap: 18px; }
.wave { position: relative; height: 300px; display: flex; align-items: center; gap: 2px; }
.wave .b { flex: 1; border-radius: 3px; background: var(--muted); opacity: .55; }
.wave .b.l { background: var(--ink); opacity: .9; }
.mark { position: absolute; top: -18px; bottom: -18px; width: 0; border-left: 4px solid; }
.mark.m-si { border-color: #3ccf8e; }
.mark.m-no { border-color: var(--signal); border-left-style: dashed; }
.mark .lab { position: absolute; top: -46px; left: 50%; transform: translateX(-50%); white-space: nowrap; font-family: var(--mono); font-size: 17px; font-weight: 700;
             padding: 6px 12px; border-radius: 8px; }
.mark.m-si .lab { background: #3ccf8e; color: #062114; }
.mark.m-no .lab { background: var(--signal); color: var(--signal-ink); }
.wlabels { position: relative; height: 36px; }
.wlabels span { position: absolute; transform: translateX(-50%); font-size: 21px; color: var(--muted); white-space: nowrap; }
.rules2 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 30px; }
.rules2 div { border-top: 3px solid var(--ink); padding-top: 16px; display: grid; gap: 8px; }
.rules2 b { font-size: 27px; }
.rules2 span { font-size: 21px; color: var(--muted); line-height: 1.4; }

/* capas */
.stack { display: grid; gap: 12px; }
.layer { display: grid; grid-template-columns: 58px 1fr; gap: 18px; align-items: center; border: 1px solid var(--line); border-radius: 16px; padding: 12px 24px; background: var(--surface); }
.layer .n { font-family: var(--mono); font-size: 20px; color: var(--signal); font-weight: 700; }
.layer b { font-size: 27px; }
.layer span { display: block; font-size: 20px; color: var(--muted); margin-top: 2px; }
.build { display: grid; grid-template-columns: 1fr 340px; gap: 70px; align-items: center; }
.build .phone { width: 340px; }

/* estilos */
.grid15 { display: grid; grid-template-columns: repeat(8, 156px); gap: 22px 46px; justify-content: center; }
.grid15 figure { margin: 0; display: grid; gap: 12px; }
.grid15 .phone { width: 100%; border-width: 5px; border-radius: 18px; }
.grid15 figcaption { font-family: var(--display); font-stretch: 80%; font-weight: 800; font-size: 22px; text-align: center; white-space: nowrap; }
.grid15 .custom { width: 100%; border-radius: 18px; font-size: 22px; padding: 12px; }

/* revisión */
.rev { display: grid; grid-template-columns: 1fr 1fr; gap: 0 70px; }
.rev ul { margin: 0; padding: 0; list-style: none; }
.rev li.hd { display: grid; grid-template-columns: 1fr; gap: 8px; border-top: 3px solid var(--ink); padding-top: 22px; margin-bottom: 8px; }
.rev .hd b { font-family: var(--display); font-stretch: 80%; font-weight: 850; font-size: 40px; }
.rev .hd span { font-size: 22px; color: var(--muted); }
.rev li { display: grid; grid-template-columns: 40px 1fr; gap: 14px; align-items: center; padding: 18px 0; border-bottom: 1px solid var(--line); font-size: 26px; }
.gate { margin-top: 40px; display: flex; gap: 22px; align-items: center; border: 3px solid var(--signal); border-radius: 18px; padding: 24px 30px; }
.gate b { font-family: var(--display); font-stretch: 80%; font-size: 34px; font-weight: 850; }
.gate span { font-size: 23px; color: var(--muted); }
.stop { width: 52px; height: 52px; border-radius: 12px; background: var(--signal); flex: none; position: relative; }
.stop::after { content: ""; position: absolute; inset: 15px; border-radius: 4px; background: var(--signal-ink); }

/* personas */
.people { display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 20px; padding: 34px 32px; display: grid; gap: 18px; align-content: start; }
.card .ic { font-family: var(--mono); font-size: 18px; font-weight: 700; color: var(--signal); letter-spacing: .1em; text-transform: uppercase; }
.card b { font-family: var(--display); font-stretch: 80%; font-weight: 850; font-size: 40px; line-height: 1.02; }
.card p { font-size: 23px; line-height: 1.45; color: var(--muted); }
.card .q { font-family: var(--mono); font-size: 19px; color: var(--ink); background: var(--paper); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }

/* control manual: proyecto de CapCut */
.flow .io.out small { display: block; margin-top: 8px; font-family: var(--mono); font-stretch: 100%; font-weight: 600; font-size: 15px; color: var(--signal); }
.cc { display: grid; grid-template-columns: 1.3fr 1fr; gap: 70px; align-items: center; }
.tl { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 26px 30px 30px; display: grid; gap: 12px; }
.tl .top { display: flex; justify-content: space-between; align-items: baseline; font-family: var(--mono); font-size: 17px; color: var(--muted); padding-bottom: 6px; }
.tl .top b { color: var(--ink); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.lane { display: grid; grid-template-columns: 128px 1fr; gap: 16px; align-items: center; }
.lane > span { font-family: var(--mono); font-size: 16px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
.lane .tr { position: relative; height: 46px; background: var(--track); border-radius: 8px; }
.lane .tr.ruler { height: 26px; background: none; border-bottom: 1px solid var(--line); }
.ruler i { position: absolute; bottom: 0; width: 1px; height: 8px; background: var(--muted); opacity: .6; }
.ruler i.m { height: 16px; opacity: 1; }
.ruler em { position: absolute; bottom: 12px; transform: translateX(-50%); font-family: var(--mono); font-style: normal; font-size: 14px; color: var(--muted); }
.clip { position: absolute; top: 5px; bottom: 5px; border-radius: 6px; overflow: hidden; }
.clip.vid { background-size: cover; background-position: center 28%; outline: 2px solid var(--paper); outline-offset: -2px; }
.clip.voz { background: repeating-linear-gradient(90deg, rgba(60, 207, 142, .95) 0 3px, rgba(60, 207, 142, .35) 3px 6px); }
.clip.sub { background: var(--ink); opacity: .82; }
.clip.tit { background: #ffc93c; }
.clip.gra { background: #7f9cff; }
.clip.mus { background: linear-gradient(90deg, rgba(79, 195, 217, .55), rgba(79, 195, 217, .9)); }
.clip.sfx { background: var(--signal); top: 9px; bottom: 9px; }
.clip b { position: absolute; left: 8px; top: 50%; transform: translateY(-50%); font-family: var(--mono); font-size: 13px; color: var(--signal-ink); white-space: nowrap; }
.playhead { position: absolute; top: 46px; bottom: 18px; width: 3px; background: var(--signal); border-radius: 2px; }
.playhead::before { content: ""; position: absolute; top: -10px; left: -7px; border: 8.5px solid transparent; border-top: 11px solid var(--signal); }
.tl .body { position: relative; display: grid; gap: 10px; }
.cc .points li { padding: 26px 0; }

/* ciclo de aprendizaje */
.cycle { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; position: relative; }
.cycle div { background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 26px 22px; display: grid; gap: 12px; position: relative; }
.cycle div::after { content: "→"; position: absolute; right: -17px; top: 50%; transform: translateY(-50%); color: var(--signal); font-size: 24px; font-weight: 700; }
.cycle div:last-child::after { content: ""; }
.cycle .num { font-family: var(--mono); color: var(--signal); font-size: 18px; font-weight: 700; }
.cycle b { font-size: 29px; }
.cycle span { font-size: 21px; color: var(--muted); line-height: 1.4; }
.back { margin-top: 14px; text-align: center; font-family: var(--mono); font-size: 18px; color: var(--signal); }
.facts { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 42px; }
.facts div { border-top: 3px solid var(--ink); padding-top: 18px; display: grid; gap: 8px; }
.facts b { font-family: var(--display); font-stretch: 75%; font-weight: 900; font-size: 64px; line-height: 1; }
.facts span { font-size: 23px; color: var(--muted); line-height: 1.4; }

/* números */
.nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0 60px; }
.nums div { border-top: 3px solid var(--ink); padding: 26px 0 34px; display: grid; gap: 10px; }
.nums b { font-family: var(--display); font-stretch: 72%; font-weight: 900; font-size: 104px; line-height: .95; }
.nums b em { font-size: 56px; }
.nums span { font-size: 24px; color: var(--muted); line-height: 1.4; max-width: 460px; }
"""


def slides():
    S = []
    # 1 · portada
    S.append(f"""
<section class="slide cover">
  <div class="grid">
    <div>
      <p class="eyebrow">Cómo funciona por dentro</p>
      <h1 style="margin-top:20px">Un editor que <em>escucha</em>, entiende, elige y se revisa solo.</h1>
      <p class="lead">Una mirada general a las piezas del sistema: qué hace con un video en bruto, en qué orden, y cómo se asegura de no equivocarse.</p>
    </div>
    <div class="fan">
      <div class="phone p1"><img src="{IMG['editorial']}"></div>
      <div class="phone p2"><img src="{IMG['karaoke']}"></div>
      <div class="phone p3"><img src="{IMG['tv']}"></div>
      <div class="tc">1 grabación en bruto → muchos videos verificados</div>
    </div>
  </div>
  <div class="specs">
    <div><b>6</b><span>etapas, de la grabación al video listo</span></div>
    <div><b>15</b><span>estilos de edición del mismo material</span></div>
    <div><b>1 a 4 min</b><span>duración exacta, al segundo</span></div>
    <div><b>2</b><span>revisiones: antes y después de producir</span></div>
  </div>
</section>""")
    # 2 · el recorrido
    nodes = [("Escucha", "Pasa la voz a texto y reconoce quién habla."), ("Entiende", "Divide la charla en ideas completas."),
             ("Elige", "Arma el guion según la historia y la duración."), ("Construye", "Corta, subtitula, diseña y pone música."),
             ("Revisa", "Controla todo antes y después de producir.")]
    nd = "".join(f'<div class="node"><span class="num">{i + 1}</span><h3>{a}</h3><p>{b}</p></div>' for i, (a, b) in enumerate(nodes))
    S.append(f"""
<section class="slide">
  <div class="head"><p class="eyebrow">El recorrido</p><h2>Del video en bruto al video listo, en seis etapas.</h2>
  <p class="lead">Cada etapa le pasa su trabajo a la siguiente. Ninguna adivina: todas se basan en lo que realmente se dijo y se grabó.</p></div>
  <div>
    <div class="flow"><div class="io">Video en bruto</div>{nd}<div class="io out"><span>Videos listos<small>+ proyecto de CapCut</small></span></div></div>
    <div class="loop"><span class="num">6</span><div><b>Aprende.</b> <span>Cada error que se encuentra se convierte en una regla nueva y en un control permanente.</span></div><span class="arc">↺ vuelve a todas las etapas</span></div>
  </div>
</section>""")
    # 3 · escucha
    def wchip(t, s): return f'<span class="w"><b>{html.escape(t)}</b><i>{int(s // 60)}:{s % 60:05.2f}</i></span>'
    q = "".join(wchip(t, s) for t, s, e, k in WORDS if k == "R")
    a = "".join(wchip(t, s) for t, s, e, k in WORDS if k == "L")
    S.append(f"""
<section class="slide">
  <div class="head"><p class="eyebrow">Etapa 1 · Escucha</p><h2>Primero escucha todo, palabra por palabra.</h2></div>
  <div class="cols">
    <ul class="points">
      <li><span class="k">01</span><span><b>Pasa la voz a texto</b><span>Cada palabra queda escrita y con el instante exacto en que se dijo, con precisión de centésimas de segundo.</span></span></li>
      <li><span class="k">02</span><span><b>Reconoce quién habla</b><span>Distingue la voz de la protagonista de la de los periodistas, para no mezclar sus palabras.</span></span></li>
      <li><span class="k">03</span><span><b>Prepara la imagen y el sonido</b><span>Limpia la voz, corrige el color del video y sigue el rostro para mantenerlo bien encuadrado.</span></span></li>
    </ul>
    <div class="script">
      <div class="line"><span class="who r">Prensa</span><div class="words">{q}</div></div>
      <div class="line"><span class="who l">Ella</span><div class="words">{a}</div></div>
      <p class="note">Fragmento real de una conferencia: así queda guardada cada palabra (texto · minuto y segundo).</p>
    </div>
  </div>
</section>""")
    # 4 · entiende
    COL = {"pregunta": "#7f9cff", "dato": "#4fc3d9", "mensaje": "#ffc93c", "cierre": "#ffffff", "ataque": "#ff4a58", "denuncia": "#ff8a5c",
           "logro": "#3ccf8e", "propuesta": "#3ccf8e"}
    pct = lambda x: f"{100 * x / SRC_DUR:.3f}%"
    blocks = "".join(f'<span class="blk" style="left:{pct(s)};width:{pct(max(1.5, e - s))};background:{COL.get(k, "#9ba5bf")}"></span>' for k, s, e in BEATS)
    axis = "".join(f'<span style="left:{pct(m * 60)}">{m}:00</span>' for m in range(8))
    leg = [("Pregunta de la prensa", "#7f9cff"), ("Dato", "#4fc3d9"), ("Mensaje", "#ffc93c"), ("Respuesta firme", "#ff4a58"),
           ("Denuncia", "#ff8a5c"), ("Propuesta o logro", "#3ccf8e"), ("Cierre", "#ffffff")]
    lg = "".join(f'<span><i style="background:{c}"></i>{t}</span>' for t, c in leg)
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:34px"><p class="eyebrow">Etapa 2 · Entiende</p><h2>Después entiende de qué se habla.</h2>
  <p class="lead">Divide toda la grabación en bloques de idea completos. A cada bloque le asigna un tipo y le propone un titular.</p></div>
  <div class="map">
    <div class="case-top"><h3>Mapa de ideas de una conferencia de 7 minutos</h3><span class="mono" style="font-size:18px;color:var(--muted)">24 bloques</span></div>
    <div><div class="bar">{blocks}</div><div class="axis">{axis}</div></div>
    <div class="legend">{lg}</div>
    <div class="ex">
      <div><span class="t" style="color:#a9c2ff">Pregunta de la prensa</span><b>NO HAY CRISIS</b><p>La pregunta queda unida a su respuesta.</p></div>
      <div><span class="t" style="color:#4fc3d9">Dato</span><b>SISTEMA SÓLIDO</b><p>Lo que informó la autoridad.</p></div>
      <div><span class="t" style="color:#ffc93c">Mensaje</span><b>MENSAJE DE CALMA</b><p>La idea con la que conviene cerrar.</p></div>
    </div>
  </div>
</section>""")
    # 5 · elige
    S.append("""
<section class="slide">
  <div class="head"><p class="eyebrow">Etapa 3 · Elige</p><h2>Elige qué entra y en qué orden, como un editor.</h2>
  <p class="lead">Según la historia que se quiere contar, toma bloques completos del mapa y arma el guion para la duración pedida.</p></div>
  <div class="cols" style="grid-template-columns:1.1fr 1fr">
    <div>
      <div class="arc3"><div class="g"><b>Gancho</b><span>Lo más fuerte, para frenar el dedo.</span></div>
        <div class="d"><b>Desarrollo</b><span>Las ideas de la historia, completas y en un orden que se entiende.</span></div>
        <div class="c"><b>Cierre</b><span>El mensaje final y las redes.</span></div></div>
      <div class="durs"><span class="lbl">Duración exacta:</span><span class="chip">1 min</span><span class="chip">2 min</span><span class="chip">3 min</span><span class="chip">4 min</span></div>
    </div>
    <ul class="points">
      <li><span class="k">✓</span><span><b>Solo ideas completas</b><span>Nunca una frase a la mitad ni una idea sin su comienzo.</span></span></li>
      <li><span class="k">✓</span><span><b>Pregunta con respuesta</b><span>Si entra una pregunta de la prensa, entra con su respuesta.</span></span></li>
      <li><span class="k">✓</span><span><b>Coherencia</b><span>Para completar la duración solo suma ideas del mismo tema.</span></span></li>
      <li><span class="k">✓</span><span><b>Palabras textuales</b><span>Elige y ordena lo que se dijo. No inventa ni cambia frases.</span></span></li>
    </ul>
  </div>
</section>""")
    # 6 · corta (onda real)
    t0, t1 = 78.55, 82.75
    bars = wave_bars(t0, t1)
    n = len(bars)
    tt = [t0 + (i + 0.5) * (t1 - t0) / n for i in range(n)]
    spk_at = lambda t: next((k for w_, s, e, k in WORDS if s - 0.05 <= t <= e + 0.05), None)
    bh = "".join(f'<span class="b{" l" if spk_at(t) == "L" else ""}" style="height:{max(3, v * 100):.1f}%"></span>' for v, t in zip(bars, tt))
    px = lambda t: f"{100 * (t - t0) / (t1 - t0):.2f}%"
    marks = [(78.89, "m-si", "corte posible"), (79.72, "m-no", "nunca acá"), (80.72, "m-si", "corte posible")]
    mk = "".join(f'<span class="mark {c}" style="left:{px(t)}"><span class="lab">{"✓ " if c == "m-si" else "✗ "}{lab}</span></span>' for t, c, lab in marks)
    wl = "".join(f'<span style="left:{px((s + e) / 2)}">{html.escape(w)}</span>' for w, s, e, k in WORDS if s >= t0 - 0.1 and e <= t1 + 0.1 and k == "L")
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:56px"><p class="eyebrow">Etapa 4 · Construye · el corte</p><h2>Corta donde corta un buen editor: en los silencios.</h2></div>
  <div class="wavebox">
    <div class="wave">{bh}{mk}</div>
    <div class="wlabels">{wl}</div>
  </div>
  <div class="rules2">
    <div><b>Mide la voz, no el texto</b><span>El corte se ubica donde la voz realmente se apaga, no donde el texto dice que termina una palabra.</span></div>
    <div><b>Acorta las pausas largas</b><span>Los silencios largos se recortan para dar ritmo, sin tocar nunca una palabra.</span></div>
    <div><b>No separa lo dicho de corrido</b><span>Si dos frases van pegadas, no las separa: busca otro punto o las deja juntas.</span></div>
  </div>
</section>""")
    # 7 · construye (capas)
    layers = [("Imagen", "Encuadre centrado en el rostro, con color corregido."), ("Subtítulos", "Sincronizados con cada palabra; las claves, resaltadas."),
              ("Titulares", "Uno por idea, cuando ella empieza a responder."), ("Identidad", "Nombre, cargo, redes y colores de la persona."),
              ("Sonido", "Voz limpia al frente y música que baja sola cuando hay voz."), ("Cierre", "Pantalla final con redes, duración exacta.")]
    ly = "".join(f'<div class="layer"><span class="n">{i + 1:02d}</span><span><b>{a}</b><span>{b}</span></span></div>' for i, (a, b) in enumerate(layers))
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:30px"><p class="eyebrow">Etapa 4 · Construye · la forma</p><h2>Le da forma por capas.</h2></div>
  <div class="build"><div class="stack">{ly}</div><div class="phone"><img src="{IMG['tv']}"></div></div>
</section>""")
    # 8 · estilos
    figs = "".join(f'<figure><div class="phone"><img src="{IMG[k]}"></div><figcaption>{n}</figcaption></figure>' for k, n in STY)
    figs += '<figure><div class="custom">Un estilo nuevo, a partir de referencias</div><figcaption>A medida</figcaption></figure>'
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:28px"><p class="eyebrow">Estilos</p><h2>Un mismo material, quince formas de contarlo.</h2></div>
  <div class="grid15">{figs}</div>
</section>""")
    # 9 · revisa
    pre = ["¿El guion se entiende de principio a fin?", "¿Alguna frase quedó cortada o sin su comienzo?", "¿Los titulares aparecen a tiempo y sin repetirse?", "¿Se lee todo? ¿Algo tapa la cara o se sale de la pantalla?"]
    post = ["Duración exacta, al segundo", "Volumen estándar de las redes", "Música por debajo de la voz", "Subtítulos fieles a lo que se escucha", "Encuadre y zona segura de cada app"]
    li = lambda xs: "".join(f'<li><span class="ok"></span><span>{x}</span></li>' for x in xs)
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:40px"><p class="eyebrow">Etapa 5 · Revisa</p><h2>Se revisa dos veces: antes y después de producir.</h2></div>
  <div>
    <div class="rev">
      <ul><li class="hd" style="border-bottom:0"><b>Antes</b><span>Un "espectador" automático mira el guion y muestras de la imagen.</span></li>{li(pre)}</ul>
      <ul><li class="hd" style="border-bottom:0"><b>Después</b><span>El control final mide el video terminado.</span></li>{li(post)}</ul>
    </div>
    <div class="gate"><span class="stop"></span><div><b>Si algo no pasa la revisión, el video no se entrega.</b><br><span>Se corrige la causa y se vuelve a revisar desde el principio.</span></div></div>
  </div>
</section>""")
    # 10 · personas
    S.append("""
<section class="slide">
  <div class="head"><p class="eyebrow">Las personas en el circuito</p><h2>La máquina propone. El equipo decide.</h2>
  <p class="lead">El sistema hace el trabajo pesado; en tres momentos clave, una persona tiene la última palabra.</p></div>
  <div class="people">
    <div class="card"><span class="ic">Aprueba</span><b>El mapa de ideas</b><p>Revisa los bloques y los titulares propuestos, y los aprueba o los ajusta.</p></div>
    <div class="card"><span class="ic">Confirma</span><b>Las palabras dudosas</b><p>Cuando la transcripción no está segura, escucha el fragmento y confirma con un clic.</p></div>
    <div class="card"><span class="ic">Corrige</span><b>Con sus palabras</b><p>Pide cambios como se lo diría a un editor, y el sistema los aplica.</p><p class="q">«En el 0:43 dice “trató”, no “trato”»</p></div>
  </div>
</section>""")
    # 11 · control manual: cada video también como proyecto de CapCut
    cuts = [0.0, 0.085, 0.2, 0.31, 0.45, 0.565, 0.69, 0.82, 0.925, 1.0]           # cortes del video (proporción de la línea de tiempo)
    pc = lambda x: f"{100 * x:.2f}%"
    clip = lambda cls, a, b, extra="": f'<span class="clip {cls}" style="left:{pc(a)};width:calc({pc(b - a)} - 3px){extra}">'
    vid = "".join(clip("vid", a, b, f";background-image:url({IMG['tv' if i % 3 == 0 else 'editorial' if i % 3 == 1 else 'karaoke']})") + "</span>"
                  for i, (a, b) in enumerate(zip(cuts[:-2], cuts[1:-1])))
    vid += clip("tit", cuts[-2], 1.0) + "</span>"
    voz = "".join(clip("voz", a + 0.004, b - 0.004) + "</span>" for a, b in zip(cuts[:-2], cuts[1:-1]))
    sub = ""
    for a, b in zip(cuts[:-2], cuts[1:-1]):
        k = 3 if b - a > 0.11 else 2
        for j in range(k):
            s0 = a + (b - a) * j / k + 0.004; s1 = a + (b - a) * (j + 1) / k - 0.006
            sub += clip("sub", s0, s1) + "</span>"
    tit = "".join(clip("tit", cuts[i] + 0.01, cuts[i] + 0.075) + "</span>" for i in (1, 3, 5, 7))
    gra = clip("gra", 0.012, 0.16) + "<b>NOMBRE</b></span>" + clip("gra", 0.36, 0.43) + "</span>" + clip("gra", 0.6, 0.67) + "</span>"
    mus = clip("mus", 0.0, 1.0) + "<b>MÚSICA</b></span>"
    sfx = "".join(clip("sfx", c - 0.006, c + 0.006) + "</span>" for c in cuts[1:-1])
    ticks = "".join(f'<i class="{"m" if k % 5 == 0 else ""}" style="left:{100 * k / 60:.3f}%"></i>' for k in range(61))
    ticks += "".join(f'<em style="left:{100 * k / 60:.3f}%">0:{k:02d}</em>' for k in (10, 20, 30, 40, 50))
    lanes = [("", f'<div class="tr ruler">{ticks}</div>'), ("Subtítulos", sub), ("Titulares", tit), ("Gráficos", gra), ("Video", vid),
             ("Voz", voz), ("Música", mus), ("Efectos", sfx)]
    ln = "".join(f'<div class="lane"><span>{a}</span>' + (b if a == "" else f'<div class="tr">{b}</div>') + "</div>" for a, b in lanes)
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:40px"><p class="eyebrow">Control manual · CapCut</p><h2 style="text-wrap:balance">Cada video también sale como proyecto de CapCut.</h2>
  <p class="lead">Además del video terminado, cada video se puede exportar en formato de CapCut, para tener el control fino de cada uno y no dejar todo en manos de la IA.</p></div>
  <div class="cc">
    <div class="tl">
      <div class="top"><b>Proyecto editable</b><span>una pista para cada cosa</span></div>
      <div class="body">{ln}<span class="playhead" style="left:calc(144px + (100% - 144px) * 0.38)"></span></div>
    </div>
    <ul class="points">
      <li><span class="k">01</span><span><b>Cada pieza, en su pista</b><span>Cortes, subtítulos, titulares, gráficos, voz, música y efectos llegan por separado, listos para tocar.</span></span></li>
      <li><span class="k">02</span><span><b>Se ajusta lo que haga falta</b><span>Corregir una palabra, cambiar o mover un titular, alargar un corte, bajar la música.</span></span></li>
      <li><span class="k">03</span><span><b>El equipo decide el final</b><span>La IA deja el video armado; la persona hace los cambios que cada video necesita y lo exporta desde CapCut.</span></span></li>
    </ul>
  </div>
</section>""")
    # 12 · aprende
    cyc = [("Se detecta", "Un error aparece en una revisión o lo marca el equipo."), ("Se corrige", "Se arregla la causa, no solo ese video."),
           ("Se vuelve regla", "La solución queda incorporada al sistema."), ("Se vuelve prueba", "Un control permanente vigila que no vuelva a pasar."),
           ("Se controla siempre", "Las pruebas se corren antes de cada entrega.")]
    cy = "".join(f'<div><span class="num">{i + 1:02d}</span><b>{a}</b><span>{b}</span></div>' for i, (a, b) in enumerate(cyc))
    S.append(f"""
<section class="slide">
  <div class="head"><p class="eyebrow">Etapa 6 · Aprende</p><h2>Cada error encontrado se convierte en una regla.</h2></div>
  <div>
    <div class="cycle">{cy}</div>
    <p class="back">↺ y el ciclo vuelve a empezar con cada video nuevo</p>
    <div class="facts">
      <div><b>+50</b><span>controles automáticos se corren antes de cada entrega: cortes, subtítulos, guion, imagen y sonido.</span></div>
      <div><b>A propósito</b><span>Los controles se prueban metiendo errores adrede. Si un control no los encuentra, no sirve y se rehace.</span></div>
    </div>
  </div>
</section>""")
    # 13 · números
    S.append("""
<section class="slide">
  <div class="head"><p class="eyebrow">En números</p><h2>Lo que se midió en el trabajo real.</h2></div>
  <div class="nums">
    <div><b>0</b><span>cortes sobre la voz en las pruebas: siempre en silencios reales.</span></div>
    <div><b>98,6<em>%</em></b><span>de acierto al reconocer quién habla: la protagonista o la prensa.</span></div>
    <div><b>15</b><span>estilos de edición, con la identidad de cada persona.</span></div>
    <div><b>1 a 4<em> min</em></b><span>de duración exacta, al segundo, o libre hasta 2 minutos.</span></div>
    <div><b>9:16</b><span>1080 × 1920, para Reels, TikTok y Shorts.</span></div>
    <div><b>&lt; 15<em> MB</em></b><span>versión liviana de cada video, para WhatsApp.</span></div>
  </div>
</section>""")
    # 14 · cierre
    S.append(f"""
<section class="slide close">
  <p class="eyebrow">En resumen</p>
  <h2 style="margin-top:22px">Rápido, consistente y <em>verificado.</em></h2>
  <p class="lead">El sistema escucha, entiende, elige, construye y se revisa. Las personas deciden lo importante.</p>
</section>""")
    total = len(S)
    return [s.replace("</section>", foot(i + 1, total) + "</section>") if i not in (0, total - 1) else s for i, s in enumerate(S)]


def build():
    S = slides()
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Cómo funciona por dentro</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap">
<style>{CSS}
body.solo .slide {{ display: none; }} body.solo .slide.show {{ display: flex; }}</style></head>
<body>{''.join(S)}
<script>
const m = location.hash.match(/^#s(\\d+)$/);
if (m) {{ document.body.classList.add('solo'); const s = document.querySelectorAll('.slide')[+m[1] - 1]; if (s) s.classList.add('show'); }}
</script></body></html>"""
    open(OUT_HTML, "w", encoding="utf-8").write(doc)
    return len(S)


def to_pdf(out):
    url = "file:///" + OUT_HTML.replace("\\", "/")
    r = subprocess.run([MD.CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                        "--virtual-time-budget=15000", f"--print-to-pdf={out}", url], capture_output=True, text=True, timeout=180)
    if not os.path.exists(out): raise RuntimeError(r.stderr[-800:])


def shots(n):
    d = J("shots_interno"); os.makedirs(d, exist_ok=True)
    for i in range(1, n + 1):
        url = "file:///" + OUT_HTML.replace("\\", "/") + f"#s{i}"
        subprocess.run([MD.CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080", "--virtual-time-budget=15000",
                        f"--screenshot={os.path.join(d, f's{i:02d}.png')}", url], capture_output=True, timeout=120)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    n = build()
    if "--shots" in sys.argv: shots(n); print("capturas:", n)
    else:
        out = J(OUT_PDF); to_pdf(out); print("pdf:", out, os.path.getsize(out) // 1024, "KB")
