#!/bin/bash
# Quick Suite Starter Kit — Check deployment status and drift
#
# Usage:
#   ./status.sh    # Check all modules for drift
set -euo pipefail

echo "=== Quick Suite Starter Kit — Status Check ==="
echo ""
python3 core/utils/orchestrator.py status
