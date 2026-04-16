#!/bin/bash
# Quick Suite Starter Kit — Single deploy entry point
# Reads manifest.yaml and dispatches to the appropriate IaC engines.
#
# Usage:
#   ./deploy.sh                  # Interactive mode (default) — prompts for approval
#   ./deploy.sh --auto-approve   # CI mode — skips approval prompts
#   SKIP_BOOTSTRAP=1 ./deploy.sh # Skip bootstrap (if already run separately)
set -euo pipefail

echo "=== Quick Suite Starter Kit Deploy ==="

# 1. Bootstrap (prerequisites, external accelerators, validation)
if [ "${SKIP_BOOTSTRAP:-0}" != "1" ]; then
  ./bootstrap.sh
  echo ""
fi

# 2. Deploy
python3 core/utils/orchestrator.py deploy "$@"
