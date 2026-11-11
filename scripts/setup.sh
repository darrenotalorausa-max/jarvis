#!/usr/bin/env bash
# Jarvis OS · preparación idempotente para macOS y Linux. No requiere privilegios de administrador.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "=== Jarvis OS: preparación ==="

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" scripts/check_python.py >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "[FALTA] Python 3.11 o superior. Instálalo desde https://www.python.org/downloads/ o con el gestor de paquetes de tu sistema."
  exit 1
fi
"$PY" scripts/check_python.py
[ -x .venv/bin/python ] || { echo "Creando el entorno de Python en .venv …"; "$PY" -m venv .venv; }
echo "Instalando dependencias de Python (backend/requirements.lock) …"
.venv/bin/python -m pip install --disable-pip-version-check -q -r backend/requirements.lock
.venv/bin/python -m pip install --disable-pip-version-check -q -r backend/requirements-desktop.txt || echo "Ventana de aplicación no disponible: Jarvis se abrirá en el navegador."

if [ "${1:-}" = "rebuild" ] || [ ! -f frontend/dist/index.html ]; then
  if ! command -v node >/dev/null 2>&1 || ! node scripts/check_node.cjs; then
    echo "[FALTA] Node.js 18 o superior, necesario una sola vez para compilar la interfaz: https://nodejs.org/"
    exit 1
  fi
  echo "Instalando dependencias y compilando la interfaz …"
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi

if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  echo "FFmpeg encontrado."
else
  echo "[AVISO] FFmpeg no está en el PATH: el Editor audiovisual no podrá leer ni exportar video."
  echo "        macOS: brew install ffmpeg · Debian/Ubuntu: sudo apt install ffmpeg · https://ffmpeg.org/download.html"
fi
echo "Preparación completada. Inicia Jarvis con ./scripts/start.sh"
