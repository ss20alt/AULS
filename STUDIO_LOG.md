# Estudio de edición — bitácora

## 1. ADN de las referencias (analysis/, analyze_refs.py)
- 9:16, entrevista a pantalla completa con la cara en el tercio superior-medio (alto de cara ≈ 0.13–0.27 del alto, mediana 0.175).
- Subtítulos de 2–3 palabras, blanco con contorno negro, tercio inferior; claves resaltadas (caja de tinta / color).
- Gancho en B/N (visor, REC, polvo, lente curva en R6) con título; "momento rojo" duotono en una palabra fuerte; globo de cómic para preguntas.
- Cortes casi invisibles (cara anclada), zoom de énfasis, barridos con destello; B-roll/fotos en R2/R7.
- Cierre blanco con íconos de redes + @; sello de redes arriba a la derecha. Loudness típico −13…−14 LUFS.

## 2. Estilos construidos (styles/)
| Proyecto | Estilo | Idea |
|---|---|---|
| v1_calma | news | Noticiero limpio: tarjeta de pregunta, claves doradas, placa de nombre |
| v2_leite | ink | TikTok tinta: B/N con lente curva, cajas negras, barridos, momento rojo, final B/N |
| v3_reporte | report | Reportaje: globo, capítulos, fotos del banco en recuadro, logo centrado, barra azul |
| v4_titulares | headline | Titulares grandes por tema, barra de progreso, cara abajo, zoom entre temas |

## 3. Iteraciones y lecciones
1. V1 → subtítulos partidos mal ("de" suelto) ⇒ chunking por programación dinámica (no termina en artículo, corta en comas, une claves con su contexto, quita tartamudeos).
2. Música casi inaudible (−23 dB bajo la voz) ⇒ music_db −19.5 (≈17–18 dB bajo la voz); el QA lo vigila (14–21 dB).
3. Peso 100 MB/min ⇒ cq 21 / 9 Mbps + versión liviana 720p ≈ 13.5 MB (WhatsApp).
4. Texto de subtítulos: el ASR del audio recortado se equivoca (oye "ahí" por "fuerte") ⇒ el texto sale de la transcripción de la fuente; el ASR solo verifica bordes. Bordes dudosos se resuelven con `drop_tokens` en curated.py (el QA/consola los lista).
5. Rango "malo" mal escrito (25 s en vez de 157 s) borraba palabras reales ⇒ corregido en plan.py.
6. V3: la cara "tapada" por las fotos es intencional ⇒ el QA descuenta los recuadros.
7. V4: el titular tapaba la frente ⇒ cara anclada más abajo (AY 1085, ext_y 330) y titular de 92 px con ajuste automático al ancho seguro.
8. Defecto de cámara (reflection) repetía el título arriba ⇒ padding "border" / sin extensión vertical innecesaria.

## 3b. Segunda tanda (V5–V7) y automatización
- V5 fx (animado rojo + FX): golpes de palabra clave con onda, chispas, aberración cromática y sacudida; stinger rojo; karaoke; brasas.
- V6 call (llamada con letra, layout v16/v17) y V7 split (pantalla dividida con panel azul y ventana de tomas del banco).
- Reglas automáticas de bordes (asr.source_words): palabra capitalizada que abre frase al final de la toma, palabra que cierra frase al inicio, token tras punto final: se descartan; lo dudoso se lista.
- selector.py: gancho (pregunta→respuesta o frase "punch") + bloques coherentes + cierre; ajuste de duración simulando el EDL real (añadir/quitar/intercambiar).
- autocfg.py: genera solo titulares, golpes, capítulos, fotos, chips, textos de gancho a partir de las palabras clave.
- make_video.py: estilo + ángulo -> video listo (QA + 1 corrección automática de cara/zoom + entrega + REPORT.md). `--all` hace el lote.
- build.py: nivel de música automático (15–19 dB bajo la voz), cfg.json dinámico, zoom_mul.

## 3c. Tercera ronda — "no cortar mientras habla, respetar el contexto" (videos de hasta 2 min)
- Causa raíz de los cortes malos: las unidades se armaban por PAUSAS (>0.7 s), así una frase como "Mi último trabajo con … los médicos fue…" quedaba partida y el selector podía elegir solo la segunda mitad.
  ⇒ content.py: frases COMPLETAS por puntuación + BLOQUES DE IDEA (24 bloques con tema, tipo e importancia) + historias por ángulo. Se editan bloques enteros; si no entra, se recorta solo al final de una frase.
- Whisper inventó una repetición sobre un silencio ("Eso fue lo más doloroso" dos veces) ⇒ detector de palabras sin voz + corrección DELETE en plan.py.
- Puntos de corte anclados a la VOZ real (plan.cut_in/cut_out): la entrada va 0.1 s antes de que empiece la voz y la salida 0.13 s después de que termina; si la frase siguiente arranca sin pausa, se corta en el final de la palabra con fundido de 35–50 ms.
- Pausas internas: solo silencios ≥ 0.4 s, se dejan 0.33 s (antes 0.3→0.27 s).
- QA nuevo: MIDSENTENCE (escena que empieza/termina a mitad de frase) y CUT_VOICE (cortes sobre voz).
- Duración libre hasta 2 min (selector2.py); versión liviana con bitrate según duración (< 15 MB).

### Reglas de corte definitivas (auditadas con audit_cuts.py: 70 fronteras, 0 con voz cruzada)
1. Entrada: si en el punto hay silencio → justo antes de que arranque la voz (0.1 s de aire, sin tocar la cola anterior).
2. Si hay voz, retroceder hasta el silencio previo SIN pasar la palabra anterior.
3. Si no hay silencio entre frases: los huecos entre sílabas engañan ("ha-cer" tiene un valle en el medio), así que se entra tras el primer SILENCIO real
   que empiece antes de la palabra nueva. Como mucho se pierde una conjunción ("Y vos" → "Vos", que se capitaliza); nunca se cuela una sílaba.
4. Salida: hasta que termina la voz + cola ≤ 0.13 s que nunca toca la voz siguiente; nunca avanza más allá de la palabra siguiente.
5. Frases dichas de corrido: salida y entrada usan la misma ventana → el mismo hueco; además el selector suelta la frase corta pegada del borde
   o incluye la vecina, y los tramos seguidos del original se unen sin corte (audio continuo).
6. Si igual cae sobre voz (el periodista habla encima): fundido de 35–50 ms.

## 3d. Cuarta ronda — automatizar la preparación (plan de 7 puntos)
1. **Ingesta en un comando** (`ingest.py`): video bruto → fuente lista en `sources/<nombre>/` (HDR→SDR calibrado, voz limpia, whisper,
   cara, alineación, voces, mapa). Probado con IMG_4572 → `lilian_conf_auto` (reproduce la preparación manual: cara ±1 px, color, voz).
2. **Banco de pruebas** (`regress.py`, 34 s): fronteras sin voz cruzada · 35 guiones (7 estilos × 5 ángulos) ≤ 2 min, sin cortes a mitad de
   palabra (la prueba detecta el 91 % de cortes plantados a propósito), sin palabras audibles de periodistas en tomas de ella, zonas del
   cliente respetadas · mapa coherente · marca desde la ficha · alineación contra medidas manuales · palabras inventadas · quién habla ≥ 98 %
   · mapa automático ≥ 90/85 % · cada corrección del cliente. Hoy: 18/18 OK.
3. **Ficha del cliente** (`clients/lilian.json` + `brand.py`): nombre, cargo, @, redes y color salen de la ficha (placa, sello, cierre, llamada).
4. **Alineación forzada** (`align.py`, wav2vec2 CTC en GPU, 7 s): por segmento de whisper. PROBADO Y DESCARTADO alinear tramos largos
   juntos: el texto de una voz lejana que el modelo no oye ("Gracias, senadora" sin micrófono) empuja a las palabras vecinas al silencio.
   Números se alinean como se dicen ("2027" → "dos mil veintisiete").
5. **Quién habla** (`speakers.py`, WavLM): huella de voz + reglas; "senadora" como vocativo ("Gracias, senadora.") ⇒ periodista.
   Las palabras de frases de periodista nunca entran al subtítulo de ella (asr.source_words) y QA las vigila (OTHER_VOICE).
