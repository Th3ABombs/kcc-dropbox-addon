FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    jq \
    && pip install --no-cache-dir kcc flask dropbox \
    && rm -rf /var/lib/apt/lists/*

COPY run.sh /run.sh
COPY app.py /app.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
