#!/bin/sh
set -e

# If the command is uvicorn with broken or literal ${PORT...}, redirect to python run.py
if [ "$1" = "uvicorn" ]; then
    echo "[*] SonicSentinel AI: Intercepted uvicorn start command. Forwarding to python run.py (PORT=${PORT:-8000})..."
    exec python run.py
fi

exec "$@"