6. **Mapa de contenido automático** (`mapper.py draft|approve|eval`): bloques 95 % precisión / 88 % cobertura contra el mapa manual, con
   reglas genéricas del castellano (marcadores "Por otro lado", "En segundo lugar", vocativos, cambio de tipo de idea, bloques > 25 s).
   Titulares por reglas editoriales: pregunta retórica (¿DÓNDE ESTÁS?, ¿QUÉ TE IMPORTA?), "no hay X" (NO HAY CRISIS), calificativos
   (IRRESPONSABLE, VENDE PATRIA), "sujeto + está ADJ" con concordancia (SISTEMA SÓLIDO, AHORROS GARANTIZADOS); un verbo suelto nunca
   es titular. Revisión en `content_review.html`; sin aprobar, content.py usa el borrador.
7. **Correcciones del cliente** (`feedback.py add <proyecto> <m:ss> "<nota>"`): el minuto del video entregado se traduce a la fuente;
   texto ("dice '…'") se re-alinea con el audio, corte ("cortó la palabra al final") protege esa palabra y su pausa, hablante
   ("es el periodista") corrige la voz. Cada caso queda como prueba permanente. Probado en una copia: los 3 tipos aplicados y verificados.
- Pendiente de confirmar con el equipo: 151.8 s de la fuente — whisper escribe "El trato de sicaria"; el audio dice "(Me/Le) trató de sicaria".

## 3e. Quinta ronda — 8 tipos nuevos de 1 minuto (styles/base.py + 8 estilos)
Estilos: karaoke (subtítulo grande con la palabra activa en caja amarilla), doc (documental: franjas negras, rótulos en la franja),
tv (mosca, zócalo de dos pisos por idea, cinta), claves (lista numerada con progreso y repaso en el cierre), cita (gancho tipográfico +
citas TEXTUALES firmadas), editorial (papel, tarjeta de video, titular con resaltador, páginas), campana (marino/dorado, actos),
podcast (reproductor con barras de la voz real). `python make_video.py --style X --angle Y --length 1min` → 60.000 s exactos.
Lecciones (cada una ya es regla del estudio):
- 1 minuto exacto: el selector rellena con bloques de la MISMA historia o del mismo tipo, nunca agradecimientos ni nombres de
  periodistas; un trozo suelto debe contener la idea del bloque (su palabra ancla) o ≥ 60 % del bloque; el relleno va DESPUÉS del cuerpo;
  si el gancho anuncia algo ("Ahora te voy a decir qué yo hago"), lo que sigue en el original va primero. Tarjeta final 2–4.7 s.
- La pregunta del periodista al inicio de un bloque de prensa NO se suelta aunque arranque pegada a la voz (es el contexto).
- Subtítulos: la regla que verifica la última palabra con el ASR del recorte solo vale en cortes reales — en tramos internos (pausas
  recortadas) borraba palabras ("en base a las exposiciones dadas" salía "a las dadas"). Prueba permanente en regress.py.
- La voz de otra persona se muestra distinta (azulada) y la pregunta entera en un bloque de 2 líneas (antes 3 destellos a 25 car/s).
- Caja roja sobre el saco rojo no se lee → amarillo con texto negro. El texto del gancho se va ANTES de que vuelva la cara.
- Relleno por reflejo en X apagado en los estilos nuevos (se veía el saco duplicado en el borde).
- Rótulos sobre el escudo dorado no se leen → en la franja negra (documental) o en placas con fondo.
- Una cita aparece solo mientras ELLA dice la palabra ancla (no cuando la dice el periodista) y mientras esa idea todavía suena.
- Mapa manual: 3 historias nuevas (jubilados, control, resumen) para no repetir contenido entre videos.

## 3f. Sexta ronda — árbitro, QA visual, banco ampliado y 6 variaciones de 3 minutos
- El equipo confirmó "Le trató de sicaria" (fuente 151.8 s). En una copia whisper lo había salteado y en la otra escribió "El trato de
  sicaria": ahora es una corrección de la fuente (feedback.fix_source, re-alineada; las correcciones pueden INSERTAR palabras).
- **Árbitro** (`arbitro.py scan|review`): compara por TIEMPO lo que escribió whisper con lo que oye wav2vec2 (lectura letra por letra).
  Primer diseño (por secuencia de texto) no oía los huecos → rediseño: (1) voz oída donde no hay texto = "falta texto"; (2) cada palabra
  contra lo oído en su propio tramo = "texto distinto". Calibrado: con la corrección quitada, la frase salteada sale 1.ª de la lista.
  Límite: "El trato" vs "Le trató" suenan casi igual (eso lo resuelve el oído humano). Página local con audio y "Está bien / Corregir".
- **QA visual** (`qa_visual.py`, integrado en qa.py): recompone muestras registrando cada pieza dibujada. CONTRAST (WCAG < 3:1),
  CARD_BLEND (caja del color del fondo), TEXT_ON_FACE (Haar, solo su cara grande), MIRROR (cálculo EXACTO con la cámara: columnas que
  caen fuera del video), SAFE_ZONE. Controles plantados: caja roja sobre el saco, rótulo sobre el escudo, texto sobre la cara y espejo
  → los 4 detectados. Encontró un problema real que se me había pasado: subtítulos del documental a 2.2:1 (corregido con contorno).
  Hallazgo: los 7 estilos viejos usaban relleno espejado de 200 px por defecto (≈30 % de los fotogramas) → ahora ext_x=0 para todos.
- **Banco**: 15 estilos × ángulos × 2 min / 1 min / 3 min (duración exacta), bloques sin huecos, toda pregunta con respuesta, QA
  visual de cada estilo sobre un proyecto real y calibración del árbitro.
- **3 minutos** (`--length 3min`): relleno con toda la conferencia en orden natural; un bloque nunca con huecos; un fragmento de prensa
  siempre termina en la respuesta de ella; la frase del gancho puede volver más tarde en su contexto (avance → historia completa).
- Cada escena guarda quién habla (scenes.json "spk"): los proyectos no dependen de la numeración de frases (cambió al insertar una).
- Lecciones de los 3 min (cada una ya es regla y casi todas prueba del banco):
  · Si una frase suena DOS veces (gancho + contexto) cada palabra va a TODAS las tomas que la contienen (antes, a la primera: el
    Twitter de Leite quedaba sin "Él que es un vende patria" — lo detectó el QA de texto).
  · QA de texto con DESEMPATE acústico: si subtítulo y ASR del recorte no coinciden, decide wav2vec2 (confirmó "Gustavo Leite"
    contra "hubo un tabulete"; mantuvo la alarma del caso real).
  · Fragmentos de subtítulo < 0.3 s se unen al vecino ("Vos," + "por supuesto,"). Preguntas: un bloque de hasta 3 líneas.
  · Titulares/tarjetas de cada idea entran cuando ELLA responde (a0), no durante la pregunta; TV: zócalo "PREGUNTA · LA PRENSA
    CONSULTA" mientras pregunta el periodista. Editorial: la página cambia con el tema, el titular con la respuesta.
  · QA visual: franjas negras de diseño no cuentan para el brillo; capas de pantalla completa y líneas finas no son texto; los
    recuadros de fotos del reportaje tapan la cara a propósito (se declaran).

## 3g. Séptima ronda — piloto automático con verificación ANTES del render, y 4 minutos
- **Piloto automático** (`make_video.py`): guion → espectador del guion → preparar → espectador + QA visual sobre fotogramas de prueba
  (se componen sin renderizar) → correcciones automáticas → render SOLO si está limpio → QA final (técnico + visual + texto con
  desempate) → entrega SOLO sin hallazgos medios/altos. Si algo falla, se detiene y deja el informe (no entrega videos con errores).
  En la primera corrida bloqueó 3 de 4 videos de 4 min: 2 falsos positivos (transiciones, gancho = pregunta+respuesta) y 1 real.
- **Espectador** (`espectador.py`): antecedente faltante, termina a mitad de oración, pregunta sin respuesta, gancho repetido enseguida,
  titular repetido (según lo que el estilo MUESTRA: `qa_titles()`), titular antes de la respuesta, subtítulo cortado en artículo,
  palabra perdida en el borde. Controles plantados (4 de guion) en el banco.
