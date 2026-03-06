#!/bin/sh
exec python -m uvicorn au_grants_agent.api:app --host 0.0.0.0 --port ${PORT:-8000}
