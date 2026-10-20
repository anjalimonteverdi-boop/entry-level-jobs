#!/usr/bin/env bash
# Runs the daily job update. Used by cron (see README).
# Optional: put USAJOBS_API_KEY and USAJOBS_EMAIL in a file named .env next to
# this project's README and they'll be loaded here.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -d .venv ]; then . .venv/bin/activate; fi
python3 -m jobagent.run >> logs/cron.log 2>&1
