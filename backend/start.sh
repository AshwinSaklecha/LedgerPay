#!/usr/bin/env bash
set -e

# Start the webhook worker in the background.
# This runs alongside the API in the same container (free-tier deployment).
# In a production setup, this would be a separate Render Background Worker
# or a dedicated process managed by a supervisor like systemd or Kubernetes.
python -m app.worker.webhook_worker &

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
