FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV QT_QPA_PLATFORM=offscreen

WORKDIR /opt

# jq serve a run.sh, p7zip-full serve a KCC per gli archivi CBR/CB7.
# libglib2.0-0, libgl1, libegl1, libdbus-1-3, libfontconfig1 e libx* servono al runtime Qt di PySide6 (usato da KCC).
# libjpeg-dev e libpng-dev tengono installate le librerie runtime grafiche.
# git, build-essential e python3-dev servono solo durante la build e vengono
# rimossi nello stesso layer: un purge in un RUN successivo non ridurrebbe la
# dimensione finale dell'immagine.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        jq \
        p7zip-full \
        libglib2.0-0 \
        libgl1 \
        libegl1 \
        libdbus-1-3 \
        libfontconfig1 \
        libxext6 \
        libxrender1 \
        libxi6 \
        libjpeg-dev \
        libpng-dev \
        git \
        build-essential \
        python3-dev; \
    git clone --depth 1 https://github.com/ciromattia/kcc.git /opt/kcc; \
    python -m pip install --upgrade pip; \
    python -m pip install --no-cache-dir -r /opt/kcc/requirements.txt; \
    python -m pip install --no-cache-dir flask dropbox requests; \
    ln -s /opt/kcc/kcc-c2e.py /usr/local/bin/kcc-c2e; \
    chmod +x /opt/kcc/kcc-c2e.py /usr/local/bin/kcc-c2e; \
    rm -rf /opt/kcc/.git; \
    apt-get purge -y --auto-remove git build-essential python3-dev; \
    rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

COPY run.sh /run.sh
COPY app.py /app.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
