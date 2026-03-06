FROM python:3.11-slim AS base

WORKDIR /app

# System deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e ".[all]" 2>/dev/null || pip install --no-cache-dir -e .

# Create data dir
RUN mkdir -p data profiles proposals

# Copy profiles if they exist
COPY profiles/ profiles/ 2>/dev/null || true

EXPOSE 8501

# Default: CLI mode
ENTRYPOINT ["au-grants"]
CMD ["--help"]