- Titulares únicos por video (`autocfg.video_tags`): si dos ideas tienen el mismo titular (IRRESPONSABLE), la segunda usa su bajada.
- **QA visual**: no juzga la legibilidad en las transiciones (±7 fotogramas de cada cambio: los barridos desenfocan todo a propósito);
  nuevo control CLIPPED (texto que se sale del cuadro). Real, encontrado al revisar: en TITULARES de 4 min la bajada se salía por la
  derecha ("…AHORROS PROT") → ahora cada línea se ajusta por separado y, si no entra, se parte. 5 errores visuales plantados en el banco.
- 4 minutos (`--length 4min`): mismo selector (toda la conferencia en orden natural); en el reportaje los recuadros de fotos se
  espacian (≥ 20 s, máx. 8) porque solo hay 3 fotos.
- Lo que el piloto automático frenó en los 4 min (y ya es regla + prueba):
  · REPORTAJE no se entregó: subtítulo a 26 car/s → el armado de subtítulos penaliza > 21 car/s.
  · Estilos viejos: preguntas largas en UNA línea que se salía del cuadro (TITULARES, REPORTAJE) → `common.two_rows` (dos filas con
    el diseño del estilo) + control plantado "widecap".
  · FX no se entregó: el cierre terminaba en "ahorros" sin "garantizados." — whisper (en el recorte) adelantó la palabra 0.9 s tras una
    pausa y la regla de bordes la borró → ahora también vale la misma palabra corrida ≤ 1.5 s. Prueba con control negativo (con la
    regla vieja falla: primero la simulé al revés y la prueba no fallaba — corregida). El espectador revisa también la última escena.
  · FX: la caja roja de la palabra activa no se distinguía del saco rojo (CARD_BLEND) → caja blanca con letra roja.
- Banco final: 51/51 (incluye 4 errores de guion y 6 visuales plantados).

## 3h. Octava ronda — skill para el equipo de Lilian (MacBook Air M3)
- Estudio autocontenido: módulos gráficos en `lib/` (antes en v5/v11/v13/v17/v18), fuentes/sonidos/material en `assets/`.
- `plataforma.py`: NVIDIA (CUDA/NVDEC/NVENC, media precisión) · Mac Apple Silicon (MPS/VideoToolbox, float32) · procesador (x264).
  Whisper en el procesador fuera de NVIDIA (int8). Fuentes de Windows → equivalentes de Mac (Georgia; Bahnschrift → DIN Alternate).
  ffmpeg reintenta sin decodificación por hardware si falla. Verificado: con el grano apagado, 45/45 fotogramas de los 15 estilos
  idénticos al píxel antes/después del cambio; sin la NVIDIA (procesador) diferencia < 1/255 y video completo de 1 min con los
  MISMOS cortes y las MISMAS 127 palabras de subtítulo (11 min sin GPU vs ≈ 4 con NVIDIA).
- Lo propio de ESTA conferencia salió del código: vocabulario de whisper (`prompt`/`tema` por fuente), palabras clave, material de
  fotos/clips (`assets/material/bcp`, `material` por fuente). Sin material: reportaje sin recuadros, pantalla dividida y llamada
  bloqueadas con aviso (no se muestran fotos del BCP en otro tema).
- `doctor.py`: autochequeo de la instalación (máquina, ffmpeg, librerías, modelos, fuentes, banco rápido, los 15 estilos contra
  referencias de la máquina original, velocidad, whisper + alineación, codificación). `empaquetar.py` → carpeta AutoeditorLilian
  (skill de Claude Code + instalar_mac.sh + LEEME). Probado desde la carpeta limpia: doctor LISTO con NVIDIA y sin ella, banco
  completo 36/36, video de 1 min sin hallazgos. LO QUE NO SE PUDO PROBAR ACÁ: MPS y VideoToolbox (solo en la Mac).

## 3i. Render al doble de velocidad (2026-10-14)
- Medición cuadro por cuadro en la RTX 2060 (Ryzen 5 3600): la GPU trabajaba solo 20–27 % del tiempo; `core.to_np` tardaba
  ~31 ms de ~61 ms por cuadro porque bajaba a la CPU el tensor PERMUTADO (no contiguo) y numpy lo reordenaba al escribirlo.
- Arreglo: `.permute(1, 2, 0).contiguous()` en la GPU antes de `.cpu()` (también en `qa_visual.faces`). 2,3 ms por cuadro,
  bytes IDÉNTICOS (60/60 cuadros reales de 4 estilos).
- Render medido: tv 16 → 34 fps · reportaje 17 → 34 · documental 17 → 40 · fx 10,6 → 17,4. Dentro del piloto automático, video
  de 1 min: render 105 → 43 s (42 fps, más rápido que el tiempo real). Banco 51/51. Ahora lo que más tarda es la verificación
  (antes y después del render), no el render.
- Para elegir máquina (propia o alquilada): lo que manda es la velocidad de UN núcleo del procesador (Python + armado de cada
  cuadro), no la placa. La placa sigue ociosa ~70 % del tiempo; 6 GB alcanzan (render ≈ 1,4 GB).
- Plan de energía de Windows en "Alto rendimiento": render +1–13 % según el estilo (tv 34 → 38,6 fps).

## 3j. Controles más rápidos sin perder nada (2026-10-14)
Medición de un video de 4 min (tv·sistema) ya con §3i: 665 s = selects 46 + ASR 35 + verificación previa 81 (×2 por una
corrección) + render 169 + liviana 14 + CONTROL FINAL 230. Cuatro cambios:
1. `core.Reader(step=N)`: ffmpeg entrega solo 1 de cada N cuadros (`select`). Los controles leían los 7.000 cuadros para revisar
   1 de cada 15–30 (el 70 % de su tiempo). `qa_visual` lo usa cuando el cuadro n del video es el n de selects.mp4.
2. Verificación previa con la MISMA densidad que el control final (1 de cada 15) y firmada (`qa_visual.firma`: cfg, EDL, palabras,
   escenas, selects y código que dibuja). `qa.run` la reutiliza si la firma coincide (`qa_visual.reutilizable`); si no, la recalcula.
   Lo que el control final iba a encontrar ahora se corrige o se frena ANTES del render. La firma solo se guarda desde make_video
   (`firmar=True`): las pruebas que plantan errores nunca dejan un resultado reutilizable.
3. Control final: UNA pasada del video terminado a 270×480 con la placa (`analyze_refs.analyze(small=True)`), que además mide
   congelados y negros (antes: dos decodificaciones completas con el procesador). `flags=neighbor` + `in_color_matrix=bt601` =
   mismas medidas que OpenCV (brillo/saturación/contraste/cara dentro de décimas; con 'area'+BT.709 el brillo subía ~2 y las
   franjas negras del documental daban saturación 143 en vez de 66).
4. Versión liviana en paralelo con el control final (`build.render(lite_async=True)` + `build.wait_lite`).
- Verificado en 5 proyectos (tv, cita, documental, llamada, 4 min): MISMOS hallazgos, QA visual idéntico cuadro a cuadro,
  congelados idénticos salvo 1 tramo límite del estilo llamada (exento de FREEZE < 2,5 s). Control final: 4 min 230 → 56 s,
  1 min 50–67 → 13–15 s. Banco 51/51 (y el banco mismo 533 → 186 s).
- Video de 4 min que pasa todo (campaña·resumen): 328 s (≈ 5,5 min) = selects 44 + ASR 33 + verificación 29 + render 176 +
  control final 35 (liviana en paralelo). Antes de §3i–3j ≈ 14 min.
- Visto en la prueba tv·sistema 4 min: el TEXT_ON_FACE que antes aparecía recién en el control final (después de render) ahora
  se ve en la verificación previa; la corrección automática (alejar la cámara) lo EMPEORÓ (×2 → ×5) y terminó en MIRROR, así que
  no se renderizó (3 min en vez de 11). Pendiente posible: corregir texto-sobre-cara moviendo el texto o acercando, no alejando.

## 3k. Render en paralelo (2026-10-14)
- `build._Prefetch`: un hilo lee de antemano los cuadros de selects.mp4 (cola de 6). `build._Writer`: el cuadro armado se pasa a
  uint8 en la GPU, se copia ASÍNCRONO a un anillo de búferes de memoria fija con un evento CUDA, y otro hilo lo manda al
  codificador. El armado del cuadro siguiente ya no espera ni al decodificador ni al traspaso (sin NVIDIA: igual que antes).
  `build.render(pipeline=False)` deja el camino en serie para comparar.
