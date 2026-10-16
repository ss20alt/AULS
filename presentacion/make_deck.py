# Genera la presentación HDERLIS (16:9) en HTML y la imprime a PDF con Chrome headless.
#   python make_deck.py            -> HDERLIS_presentacion.pdf
#   python make_deck.py --shots    -> capturas PNG de cada diapositiva (revisión)
import os, sys, json, base64, subprocess, html

HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *p: os.path.join(HERE, *p)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BRAND = "HDERLIS"

img = {k: "data:image/jpeg;base64," + base64.b64encode(open(J(f"{k}.jpg"), "rb").read()).decode()
       for k in ("news", "ink", "report", "headline", "fx", "call", "split")}
case = json.load(open(J("caso.json"), encoding="utf-8"))

CSS = """
@page { size: 1920px 1080px; margin: 0; }
:root {
  --paper: #0a1124; --surface: #111a33; --ink: #e8ecf5; --muted: #9ba5bf; --line: #253050; --track: #1b2441;
  --signal: #ff4a58; --signal-ink: #1a0508; --bezel: #000611; --chip: rgba(155, 165, 191, .22); --chip-line: rgba(155, 165, 191, .34);
  --display: "Archivo", "Arial Narrow", Arial, sans-serif;
  --body: "Source Sans 3", "Segoe UI", Arial, sans-serif;
  --mono: "JetBrains Mono", Consolas, monospace;
  color-scheme: dark;
}
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
html, body { margin: 0; padding: 0; background: var(--paper); color: var(--ink); font-family: var(--body); }
.slide { width: 1920px; height: 1080px; position: relative; overflow: hidden; background: var(--paper);
         padding: 92px 120px 120px; display: flex; flex-direction: column; break-after: page; page-break-after: always; }
.slide:last-child { break-after: auto; page-break-after: auto; }
h1, h2, h3 { font-family: var(--display); margin: 0; line-height: 1.0; letter-spacing: -0.01em; }
h1 { font-size: 118px; font-weight: 900; font-stretch: 72%; }
h2 { font-size: 76px; font-weight: 850; font-stretch: 76%; max-width: 1500px; }
h3 { font-size: 34px; font-weight: 760; font-stretch: 84%; }
em { font-style: normal; color: var(--signal); }
p { margin: 0; }
.eyebrow { font-family: var(--mono); font-size: 20px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--signal); font-weight: 600; }
.lead { font-size: 31px; line-height: 1.38; color: var(--muted); max-width: 1180px; }
.muted { color: var(--muted); }
.head { display: grid; gap: 22px; margin-bottom: 52px; }
.slide > .head + * { margin-block: auto; }
.foot { position: absolute; left: 120px; right: 120px; bottom: 44px; display: flex; justify-content: space-between; align-items: center;
        font-family: var(--mono); font-size: 17px; color: var(--muted); border-top: 1px solid var(--line); padding-top: 16px; }
.brand { display: inline-flex; align-items: center; gap: 12px; font-family: var(--display); font-weight: 900; font-stretch: 70%; letter-spacing: 0.04em; color: var(--ink); }
.cut { width: 24px; height: 24px; border-radius: 50%; border: 4px solid var(--signal); position: relative; display: inline-block; }
.cut::after { content: ""; position: absolute; left: 50%; top: -7px; bottom: -7px; width: 4px; background: var(--signal); transform: translateX(-50%) rotate(28deg); }
.phone { aspect-ratio: 9 / 16; border-radius: 26px; border: 7px solid var(--bezel); overflow: hidden; background: var(--bezel); box-shadow: 0 24px 50px -20px rgba(0,0,0,.75); }
.phone img { width: 100%; height: 100%; object-fit: cover; display: block; }
.mono { font-family: var(--mono); font-variant-numeric: tabular-nums; }

/* portada */
.cover { padding-top: 80px; }
.cover .grid { display: grid; grid-template-columns: 1.12fr 1fr; gap: 70px; align-items: center; flex: 1; }
.cover .big { display: flex; align-items: center; gap: 22px; font-size: 54px; margin-bottom: 40px; }
.cover .big .cut { width: 46px; height: 46px; border-width: 7px; }
.cover .big .cut::after { width: 7px; top: -12px; bottom: -12px; }
.cover .lead { margin-top: 30px; font-size: 30px; }
.fan { position: relative; height: 660px; }
.fan .phone { position: absolute; width: 290px; }
.fan .p1 { left: 0; top: 70px; transform: rotate(-7deg); }
.fan .p2 { left: 230px; top: 0; z-index: 2; }
.fan .p3 { left: 460px; top: 70px; transform: rotate(7deg); }
.tc { position: absolute; left: 120px; bottom: -6px; font-family: var(--mono); font-size: 20px; background: var(--ink); color: var(--paper); padding: 9px 16px; border-radius: 8px; z-index: 3; }
.specs { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 3px solid var(--ink); margin-top: 26px; }
.specs div { padding: 20px 22px 0 0; display: grid; gap: 6px; }
.specs div + div { padding-left: 22px; border-left: 1px solid var(--line); }
.specs b { font-family: var(--display); font-stretch: 75%; font-size: 52px; font-weight: 850; line-height: 1; }
.specs span { color: var(--muted); font-size: 22px; }

/* problema */
.three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 60px; border-top: 3px solid var(--ink); padding-top: 34px; }
.three article { display: grid; gap: 16px; align-content: start; }
.three .tag { font-family: var(--mono); font-size: 20px; color: var(--signal); font-weight: 600; }
.three p { font-size: 27px; line-height: 1.45; color: var(--muted); }

/* pasos */
.steps { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 3px solid var(--ink); }
.step { padding: 26px 34px 28px 0; display: grid; gap: 12px; align-content: start; border-bottom: 1px solid var(--line); }
.step:not(:nth-child(3n+1)) { padding-left: 34px; border-left: 1px solid var(--line); }
.step .n { font-family: var(--mono); font-size: 18px; color: var(--muted); display: flex; align-items: center; gap: 12px; }
.step .n b { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--ink); color: var(--paper); font-weight: 600; font-size: 17px; }
.step h3 { font-size: 31px; }
.step p { font-size: 23px; line-height: 1.42; color: var(--muted); }
.step .inside { font-family: var(--mono); font-size: 16px; border-top: 1px dashed var(--line); padding-top: 10px; }

/* caso */
.case { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 34px 40px; display: grid; gap: 26px; }
.case-top { display: flex; justify-content: space-between; align-items: baseline; }
.case-top .mono { font-size: 18px; color: var(--muted); }
.tl { position: relative; padding-top: 40px; }
.bar { position: relative; height: 70px; background: var(--track); border-radius: 10px; }
.blk { position: absolute; top: 8px; bottom: 8px; border-radius: 5px; background: var(--chip); border: 1px solid var(--chip-line); }
.blk.on { background: var(--signal); border-color: var(--signal); }
.blk .o { position: absolute; top: -40px; left: 50%; transform: translateX(-50%); font-family: var(--mono); font-size: 17px; font-weight: 600;
          background: var(--ink); color: var(--paper); border-radius: 999px; width: 30px; height: 30px; display: grid; place-items: center; }
.axis { position: relative; height: 26px; margin-top: 8px; }
.axis span { position: absolute; transform: translateX(-50%); font-family: var(--mono); font-size: 17px; color: var(--muted); }
.axis span:first-child { transform: none; }
.edit { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.edit li { border: 1px solid var(--line); border-radius: 14px; padding: 16px 20px; display: grid; gap: 6px; background: var(--paper); }
.edit .row { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 16px; color: var(--muted); }
.edit .role { color: var(--signal); font-weight: 600; }
.edit b { font-family: var(--display); font-stretch: 80%; font-size: 27px; }
.edit p { font-size: 19px; color: var(--muted); line-height: 1.35; }

/* estilos */
.styles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 52px; }
.style { display: grid; grid-template-columns: 200px 1fr; gap: 22px; align-items: start; }
.style .phone { width: 200px; }
.style .txt { display: grid; gap: 12px; padding-top: 6px; }
.style h3 { font-size: 32px; }
.style p { font-size: 21px; line-height: 1.4; color: var(--muted); }
.style .for { font-family: var(--mono); font-size: 16px; color: var(--ink); border-top: 1px solid var(--line); padding-top: 10px; }
.styles.two { grid-template-columns: repeat(4, 1fr); gap: 56px; }
.styles.two .style { grid-template-columns: 1fr; gap: 20px; }
.styles.two .phone, .styles.two .custom { width: 252px; }
.styles.two .style p { font-size: 22px; }
.styles.two { margin-bottom: 40px !important; }
.custom { width: 200px; max-width: 100%; aspect-ratio: 9 / 16; border-radius: 26px; border: 3px dashed var(--muted); display: grid; place-items: center; text-align: center; padding: 18px;
          color: var(--muted); font-family: var(--display); font-stretch: 78%; font-weight: 750; font-size: 28px; line-height: 1.1; }

/* calidad */
.qa { display: grid; grid-template-columns: 1fr 1fr; gap: 0 80px; }
.qa ul { margin: 0; padding: 0; list-style: none; border-top: 3px solid var(--ink); }
.qa li { display: grid; grid-template-columns: 40px 1fr auto; gap: 16px; align-items: baseline; padding: 22px 0; border-bottom: 1px solid var(--line); }
.ok { width: 28px; height: 28px; border-radius: 50%; background: var(--signal); position: relative; top: 4px; }
.ok::after { content: ""; position: absolute; left: 9px; top: 4px; width: 8px; height: 14px; border: solid var(--signal-ink); border-width: 0 3.5px 3.5px 0; transform: rotate(45deg); }
.qa strong { display: block; font-size: 27px; }
.qa .d { font-size: 22px; color: var(--muted); }
.qa .v { font-family: var(--mono); font-size: 19px; white-space: nowrap; }

/* tabla */
table { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--line); border-radius: 18px; overflow: hidden; }
th, td { text-align: left; padding: 24px 30px; border-bottom: 1px solid var(--line); font-size: 26px; vertical-align: top; }
th { font-family: var(--mono); font-size: 18px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
th:last-child { color: var(--signal); }
td:first-child { font-weight: 700; width: 25%; }
td:nth-child(2) { color: var(--muted); }
tr:last-child td { border-bottom: 0; }

/* servicio */
.svc { display: grid; grid-template-columns: 1fr 1.45fr; gap: 80px; }
.deliv { margin: 0; padding: 0; list-style: none; border-top: 3px solid var(--ink); }
.deliv li { display: grid; grid-template-columns: 130px 1fr; gap: 18px; padding: 20px 0; border-bottom: 1px solid var(--line); font-size: 23px; line-height: 1.4; }
.deliv .k { font-family: var(--mono); font-size: 18px; color: var(--signal); font-weight: 600; padding-top: 3px; }
.plans { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; }
.plan { border: 1px solid var(--line); border-radius: 18px; padding: 28px; display: grid; gap: 14px; align-content: start; background: var(--surface); }
.plan.feat { border: 3px solid var(--signal); }
.plan .what { font-family: var(--display); font-stretch: 78%; font-weight: 850; font-size: 42px; line-height: 1; }
.plan p { font-size: 21px; line-height: 1.4; color: var(--muted); }
.plan .price { font-family: var(--mono); font-size: 17px; color: var(--ink); border-top: 1px solid var(--line); padding-top: 12px; }

/* preguntas */
.faq { display: grid; grid-template-columns: 1fr 1fr; gap: 0 80px; }
.faq div { padding: 22px 0; border-bottom: 1px solid var(--line); display: grid; gap: 10px; }
.faq .col { border-top: 3px solid var(--ink); padding: 0; border-bottom: 0; }
.faq b { font-size: 27px; }
.faq p { font-size: 23px; line-height: 1.42; color: var(--muted); }

/* cierre */
.close { justify-content: center; }
.close h2 { font-size: 112px; font-stretch: 72%; font-weight: 900; max-width: 1400px; }
.close .lead { margin-top: 34px; }
.close .big { display: flex; align-items: center; gap: 22px; font-size: 54px; margin-bottom: 56px; }
.close .big .cut { width: 46px; height: 46px; border-width: 7px; }
.close .big .cut::after { width: 7px; top: -12px; bottom: -12px; }
"""


