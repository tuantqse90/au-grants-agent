FROM python:3.11-slim AS base

WORKDIR /app

# System deps for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e ".[all]" 2>/dev/null || pip install --no-cache-dir -e .

# Create data dirs
RUN mkdir -p data profiles proposals templates

# Init DB on build
RUN au-grants init || true

COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000 8501

# Default: API server
CMD ["sh", "start.sh"]