- Verificado con el grano aleatorio fijado: los bytes que entran al codificador son IDÉNTICOS (sha1 de todo el video) en 6
  proyectos. Render: tv 1 min 55 → 23 s · karaoke 48 → 25 · cita 53 → 26 · fx 205 → 122 · campaña 4 min 192 → 86 (85 fps) ·
  llamada 233 → 204 (la frenan sus propios clips de fondo). Banco 51/51.
- Video de 4 min que pasa todo (campaña·resumen), de punta a punta: 232 s ≈ 3,9 min = selects 42 + ASR 30 + verificación 26 +
  mezcla 7 + render 93 + control final 33 (liviana en paralelo). Era ≈ 14 min antes de §3i.

## 4. Uso
```
python empaquetar.py                                                 # arma ~/Documents/AutoeditorLilian (skill para el equipo)
python doctor.py                                                     # autochequeo de una instalación
python make_video.py --style campana --angle resumen --length 4min   # piloto automático completo (verifica antes y después del render)
python espectador.py <proyecto>                                       # control editorial solo
python arbitro.py scan <fuente> && python arbitro.py review <fuente>   # revisar la transcripción con un clic (http://127.0.0.1:8765)
python qa_visual.py <proyecto>                                          # QA visual solo
python make_video.py --style doc --angle resumen --length 3min          # 3 minutos exactos
python make_video.py --style karaoke --angle leite --length 1min   # 1 minuto exacto (estilos nuevos: karaoke doc tv claves cita editorial campana podcast)
python ingest.py <video> --name <fuente>           # video bruto -> fuente lista (todos los pasos)
python mapper.py approve <fuente>                  # aprobar el mapa de contenido automático
python regress.py [--fast]                         # banco de pruebas completo
python feedback.py add <proyecto> 0:43 "dice 'texto correcto'"   # corrección del cliente -> arreglo + prueba
python build.py <proyecto> --rebuild --prepare     # EDL + voz + selects + ASR + palabras
python build.py <proyecto> --stills 1 5 20          # fotogramas de prueba (stills/)
python build.py <proyecto>                          # render + versión liviana
python make_video.py --style fx --angle calma        # TODO automático (estilos: news ink report headline fx call split; ángulos: calma leite propuestas prensa)
python make_video.py --all                           # lote recomendado (2 min, bloques de idea)
python make_video.py --style ink --angle leite --length 60   # versión de 60 s
python qa.py <proyecto>                             # qa.json / qa.md / qa_sheet.png
python audit_cuts.py                                # auditoría de todas las fronteras de frase de la fuente
python content.py                                   # mapa de contenido (bloques de idea)
```
Proyectos nuevos: agregar una entrada en curated.py (guion con tiempos de la fuente) o generar el guion con `plan.pick_script(angle)`.

## 5. Estado y pendiente
- Entregado: V1–V7 curados + lote automático `Lilian_AUTO_*` (7 estilos) sin intervención manual.
- Mejora continua observada en el lote: títulos repetidos (corregido con scene_title único), subtítulos secundarios (content_words), palabra suelta "e" tras pausa recortada (pendiente), cutaways del reportaje frecuentes (ajustable: n máx.).
- Pendiente: diarización automática (hoy REPORTER manual para esta fuente), nuevas fuentes/personas, validar en un segundo video bruto, refinar el selector (coherencia narrativa por temas con embeddings), música/FX por estilo más variados.

## 3l. Calidad de imagen (2026-10-14, en prueba con el usuario)
- Medido: la cara pierde nitidez por el zoom digital (10–32 %, la grabación no tiene más resolución), el agrandado bilineal,
  el tope de 9 Mbps con grano y, en la liviana de 4 min, 0,37 Mbps. Y el color: la conversión HDR→SDR con npl=110 dejaba
  todo demasiado claro (piel L 182 vs 145 en la captura del original del usuario; distancia de color 111).
- Cambios: `core.warp_src` bicúbico (+clamp) · `start_encoder` hasta 18 Mbps (bufsize 36M) · grano fijo a la mitad (0.010 → 0.005;
  el grano fuerte de los ganchos en blanco y negro queda) · `ingest.video_filter` npl=300 (opción A elegida por el usuario: distancia
  de color 20). Nitidez de la cara +26–31 %, archivo final ×2 (≈ 130 MB por minuto), render igual.
- La conferencia BCP ahora usa `sources/lilian_conferencia_bcp/fuente_colorA.mp4` (mismo proceso que la carga automática:
  alineado cuadro a cuadro, 0,999). La anterior queda en v3/fuente_v3.mp4. Respaldo de los archivos cambiados en
  lilinatest/respaldo_calidad_2026-10-14/. Zoom: `core.ZOOM_FIJO = 1.06` (variable STUDIO_ZOOM_FIJO; 0 = el zoom animado de cada estilo): acercamiento fijo a la cara, sin
  entrar y salir, siguiendo la cara; aprobado por el usuario 2026-10-14. PENDIENTE (el usuario pidió esperar): banco de pruebas,
  referencias del doctor con el nuevo look y borrar las copias de prueba (_q_*, _z50, _z25, _zfijo, prueba_colorA y PRUEBA_*.mp4 en Descargas).

## 3m. Formato REUNIÓN: video horizontal de varias personas → vertical informativo (2026-10-14/16)
- Caso: reunión en la oficina (IMG_4801.MOV, 1920×1080 HLG, 9:48): Lilian presenta a invitados que se suman a su movimiento
  ("Gustavo Mussi se suma a Causa Republicana"). Formato distinto a la conferencia: varias personas, cámara que va de una a otra,
  sin periodistas. Módulo aparte: `reunion.py` (análisis, selección, bordes, QA, entrega) + `lib/reunion_render.py` (render).
- Análisis automático: voces (huella de Lilian + agrupamiento WavLM del resto), caras (YuNet + SFace a resolución completa,
  `clients/lilian_faceprint.npy`), "quién habla en cada ventana" por sincronía labios-voz + movimiento de boca + voto del turno
  (98 % de las frases bien atribuidas; 62/63 ventanas de cara correctas, la que falla es un paneo que la selección evita).
  Nombres: la anfitriona los dice al presentar → borrador `people.json` + `people.png`; el editor confirma con
  `people <fuente> set S1 "Nombre" "Cargo"` y `approve` (las caras aprobadas quedan en `clients/lilian_people/` y la próxima
  reunión con esas personas las reconoce solas).
- Selección (80+ pruebas a 60/90/120/140/150/180 s, reglas en `select()`): presentación de la anfitriona hasta la frase que
  nombra invitados + tema; el PROTAGONISTA (el invitado del título) entra siempre, también en 60 s; si una idea no entra
  entera entra su mejor VENTANA de frases completas; final limpio (no termina en "de/del/y…" ni justo antes de una
  continuación pegada: "…a sumar." | "No venimos a restar."); una frase abre un tramo solo si se entiende sola; tema ponderado
  por rareza (lo que se repite en toda la charla casi no suma; las raíces del título sí); se penaliza repetir la misma imagen
  en dos bloques ("león dormido") y la transcripción rota ("Partido 1 -C.").
- Bordes oídos: inicio/fin de cada bloque se verifican con ASR aislado + energía (sobra/falta palabra, palabra cortada) con
  límites anti-oscilación; "N@t" en `--frases` = bloque que termina en una pausa real DENTRO de la frase N.
- Montaje: respiración de 12 cuadros tras la última palabra (imagen sigue, voz con fundido); fundido EN MOVIMIENTO solo en
  cambio de persona; misma persona = corte directo con otro encuadre (un fundido ahí da "doble cara").
- Imagen: HLG → SDR con hable npl=300 (igual a la captura del usuario, sin subir brillo); vidstab suave + recorte 4:5 anclado
  a la cara (σ=40), sin zooms salvo un empuje lento del 6 % en tomas > 12 s. Diseño (pedido del usuario 2026-10-14): TITULAR
  ABAJO, a la altura de los micrófonos (y≈1288–1430, zona segura), subtítulos encima (y≈1196), placa de nombre encima de
  ellos la primera vez que habla cada persona (y≈1018); arriba solo el fondo desenfocado (zona de la app).
