#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run.sh — ISRO SOC Analytics Platform launcher
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtualenv if present
if [ -f ".venv/bin/activate" ]; then
    echo "→ Activating virtual environment..."
    source .venv/bin/activate
fi

# Create required directories
mkdir -p logs joblib_cache models/saved rules/uploaded

# Verify .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env not found — copying from .env.example"
    cp .env.example .env
    echo "   Please edit .env with your Elasticsearch credentials before proceeding."
fi

echo "→ Starting ISRO SOC Analytics Platform..."
streamlit run app.py \
    --server.headless false \
    --server.port 8501 \
    --browser.gatherUsageStats false \
    "$@"
