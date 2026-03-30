#!/bin/bash
# ST Records Feedback Loop Orchestration
#
# Runs the full feedback cycle:
# 1. Sky-Lynx analyzes outcomes + usage data
# 2. Persona upgrader processes new recommendations
# 3. Report loop status
#
# Usage:
#   ./scripts/run_loop.sh              # Full loop
#   ./scripts/run_loop.sh --dry-run    # Dry run (no API calls, no patches)

set -euo pipefail

# Source shared env for cron context (API keys, PATH, etc.)
if [[ -f "$HOME/.env.shared" ]]; then
    set -a
    source "$HOME/.env.shared"
    set +a
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNOW_TOWN_DIR="$(dirname "$SCRIPT_DIR")"
SKY_LYNX_DIR="$HOME/projects/sky-lynx"

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
fi

echo "============================================================"
echo "  ST Records Feedback Loop"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# Step 1: Run Sky-Lynx analyzer
echo ""
echo ">>> Step 1: Sky-Lynx Analysis"
echo "------------------------------------------------------------"
cd "$SKY_LYNX_DIR"
source .venv/bin/activate
python -m sky_lynx.analyzer --no-pr $DRY_RUN
deactivate 2>/dev/null || true

# Step 2: Run persona upgrader
echo ""
echo ">>> Step 2: Persona Upgrade Engine"
echo "------------------------------------------------------------"
cd "$SNOW_TOWN_DIR"
source .venv/bin/activate
python scripts/persona_upgrader.py $DRY_RUN

# Step 3: Report status
echo ""
echo ">>> Step 3: Loop Status"
echo "------------------------------------------------------------"
python scripts/loop_status.py

echo ""
echo "ST Records feedback loop complete at $(date '+%Y-%m-%d %H:%M:%S')"