- QA final: cabeza/cola de cada bloque oídas en el video terminado (si un tramo corto hace alucinar a whisper —"para más
  información visite"— se re-oye CON contexto), negros, volumen (−15.5…−12.5 LUFS). Entrega: Descargas (+ carpeta de Drive del
  usuario si existe: `DELIVER_DIRS`).
- Entregados: Mussi 2:30 automático (`--length 150`), 1:30 y 1:10 con frases elegidas.

### Uso del formato reunión
```
python reunion.py ingest <video> --name <fuente> --tema "nombres propios, temas"   # audio, ASR, voces, caras, borrador de personas
python reunion.py people <fuente>                                                   # ver el borrador (people.png)
python reunion.py people <fuente> set S1 "Gustavo Mussi" "Ex diputado por Guairá"   # corregir nombre/cargo
python reunion.py people <fuente> approve                                           # confirmar (guarda las caras)
python reunion.py edit <fuente> --length 150 --titulo "LÍNEA 1|LÍNEA 2"             # selección automática + render + QA + entrega
python reunion.py edit <fuente> --length 90 --no-render --no-deliver --proj prueba  # solo ver qué elegiría (pruebas: SIEMPRE --no-deliver)
python reunion.py frases <fuente>                                                   # frases numeradas
python reunion.py edit <fuente> --frases "0@29.1,30-34,85-90,135-138" --proj nombre  # bloques elegidos a mano (N@t = termina en la pausa t)
python reunion.py ideas <fuente>  ·  qa <fuente> <proyecto>  ·  eval <fuente>
REUNION_DEBUG=1 (traza de la selección) / =2 (ventanas candidatas con puntaje)
```
- Lección técnica: parches escritos con heredoc de bash convirtieron `\b` de los regex en el carácter "backspace" (no daban
  error, simplemente no coincidían): escribir parches con un archivo y verificar que no haya chr(8).

## 3n. Estado 2026-10-16
- Referencias del doctor regeneradas con el look nuevo (zoom fijo 1.06, bicúbico); las de 2026-10-13 quedan en
  lilinatest/respaldo_referencia_doctor_2026-10-13/.
- `regress.py`: la prueba de "errores plantados" solo corre en la fuente que tiene esas frases (la conferencia BCP); antes
  rompía la carga de cualquier otra fuente (feminicidios).
- Paquete del equipo (`empaquetar.py`): ahora incluye el formato reunión (modelos de caras YuNet/SFace, `clients/lilian_people*`,
  `lilian_faceprint`) y la skill describe Windows y Mac.

## 3o. Referencias del equipo (18 TikToks editados) + brutos nuevos (2026-10-16)
- Análisis: `analyze_batch.py refs|raw|match` (ADN + transcripción con tiempos + música de fondo + hoja grande) y
  `_measure_refs.py` (gancho B/N, tarjeta final, música, altura del subtítulo, sello). Informe completo:
  `analysis/tiktok2610/REPORTE.md`; brutos en `analysis/crudos2610` (hojas ALL_a/ALL_b).
- La "casa" medida: tarjeta final blanca 3.0 s (18/18) · subtítulo único blanco con contorno, 2–4 palabras, centro a 0.641 del
  alto (14/18) · música ≈ 15–20 dB bajo la voz que sigue en la tarjeta (16/18) · cara a 0.32 del alto · color natural (brillo 131,
  saturación 54) · sin placa de nombre · gancho B/N limpio de 1.5–4 s (7/18; en 5 es la frase fuerte de más adelante) que entra al
  color con un barrido desenfocado · duración = la declaración entera (35–198 s), no minutos exactos.
- Estilo nuevo `redes` (styles/redes.py, `make_video.py --style redes`): ese look. El B/N cubre TODO el gancho (pregunta +
  respuesta) y el color entra cuando empieza el contenido. Prueba: BCP · calma · 1 min → 77 s de punta a punta, render 21 s,
  música 17.5 dB bajo la voz, QA sin hallazgos. Banco 44/45 (la falla es la de feminicidios/juzgados, previa) y referencias del
  doctor para `redes` creadas.
- Brutos DJI exportados = ANAMÓRFICOS (9:16 guardado en 1728×1080 / 1080×1080 / 1280×720, SAR 45:128 · 9:16 · 81:256): ingest los
  trataba como horizontales y los aplastaba. Arreglo: `ingest.probe` usa el SAR (ancho real), `video_filter` pasa a píxeles
  cuadrados antes de recortar, `square_px` en el seguimiento de cara y en el formato panel, aviso de resolución baja (608×1080,
  405×720). Prueba permanente en `regress.py` (fuente BCP). El original del DJI (1512×2688) tiene 4× más detalle: pedirlo.
- Pendiente / ideas que salen de las referencias: formato RECORRIDA/EVENTO (tomas sueltas + música + título manuscrito +
  fotos en tarjetas, como T08/T09/T18) para los brutos de eventos; cifras en pantalla sincronizadas con la voz (T04); sesión del
  Senado sobre fondo de color (T15/T16); tomas de apoyo del público sobre la voz en discursos (T01).

## 3p. Cifras en pantalla sincronizadas con la voz — SOLO en algunos casos (2026-10-16, pedido del usuario)
- `cifras.py`: detector de estadísticas en lo que ella dice: número (cifra o palabras; une "37" + ".825" que parte whisper) + lo
  que cuenta ("víctimas de feminicidio", "denuncias de violencia familiar", "hijos e hijas"). Descarta años/fechas ("el 2025",
  "12 de octubre"), horas ("21 y 30"), leyes/artículos, edades y duraciones ("22 años", "durante 20 años", "72 horas"),
  cantidades < 10 y números sin sustantivo. Si se corrige al toque ("20 víctimas, 21 ya") toma la última. Puntaje: sustantivo
  de estadística +3, ≥20 +1, ≥100 +1, dicho como cifra +0.5, tiempo +1 solo. Se muestran las de puntaje ≥ 3.5, ≤ 2 por minuto,
  separadas ≥ 3.5 s (en un tramo de cifras van en fila, una cada 3–4 s, como en la referencia T04).
- Sobre las 18 referencias: solo T04 tendría tarjetas (258 feminicidios, 37.825 denuncias, 20 feminicidios) = justo donde el
  equipo usó infografías; la conferencia BCP: ninguna. "Solo en algunos casos" sale solo.
- `styles/cifras_capa.py` (la usa `redes`): tarjeta blanca 820×150 con bloque rojo + ícono, número navy que CUENTA hasta la cifra
  mientras ella lo dice (0.7–1.3 s), etiqueta en mayúsculas; entra subiendo, dura hasta 4.2 s o hasta el fin de su idea, sale
  antes de la siguiente; carril de los micrófonos encima del subtítulo (abajo a 1162), nunca sobre la cara; swish suave al
  entrar y clic al terminar de contar. Solo lo que dice ella (no la pregunta del periodista).
- Control: `make_video.py … --cifras auto|no|mas` (cfg "cifras"); lista manual en cfg o `sources/<fuente>/cifras.json`
  ([{trigger, value, label, icon}]) manda sobre lo automático; el proyecto guarda `cifras.json` con lo mostrado.
- Prueba: feminicidios · juzgados (redes) → 37 feminicidios (27.0 s), 258 víctimas de feminicidio (34.2 s), 21 víctimas (41.1 s).
  Banco 46/47 (+2 pruebas: 9 frases del detector y "BCP sin tarjetas"). OJO: esa fuente es panel de TV con láminas → el QA del
  video entero marca congelados/sin cara por las láminas (no por las cifras); para fuentes panel el estilo es `datos`.

