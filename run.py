# ==============================================================================
# 🛡️ SonicSentinel AI — Production Server Starter (run.py)
# Handles dynamic $PORT on Railway, Render, Docker, and Cloud environments safely.
# ==============================================================================
import os
import sys
import uvicorn

if __name__ == "__main__":
    port_env = os.environ.get("PORT", "8000").strip()
    try:
        port = int(port_env)
    except (ValueError, TypeError):
        port = 8000

    host = os.environ.get("HOST", "0.0.0.0").strip()
    print(f"[*] Starting SonicSentinel AI on {host}:{port} (PORT={port_env})...")
    sys.stdout.flush()
    uvicorn.run("app:app", host=host, port=port, log_level="info")
