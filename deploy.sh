#!/bin/bash
# Quick Suite Starter Kit — Single deploy entry point
# Reads manifest.yaml and dispatches to the appropriate IaC engines.
set -euo pipefail

echo "=== Quick Suite Starter Kit Deploy ==="
python3 core/utils/orchestrator.py deploy
