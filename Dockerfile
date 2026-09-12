FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    ENV_FILE=/app/.env \
    M3U_FILE=/data/eventos.m3u \
    XML_FILE=/data/eventos.xml \
    TV_EVENTS_FILE=/data/eventos.json \
    FUTBOL_LIBRE_URL_FILE=/data/futbol_libre_urls.env \
    PROGRESS_FILE=/data/.update-futbollibre.progress.json \
    CHROME_BINARY=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver ca-certificates bash procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY server.sh update-futbollibre.sh update-futbol-libre-sites.sh config.sh .env.example ./
COPY output ./output
COPY installers ./installers

RUN mkdir -p /data \
    && chmod +x server.sh update-futbollibre.sh update-futbol-libre-sites.sh \
    && chmod +x /app/installers/*.sh /app/installers/*.command

EXPOSE 8080 45678/udp

CMD ["python", "-m", "server.api_service"]
