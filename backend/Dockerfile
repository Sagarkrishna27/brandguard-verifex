FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-kan \
    tesseract-ocr-tam \
    tesseract-ocr-tel \
    tesseract-ocr-mal \
    tesseract-ocr-ben \
    tesseract-ocr-guj \
    tesseract-ocr-mar \
    tesseract-ocr-pan \
    tesseract-ocr-ori \
    tesseract-ocr-asm \
    tesseract-ocr-urd \
    tesseract-ocr-san \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
