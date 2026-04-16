#!/bin/bash
# Quick Suite Starter Kit — Cost estimation
#
# Usage:
#   ./cost.sh    # Estimate costs for selected modules
set -euo pipefail

python3 core/utils/orchestrator.py cost
