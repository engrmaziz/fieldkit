FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY services/mock-erp/ services/mock-erp/

RUN uv sync --package fieldkit-mock-erp

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8007

CMD ["uvicorn", "fieldkit_mock_erp.main:app", "--host", "0.0.0.0", "--port", "8007"]
