---
name: autoeditor-lilian
description: Autoeditor de videos de la senadora Lilian Samaniego (Windows con NVIDIA o Mac Apple Silicon). Toma una grabación en bruto y produce videos verticales 9:16 para redes con cortes que nunca caen sobre la voz, subtítulos verificados, titulares y control de calidad automático antes y después de renderizar. Dos formatos — CONFERENCIA/DECLARACIÓN (Lilian sola o con periodistas: 1, 2, 3 o 4 minutos, 15 estilos) y REUNIÓN (video horizontal con varias personas, p. ej. Lilian presenta a quienes se suman: vertical informativo de la duración pedida). Usar cuando pidan editar, cortar, armar, renderizar o corregir videos de Lilian, ingresar un video nuevo en bruto, revisar la transcripción o cargar correcciones del equipo.
---

# Autoeditor de Lilian Samaniego

Todo el trabajo lo hace el estudio en `studio/` (Python). Vos (Claude) lo operás, verificás y conversás con la persona del equipo.
Trabajá SIEMPRE desde la carpeta `studio/`. En esta guía `PY` es el Python del estudio:
- **Mac**: `.venv/bin/python` (lo crea `instalar_mac.sh`).
- **Windows**: `python` (Python 3.12 con torch CUDA; ffmpeg 9 de winget con zscale). En Git Bash anteponé `PYTHONIOENCODING=utf-8`.

## 0. Antes de editar: la instalación tiene que estar sana
- Mac, primera vez o algo falla: `bash ../instalar_mac.sh` (ffmpeg, Python, librerías, modelos y autochequeo).
- Autochequeo: `PY doctor.py` (completo) o `PY doctor.py --rapido` (≈ 1 min) → tiene que terminar en **LISTO**. Si dice
  **HAY PROBLEMAS**, NO edites videos: mostrá las líneas FALLA de `tests/doctor_informe.txt` y, si hay imágenes en
  `tests/diferencias/`, miralas (yo | referencia | diferencia). Pedile que mande ese informe a quien le pasó el autoeditor.
- `dispositivo: cuda` = NVIDIA (Windows, lo más rápido: NVDEC + NVENC). `mps` = chip gráfico de la Mac (correcto).
  `cpu` = funciona pero lento.

## 0b. El camino corto: UN comando para cualquier video
```
PY auto.py "<video o carpeta>" --tema "nombres propios" [--titulo "EVENTO" --sub "fecha"] [--length 1min|3min|4min|completo]
```
Entiende cada video, los agrupa por evento y decide como un editor (declaración entera o resumen, montaje de evento, reunión,
TV). `--solo-plan` muestra qué haría. Si algo no da (material insuficiente, nombres sin confirmar, plano muy lejano) lo dice.
Usá los pasos de abajo cuando la persona pida algo puntual (un estilo, un ángulo, frases elegidas).
Al final imprime un INFORME (también `projects/_informes/auto_<fecha>.md`): cada video, formato, estado (ok / ok con aviso /
no entregado / omitido / espera nombres) y el motivo en palabras. Decisiones aprendidas en la prueba de estrés:
declaración con < 25 s útiles de ella + otras tomas del mismo día → montaje con su voz; TV, reunión y editados nunca se
agrupan con tomas; tandas de < 12 s se omiten (avisando); reunión: se edita sola SOLO si cada invitado se reconoce por
voz Y cara (registro de personas aprobadas) o si ese mismo archivo ya fue aprobado; si no, pide confirmar nombres.

## 1. ¿Qué formato es el video?
| el bruto… | formato | herramienta |
|---|---|---|
| Lilian habla a cámara / conferencia de prensa / declaración (con o sin preguntas de periodistas) | CONFERENCIA | `ingest.py` + `make_video.py` (§2–3) |
| reunión horizontal con varias personas que hablan por turnos (Lilian presenta, los invitados hablan) | REUNIÓN | `reunion.py` (§4) |
| tomas sueltas de un acto/visita/cumpleaños (saludos, público, fotos; ella casi no habla) | EVENTO | `evento.py` (§4c) |

