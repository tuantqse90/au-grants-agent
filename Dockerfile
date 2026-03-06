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

# Copy profiles and templates if they exist
COPY profiles/ profiles/ 2>/dev/null || true
COPY templates/ templates/ 2>/dev/null || true

# Init DB on build
RUN au-grants init || true

EXPOSE 8000 8501

# Default: API server
CMD ["python", "-m", "uvicorn", "au_grants_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
