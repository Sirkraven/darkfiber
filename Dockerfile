# DarkFiber (C3): one image, two services (see docker-compose.yml) --
# `darkfiber-pipeline` (continuous ingestion) and `darkfiber-dashboard`
# (operator UI). Built from the same package so both always see the same
# code; docker-compose picks the command per service.
FROM python:3.11-slim

# curl: used by the pipeline service's own HEALTHCHECK below (no extra
# runtime dependency pulled into the Python image -- it's a standard
# Debian package, not a pip install).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

# h5: real DAS files are HDF5 (QuakeFlow convention). ops: installation.yaml
# parsing. dashboard: the Streamlit operator UI (C2). No dev/test extras --
# this is a runtime image, not a CI image.
RUN pip install --no-cache-dir ".[h5,ops,dashboard]"

# Populated by a bind mount or volume at run time (see docker-compose.yml):
# installation.yaml, the source data files, the SQLite ledger, logs, backups.
RUN mkdir -p /data
WORKDIR /data

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

ENTRYPOINT []
CMD ["darkfiber-pipeline", "--config", "/data/installation.yaml"]
