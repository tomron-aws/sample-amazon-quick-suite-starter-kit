#!/bin/bash
# Quick Suite Starter Kit — Deploy entry point
#
# Usage:
#   ./deploy.sh                  # Generate + apply (prompts for approval)
#   ./deploy.sh --auto-approve   # Generate + apply (CI mode, no prompts)
#   ./deploy.sh generate         # Generate only — produces Terraform files
set -euo pipefail

echo "=== Quick Suite Starter Kit Deploy ==="

# Bootstrap (prerequisites, external accelerators, validation)
if [ "${SKIP_BOOTSTRAP:-0}" != "1" ]; then
  ./bootstrap.sh
  echo ""
fi

# If "generate" is passed, just generate and exit
if [ "${1:-}" = "generate" ]; then
  python3 core/utils/orchestrator.py generate
  exit 0
fi

# Otherwise: generate + apply
python3 core/utils/orchestrator.py deploy "$@"
