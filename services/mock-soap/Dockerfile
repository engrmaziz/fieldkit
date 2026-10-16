FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY services/mock-soap/ services/mock-soap/

RUN uv sync --package fieldkit-mock-soap

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8010

CMD ["uvicorn", "fieldkit_mock_soap.main:app", "--host", "0.0.0.0", "--port", "8010"]
