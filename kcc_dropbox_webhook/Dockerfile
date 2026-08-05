FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git \
    jq \
    p7zip-full \
    libpng-dev \
    libjpeg-dev \
    python3-dev \
    python3-pyqt5 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN git clone --depth 1 https://github.com/ciromattia/kcc.git /opt/kcc \
    && python3 -m pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir -r /opt/kcc/requirements.txt \
    && python3 -m pip install --no-cache-dir flask dropbox

COPY run.sh /run.sh
COPY app.py /app.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