## 3q. Autoentrenamiento con los brutos nuevos: ENTENDER cualquier video + discursos en actos (2026-10-16)
- `entender.py` (nuevo): ficha de cualquier video → TIPO (conferencia · discurso · mensaje a cámara · reunión · TV/radio/Senado ·
  evento · toma corta · ya editado) + formato/estilo/comando recomendado + avisos. Mide formato real (SAR, rotación, HDR),
  habla (VAD) y cuánto es de Lilian (huella de voz, ventanas de 3 s), otras voces (agrupamiento), música/aplausos de fondo,
  caras (YuNet; Lilian por huella de cara SFace), movimiento de cámara, subtítulos/cortes/tarjeta final (ya editado) y zócalo
  de TV (densidad de texto en la franja de abajo ≥ 0.2). En una carpeta agrupa tomas por evento (fecha del archivo).
  Verdad etiquetada a mano: `analysis/entender_verdad.json` (34 videos) → `python entender.py --evaluar` = 34/34 (son los
  mismos con que se ajustaron las reglas: cada video nuevo que llegue se suma a la verdad). La caché guarda MEDIDAS (la
  decisión se recalcula). `ingest.py` lo usa: guarda `tipo` en source.json y avisa si conviene otro formato; TV → panel.
- Discurso en un acto (DJI 11 min, Encarnación): lo que falló y quedó arreglado —
  · voz: con parlantes y sala su similitud con la huella baja a 0.78–0.94 y ella dice "ustedes" todo el tiempo → 22 frases
    suyas quedaban como "periodista". `speakers._label_monologo` (tipo discurso/mensaje): agrupa las voces DEL VIDEO, la de
    ella = el grupo con más tiempo entre los parecidos a la huella; sin reglas de prensa → solo el locutor (0–3 s) queda afuera.
  · frases: whisper dejó 593–672 s SIN puntuación (una "frase" de 78 s). `content.build_sentences`: > 30 s se parte en sus
    pausas reales (trozos ≤ 22 s); los trozos que arrancan a mitad de frase quedan `soft_start` y el mapa nunca empieza un
    bloque ahí. La conferencia BCP no cambia (sus frases largas bien puntuadas llegan a 28 s).
  · encuadre: de cuerpo entero la cara era 0.10 del alto → `make_video.auto_zoom`: acerca hasta la cara de referencia sin
    agrandar el original más de 3.2× (404×720 ya va ×2.7 → zoom ×1.13); el QA pasa FACE_SMALL a "baja" con el motivo.
  · QA de cortes: el umbral fijo de −28 dB es el ruido de la sala en un acto (mediana −20) → todo corte parecía "sobre la voz".
    `qa._real`: umbral relativo al piso de ruido y la definición real: el borde cae DENTRO de una palabra suya o ella sigue
    sin respiro (< 0.12 s).
  · duración exacta: con frases largas no se llega justo → se completa una idea con su frase siguiente del mismo bloque y,
    si aun así faltan ≤ 6 s, la tarjeta final crece hasta 6 s (antes que cortar una idea). Queda: news · 4 min (−5.4 s).
- Resultado: `Lilian_Encarnacion_discurso_1min` (redes) entregado — gancho "No podemos compartir con nuestros hijos porque ya
  no hay tiempo." → "¿miedo de qué?…" → "Por eso nace Causa Republicana…" → cierre "No se trata solamente de hablar de
  elecciones…"; QA solo con avisos bajos. Banco 58/60 (fallas: feminicidios sin material para 3–4 min; news 4 min del discurso).


## 3r. Formato EVENTO / RECORRIDA: tomas sueltas -> montaje con música (2026-10-16)
- `evento.py` (nuevo): varias tomas de un mismo acto/visita/cumpleaños (de una carpeta: `--grupo N` = N-ésimo evento de
  entender.py; o una lista) -> video vertical al pulso de la música (104 BPM), título manuscrito (Ink Free / Marker Felt en
  Mac, borde rojo de la casa + fecha en etiqueta), voz de Lilian con subtítulo cuando habla, barrido al cambiar de toma,
  empuje lento a la cara principal en cada toma, cierre blanco 3 s. Como las referencias T08/T09/T18.
- Cómo elige: cada toma se mira a 10 cps (nitidez, temblor, barridos, brillo, caras YuNet, Lilian por huella de cara) y se
  escucha (VAD + huella de voz con umbral flexible + whisper). Prioridad: frases COMPLETAS de ella (1.2–9 s, con su audio y
  subtítulo), luego la mejor toma de cada video, luego el resto por puntaje; tomas de 4–8 pulsos (2.3–4.6 s ≈ 15 cortes/min,
  como las referencias); nunca barridos de cámara, oscuro o movido; orden real (toma por toma, en su tiempo).
- Reglas aprendidas en las pruebas: (1) si ella pide no grabar ("esta parte no se va a grabar", "apaguen", "no lo graben",
  "esto no sale") NADA de esa toma desde ahí — ni voz ni imagen (lo había usado: "Vamos a apagar todo."); (2) sus frases
  tienen que entenderse solas (no minúscula inicial, no "pero/porque/entonces…", ≥ 4 palabras, con final y sin que las corte
  el final de la toma: "Ese es el nombre de Roa Cuniba" sin cierre -> afuera); (3) el título no tapa caras: arriba salvo que
  en los primeros 3 s haya caras en esa franja -> abajo; (4) títulos largos en 2 líneas grandes; (5) mezcla a media escala
  (la música recortaba a +6.9 dB) y loudnorm −14 LUFS; sin voz de ella, la música no se agacha (core.make_duck).
- Pruebas (brutos del usuario): 7/2 cumpleaños de Arnaldo (3 tomas, 184 s -> 11 tomas, 47 s), 5/1 Arnaldo 2026 (con 3 frases
  de ella; corta desde que pide no grabar), 22/8 con los jóvenes (3 tomas cortas -> 13 s). QA: sin negros, −14.6…−15.1 LUFS,
  duración exacta. Muestras entregadas: MUESTRA_evento_*. Banco: + prueba "no se va a grabar / frases colgadas" (20/20 BCP).
- TRAMPA repetida: un regex con `\\b` dentro de un comando de la terminal llega como "backspace" (los escapes se interpretan
  una vez más): parches SIEMPRE en archivo; `chr(8)` en 0 en todo el estudio.


## 3s. Mejoras previstas: "no grabar" en todo el estudio, público sobre la voz, Senado sobre fondo liso (2026-10-16)
- "Pide no grabar" en conferencias/discursos: `plan.off_record_from` (mismas frases que evento.py) -> desde esa frase la fuente
  queda BAD (nunca entra en un guion). Ninguna fuente actual lo tiene; probado con frases sintéticas.
- Tomas de apoyo del público sobre la voz (referencia T01): `styles/broll_capa.py`, en `redes` con `make_video.py --broll
  <carpeta|videos del MISMO acto>`. Elige tomas nítidas, quietas, con público y SIN la cara de Lilian (labios), las pone sobre
  cada SALTO entre tramos de su discurso (desde 0.4 s antes, 1.8–2.6 s), nunca en el gancho, sobre cifras ni al final; ≤ 3 por
  minuto (`broll_por_min`); declara esos tramos "sin cara" al QA (tramos_estilo.json). Prueba técnica (discurso Encarnación +
  tomas de OTRO acto, no entregada): 2 saltos tapados, QA solo avisos bajos. Para entregar hace falta público del mismo acto.
- Senado sobre fondo liso (referencias T15 rosa claro 254,171,173 · T16 rosa fuerte 240,110,124; video en la franja del medio):
  estilo `datos` con `--fondo rosa|rosa_fuerte|bordo|azul|rojo|blanco|#RRGGBB`. Con fondo CLARO el QA de contraste frenaba
  (titular blanco sobre rosa 1.8:1; tarjetas rosa sobre rosa): titulares y fuente en oscuro, tarjetas pálidas -> blancas con
  borde y ENCABEZADO bordó (rótulo en blanco), ítems apagados en bordó tenue. Resultado: QA previo y final sin problemas
  (solo ritmo lento, baja). Entregado MUESTRA_senado_fondo_rosa_feminicidios. Banco 59/61 (las 2 fallas conocidas).
- Pendiente: toma del documento (acercar al papel cuando lo muestra, T04/T05) — falta un bruto donde ella muestre un documento.


## 3t. Segunda tanda de referencias (37 TikToks) — escenarios y estructura (2026-10-16)
- Informe: `analysis/tiktok1610b/REPORTE.md` (tiras de fotogramas TIRAS_01…10). Escenarios: rueda de prensa/declaración en el
  Congreso 17 · sesión del Senado (TV) 7 · reunión 3 · cobertura con varias personas y placas de nombre 3 · evento/acto 4 ·
  vida personal/cocina/feria 4. Estructura: la declaración ENTERA (mediana 120 s, 41–346 s); 6/37 repiten la frase fuerte al
  inicio en COLOR (0/37 en B/N); tarjeta final 30/37; subtítulo a 0.641; música 31/37 (≈ 16 dB bajo la voz); insertos de
  contexto 6/37 (notas de diario, posteo, tabla, infografía, cifras sobre violeta).
