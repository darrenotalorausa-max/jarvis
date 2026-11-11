#!/usr/bin/env bash
# Doomsday · lanzador para macOS y Linux (puerto 8766, datos en doomsday_home/). Ctrl+C para detener. Con --app se abre en ventana propia.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist-doomsday/doomsday.html ]; then ./scripts/setup.sh; fi
cd backend
exec ../.venv/bin/python -m doomsday.launch "$@"
