FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y \
    git \
    jq \
    p7zip-full \
    libjpeg-dev \
    libpng-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone --depth 1 https://github.com/ciromattia/kcc.git /opt/kcc \
    && python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r /opt/kcc/requirements.txt \
    && ln -s /opt/kcc/kcc-c2e.py /usr/local/bin/kcc-c2e \
    && chmod +x /opt/kcc/kcc-c2e.py /usr/local/bin/kcc-c2e \
    && python -m pip install --no-cache-dir flask dropbox

COPY run.sh /run.sh
COPY app.py /app.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