def foot(n, total):
    return f'<div class="foot"><span class="brand"><span class="cut"></span>{BRAND}</span><span>{n:02d} / {total:02d}</span></div>'


def slides():
    S = []
    # 1 · portada
    S.append(f"""
<section class="slide cover">
  <div class="brand big"><span class="cut"></span>{BRAND}</div>
  <div class="grid">
    <div>
      <p class="eyebrow">Edición de video para comunicación política y pública</p>
      <h1 style="margin-top:20px">Una conferencia de 7&nbsp;minutos. <em>Siete videos</em> listos para publicar.</h1>
      <p class="lead">Un sistema de edición con inteligencia artificial que entiende lo que se dice, elige las ideas completas y corta donde corta un buen editor: en los silencios, nunca en mitad de una frase.</p>
    </div>
    <div class="fan">
      <div class="phone p1"><img src="{img['news']}"></div>
      <div class="phone p2"><img src="{img['fx']}"></div>
      <div class="phone p3"><img src="{img['call']}"></div>
      <div class="tc">07:14 en bruto → 7 videos de 1:42 a 1:55</div>
    </div>
  </div>
  <div class="specs">
    <div><b>7</b><span>estilos de edición del mismo material</span></div>
    <div><b>≤ 2:00</b><span>por video, con gancho, desarrollo y cierre</span></div>
    <div><b>9:16</b><span>1080 × 1920, para Reels, TikTok y Shorts</span></div>
    <div><b>&lt; 15 MB</b><span>versión liviana para WhatsApp</span></div>
  </div>
</section>""")
    # 2 · problema
    S.append("""
<section class="slide">
  <div class="head"><p class="eyebrow">Lo que resuelve</p><h2>El material existe. Lo difícil es convertirlo en algo que la gente mire.</h2></div>
  <div class="three">
    <article><span class="tag">El bruto es largo</span><h3>Nadie ve una conferencia entera en el celular.</h3><p>Una rueda de prensa dura entre 5 y 30 minutos. En redes, lo que funciona es un video vertical de uno o dos minutos que arranque con lo más fuerte.</p></article>
    <article><span class="tag">Editar a mano lleva horas</span><h3>Cada pieza consume tiempo de un editor.</h3><p>Elegir fragmentos, cortar, subtitular, diseñar y mezclar el audio de un solo video lleva horas. Hacer varias versiones del mismo material casi nunca entra en el presupuesto.</p></article>
    <article><span class="tag">Los errores se notan</span><h3>Un mal corte cambia lo que se dijo.</h3><p>Frases cortadas por la mitad, subtítulos mal escritos o música que tapa la voz restan credibilidad, y en comunicación política eso tiene costo.</p></article>
  </div>
</section>""")
    # 3 · cómo funciona
    steps = [
        ("Envío", "Nos mandás el video en bruto", "Una conferencia, entrevista o discurso grabado con celular o cámara, tal como salió. Sin preparar nada.", "Video + audio originales"),
        ("Comprensión", "Transcribe y entiende el contenido", "Pasa todo a texto palabra por palabra y arma un mapa del contenido: frases completas, preguntas de la prensa, temas y bloques de idea que no se pueden separar.", "Transcripción con IA en GPU · 24 bloques en el caso real"),
        ("Guion", "Elige qué entra y en qué orden", "Según el enfoque que pidas, arma un guion con un gancho al inicio, los bloques más importantes y un cierre, hasta 2 minutos.", "Solo bloques enteros, nunca una idea a la mitad"),
        ("Corte", "Corta como un editor profesional", "Cada corte cae en un silencio real de la voz. Acorta las pausas largas, mantiene la cara bien encuadrada y no separa frases dichas de corrido.", "Cortes medidos sobre la energía de la voz"),
        ("Diseño", "Subtitula, diseña y anima", "Subtítulos sincronizados con cada palabra, palabras clave resaltadas, titulares, fotos de apoyo, animaciones, efectos y música por debajo de la voz.", "7 estilos, con los colores y redes del cliente"),
        ("Control y entrega", "Revisa la calidad y entrega", "Un control automático verifica cortes, frases, subtítulos, volumen, encuadre y zona segura. Recibís el video en alta calidad y una versión liviana.", "Informe de calidad por video"),
    ]
    st = "".join(f'<div class="step"><div class="n"><b>{i + 1}</b>{a}</div><h3>{b}</h3><p>{c}</p><p class="inside">{d}</p></div>' for i, (a, b, c, d) in enumerate(steps))
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:40px"><p class="eyebrow">Cómo funciona</p><h2>Del video en bruto al video publicado, en seis pasos.</h2>
  <p class="lead">El sistema hace el trabajo pesado y un editor supervisa las decisiones.</p></div>
  <div class="steps">{st}</div>
