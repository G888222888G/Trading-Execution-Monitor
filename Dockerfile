FROM python:3.12-slim@sha256:e5c9fa26ffb76e11e0f054f30dc2523a2f9693f0c36c0cf1e39b27e152d899fc

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data

RUN python -m pip install --no-cache-dir . \
    && mkdir -p /app/var

ENV EXECUTION_MONITOR_ALLOW_CONTAINER_BIND=1
EXPOSE 8765

CMD ["execution-monitor", "serve", "--host", "0.0.0.0", "--port", "8765", "--db", "/app/var/demo.db", "--venue-state", "/app/var/demo-venue.json"]
