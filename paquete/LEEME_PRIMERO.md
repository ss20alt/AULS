# Autoeditor de Lilian Samaniego — para el equipo

Este paquete es el autoeditor completo: toma una grabación en bruto de Lilian y arma videos verticales para redes, con control de
calidad automático. Se usa conversando con **Claude Code** (que ya sabe cómo operarlo gracias a la skill que viene incluida).

## Qué hace
- **Conferencias / declaraciones** de Lilian → videos de 1, 2, 3 o 4 minutos en 15 estilos.
- **Reuniones** (video horizontal con varias personas, p. ej. Lilian presenta a quienes se suman) → video vertical informativo
  donde cada persona termina su idea, con placa de nombre y cargo, titular abajo y subtítulos.

## Qué necesitás
- Una Mac con Apple Silicon (MacBook Air M3 está bien). Ideal 16 GB de memoria; con 8 GB funciona pero más justo.
  (También corre en Windows con placa NVIDIA: es la máquina original; ahí no se usa `instalar_mac.sh`.)
- ~12 GB libres (paquete + modelos) y conexión a internet la primera vez.
- Claude Code instalado (https://claude.com/claude-code).

## Instalación (una sola vez, ≈ 20–40 min según internet)
1. Copiá la carpeta `AutoeditorLilian` donde quieras (por ejemplo en Documentos).
2. Abrí la app Terminal, entrá a la carpeta y ejecutá:
   ```
   cd ~/Documents/AutoeditorLilian
   bash instalar_mac.sh
   ```
3. Al final tiene que decir **LISTO: funciona igual que en la máquina original**.
   Si dice **HAY PROBLEMAS**, mandale a quien te pasó el paquete el archivo `studio/tests/doctor_informe.txt`
   (y la carpeta `studio/tests/diferencias/` si existe).

## Uso diario
1. Abrí Claude Code en la carpeta `AutoeditorLilian`:
   ```
   cd ~/Documents/AutoeditorLilian
   claude
   ```
2. Pedile en tus palabras, por ejemplo:
   - "Ingresá este video nuevo: ~/Downloads/IMG_5001.MOV, es sobre el presupuesto de salud"
   - "Haceme un video de 1 minuto estilo karaoke sobre la respuesta a Leite"
   - "Hacé 3 variaciones de 3 minutos y verificá cada una"
   - "En el video de recién, en el 0:43 dice 'trató', no 'trato'"
   - "Ingresá esta reunión: ~/Downloads/IMG_4801.MOV. Quiero 1:30: que Lilian presente y después hablen los dos invitados"
3. Los videos terminados quedan en **Descargas** (más una versión liviana para WhatsApp).

## Primera prueba recomendada
Pedile a Claude: *"Hacé un video de 1 minuto estilo noticiero con el ángulo calma de la conferencia del Banco Central"*.
Así confirmás que todo anda antes de usarlo con material nuevo.

## Cuidado
Este paquete contiene la huella de voz y material de Lilian: es solo para su equipo. No lo subas a lugares públicos.
