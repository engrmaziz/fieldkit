FROM python:3.12-slim

WORKDIR /app

# Install system dependencies: tesseract-ocr, German traineddata, poppler-utils, and libgl for opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY services/docai/ services/docai/

RUN uv sync --package fieldkit-docai

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8004

CMD ["uvicorn", "fieldkit_docai.main:app", "--host", "0.0.0.0", "--port", "8004"]