- Nuevo: `--angle completo` (content.STORIES: todos los bloques en orden real, sin gancho, hasta 360 s; prueba BCP 5:57 sin
  hallazgos, entregada como MUESTRA_declaracion_completa_BCP_6min) · `--gancho bn|color|no` (selector2.build(hook=…),
  redes: color = sin B/N, solo el barrido) · `--insertos <carpeta>` (styles/insertos_capa.py: imagen nítida sobre ella misma
  desenfocada, acercamiento lento, aparece cuando ella dice el nombre del archivo o la frase de insertos.json; probado con las
  infografías del equipo sobre feminicidios: aparecen en "En el 2025 hubo 37…" y "esa es la cronología").
- `styles/base.declarar_tramos(dir, capa, spans, quietos)`: cada capa (insertos, broll) declara SUS tramos sin cara/quietos para
  el QA; antes se acumulaban entre corridas.
- `entender.py`: tarjeta final blanca = ya editado (ningún bruto termina en blanco); vertical con ≥ 2 voces que conversan y ella
  de cuerpo entero = evento; fecha del nombre tolerante (ids de TikTok). Verdad: 71 videos. EXAMEN LIMPIO (37 nunca vistos,
  antes de ajustar): 30/37 = 81 %. Después: 71/71 (ajustado con ellos: la próxima tanda es el examen honesto).
- Banco 59/61 (las 2 fallas conocidas; el test de guiones ahora también recorre "completo").


## 3u. Pulido: un solo comando, bordes de grabación, cara de lejos, banco 76/76 (2026-10-16)
- `auto.py <video|carpeta|varios>`: entiende cada video y lo edita con el formato que corresponde. Agrupa TODO por evento
  (fecha) y decide como un editor: si ella habla (declaración/discurso) se edita eso y las tomas sueltas del MISMO evento tapan
  sus saltos (--broll); si solo hay tomas, montaje (si hay ≥ 12 s); si ella habla pero filmada de LEJOS (cara < 5 % del alto),
  su voz va dentro del montaje del evento; reunión -> prepara y pide confirmar nombres; ya editado -> referencia. Duración
  "auto": declaración ENTERA si ella habla ≤ 4 min, si no lo más importante (≈ 2 min). Copias idénticas se ignoran.
  `--solo-plan` muestra qué haría sin preparar nada.
- `plan.recording_edges`: frases que la GRABACIÓN cortó (cámara que arranca con ella ya hablando: voz desde los 10–40 ms y sin
  pausa en 0.6 s, relativo al ruido de la sala; o que termina mientras habla: última palabra sin punto o con "...") -> BAD.
  Solo se activa en el video del 9/1 (no en las fuentes conocidas). Antes: QA frenaba con "escena que termina a mitad de oración".
- `ingest.track_face`: YuNet a 540×960 + huella de cara (cada ~10 muestras) en vez de Haar a 270×480: ve caras chicas y se
  queda con ELLA. En el 9/1 Haar se enganchaba a algo de 311 px que no era ella; YuNet la encuentra (66 px, parecido 0.64).
- evento.py: frases por pausas si whisper no puntúa; un trozo que termina en coma se une con el siguiente; nunca termina en
  "y/de/que…"; sin punto, solo si lo que sigue no la continúa (minúscula); guía de transcripción (+ --tema); REUTILIZA la
  transcripción de ingest si el mismo archivo ya se ingresó (mucho mejor: "hice un compromiso con mi amiga Mari").
- Duración exacta 3–4 min con frases largas: respiración antes de cada idea hasta 0.6 s + tarjeta ≤ 6 s (discurso news 4 min:
  234.6 -> 240.0). Si el MAPA no tiene ideas suficientes (feminicidios: 6 ideas = 2:15) se avisa el motivo y qué hacer, y el
  banco no lo cuenta como error. make_video también entrega en la carpeta de Drive (EXTRA_DELIVER) si existe.
- Entregado: AUTO_evento_Epi_Centurion_9ene (hecho de punta a punta por auto.py). Banco: 76/76 (+ bordes de grabación,
  frase con coma partida en el montaje; + la fuente del 9/1 como caso de plano lejano).


## 3v. Marca CAUSA REPUBLICANA + prohibida la letra manuscrita + logos animados (2026-10-16)
- REGLA DEL USUARIO (enojado, con razón): "este tipo de formato y estilo de letra JAMÁS hagas, queda muy mal para este tipo de
  contenido, muy informal" — era el título del montaje de evento en Ink Free blanco con contorno rojo (lo había copiado de los
  vlogs personales). Arreglo: evento.title_sprite institucional (Montserrat Black blanco sobre bloque rojo de la marca + fecha en
  placa blanca con letras rojas, entra con barrido sobrio); "inkfree" fuera de plataforma.FONTS; prueba permanente en regress
  que falla si algún archivo usa una fuente manuscrita/informal. Los 4 montajes re-renderizados y reemplazados en Drive.
- Manual de marca (`Downloads/MANUAL DE MARCA CAUSA REPUBLICANA.pdf`, 5 págs., oct. 2025): Montserrat Medium/ExtraBold/Black;
  rojo HEX #C8102E (Pantone 186C; el dibujo del PDF se ve #ED1C24 por la conversión CMYK); blanco; logotipo (isologo + CAUSA /
  REPUBLICANA), isologotipo CR con estrella, eslogan #GanarParaServir (arte propio), cierre /somoscausapy con IG/FB/Twitter/TikTok.
- `marca_causa.py extraer`: los logos del PDF son MÁSCARAS de baja resolución (isologo 263 px) -> vectorizado por contornos y
  redibujado en alta (isologo 1578 px, logotipo 4593 px) y separado en piezas: marco, C, R, estrella (hueco de la R), letras de
  CAUSA (5) y REPUBLICANA (11), eslogan. `assets/marca_causa/piezas/` + piezas.json.
- `logo_animado.py todo` -> `assets/marca_causa/animados/`: intro 3.8 s (el marco se dibuja, la C crece, la R sube, la estrella
  se marca girando, el isologo se ubica, CAUSA y REPUBLICANA letra por letra, eslogan con barrido, brillo sutil) en 9:16, 1:1 y
  16:9, fondo rojo y fondo blanco, con sonido sutil; intro 9:16 TRANSPARENTE (ProRes 4444, para poner sobre un video en CapCut);
  cierre 9:16 como la última página del manual; mosca transparente (isologo chico en bucle). Entregados en
  videosclaudesubir/LOGOS_CAUSA_REPUBLICANA. Banco 77/77.