</section>""")
    # 4 · caso real
    src = case["source"]; order = case["order"]
    pct = lambda x: f"{100 * x / src:.3f}%"
    blocks = "".join(f'<span class="blk{" on" if b["id"] in order else ""}" style="left:{pct(b["s"])};width:{pct(max(0.8, b["e"] - b["s"]))}">'
                     + (f'<span class="o">{order.index(b["id"]) + 1}</span>' if b["id"] in order else "") + "</span>" for b in case["beats"])
    axis = "".join(f'<span style="left:{pct(m * 60)}">{m}:00</span>' for m in range(8))
    desc = {"q_crisis": "La prensa pregunta si hay riesgo de crisis; la respuesta es directa.", "bcp_solido": "Qué informó el Banco Central sobre el sistema financiero.",
            "control": "Hubo control al banco y está en proceso de sumario.", "tranquila": "El llamado a que la ciudadanía esté tranquila.",
            "jubilados": "El mensaje a jubilados y ahorristas.", "calma": "El mensaje final: los ahorros están garantizados."}
    beat = {b["id"]: b for b in case["beats"]}
    roles = {0: "Gancho", len(order) - 1: "Cierre"}
    edit = "".join(f'<li><div class="row"><span class="role">{i + 1} · {roles.get(i, "Desarrollo")}</span><span>original {int(beat[b]["s"] // 60)}:{int(beat[b]["s"] % 60):02d}</span></div>'
                   f'<b>{html.escape(beat[b]["tag"])}</b><p>{desc.get(b, beat[b]["topic"])}</p></li>' for i, b in enumerate(order))
    S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:34px"><p class="eyebrow">Un caso real</p><h2>Así decidió el sistema qué entraba en «Mensaje de calma».</h2>
  <p class="lead">La conferencia dura 7:14. El sistema la dividió en 24 bloques de idea, eligió 6 y armó un video de 1:50, con la pregunta de la prensa como gancho.</p></div>
  <div class="case">
    <div class="case-top"><h3>Conferencia completa, 0:00 a 7:14</h3><span class="mono">en rojo: lo que entró · el número es el orden en el video</span></div>
    <div class="tl"><div class="bar">{blocks}</div><div class="axis">{axis}</div></div>
    <ol class="edit">{edit}</ol>
  </div>
</section>""")
    # 5-6 · estilos
    styles = [("news", "Noticiero", "Sobrio e informativo. Tarjeta con la pregunta, nombre en pantalla y palabras clave en dorado.", "Aclaraciones y comunicados"),
              ("ink", "TikTok tinta", "Gancho en blanco y negro con lente curva, frases clave en cajas de tinta, barridos y un momento en rojo.", "Respuestas y posicionamientos fuertes"),
              ("report", "Reportaje", "Capítulos por tema, fotos y logos en recuadro, y la pregunta de la prensa en un globo.", "Explicar un tema con contexto"),
              ("headline", "Titulares", "Un titular grande por cada tema y una barra de progreso que muestra en qué parte va el video.", "Propuestas y logros"),
              ("fx", "Animado con efectos", "Las palabras clave estallan en pantalla, con transiciones rojas y subtítulos tipo karaoke.", "Campañas y máximo impacto"),
              ("call", "Llamada con letra", "Foto fija arriba, la voz como una llamada y la letra que se ilumina palabra por palabra.", "Mensajes personales y cercanos"),
              ("split", "Pantalla dividida", "La entrevista arriba y, abajo, el tema en curso con tomas de apoyo del lugar.", "Informar con apoyo visual"),
              (None, "A medida", "Nos pasás los videos que te gustan y entrenamos un estilo nuevo con tu identidad visual.", "Marcas y equipos con línea propia")]
    def card(s):
        k, name, d, f = s
        vis = f'<div class="phone"><img src="{img[k]}"></div>' if k else '<div class="custom">Tu estilo, a partir de tus referencias</div>'
        return f'<div class="style">{vis}<div class="txt"><h3>{name}</h3><p>{d}</p><p class="for">Ideal para: {f}</p></div></div>'
    for part, (a, b) in enumerate(((0, 4), (4, 8))):
        S.append(f"""
<section class="slide">
  <div class="head" style="margin-bottom:46px"><p class="eyebrow">Estilos de edición · {part + 1} de 2</p><h2>{'El mismo material, siete formas de contarlo.' if part == 0 else 'Más estilos, y uno hecho a tu medida.'}</h2></div>
  <div class="styles two">{''.join(card(s) for s in styles[a:b])}</div>
</section>""")
    # 7 · calidad
    qa1 = [("Cortes en silencio", "Los cortes caen entre palabras, nunca sobre una palabra de quien habla.", "0 en los 7 videos"),
           ("Frases completas", "Ninguna escena empieza ni termina a mitad de una frase.", "0 en los 7 videos"),
           ("Subtítulos fieles", "El texto se compara con una segunda transcripción del audio final.", "palabra a palabra"),
           ("Duración justa", "Gancho, desarrollo y cierre, sin pasar los 2 minutos.", "1:42 a 1:55")]
    qa2 = [("Volumen estándar de redes", "Mismo nivel que el resto del contenido de las plataformas.", "−14 LUFS"),
           ("Música que no tapa la voz", "La música se baja sola cuando hay voz.", "≈ 17 dB debajo"),
           ("Zona segura de cada app", "Nada importante queda debajo de los botones de TikTok, Reels o Shorts.", "1080 × 1920"),
           ("Rostro siempre encuadrado", "La cara queda centrada aunque la persona se mueva.", "seguimiento continuo")]
    li = lambda q: "".join(f'<li><span class="ok"></span><span><strong>{a}</strong><span class="d">{b}</span></span><span class="v">{c}</span></li>' for a, b, c in q)
    S.append(f"""
<section class="slide">
  <div class="head"><p class="eyebrow">Control de calidad</p><h2>Cada video pasa por una revisión automática antes de llegar a tus manos.</h2>
  <p class="lead">Los valores de la derecha son los medidos en los videos del caso real.</p></div>
  <div class="qa"><ul>{li(qa1)}</ul><ul>{li(qa2)}</ul></div>
</section>""")
    # 8 · comparación
    rows = [("Tiempo por video", "Varias horas de trabajo de un editor", "Minutos de proceso por video, más la revisión"),
            ("Versiones del mismo material", "Normalmente una", "Siete estilos distintos de un solo bruto"),
            ("Elección de fragmentos", "Depende del criterio y del tiempo disponible", "Mapa completo del contenido; se eligen ideas enteras"),
            ("Cortes", "Manuales, con riesgo de cortar una frase", "Medidos sobre la voz, siempre en silencios reales"),
            ("Subtítulos", "Se escriben o corrigen a mano", "Automáticos, sincronizados y verificados"),
            ("Control de calidad", "Revisión visual", "Revisión automática con informe, más supervisión")]
    tr = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)
    S.append(f"""
<section class="slide">
  <div class="head"><p class="eyebrow">Comparación</p><h2>Lo que cambia frente a la edición tradicional.</h2></div>
  <table><thead><tr><th></th><th>Edición tradicional</th><th>{BRAND}</th></tr></thead><tbody>{tr}</tbody></table>
</section>""")
    # 9 · servicio
    S.append(f"""
<section class="slide">
  <div class="svc">
    <div><div class="head" style="margin-bottom:34px"><p class="eyebrow">Qué recibís</p><h2 style="font-size:68px">Listo para publicar, por cada video.</h2></div>
      <ul class="deliv">
        <li><span class="k">HD</span><span>Video en alta calidad, 1080 × 1920, para Instagram, TikTok y YouTube Shorts.</span></li>
        <li><span class="k">WhatsApp</span><span>Versión liviana de menos de 15 MB para grupos y estados.</span></li>
        <li><span class="k">Guion</span><span>El texto de lo que entró y en qué orden, para revisarlo o aprobarlo.</span></li>
        <li><span class="k">Informe</span><span>El control de calidad del video: cortes, subtítulos, volumen y encuadre.</span></li>
      </ul></div>
    <div><div class="head" style="margin-bottom:34px"><p class="eyebrow">Formas de trabajar</p><h2 style="font-size:68px">Elegí cómo empezar.</h2></div>
      <div class="plans">
        <div class="plan"><p class="eyebrow">Muestra</p><p class="what">1 bruto → 2 videos</p><p>Para probar el sistema con tu propio material y elegir el estilo que mejor te queda.</p><p class="price">Precio a convenir</p></div>
        <div class="plan feat"><p class="eyebrow">Campaña</p><p class="what">1 bruto → 7 videos</p><p>Todos los estilos y enfoques de una misma conferencia, para publicar toda la semana.</p><p class="price">Precio a convenir</p></div>
        <div class="plan"><p class="eyebrow">Mensual</p><p class="what">Varios brutos por mes</p><p>Edición continua de conferencias, entrevistas y actividades, con tu estilo fijo.</p><p class="price">Precio a convenir</p></div>
      </div></div>
  </div>
</section>""")
    # 10 · preguntas
    faq = [("¿Qué tengo que enviar?", "Solo el video original, tal como se grabó. Fotos del lugar, logos o videos de referencia de tu canal sirven para personalizar el estilo."),
           ("¿Cuánto tarda?", "El proceso de cada video lleva unos minutos. Con la revisión incluida, una tanda de siete videos de un mismo bruto puede estar lista en el día."),
           ("¿Puedo pedir cambios?", "Sí. Podés cambiar el enfoque, sacar o sumar un fragmento, ajustar un titular o elegir otro estilo, y el video se vuelve a generar."),
           ("¿La IA puede cambiar lo que dijo la persona?", "No. El sistema solo elige y ordena fragmentos reales del video. No genera voz ni inventa frases, y corta entre frases completas."),
           ("¿Sirve para otras personas y otros temas?", "Sí. Para cada video nuevo se arma su propio mapa de contenido. El estilo se adapta a tus colores, tu logo y tus redes."),
           ("¿La música tiene derechos de autor?", "La música y los efectos de sonido se generan con el propio sistema, así que no dependen de canciones de terceros.")]
    col = lambda q: "".join(f"<div><b>{a}</b><p>{b}</p></div>" for a, b in q)
    S.append(f"""
<section class="slide">
  <div class="head"><p class="eyebrow">Preguntas frecuentes</p><h2>Lo que suelen preguntar.</h2></div>
  <div class="faq"><div class="col">{col(faq[:3])}</div><div class="col">{col(faq[3:])}</div></div>
</section>""")
    # 11 · cierre
    S.append(f"""
<section class="slide close">
  <div class="brand big"><span class="cut"></span>{BRAND}</div>
  <p class="eyebrow">Probalo con tu material</p>
  <h2 style="margin-top:22px">Mandanos un video en bruto. <em>Te devolvemos una muestra editada.</em></h2>
  <p class="lead">Escribinos para coordinar el envío del archivo y el enfoque que querés comunicar.</p>
</section>""")
    total = len(S)
    out = []
    for i, s in enumerate(S):
        if i not in (0, total - 1): s = s.replace("</section>", foot(i + 1, total) + "</section>")
        out.append(s)
    return out


