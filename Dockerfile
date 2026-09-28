# ==============================================================================
# 🛡️ SonicSentinel AI — Production Railway Dockerfile
# ==============================================================================
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install essential OS dependencies for audio DSP (libsndfile, ffmpeg) and builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy application source code
COPY . .

# Ensure upload and runtime directories exist with correct permissions
RUN mkdir -p /app/uploads /app/src/models/saved_models /app/src/models/gtm_files

# Install uvicorn wrapper to handle unexpanded ${PORT...} if invoked directly by platform
RUN cp /app/uvicorn_wrapper.py /usr/local/bin/uvicorn && \
    chmod +x /usr/local/bin/uvicorn /app/entrypoint.sh

ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "run.py"]
