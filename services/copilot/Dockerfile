FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY services/mock-erp/ services/mock-erp/
COPY services/copilot/ services/copilot/

RUN uv sync --package fieldkit-copilot

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8003

CMD ["uvicorn", "fieldkit_copilot.api:app", "--host", "0.0.0.0", "--port", "8003"]
