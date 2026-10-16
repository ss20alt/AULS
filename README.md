# Autoeditor de Lilian Samaniego

Estudio de edición automática: entiende cada video (declaración, Senado/TV, reunión, evento), lo edita en vertical con la
marca y lo controla antes de entregarlo. Bitácora completa de decisiones y pruebas: `STUDIO_LOG.md`. Guía para Claude: `paquete/SKILL.md`.

## Qué hay en este repositorio y qué NO

| Está acá (código) | NO está (se consigue aparte) |
|---|---|
| todo el código `.py`, estilos, reglas, pruebas chicas | videos de trabajo (`projects/`, `sources/`): decenas de GB |
| fuentes Montserrat, sonidos, piezas del logo de Causa Republicana | modelos de IA (`models/`): se bajan con un comando |
| análisis de las referencias (JSON), skill y guías | **huellas de voz y cara** (`clients/*.npy`, `clients/lilian_people/`): datos biométricos, se pasan en privado |

## Instalar en otra PC (Windows con NVIDIA)

1. Instalar **Python 3.12** (python.org, marcar "Add to PATH"), **Git** (git-scm.com) y **ffmpeg** (`winget install Gyan.FFmpeg`).
2. Bajar el código:
   ```
   git clone <dirección del repositorio> lilinatest\studio
   cd lilinatest\studio
   ```
3. Librerías (torch con CUDA primero; esta PC usa CUDA 12.6):
   ```
   pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu126
   pip install -r requirements.txt
   ```
4. Modelos (una sola vez, ≈ 4.6 GB): `python models/download_models.py`
5. Huellas de Lilian: copiar a `clients/` los archivos `lilian_voiceprint.npy`, `lilian_voiceprint.json`,
   `lilian_faceprint.npy`, `lilian_faceprint.json` (desde el paquete del equipo o un Drive privado; no van al repositorio).
6. Autochequeo: `python doctor.py` y banco de pruebas `python regress.py --fast`.

Mac (Apple Silicon): el instalador `paquete/instalar_mac.sh` hace los pasos 3–6 (usa el paquete del equipo, que ya trae las huellas).

## Mantener las PCs al día

- En la PC donde se trabaja, cada cambio queda guardado: `git add -A` + `git commit -m "qué cambió"` + `git push`.
- En la otra PC: `git pull` (baja solo lo que cambió). Si algo se rompe: `git log` para ver los cambios y
  `git revert <código>` para deshacer uno.
- Los videos y fuentes NO viajan por git: se comparten por Drive (`videosclaudesubir`) o se vuelven a ingresar.
