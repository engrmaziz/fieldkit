FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy workspace configuration and dependencies
COPY pyproject.toml /app/
COPY packages/common /app/packages/common
COPY packages/llm /app/packages/llm
COPY services/hello /app/services/hello

# Install workspace
RUN uv pip install --system -e /app/packages/common -e /app/packages/llm -e /app/services/hello

EXPOSE 8000

CMD ["uvicorn", "fieldkit_hello.main:app", "--host", "0.0.0.0", "--port", "8000"]
