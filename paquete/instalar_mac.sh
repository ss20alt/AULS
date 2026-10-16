#!/bin/bash
# Instalación del Autoeditor de Lilian en una Mac con Apple Silicon (M1/M2/M3/M4).
# Uso: abrir Terminal en esta carpeta y ejecutar:  bash instalar_mac.sh
# Instala (si faltan) Homebrew, ffmpeg y Python 3.12; crea el entorno, instala librerías, descarga los modelos (~4.6 GB) y corre el autochequeo.
set -e
cd "$(dirname "$0")/studio"
echo "== Autoeditor de Lilian — instalación"
if [ "$(uname -m)" != "arm64" ]; then echo "AVISO: esta Mac no es Apple Silicon; funcionará pero muy lento."; fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Falta Homebrew. Instalalo con el comando de https://brew.sh y volvé a correr este script."; exit 1
fi
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
PY="$(brew --prefix python@3.12)/bin/python3.12"
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
if ! pip install -r requirements.txt; then
  echo "Alguna versión exacta no está para esta Mac: instalando las últimas compatibles"
  pip install -r requirements-libre.txt
fi
echo "== modelos (una sola vez)"
python models/download_models.py
echo "== autochequeo"
python doctor.py || true
echo ""
echo "Listo. Informe: studio/tests/doctor_informe.txt"
echo "Para editar: abrí Claude Code en la carpeta AutoeditorLilian y pedile lo que necesites (usa la skill autoeditor-lilian)."
