FROM ghcr.io/ciromattia/kcc:latest

USER root

RUN if command -v apk >/dev/null 2>&1; then \
      apk add --no-cache jq python3 py3-pip; \
    elif command -v apt-get >/dev/null 2>&1; then \
      apt-get update && apt-get install -y jq python3 python3-pip && rm -rf /var/lib/apt/lists/*; \
    else \
      echo "No supported package manager found"; exit 1; \
    fi

RUN python3 -m pip install --no-cache-dir flask dropbox

COPY run.sh /run.sh
COPY app.py /app.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
