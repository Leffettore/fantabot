#!/usr/bin/env bash
# Weekly lineup run, started by fantabot-matchday.timer. Arms the submit; FANTABOT_AUTO_ACT
# must also be true in .env or this stays a dry run.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
export PYTHONIOENCODING=utf-8 COLUMNS=160
exec .venv/bin/fantabot lineup submit-all --arm --refresh >> "logs/matchday-$(date +%F).log" 2>&1
