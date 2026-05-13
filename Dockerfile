FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY api_service.py candidate_store.py resume_parser.py ./

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api_service:app --host 0.0.0.0 --port ${PORT:-8000}"]
