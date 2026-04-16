"""Orchestrator — reads manifest.yaml, validates modules, and dispatches to IaC engines."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from param_resolver import resolve_params
from deploy_targets import DeployTarget, resolve_target, validate_targets
from deploy_log import DeployLogger
from cost_estimator import print_cost_report

DEPLOY_STATE_FILE = ".deploy-state.json"

# --- Param type validators ---
# Each returns (is_valid, error_message).

_PARAM_VALIDATORS: dict[str, callable] = {}


def _register_validator(type_name: str):
    """Decorator to register a param type validator."""
    def decorator(fn):
        _PARAM_VALIDATORS[type_name] = fn
        return fn
    return decorator


@_register_validator("string")
def _validate_string(value: str, param: dict) -> tuple[bool, str]:
    if not isinstance(value, str) or not value:
        return False, "must be a non-empty string"
    pattern = param.get("pattern")
    if pattern and not re.match(pattern, value):
        return False, f"must match pattern: {pattern}"
    return True, ""


@_register_validator("arn")
def _validate_arn(value: str, param: dict) -> tuple[bool, str]:
    if not isinstance(value, str) or not value.startswith("arn:"):
        return False, "must be a valid ARN (arn:aws:...)"
    pattern = param.get("pattern")
    if pattern and not re.match(pattern, value):
        return False, f"must match pattern: {pattern}"
    return True, ""


@_register_validator("email")
def _validate_email(value: str, _param: dict) -> tuple[bool, str]:
    if not isinstance(value, str) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        return False, "must be a valid email address"
    return True, ""


@_register_validator("json")
def _validate_json(value: str, _param: dict) -> tuple[bool, str]:
    try:
        json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return False, "must be valid JSON"
    return True, ""


@_register_validator("aws_region")
def _validate_aws_region(value: str, _param: dict) -> tuple[bool, str]:
    if not isinstance(value, str) or not re.match(r"^[a-z]{2}-[a-z]+-\d+$", value):
        return False, "must be a valid AWS region (e.g. us-east-1)"
    return True, ""


def validate_param_value(param: dict, value: str) -> tuple[bool, str]:
    """Validate a single param value against its type and pattern."""
    param_type = param.get("type")
    if not param_type:
        return True, ""  # No type specified, skip validation
    validator = _PARAM_VALIDATORS.get(param_type)
    if not validator:
        return True, ""  # Unknown type, skip (forward-compatible)
    return validator(value, param)


def load_manifest(path: str = "manifest.yaml") -> dict:
    """Load and return the project manifest."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_module_config(module_path: str) -> dict:
    """Load a module's config.yaml."""
    # Strip version pin if present (e.g. "use-case-accelerators/idp@v1.0.0")
    base = module_path.split("@")[0]
    config_path = Path(base) / "config.yaml"
    if not config_path.exists():
        print(f"ERROR: Module config not found: {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def validate(manifest: dict) -> None:
    """Validate manifest: check all modules exist, required params are set, and values are valid."""
    errors = []
    params = manifest.get("params", {})

    # Validate global manifest params
    region = params.get("region")
    if region:
        is_valid, err_msg = validate_param_value({"type": "aws_region"}, str(region))
        if not is_valid:
            errors.append(f"Global param 'region': {err_msg} — got '{region}'")

    # Validate deploy targets
    target_errors = validate_targets(manifest)
    errors.extend(target_errors)

    for mod in manifest.get("modules", []):
        base = mod.split("@")[0]
        if not Path(base).exists():
            errors.append(f"Module directory not found: {base}")
            continue
        config = load_module_config(mod)

        # Check module status
        status = config.get("status", "ready")
        if status == "planned":
            errors.append(
                f"Module '{mod}' has status 'planned' (not yet implemented). "
                "Remove it from your manifest or wait for a future release."
            )
            continue
        if status == "preview":
            print(f"  ⚠ Module '{mod}' has status 'preview' — not production-ready")

        for param in config.get("params", []):
            name = param["name"]
            value = params.get(name)
            # Check required
            if param.get("required") and not value:
                errors.append(f"Module '{mod}' requires param '{name}'")
                continue
            # Skip validation if value is empty and param is optional
            if not value:
                continue
            # Type/format validation
            is_valid, err_msg = validate_param_value(param, str(value))
            if not is_valid:
                errors.append(f"Param '{name}' (module '{mod}'): {err_msg} — got '{value}'")
    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("✓ Manifest validated successfully")


def resolve_deploy_order(manifest: dict) -> list[str]:
    """Topological sort of modules based on their declared dependencies.

    Implicit dependencies (listed in config.yaml but not in the manifest) are
    automatically added so the deploy always succeeds.
    """
    manifest_modules = [m.split("@")[0] for m in manifest.get("modules", [])]
    module_set = set(manifest_modules)

    # Build adjacency: module -> list of modules it depends on
    deps: dict[str, list[str]] = {}

    def ensure_module(mod: str) -> None:
        """Recursively pull in implicit dependencies."""
        if mod in deps:
            return
        config = load_module_config(mod)
        mod_deps = config.get("dependencies") or []
        deps[mod] = mod_deps
        for d in mod_deps:
            module_set.add(d)
            ensure_module(d)

    for mod in list(manifest_modules):
        ensure_module(mod)

    # Kahn's algorithm — in_degree[m] = number of deps m has within module_set
    in_degree: dict[str, int] = {m: 0 for m in module_set}
    for mod in module_set:
        for d in deps.get(mod, []):
            if d in module_set:
                in_degree[mod] += 1

    queue = sorted(m for m in module_set if in_degree[m] == 0)
    ordered: list[str] = []

    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for mod in module_set:
            if current in deps.get(mod, []):
                in_degree[mod] -= 1
                if in_degree[mod] == 0:
                    queue.append(mod)
        queue.sort()

    if len(ordered) != len(module_set):
        cycle_modules = module_set - set(ordered)
        print(f"ERROR: Circular dependency detected involving: {', '.join(sorted(cycle_modules))}")
        sys.exit(1)

    return ordered


def group_by_iac_type(manifest: dict) -> dict[str, list[str]]:
    """Group modules by their iac_type."""
    groups: dict[str, list[str]] = {}
    for mod in manifest.get("modules", []):
        config = load_module_config(mod)
        iac_type = config.get("iac_type", "terraform")
        groups.setdefault(iac_type, []).append(mod)
    return groups


def deploy_terraform(modules: list[str], manifest: dict, auto_approve: bool = False, target_env: dict | None = None) -> None:
    """Deploy Terraform modules."""
    print(f"\n=== Deploying {len(modules)} Terraform module(s) ===")
    tf_dir = Path("templates/customer-project/tf-app")
    if not tf_dir.exists():
        print("  Generating Terraform root config...")
        tf_dir.mkdir(parents=True, exist_ok=True)
        lines = ['# Auto-generated from manifest.yaml\n']
        for mod in modules:
            base = mod.split("@")[0]
            tf_path = Path(base) / "terraform"
            if tf_path.exists():
                mod_name = base.replace("/", "_").replace("-", "_")
                lines.append(f'module "{mod_name}" {{')
                lines.append(f'  source = "../../../{tf_path}"')
                for k, v in manifest.get("params", {}).items():
                    lines.append(f'  {k} = "{v}"')
                lines.append("}\n")
        (tf_dir / "main.tf").write_text("\n".join(lines))
    subprocess.run(["terraform", "init"], cwd=tf_dir, check=True, env=target_env)
    if auto_approve:
        subprocess.run(["terraform", "apply", "-auto-approve"], cwd=tf_dir, check=True, env=target_env)
    else:
        print("\n  Running terraform plan...")
        subprocess.run(["terraform", "plan", "-out=tfplan"], cwd=tf_dir, check=True, env=target_env)
        print("\n  Review the plan above. Applying...")
        subprocess.run(["terraform", "apply", "tfplan"], cwd=tf_dir, check=True, env=target_env)


def deploy_external(modules: list[str], manifest: dict, auto_approve: bool = False, target_env: dict | None = None) -> None:
    """Deploy external modules via their own deploy scripts.

    Manifest params are passed as environment variables prefixed with QS_PARAM_
    so the accelerator's deploy.sh can consume them without coupling to our manifest format.
    """
    print(f"\n=== Deploying {len(modules)} external module(s) ===")
    # Build env vars from manifest params, layered on top of target env
    param_env = dict(target_env or os.environ)
    for key, value in manifest.get("params", {}).items():
        param_env[f"QS_PARAM_{key.upper()}"] = str(value)
    param_env["QS_PROJECT"] = manifest.get("project", "")
    if auto_approve:
        param_env["QS_AUTO_APPROVE"] = "1"

    for mod in modules:
        base = mod.split("@")[0]
        deploy_script = Path(base) / "deploy.sh"
        if deploy_script.exists():
            print(f"  Deploying {mod}...")
            subprocess.run(["bash", str(deploy_script)], check=True, env=param_env)
        else:
            print(f"  WARNING: No deploy.sh found for {mod}, skipping")


def deploy_config(modules: list[str], manifest: dict, auto_approve: bool = False, target_env: dict | None = None) -> None:
    """Deploy config-only modules via their deploy scripts.

    Manifest params are passed as QS_PARAM_* environment variables,
    same contract as deploy_external.
    """
    print(f"\n=== Deploying {len(modules)} config-only module(s) ===")
    param_env = dict(target_env or os.environ)
    for key, value in manifest.get("params", {}).items():
        param_env[f"QS_PARAM_{key.upper()}"] = str(value)
    param_env["QS_PROJECT"] = manifest.get("project", "")
    if auto_approve:
        param_env["QS_AUTO_APPROVE"] = "1"

    for mod in modules:
        base = mod.split("@")[0]
        deploy_py = Path(base) / "deploy.py"
        if deploy_py.exists():
            print(f"  Deploying {mod}...")
            subprocess.run([sys.executable, str(deploy_py)], check=True, env=param_env)
        else:
            print(f"  WARNING: No deploy.py found for {mod}, skipping")


DEPLOYERS = {
    "terraform": deploy_terraform,
    "external": deploy_external,
    "config-only": deploy_config,
}


# --- Status / drift detection ---

STATUS_NO_DRIFT = "no_drift"
STATUS_DRIFT = "drift"
STATUS_UNKNOWN = "unknown"
STATUS_ERROR = "error"


def check_status_terraform(mod: str, manifest: dict, target_env: dict | None = None) -> tuple[str, str]:
    """Check Terraform module drift via terraform plan. Returns (status, detail)."""
    tf_dir = Path("templates/customer-project/tf-app")
    if not tf_dir.exists():
        return STATUS_UNKNOWN, "Terraform directory not found — module may not have been deployed yet"
    print(f"  Running terraform plan...")
    result = subprocess.run(
        ["terraform", "plan", "-detailed-exitcode", "-no-color"],
        capture_output=True, text=True, cwd=tf_dir, env=target_env,
    )
    if result.returncode == 0:
        return STATUS_NO_DRIFT, "Infrastructure matches state"
    if result.returncode == 2:
        return STATUS_DRIFT, result.stdout.strip()[:500]
    return STATUS_ERROR, f"terraform plan failed: {result.stderr.strip()[:200]}"


def check_status_external(mod: str, manifest: dict, target_env: dict | None = None) -> tuple[str, str]:
    """Check external module status via optional status.sh. Returns (status, detail)."""
    base = mod.split("@")[0]
    status_script = Path(base) / "status.sh"
    if not status_script.exists():
        return STATUS_UNKNOWN, "No status.sh provided — cannot check drift"
    result = subprocess.run(
        ["bash", str(status_script)],
        capture_output=True, text=True, env=target_env,
    )
    if result.returncode == 0:
        return STATUS_NO_DRIFT, result.stdout.strip()[:500] or "OK"
    return STATUS_DRIFT, result.stdout.strip()[:500] or result.stderr.strip()[:500]


def check_status_config(mod: str, manifest: dict, target_env: dict | None = None) -> tuple[str, str]:
    """Check config-only module status via optional status.py. Returns (status, detail)."""
    base = mod.split("@")[0]
    status_py = Path(base) / "status.py"
    if not status_py.exists():
        return STATUS_UNKNOWN, "No status.py provided — cannot check drift"
    result = subprocess.run(
        [sys.executable, str(status_py)],
        capture_output=True, text=True, env=target_env,
    )
    if result.returncode == 0:
        return STATUS_NO_DRIFT, result.stdout.strip()[:500] or "OK"
    return STATUS_DRIFT, result.stdout.strip()[:500] or result.stderr.strip()[:500]


STATUS_CHECKERS = {
    "terraform": check_status_terraform,
    "external": check_status_external,
    "config-only": check_status_config,
}


def save_deploy_state(state: dict) -> None:
    """Persist deploy state to disk for resume capability."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    Path(DEPLOY_STATE_FILE).write_text(json.dumps(state, indent=2))


def load_deploy_state() -> dict | None:
    """Load previous deploy state, if any."""
    path = Path(DEPLOY_STATE_FILE)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def clear_deploy_state() -> None:
    """Remove the deploy state file after successful completion."""
    path = Path(DEPLOY_STATE_FILE)
    if path.exists():
        path.unlink()


def run_deploy(ordered: list[str], manifest: dict, auto_approve: bool, resume_after: str | None = None, logger: DeployLogger | None = None) -> None:
    """Execute the deploy loop with error handling and state tracking."""
    state = {
        "ordered": ordered,
        "deployed": [],
        "failed": None,
        "remaining": list(ordered),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # If resuming, skip already-deployed modules
    if resume_after:
        try:
            resume_idx = ordered.index(resume_after) + 1
        except ValueError:
            print(f"ERROR: Module '{resume_after}' not found in deploy order")
            sys.exit(1)
        state["deployed"] = ordered[:resume_idx]
        state["remaining"] = ordered[resume_idx:]
        print(f"\nResuming after '{resume_after}' — skipping {resume_idx} already-deployed module(s)")
        if logger:
            logger.log_event("resume", resume_after=resume_after, skipped=resume_idx)

    save_deploy_state(state)

    for mod in list(state["remaining"]):
        config = load_module_config(mod)
        iac_type = config.get("iac_type", "terraform")
        deployer = DEPLOYERS.get(iac_type)
        if not deployer:
            print(f"ERROR: Unknown iac_type '{iac_type}' for module '{mod}'")
            sys.exit(1)

        # Resolve deployment target (account/region/profile)
        target = resolve_target(mod, manifest)
        target_env = target.apply_to_env(dict(os.environ))
        if target.profile or target.account:
            print(f"  Target: {target}")

        if logger:
            logger.log_module_start(mod, iac_type)

        try:
            deployer([mod], manifest, auto_approve, target_env=target_env)
            state["deployed"].append(mod)
            state["remaining"].remove(mod)
            save_deploy_state(state)
            if logger:
                logger.log_module_success(mod)
        except subprocess.CalledProcessError as e:
            state["failed"] = mod
            save_deploy_state(state)
            if logger:
                logger.log_module_failure(mod, e.returncode)
                logger.finish("failed", deployed=state["deployed"], failed=mod)
            print(f"\n{'=' * 60}")
            print(f"DEPLOY FAILED at module: {mod}")
            print(f"  iac_type: {iac_type}")
            print(f"  exit code: {e.returncode}")
            print(f"{'=' * 60}")
            print(f"\nSuccessfully deployed ({len(state['deployed'])}):")
            for d in state["deployed"]:
                print(f"  ✓ {d}")
            print(f"\nFailed:")
            print(f"  ✗ {mod}")
            if state["remaining"]:
                print(f"\nNot attempted ({len(state['remaining'])}):")
                for r in state["remaining"]:
                    print(f"  - {r}")
            print(f"\nRecovery options:")
            print(f"  1. Fix the issue and resume:  python3 core/utils/orchestrator.py resume")
            print(f"  2. Retry from scratch:        python3 core/utils/orchestrator.py deploy")
            print(f"  3. Roll back deployed modules manually (see below)")
            print(f"\nRollback commands for deployed modules:")
            for d in reversed(state["deployed"]):
                d_config = load_module_config(d)
                d_type = d_config.get("iac_type", "terraform")
                if d_type == "terraform":
                    print(f"  cd templates/customer-project/tf-app && terraform destroy  # covers {d}")
                else:
                    print(f"  # {d} ({d_type}): manual rollback required")
            print(f"\nDeploy state saved to {DEPLOY_STATE_FILE}")
            sys.exit(1)

    if logger:
        logger.finish("success", deployed=state["deployed"])
    clear_deploy_state()
    print("\n✓ All modules deployed successfully")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py <validate|deploy|resume|status|cost> [--auto-approve]")
        sys.exit(1)

    command = sys.argv[1]
    auto_approve = "--auto-approve" in sys.argv
    manifest = load_manifest()
    manifest = resolve_params(manifest)

    if command == "validate":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        print(f"Deploy order: {' → '.join(ordered)}")
    elif command == "deploy":
        validate(manifest)
        if auto_approve:
            print("⚠ Running with --auto-approve: skipping interactive approval")
        ordered = resolve_deploy_order(manifest)
        print(f"\nDeploy order ({len(ordered)} module(s)):")
        for i, mod in enumerate(ordered, 1):
            config = load_module_config(mod)
            print(f"  {i}. {mod} (iac_type={config.get('iac_type', 'terraform')})")
        logger = DeployLogger("deploy", manifest)
        logger.log_event("deploy_start", auto_approve=auto_approve, deploy_order=ordered)
        run_deploy(ordered, manifest, auto_approve, logger=logger)
    elif command == "resume":
        state = load_deploy_state()
        if not state:
            print("No deploy state found — nothing to resume. Run 'deploy' instead.")
            sys.exit(1)
        failed = state.get("failed")
        remaining = state.get("remaining", [])
        if not remaining and not failed:
            print("Previous deploy completed successfully — nothing to resume.")
            clear_deploy_state()
            sys.exit(0)
        print(f"Resuming deploy from state file ({DEPLOY_STATE_FILE})")
        print(f"  Previously deployed: {', '.join(state.get('deployed', [])) or '(none)'}")
        print(f"  Failed: {failed or '(none)'}")
        print(f"  Remaining: {', '.join(remaining) or '(none)'}")
        # Re-resolve order but resume from the failed module
        ordered = resolve_deploy_order(manifest)
        resume_after = state["deployed"][-1] if state.get("deployed") else None
        if auto_approve:
            print("⚠ Running with --auto-approve: skipping interactive approval")
        logger = DeployLogger("resume", manifest)
        logger.log_event("resume_start", resume_after=resume_after)
        run_deploy(ordered, manifest, auto_approve, resume_after=resume_after, logger=logger)
    elif command == "status":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        print(f"\n=== Checking status of {len(ordered)} module(s) ===\n")
        results = {}
        for mod in ordered:
            config = load_module_config(mod)
            iac_type = config.get("iac_type", "terraform")
            checker = STATUS_CHECKERS.get(iac_type)
            if not checker:
                results[mod] = (STATUS_UNKNOWN, f"No status checker for iac_type '{iac_type}'")
                continue
            target = resolve_target(mod, manifest)
            target_env = target.apply_to_env(dict(os.environ))
            print(f"[{mod}] ({iac_type})")
            try:
                status, detail = checker(mod, manifest, target_env)
            except Exception as e:
                status, detail = STATUS_ERROR, str(e)
            results[mod] = (status, detail)
            icon = {"no_drift": "✓", "drift": "⚠", "unknown": "?", "error": "✗"}[status]
            print(f"  {icon} {status}: {detail}\n")

        # Summary
        print("=" * 50)
        print("Summary:")
        counts: dict[str, int] = {}
        for _mod, (st, _detail) in results.items():
            counts[st] = counts.get(st, 0) + 1
        for s in [STATUS_NO_DRIFT, STATUS_DRIFT, STATUS_UNKNOWN, STATUS_ERROR]:
            if counts.get(s):
                icon = {"no_drift": "✓", "drift": "⚠", "unknown": "?", "error": "✗"}[s]
                print(f"  {icon} {s}: {counts[s]}")
        if counts.get(STATUS_DRIFT, 0) > 0:
            print(f"\nRun './deploy.sh' to reconcile drifted modules.")
    elif command == "cost":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        print_cost_report(manifest, ordered)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