Primero preguntale al estudio: `PY entender.py "<video>"` (o una carpeta entera) → tipo (conferencia, discurso, mensaje,
reunión, TV, evento, toma corta, ya editado), por qué, avisos (resolución, píxeles DJI, música) y el comando a usar. Una
carpeta además agrupa las tomas por evento. `ingest.py` ya lo usa y guarda el tipo (en discurso/mensaje la voz se decide
con las voces del propio video). Si la ficha te parece mal, mirá 3–4 fotogramas del bruto (ffmpeg → png → Read), corregí
y sumá el video a `analysis/entender_verdad.json` (`PY entender.py --evaluar`).

## 2. CONFERENCIA: fuentes y proyectos
- `sources/lilian_conferencia_bcp/` = la conferencia sobre el Banco Central (oct. 2026) ya preparada, con su mapa de contenido
  manual (8 historias) y su material de fotos (`material: bcp`). Sirve para editar esa conferencia y para el banco de pruebas.
- Video nuevo en bruto:
  ```
  PY ingest.py "/ruta/al/video.MOV" --name <nombre_corto> --tema "nombres propios y temas del video"
  ```
  Exportaciones del DJI con píxeles no cuadrados (1728×1080 / 1080×1080 / 1280×720 que en realidad son 9:16): el ingest las
  endereza solo y avisa si la resolución real es baja; si existe el archivo ORIGINAL de la cámara, pedí ese.
  `--tema` mejora mucho la transcripción (ej.: "Gustavo Leite, IPS, Banco Central del Paraguay"). `--material bcp` SOLO si el
  video es sobre el Banco Central. Avisá a la persona que tarda (transcribir + preparar) y dejalo correr.
- Después de ingresar:
  1. **Mapa de contenido**: borrador en `sources/<fuente>/content_review.html`. Si la persona lo aprueba:
     `PY mapper.py approve <fuente>`. Los titulares automáticos son buenos pero no perfectos: proponé mejoras.
  2. **Árbitro de la transcripción**: `PY arbitro.py review <fuente>` abre http://127.0.0.1:8765 con cada duda; la persona
     escucha y decide "Está bien" / "Corregir". Hacelo antes de producir videos importantes.
- Para trabajar con una fuente: `STUDIO_SOURCE=<fuente>` delante del comando (por defecto: la conferencia BCP).

## 3. CONFERENCIA: producir un video (piloto automático)
```
STUDIO_SOURCE=<fuente> PY make_video.py --style <estilo> --angle <ángulo> --length 1min|3min|4min
```
(sin `--length`: duración libre hasta 2 min). Ángulos = historias del mapa: `PY -c "import content; print(list(content.STORIES))"`.

El piloto automático: guion → **espectador** (control editorial) → preparar → espectador + **QA visual** en fotogramas de prueba
→ render **solo si está limpio** → QA final (técnico, visual, texto con desempate acústico) → entrega en Descargas **solo sin
hallazgos medios/altos**. Si se frena, leé el motivo en el log o en `projects/<proyecto>/qa.md` y corregí la causa; nunca uses
`--force` para entregar algo con errores sin decírselo a la persona.

