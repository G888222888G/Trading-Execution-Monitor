FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data

RUN python -m pip install --no-cache-dir . \
    && mkdir -p /app/var

ENV EXECUTION_MONITOR_ALLOW_CONTAINER_BIND=1
EXPOSE 8765

CMD ["execution-monitor", "serve", "--host", "0.0.0.0", "--port", "8765", "--db", "/app/var/demo.db", "--venue-state", "/app/var/demo-venue.json"]
