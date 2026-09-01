FROM python:3.14-slim@sha256:656d12e70054d5fda18a045e2494c96701e9792dd1445f95b3d038df954f57e9

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data

RUN python -m pip install --no-cache-dir . \
    && mkdir -p /app/var

ENV EXECUTION_MONITOR_ALLOW_CONTAINER_BIND=1
EXPOSE 8765

CMD ["execution-monitor", "serve", "--host", "0.0.0.0", "--port", "8765", "--db", "/app/var/demo.db", "--venue-state", "/app/var/demo-venue.json"]
