#!/usr/bin/env bash
# Jarvis OS · lanzador para macOS y Linux. Ctrl+C para detener. Con --app se abre en ventana propia.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist/index.html ]; then ./scripts/setup.sh; fi
cd backend
exec ../.venv/bin/python -m jarvis.launch "$@"
