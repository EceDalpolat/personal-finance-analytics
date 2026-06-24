FROM python:3.13-slim

WORKDIR /app

# Runtime + test deps (kept explicit; mirrors pyproject dependencies).
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" pydantic-settings httpx asyncpg structlog \
    opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-asyncpg \
    opentelemetry-instrumentation-httpx \
    pytest pytest-asyncio

COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
