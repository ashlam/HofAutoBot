FROM python:3.9-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        tesseract-ocr \
        tesseract-ocr-eng \
        fonts-liberation \
        libnss3 \
        libxss1 \
        libasound2 \
        libxshmfence1 \
        libgbm1 \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TESSERACT_PATH=/usr/bin/tesseract \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    WDM_LOCAL=1

WORKDIR /app

COPY requirements.txt ./
RUN sed -i '/^PyQt5/d' requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/
COPY configs/ ./configs/

RUN mkdir -p /app/logs /app/source_codes

VOLUME ["/app/configs", "/app/logs", "/app/source_codes"]

ENTRYPOINT ["python", "-u", "scripts/start_up_cli.py"]
CMD ["--server-id", "1"]