def build():
    S = slides()
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{BRAND} · Presentación</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>{CSS}
body.solo .slide {{ display: none; }} body.solo .slide.show {{ display: flex; }}</style></head>
<body>{''.join(S)}
<script>
const m = location.hash.match(/^#s(\\d+)$/);
if (m) {{ document.body.classList.add('solo'); const s = document.querySelectorAll('.slide')[+m[1] - 1]; if (s) s.classList.add('show'); }}
</script></body></html>"""
    open(J("deck.html"), "w", encoding="utf-8").write(doc)
    return len(S)


def to_pdf(out):
    url = "file:///" + J("deck.html").replace("\\", "/")
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                        "--virtual-time-budget=15000", f"--print-to-pdf={out}", url], capture_output=True, text=True, timeout=180)
    if not os.path.exists(out): raise RuntimeError(r.stderr[-800:])


def shots(n):
    os.makedirs(J("shots"), exist_ok=True)
    for i in range(1, n + 1):
        url = "file:///" + J("deck.html").replace("\\", "/") + f"#s{i}"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080", "--virtual-time-budget=15000",
                        f"--screenshot={J('shots', f's{i:02d}.png')}", url], capture_output=True, timeout=120)


if __name__ == "__main__":
    n = build()
    if "--shots" in sys.argv: shots(n); print("capturas:", n)
    else:
        out = J(f"{BRAND}_presentacion.pdf"); to_pdf(out); print("pdf:", out, os.path.getsize(out) // 1024, "KB")
