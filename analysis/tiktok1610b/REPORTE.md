# Segunda tanda de referencias editadas (37 TikToks, oct. 2026) — análisis de estructura y escenarios
Carpeta: `C:\Users\acer\Videos\TIKTOKLILIAN` (los descargados el 16/10 desde las 9:00). Herramientas:
`python analyze_batch.py refs <carpeta> tiktok1610b --desde "2026-10-16 09:00" --prefijo N` · `_tiras.py tiktok1610b`
(TIRAS_01…10.jpg: 10 fotogramas por video) · `_measure_refs.py tiktok1610b`.

## Escenarios (cuántos de 37)
| escenario | videos | cómo lo editan |
|---|---|---|
| Rueda de prensa / declaración en el Congreso (escudo, micrófonos) | 17 (N06 N09 N10 N12 N14 N15 N16 N18 N21 N22 N24 N26 N27 N28 N31 N34 + N08) | casi toda la declaración en UNA toma, 1–3 min, subtítulo único, tarjeta final; a veces un inserto (captura de noticia, tabla) |
| Sesión del Senado (señal de TV) | 7 (N02 N03 N04 N05 N25 N29 N32) | recorte vertical de la señal conservando su franja inferior ("SESIÓN ORDINARIA / Lilian Samaniego"); N32 y N07 sobre fondo rosa; N05 se publicó horizontal entero |
| Reunión / mesa de trabajo | 3 (N07 N11 N23) | plano general + planos de ella; varias personas |
| Cobertura con varias personas | 3 (N12 N27 N37) | ella + dirigentes / expositores con PLACA DE NOMBRE (N27 recuadro blanco, N37 franja verde) |
| Evento / homenaje / acto | 4 (N01 N17 N19 N35) | cortes rápidos (12–23/min), público, música; N17 abre con nota de diario |
| Vida personal / cocina / feria | 4 (N13 N20 N33 N36) | cámara en mano, música, subtítulo en caja negra (N13) |

## Estructura que se repite
- **Duración**: la declaración entera — mediana ≈ 120 s, de 41 a 346 s. No cortan a 1 minuto.
- **Apertura**: 6 de 37 repiten al inicio la frase fuerte (N03 N04 N05 N07 N21 N34), EN COLOR (0 de 37 en blanco y negro). El resto
  arranca directo con la primera frase de la declaración.
- **Cierre**: tarjeta final blanca 2.8–3.4 s en 30 de 37 (los 7 sin tarjeta son publicaciones casi en bruto).
- **Subtítulo**: centro a 0.641 del alto (mediana, igual que la 1.ª tanda); variantes en mayúsculas con caja/amarillo (N14 N24 N28).
- **Sello de redes arriba a la derecha**: 15 de 37 (en la 1.ª tanda, más reciente, 2 de 18: lo están dejando).
- **Música**: 31 de 37, ≈ 16 dB bajo la voz. Volumen mediano −16.2 LUFS.
- **Insertos de contexto** (6): nota de diario (N04, N17), captura de un posteo de un diario (N15), tarjetas con cifras sobre
  fondo violeta con círculo marcando el dato (N18), tabla/documento con acercamiento (N25), infografía (N26). Aparecen cuando
  ella nombra el tema; su voz sigue.

## Lo que se agregó al autoeditor por esta tanda
- `--angle completo`: la declaración entera en orden real, sin gancho (hasta 6 min). Prueba BCP: 5:57, sin hallazgos.
- `--gancho bn|color|no` en el estilo redes (la 1.ª tanda usaba B/N; esta, color o nada).
- `--insertos <carpeta>`: noticias, documentos, tablas e infografías a pantalla completa cuando ella dice el nombre del archivo
  (o la frase de `insertos.json`), con acercamiento lento, su voz y subtítulo encima.
- `entender.py`: la tarjeta final blanca = "ya editado" (ningún bruto termina en blanco); recorrida vertical con varias voces =
  evento. En los 37 nunca vistos acertó 30 (81 %) antes de ajustar; 71/71 después (con estos mismos).
