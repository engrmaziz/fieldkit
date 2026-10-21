FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for OpenCV and video stream handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY services/vision-edge/ services/vision-edge/

RUN uv sync --package fieldkit-vision-edge

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8005

CMD ["uvicorn", "fieldkit_vision.main:app", "--host", "0.0.0.0", "--port", "8005"]
