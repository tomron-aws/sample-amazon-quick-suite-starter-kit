#!/bin/bash
# Quick Suite Starter Kit — Bootstrap
# Validates prerequisites, pulls external accelerators, and validates the manifest.
#
# Usage:
#   ./bootstrap.sh           # Run before deploy.sh (or deploy.sh calls it automatically)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

echo "=== Quick Suite Starter Kit — Bootstrap ==="
echo ""

# ------------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------------
echo "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || fail "python3 is required but not found"
info "python3 $(python3 --version 2>&1 | awk '{print $2}')"

command -v node >/dev/null 2>&1 || fail "node is required but not found"
info "node $(node --version)"

command -v npx >/dev/null 2>&1 || fail "npx is required but not found"
info "npx available"

if ! python3 -c "import yaml" 2>/dev/null; then
  fail "PyYAML is required: pip install pyyaml"
fi
info "PyYAML installed"

# Check for optional tools based on what the manifest needs
MANIFEST="${SCRIPT_DIR}/manifest.yaml"
if [ ! -f "$MANIFEST" ]; then
  fail "manifest.yaml not found in ${SCRIPT_DIR}"
fi

# Detect if Terraform modules are in the manifest
if python3 -c "
import yaml, sys
m = yaml.safe_load(open('$MANIFEST'))
modules = m.get('modules', [])
for mod in modules:
    base = mod.split('@')[0]
    import pathlib
    cfg = pathlib.Path(base) / 'config.yaml'
    if cfg.exists():
        c = yaml.safe_load(cfg.read_text())
        if c.get('iac_type') == 'terraform':
            sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
  command -v terraform >/dev/null 2>&1 || warn "Terraform modules in manifest but 'terraform' not found in PATH"
fi

echo ""

# ------------------------------------------------------------------
# 2. Install Node dependencies if needed
# ------------------------------------------------------------------
if [ ! -d "node_modules" ]; then
  echo "Installing Node dependencies..."
  npm install --no-audit --no-fund
  info "Node dependencies installed"
else
  info "Node dependencies already installed"
fi

echo ""

# ------------------------------------------------------------------
# 3. Pull external accelerators (git subtree)
# ------------------------------------------------------------------
echo "Checking external accelerators..."

# Registry of known external accelerator repos.
# Add new accelerators here as: [module_path]="git_remote_url"
declare -A ACCELERATOR_REPOS
ACCELERATOR_REPOS=(
  ["use-case-accelerators/idp-accelerator"]="https://github.com/aws-samples/sample-idp-accelerator.git"
  ["use-case-accelerators/live-meeting-assistant"]="https://github.com/aws-samples/sample-live-meeting-assistant.git"
)

# Parse manifest for external accelerator modules
EXTERNAL_MODULES=$(python3 -c "
import yaml, pathlib
m = yaml.safe_load(open('${MANIFEST}'))
for mod in m.get('modules', []):
    base = mod.split('@')[0]
    cfg_path = pathlib.Path(base) / 'config.yaml'
    if cfg_path.exists():
        c = yaml.safe_load(cfg_path.read_text())
        if c.get('iac_type') == 'external':
            version = ''
            if '@' in mod:
                version = mod.split('@')[1]
            print(f'{base}|{version}')
" 2>/dev/null || true)

if [ -z "$EXTERNAL_MODULES" ]; then
  info "No external accelerators in manifest"
else
  while IFS='|' read -r mod_path version; do
    [ -z "$mod_path" ] && continue

    repo_url="${ACCELERATOR_REPOS[$mod_path]:-}"
    if [ -z "$repo_url" ]; then
      warn "No git remote configured for ${mod_path} — skipping subtree pull"
      continue
    fi

    # Determine the ref to pull (tag, branch, or default)
    ref="${version:-main}"

    if [ -d "${mod_path}/.git-subtree-marker" ] 2>/dev/null || \
       git log --oneline --all -- "${mod_path}" 2>/dev/null | head -1 | grep -q "subtree"; then
      echo "  Updating ${mod_path} (ref: ${ref})..."
      git subtree pull --prefix="${mod_path}" "${repo_url}" "${ref}" --squash -m "chore: update ${mod_path} to ${ref}" 2>/dev/null || \
        warn "Failed to update ${mod_path} — continuing with existing version"
    else
      if [ ! -f "${mod_path}/config.yaml" ]; then
        echo "  Pulling ${mod_path} (ref: ${ref})..."
        git subtree add --prefix="${mod_path}" "${repo_url}" "${ref}" --squash -m "chore: add ${mod_path} at ${ref}" 2>/dev/null || \
          warn "Failed to pull ${mod_path} — ensure the repo URL and ref are correct"
      else
        info "${mod_path} already present (local)"
      fi
    fi
  done <<< "$EXTERNAL_MODULES"
fi

echo ""

# ------------------------------------------------------------------
# 4. Validate manifest
# ------------------------------------------------------------------
echo "Validating manifest..."
python3 core/utils/orchestrator.py validate

echo ""
info "Bootstrap complete — ready to deploy"