Cifras en pantalla (estilo `redes`, SOLO en algunos casos): cuando ella dice una estadística de peso ("258 víctimas de
feminicidio") aparece una tarjeta en el carril de los micrófonos y el número cuenta mientras lo dice. Fechas, horas, edades,
leyes y números chicos NO; si el guion no tiene cifras de peso, no hay tarjetas. `--cifras auto` (por defecto) | `no` | `mas`;
lista manual en `sources/<fuente>/cifras.json`. Revisá `projects/<p>/cifras.json` y la hoja: el número tiene que ser el que
ella dice (si se corrige, el último).

Cómo publica el equipo (55 TikToks medidos): la mayoría sube la declaración ENTERA (1–4 min, en orden, sin gancho) →
`--angle completo`. Gancho: `--gancho bn` (blanco y negro), `color` (repite la frase fuerte en color) o `no`.
`--insertos <carpeta>`: notas de diario, posteos, tablas o infografías que aparecen a pantalla completa cuando ella dice el
nombre del archivo (`huelga_medica.jpg` → "huelga médica") o la frase de `insertos.json`; su voz y el subtítulo siguen.

Opciones del piloto automático (estilo `redes`): `--broll <carpeta>` = tomas del público del MISMO acto que tapan los saltos
del discurso mientras sigue su voz (nunca con su cara: los labios no coincidirían). Estilo `datos` (TV/Senado):
`--fondo rosa|rosa_fuerte|bordo|azul|rojo|blanco|#RRGGBB` = señal sobre fondo liso (rosa en octubre, como el equipo).
Si en el bruto ella pide no grabar ("esta parte no se va a grabar", "apaguen"…), desde ahí no se usa nada (todos los formatos).

Imagen: acercamiento FIJO a la cara (`core.ZOOM_FIJO = 1.06`, variable `STUDIO_ZOOM_FIJO`; 0 = el zoom animado de cada estilo),
siguiendo la cara, sin entrar y salir (aprobado por el usuario). HDR del iPhone → SDR con hable npl=300 (no subir el brillo).

| estilo | look | notas |
|---|---|---|
| news | noticiero limpio, tarjeta de pregunta | |
| ink | TikTok tinta, cajas negras, final B/N | |
| report | reportaje: globo de pregunta, capítulos, recuadros de fotos | fotos solo si la fuente tiene material |
| headline | titulares grandes por tema | |
| fx | animado rojo con efectos | |
| call | llamada con letra (foto fija + panel) | **requiere material del tema** |
| split | pantalla dividida con tomas | **requiere material del tema** |
| karaoke | subtítulo grande, palabra activa en caja amarilla | |
| doc | documental, franjas de cine | |
| tv | TV noticias: zócalo, cinta | |
| claves | "N claves" numeradas + repaso | |
| cita | gancho tipográfico + citas textuales firmadas | |
| editorial | revista: papel, tarjeta de video, páginas | |
| campana | campaña: marino y dorado, actos | |
| podcast | reproductor con barras de su voz | |
| **redes** | **el look que publica el equipo** (18 TikToks medidos): subtítulo único blanco a 0.64 del alto, gancho en B/N que entra al color con barrido, color natural, música baja, sin placa | **recomendado por defecto** |

## 4. REUNIÓN: video horizontal con varias personas → vertical informativo
Ejemplo real: "Ex diputado Gustavo Mussi se suma a Causa Republicana" (Lilian presenta; hablan Mussi y Aarón Ruiz Díaz).
```
PY reunion.py ingest "/ruta/video.MOV" --name <fuente> --tema "nombres propios, movimiento, partido, lugar"
PY reunion.py people <fuente>                         # borrador de personas (people.png): S1, S2… con nombre y cargo
PY reunion.py people <fuente> set S1 "Nombre Apellido" "Cargo"
PY reunion.py people <fuente> approve                 # CONFIRMAR con la persona: nombres bien escritos (no como los oye whisper)
PY reunion.py edit <fuente> --length 150 --titulo "EX DIPUTADO GUSTAVO MUSSI|SE SUMA A CAUSA REPUBLICANA"
```
- Pruebas de selección sin gastar tiempo ni llenar Descargas: `--no-render --no-deliver --proj prueba` (muestra qué elegiría).
- Narrativa pedida a mano ("que Lilian presente y después hablen X e Y, 1:10"): `PY reunion.py frases <fuente>` lista las frases
  numeradas; armá el guion y `PY reunion.py edit <fuente> --frases "0@29.1,30-34,85-90,135-138" --proj <nombre>`.
  Cada rango = un bloque; `N@t` = el bloque termina en la pausa t DENTRO de la frase N (solo en una pausa real: verificá con
  `reunion.asr_words` y la energía que no haya voz entre el final y la siguiente palabra).
- Antes de proponer una versión corta, leé el guion completo: cada persona termina su idea, nada empieza con
  "y eso / por eso / no venimos…" sin lo anterior, y nada se repite entre bloques.
- Lo automático: presentación de la anfitriona hasta que nombra a los invitados y el tema; el invitado del título entra
  siempre (también en 60 s); finales limpios; respiración de 12 cuadros tras cada bloque; fundido solo en cambio de persona.
- Diseño: panel 4:5 a ancho completo con la cara anclada (sin zooms molestos), fondo = la misma imagen desenfocada, **titular
  ABAJO a la altura de los micrófonos**, subtítulos encima, placa de nombre (nombre + cargo) la primera vez que habla cada
  persona, cierre con redes. Color = el del bruto.
- QA: el `edit` termina con `QA OK` o `QA CON HALLAZGOS`; con hallazgos NO se entrega. Escuchá el hallazgo (re-oí el tramo con
  más contexto con `reunion.asr_words` sobre `projects/<p>/final16.wav`) antes de concluir que es real o falso.
- Re-render rápido tras cambiar solo gráficos: `reunion_render.render(fuente, pd)` + `reunion.qa` + `reunion.deliver_files`.
- Si cambiás reglas de selección: probá a 60/90/120/150 s con `--no-render` y revisá cada bloque. `REUNION_DEBUG=1` traza la
  selección paso a paso; `=2` muestra las ventanas candidatas con su puntaje.

## 4c. EVENTO / RECORRIDA: tomas sueltas de un acto, visita o cumpleaños → montaje con música
```
PY entender.py "<carpeta>"                       # agrupa las tomas por evento (fecha) y dice cuáles son "evento"/"toma corta"
PY evento.py "<carpeta>" --grupo <N> --titulo "CUMPLEAÑOS DE ARNALDO" --sub "7 de febrero" [--length 40] --name <nombre>
```
- Elige solo: frases COMPLETAS de Lilian (con su audio y subtítulo), las tomas más nítidas y quietas con caras (y ella), al
  pulso de la música (≈ 15 cortes/min), título manuscrito que no tapa caras, barridos entre tomas, cierre blanco.
- Si ella pide no grabar ("esta parte no se va a grabar", "apaguen"…), desde ahí esa toma no se usa: confirmalo en el log.
- Pedile a la persona el TÍTULO y la fecha (o proponelos con lo que se dice en las tomas: carteles, nombres). Pruebas con
  `--no-render` (muestra qué elegiría) o `--no-deliver`.

## 4b. Aprender de videos nuevos (referencias editadas o brutos)
```
PY analyze_batch.py refs "<carpeta de videos editados>" <etiqueta>   # ADN, transcripción, música, hoja grande por video
PY analyze_batch.py raw  "<carpeta de brutos>" <etiqueta>
PY analyze_batch.py match <etiqueta_refs> <etiqueta_brutos>     # qué tramo del bruto usó cada video editado
```
Mirá las hojas (`analysis/<etiqueta>/*_sheet.jpg`) con Read, medí lo que se repite y dejalo en `STUDIO_LOG.md` (ver §3o y
`analysis/tiktok2610/REPORTE.md`: así publica el equipo).

## 5. Verificá con tus ojos antes de decir "listo"
El QA automático atrapa casi todo, pero mirá siempre una hoja de fotogramas del video terminado:
```
cd projects/<proyecto> && for t in 1 5 20 40 55; do ffmpeg -v error -y -ss $t -i video.mp4 -frames:v 1 -vf scale=300:-1 f_$t.png; done
ffmpeg -v error -y -i f_1.png -i f_5.png -i f_20.png -i f_40.png -i f_55.png -filter_complex hstack=5 hoja.png
```
(en CONFERENCIA el archivo es `<proyecto>.mp4`) y leé `hoja.png` (herramienta Read). Revisá: texto sobre la cara, texto que no se
lee, la cara correcta de quien habla, fotos que no corresponden al tema, primera y última frase completas, nombres bien escritos,
cierre con redes. Contale a la persona lo que viste.

## 6. Reglas aprendidas (no romperlas)
- Un mismo archivo puede tener varias fuentes: auto.py usa la MÁS corregida a mano (no crea otra). Corregir siempre esa.
- Reunión: nombres solo con voz Y cara reconocidas (la cara sola se equivocó); si no, confirmar en la hoja de caras.
- Nada fijo en el código que dependa del video (fechas, lugares, nombres): sale de la fuente (source.json `fecha`, `tipo`)
  o de una opción. La placa SENADO del estilo datos usa la fecha real de la toma.
- Titulares automáticos: frases nominales (sustantivo+adjetivo, nombre entero, "X de Y"); `mapper.titular_malo()` los controla.
- Estilo datos sin `datos.json`: las cifras de peso que ella dice salen solas como tarjetas (solo si las hay).
- JAMÁS letra manuscrita, de marcador, tipo cómic ni ningún estilo informal en títulos o gráficos (el usuario lo prohibió).
  Títulos y placas: Montserrat (Medium/ExtraBold/Black) y los colores de la marca; contenido político = institucional.
  No copiar recursos de los videos personales (peluquería, cocina) a contenido político. Hay una prueba que lo controla.
- Marca Causa Republicana: `assets/marca_causa/` (piezas del logo en alta, `marca_causa.py`); logos animados:
  `PY logo_animado.py todo` (intro 9:16/1:1/16:9 fondo rojo y blanco, transparente, cierre /somoscausapy, mosca).
- Nunca cortar mientras alguien habla ni a mitad de frase; editar por **bloques de idea completos**; cada persona termina su
  idea antes de que entre la siguiente; nada de transición brusca justo después de la última palabra.
- Una pregunta del periodista siempre con su respuesta; ninguna escena empieza con "Por lo tanto / Como lo…" sin lo anterior.
- Sus palabras se respetan **textuales**; el texto se corrige solo si el audio lo confirma (árbitro) o el equipo lo confirma.
  "Le trató de sicaria" está confirmado por el equipo. Nombres: como los da el equipo ("Aarón Ruiz Díaz", no lo que oye whisper).
- Palabras de periodistas nunca en el subtítulo de ella; la voz de otra persona va distinta (azulada) y la pregunta entera.
- Titulares únicos por video; aparecen cuando ELLA responde, no durante la pregunta.
- Tarjetas y titulares ABAJO (a la altura de los micrófonos, dentro de la zona segura 9:16 y 270–1440), nunca arriba.
- Video informativo = sin gancho al principio.
- No usar las fotos del Banco Central en videos de otros temas (por eso `material`).
- Duración exacta: la tarjeta final (redes) absorbe la diferencia.
- Si algo sale mal y lo arreglás: que quede como regla en el código **y** como prueba en `regress.py`.

## 7. Correcciones del equipo
- "En el 0:43 dice 'Le trató de sicaria'": `PY feedback.py add <proyecto> 0:43 "dice 'texto correcto'"` → se re-alinea con el
  audio y queda como prueba permanente. También: "cortó la palabra al final", "ahí habla el periodista".
- Después de cualquier corrección o cambio de código: `PY regress.py --fast` tiene que dar todo OK; antes de dar por buena una
  tanda grande: `PY regress.py` (completo).

## 7b. Versiones del código (git) y otra PC
- El código vive en git (rama main) y en el repositorio PRIVADO https://github.com/ss20alt/AULS. Cada mejora: `git add` de
  los archivos tocados + `git commit -m "qué cambió y por qué"` + `git push`. Antes de tocar algo grande, `git status`.
- Volver atrás: `git log --oneline` y `git revert <código>` (nunca borrar historia).
- NUNCA al repositorio: videos, sources/, projects/, modelos ni huellas de voz/cara (están en .gitignore; revisar antes de
  agregar archivos nuevos que no sean código). Otra PC: README.md.
- Pruebas por área: tests/pruebas_<area>.py con `pruebas(check)`; regress.py las carga solas.

## 8. Si algo falla
- `doctor.py` primero. Errores de ffmpeg con un video raro: el estudio reintenta sin decodificación por hardware.
- Mac lenta: enchufada, sin modo de bajo consumo; la MacBook Air baja la velocidad si se calienta (avisar en renders largos).
- Bitácora completa de decisiones y lecciones: `STUDIO_LOG.md` (§3m = formato reunión).
- Privacidad: este paquete tiene la huella de voz y de cara de Lilian (`clients/lilian_voiceprint.npy`, `lilian_faceprint.npy`)
  y su material: es solo para su equipo; no subirlo a lugares públicos.
