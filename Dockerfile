# Cloud Run image
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PORT=8080
WORKDIR /srv
# ffmpeg turns phone voice notes (m4a, amr, 3gp, webm) into WAV, which Gemini can read.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app app
COPY data data
COPY web web
RUN useradd --system --uid 10001 govi && chown -R govi /srv
USER govi
# One worker: the Firestore store keeps a write-through cache in memory, so run a single instance.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'
