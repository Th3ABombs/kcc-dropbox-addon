FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /opt

# jq serve a run.sh, p7zip-full serve a KCC per gli archivi CBR/CB7: restano.
# git, build-essential e python3-dev servono solo durante la build e vengono
# rimossi nello stesso layer: un purge in un RUN successivo non ridurrebbe la
# dimensione finale dell'immagine.
# libjpeg-dev e libpng-dev restano di proposito: sono pochi KB e tengono
# installate le librerie runtime corrette senza doverne fissare il nome, che
# cambia tra le release di Debian.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        jq \
        p7zip-full \
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
