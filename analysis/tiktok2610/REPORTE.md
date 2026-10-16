# Referencias editadas del equipo (TikTok de Lilian, oct. 2026) — análisis
Carpeta: `C:\Users\acer\Videos\TIKTOKLILIAN` (18 videos, 26.8 min). Herramienta: `python analyze_batch.py refs <carpeta> tiktok2610`
(ADN por video `Txx.json`, transcripción `Txx_words.json`, hoja grande `Txx_sheet.jpg`) + `_measure_refs.py` → `measures.json`.

## Lo que hacen SIEMPRE (la "casa")
| rasgo | medida | en cuántas |
|---|---|---|
| tarjeta final blanca con íconos rojos (fb, ig, X, tiktok, whatsapp) + /LILIANSAMANIEGOPY | 3.0–3.1 s | 18/18 |
| subtítulo único: blanco, negrita, contorno negro, 2–4 palabras, una línea, centrado | centro a 0.641 del alto (y≈1231 en 1920) | 14/18 |
| variante: MAYÚSCULAS cursiva negrita en 2 líneas, palabras clave en caja roja / revelado karaoke | centro a 0.80 del alto | 2/18 (T14, T17) |
| música de fondo bajo la voz, sigue en la tarjeta final | ≈ 15–20 dB bajo la voz | 16/18 |
| volumen final (grabación propia) | −12 a −14 LUFS | — |
| cara (mediana) | centro a 0.32 del alto, alto de cara 0.19 | — |
| color | natural: brillo 131, saturación 54 (más claro y menos saturado que las referencias viejas) | — |
| sin placa de nombre (en material propio) | — | 18/18 |
| sello de redes arriba a la derecha durante el video | — | 2/18 |

## Recursos que usan según el contenido
- **Gancho en BLANCO Y NEGRO** (7/18; T03 T04 T05 T09 T10 T11 T15): 1.5–4 s. En 5 de 7 es la FRASE FUERTE de más adelante
  repetida al principio; entra al color con un barrido desenfocado (T03 5.4 s).
- **Datos en pantalla sincronizados con la voz** (T02, T04, T10): infografía propia (258 feminicidios, 37.825 denuncias, 69 hijos
  huérfanos, 20 en 2026) a pantalla completa con acercamiento a CADA cifra cuando ella la dice, o la infografía fija en la mitad
  de abajo mientras habla (T10, pantalla dividida).
- **Toma del documento** (T04, T05): ella muestra el proyecto de ley; plano del papel y de la firma.
- **Reposteos de TV/radio** (T02, T10, T13): se respeta el zócalo del canal; T13 apila presentador abajo / ella arriba;
  ritmo rápido (15 cortes/min) con primeros planos.
- **Sesión del Senado** (T15, T16): la señal horizontal centrada sobre un fondo de color liso (rosa = octubre rosa) con franjas
  arriba/abajo; acercamientos para romper la toma única de 2–3 min.
- **Saltos de toma alternando plano abierto / cerrado** (T07, T17): mensaje a cámara.
- **Discurso con tomas de apoyo del público** (T01): la voz sigue sobre planos de la gente; la frase clave ("…seré la próxima
  presidenta…") con cortes rápidos y palabras grandes sobre negro; cierra con testimonios de militantes.
- **Recorrida / vida personal** (T08 peluquería, T09 Caacupé, T18 misa): música más presente, título manuscrito ("DÍA DE PELU",
  "CAACUPÉ" en pincel), subtítulos en cursiva de color (violeta / azul), stickers (destellos, corazones), fotos en tarjetas
  sobre fondo violeta con franjas, marco de visor de cámara, barridos desenfocados; guaraní subtitulado tal cual.

## Duración
35–198 s (mediana ≈ 80 s). NO usan duraciones exactas de 1/2/3/4 min: toman la declaración entera o el tramo completo.

## Brutos nuevos (`C:\Users\acer\Desktop\lilianclaude\skill\VIDEOSCRUDOLILIAN`, análisis en `analysis/crudos2610`)
- Las exportaciones del DJI vienen **anamórficas**: 9:16 guardado en 1728×1080 / 1080×1080 / 1280×720 (SAR 45:128 · 9:16 ·
  81:256) → imagen real 608×1080 o 405×720 (baja: se verá blanda). Sin el arreglo de `ingest.probe` se trataban como horizontales.
  El DJI original (B01, 1512×2688 HEVC 10 bits) tiene 4 veces más detalle: pedir los archivos originales.
- B02 (11:18): discurso entero de Lilian en un acto de Causa Republicana (Encarnación, dic. 2025), cámara fija → formato
  CONFERENCIA/discurso (`ingest.py`). Baja resolución (405×720).
- B01, B03, B05–B09, B11–B13: tomas de eventos (saludos, público, mesa principal, cumpleaños, fotos) sin que ella hable o con
  la voz del animador → material para un formato RECORRIDA/EVENTO con música (como T08/T09/T18). B04, B10: momentos cortos
  donde ella habla. "Dji … 0020 D (1).mp4" es copia idéntica de "… 0020 D.mp4".
- Ninguno de los brutos es la fuente de las referencias (no comparten frases): son material nuevo.