## 3w. Prueba de estrés de auto.py con TODO el material + correcciones (2026-10-16)
Corrida: los 14 brutos de VIDEOSCRUDOLILIAN + IMG_4572 (conferencia BCP) + IMG_4801 (reunión Mussi) + LS1 (Senado TV), sin
indicaciones. Resultado: 6 bien, 1 bloqueado, 1 a la espera de nombres; 2 tandas omitidas por poco material.
Lo que salió mal y se corrigió:
- 5-ene "Dji…0020 D (1)": entendido como declaración, pero de 40 s solo 16 s útiles (saludo en un cumpleaños; después pide "esta
  parte no se va a grabar"). Salía un video de 14 s, bloqueado por el QA. auto.py: si hay otras tomas del mismo evento y la voz
  útil de ella (medida tras la ingesta) es < 25 s, NO es una declaración -> va al montaje del evento con su voz. Sola, se edita
  igual y el informe avisa "muy corto".
- QA FACE_LOST/FACE_SMALL falsos: (a) la placa final no se descontaba (en 14 s es el 18 %); (b) Haar mide la cara más chica
  (0.75× YuNet en ese plano) y pierde perfiles. qa.segunda_opinion(): si Haar duda, YuNet (calibrado Haar ≈ 0.95× YuNet en 6
  videos). Prueba con tests/cara_perfil.mp4.
- LS1 (estilo datos): DARK porque el fondo bordó contaba como imagen -> el estilo declara zona_imagen y el QA mide el recuadro
  (59.7 -> 98.4). La placa decía "SENADO · SESIÓN 14/10/2026" ESCRITA EN EL CÓDIGO: ahora fecha real de la toma (source.json
  "fecha", entender.fecha en hora local) y "SENADO" solo con pistas de sesión; cfg "etiqueta" manda. Tramos en que la TV muestra
  una lámina (panel.json sin_cara) se declaran al QA (no son cara perdida ni congelado: son las cifras que ella pidió mostrar).
- Estilo datos sin datos.json: ahora toma las cifras de peso que ella dice (cifras.py) como tarjetas "dato" sincronizadas, sin
  repetir la misma cifra (gancho + contexto). Bloque con ≥ 2 cifras de peso: importancia 5 y titular "LAS CIFRAS"; el gancho es
  la frase MÁS fuerte del bloque más importante ("Del 2020 al 2025 hubo 258 víctimas de feminicidio."), no la primera.
  Frases operativas ("Podría mostrar la imagen de las cifras…", prueba de sonido) no son contenido (mapper.OPERATIVA).
- Titulares del mapa automático: "FUERTE EN NUESTRA", "DEBE QUEDAR", "AQUEL PROYECTO", "PAÍS EMPIEZA", "CABALLERO LEVANTÓ",
  "¿CÓMO ES?", "2026"; "LOS DATOS" por un año, "LO LOGRADO" por "lograríamos". mapper: sustantivo = aparece tras artículo o
  posesivo en la transcripción (nouns_of); pares sustantivo+adjetivo, adjetivo antepuesto+sustantivo o nombre propio ENTERO;
  "X de Y"; nombre de alguien que ella menciona ("la senadora Yolanda Paredes") no es titular salvo en un ataque; año ≠ dato;
  logro solo en pasado; titular_malo() controla cada fuente. Ahora: "CASO DEL FEMINICIDIO", "MESA TÉCNICA", "JUSTICIA RÁPIDA",
  "¿CÓMO ES POSIBLE?", "LAS CIFRAS"; los de la conferencia BCP siguen iguales.
- Titulares en el video: si la frase del gancho vuelve después en su contexto, la idea tenía UN solo tramo (desde el gancho) y el
  titular anterior quedaba puesto sobre otra idea. autocfg.beat_timeline arma tramos seguidos; el gancho que adelanta va sin titular.
- Agrupado: LS1 (TV) e IMG_4801 (reunión) salían como "un evento" por grabarse con 11 min de diferencia (metadatos de grabación).
  TV, reunión y editados van siempre aparte.
- Reunión: probé aprobar sola una reunión cuando las CARAS de los invitados ya estaban en el registro. Error grave encontrado:
  en la nueva ingesta de IMG_4801 la sincronía de labios asignó la voz de Mussi a la cara de Aarón (y el QA no lo ve). Por eso:
  (1) al aprobar se guarda también la huella de VOZ de cada invitado (clients/<cliente>_people/<nombre>.voz.npy; Mussi·Aarón
  0.54); (2) en una reunión nueva, la voz reconocida (≥ 0.90 y margen ≥ 0.05) elige la cara registrada de esa persona (antes que
  los labios); (3) auto.py edita sin preguntar SOLO si todos los invitados se reconocen por voz Y cara; si el mismo archivo ya
  fue aprobado, edita esa fuente (no re-adivina). Si no, espera la confirmación de nombres como siempre.
- reunion.py edit --titulo con fuente sin título se caía (None.replace); el título pedido ahora guía la selección y queda guardado.
- Velocidad: video de trabajo panel 25 -> ~6 min para 12 min de TV (desenfoque del fondo a 1/4: 65 -> 8 ms/cuadro, igual a la
  vista); cara cada 3–4 cuadros en videos > 4/10 min (305 -> 163 s).
- 4 min exactos de un discurso de frases largas: respiración previa hasta 0.8 s (antes 0.6) para no quedar 5.7 s corto.
- Control plantado "texto sobre la cara" (cita): el encuadre de la prueba bajó la cara y el error ya no se plantaba; el control
  ahora baja el texto a la cara (Style.hook_y).
- Informe de auto.py: hallazgos del QA en palabras ("ritmo tranquilo", "cara chica…") y lo omitido también aparece.


## 3x. Arreglos de la auditoría + control de versiones (git, GitHub privado) + limpieza (2026-10-16)
Auditoría por áreas (6 auditores + escéptico + crítico): 59 puntos flojos, 52 importantes, todos confirmados. Los que no
necesitan al usuario se arreglaron en paralelo (un agente por área, revisión adversarial y reparación) y después una revisión
cruzada de todo el diff encontró 7 problemas entre áreas, también corregidos. Banco completo 164 -> 200/200 (36 pruebas nuevas en
tests/pruebas_*.py, que regress carga solas; las que necesitan datos que no viajan se saltean en el paquete o en un clon).
- Glosario: el del BCP ("bueno"->"Ueno", "cantidad"->"entidad", "filo"->"vilo") estaba en la ficha y se aplicaba a TODOS los
  videos. Pasó a las fuentes del BCP; la ficha solo deja pasar nombres propios (plan.glosario_cliente) y nunca toca una palabra que
  la fuente usa como común. El Senado vuelve a decir "la mayor cantidad de denuncias".
- entender: archivo roto/a medio copiar = tipo "roto" (no frena la tanda); lo que falta en la PC = FallaEstudio (corta una vez con
  el motivo). Eventos: tope de 4 h, > 1 km por GPS = otro lugar, hora de nombres de WhatsApp, fechas en hora local.
- auto.py: reconoce el ARCHIVO original (huella, ruta+duración o nombre+duración) y usa la fuente con más correcciones humanas
  (LS1 -> lilian_senado_feminicidios, Encarnación -> lilian_encarnacion_acto); una ingesta nueva del mismo archivo hereda las
  correcciones. Si el mapa no tiene la historia pedida usa la del editor ("juzgados"). El informe cuenta las dudas del árbitro sin
  revisar dentro del video. Montajes con nombre único. Borradores automáticos se rehacen si cambian mapper.py o el glosario (nunca
  uno corregido a mano).
- Senado por TV: en una SESIÓN (ella le habla a la presidencia) decide la voz, no las reglas de prensa. LS1 automático 56/56 contra
  la versión corregida a mano (antes 3 frases de ella como otra voz); BCP 98,6 %. "presidente/a" es vocativo solo separado por signos.
- Evento: tomas de ambiente sin voz cortada y frases que entran/salen en pausas; QA del montaje con duración, zona segura, título
  que no tapa caras (YuNet). Pendiente conocido: si no hay ningún silencio medible antes de una frase de ella (música continua) el
  corte puede caer en su voz; endurecerlo con la huella descartaba todas las frases de la fiesta del 5-ene -> hace falta energía.
- Reunión: QA con duración vs pedido (en el EDL), placa de nombre sobre la persona correcta (voz->cara), textos sin tapar la cara.
  Re-ingesta de IMG_4801 con huella de voz: S1 = Mussi, S2 = Aarón (antes salían cruzados por labios).
- selector2: la frase del gancho no vuelve a sonar antes de 20 s. regress: un mapa AUTOMÁTICO sin aprobar puede quedar hasta 10 %
  corto en los cortes exactos si lo avisa (los aprobados siguen exactos).
- Control de versiones: git en studio/ (rama main), privado en GitHub: https://github.com/ss20alt/AULS (credencial de Windows del
  usuario ss20alt). .gitignore: sin projects/, sources/, models/ (se bajan con models/download_models.py, que ahora trae también
  YuNet y SFace), huellas biométricas (clients/*.npy, clients/*_people/), cuadros con caras de invitados ni resúmenes con GPS.
  README.md = cómo instalar en otra PC y mantenerlas al día (git pull).
- Limpieza: 47 copias de prueba borradas (pruebas de estilo, corridas de prueba, §3l zoom/color y PRUEBA_*.mp4 de Descargas):
  projects 44 -> 30 GB. Se conservan los proyectos entregados (para correcciones con feedback.py) y _prueba (doctor).
- Paquete del equipo rearmado (empaquetar.py): lleva las pruebas nuevas y VERSION.json con el commit; por defecto SIN huellas de
  invitados (--con-invitados para incluirlas).
