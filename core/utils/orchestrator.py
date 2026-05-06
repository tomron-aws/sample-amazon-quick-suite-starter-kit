"""Orchestrator — reads manifest.yaml, validates modules, and dispatches to IaC engines."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from param_resolver import resolve_params
from deploy_targets import resolve_target, validate_targets
from cost_estimator import print_cost_report

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


TF_OUTPUT_DIR = Path("generated")


def generate_terraform(modules: list[str], manifest: dict) -> Path:
    """Generate a native Terraform root module from the manifest.

    Produces:
      - main.tf       — module blocks with var references
      - variables.tf  — union of all module params as TF variables
      - terraform.tfvars — param values from manifest
    """
    tf_dir = TF_OUTPUT_DIR
    tf_dir.mkdir(parents=True, exist_ok=True)
    params = manifest.get("params", {})

    # Collect the union of all params across selected modules (preserving first-seen defaults)
    all_params: dict[str, dict] = {}
    for mod in modules:
        config = load_module_config(mod)
        for p in config.get("params", []):
            if p["name"] not in all_params:
                all_params[p["name"]] = p

    # Detect if any module uses the AWSCC provider
    needs_awscc = any(
        "awscc_" in (Path(m.split("@")[0]) / "terraform" / "main.tf").read_text()
        for m in modules
        if (Path(m.split("@")[0]) / "terraform" / "main.tf").exists()
    )

    # --- main.tf ---
    main_lines = [
        "# Auto-generated from manifest.yaml — do not edit manually.",
        "# Re-generate with: python3 core/utils/orchestrator.py generate",
        "",
        "terraform {",
        '  required_providers {',
        '    aws = {',
        '      source  = "hashicorp/aws"',
        '      version = "~> 6.0"',
        '    }',
    ]
    if needs_awscc:
        main_lines += [
            '    awscc = {',
            '      source  = "hashicorp/awscc"',
            '      version = "~> 1.0"',
            '    }',
        ]
    main_lines += [
        '  }',
        '}',
        "",
        "provider \"aws\" {",
        "  region = var.region",
        "}",
        "",
    ]
    if needs_awscc:
        main_lines += [
            "provider \"awscc\" {",
            "  region = var.region",
            "}",
            "",
        ]
    # Build a map of module base path -> TF module name for depends_on
    mod_name_map = {}
    for mod in modules:
        base = mod.split("@")[0]
        mod_name_map[base] = base.replace("/", "_").replace("-", "_")

    # Track params that are wired via module outputs (not user-facing)
    wired_params: set[str] = set()
    # Build a map of module outputs: module_path -> set of output names
    mod_outputs: dict[str, set[str]] = {}
    for mod in modules:
        base = mod.split("@")[0]
        tf_file = Path(base) / "terraform" / "main.tf"
        if tf_file.exists():
            import re as _re
            mod_outputs[base] = set(_re.findall(r'output\s+"(\w+)"', tf_file.read_text()))

    for mod in modules:
        base = mod.split("@")[0]
        tf_path = Path(base) / "terraform"
        if not tf_path.exists():
            continue
        mod_name = mod_name_map[base]
        config = load_module_config(mod)
        mod_params = config.get("params", [])
        mod_deps = config.get("dependencies") or []
        main_lines.append(f'module "{mod_name}" {{')
        main_lines.append(f'  source = "../{tf_path}"')
        for p in mod_params:
            # Check if a dependency module exports this param as an output
            wired = False
            for dep in mod_deps:
                if dep in mod_outputs and p["name"] in mod_outputs[dep]:
                    dep_mod_name = mod_name_map[dep]
                    main_lines.append(f'  {p["name"]} = module.{dep_mod_name}.{p["name"]}')
                    wired_params.add(p["name"])
                    wired = True
                    break
            if not wired:
                main_lines.append(f'  {p["name"]} = var.{p["name"]}')
        # Add depends_on for declared dependencies
        dep_refs = [f"module.{mod_name_map[d]}" for d in mod_deps if d in mod_name_map]
        if dep_refs:
            main_lines.append(f'  depends_on = [{", ".join(dep_refs)}]')
        main_lines.append("}")
        main_lines.append("")

    # Add outputs for all module outputs
    for mod in modules:
        base = mod.split("@")[0]
        mod_name = mod_name_map[base]
        for output_name in mod_outputs.get(base, []):
            safe_name = f"{mod_name}__{output_name}"
            main_lines.append(f'output "{safe_name}" {{')
            main_lines.append(f'  value = module.{mod_name}.{output_name}')
            main_lines.append("}")
            main_lines.append("")

    (tf_dir / "main.tf").write_text("\n".join(main_lines) + "\n")

    # --- variables.tf ---
    var_lines = ["# Auto-generated from manifest.yaml — do not edit manually.", ""]
    # Always include region
    if "region" not in all_params:
        var_lines += [
            'variable "region" {',
            "  type    = string",
            '  default = "us-east-1"',
            "}",
            "",
        ]
    for name, p in all_params.items():
        if name in wired_params:
            continue
        tf_type = "string"
        if p.get("type") == "json":
            tf_type = "list(string)"
        var_lines.append(f'variable "{name}" {{')
        var_lines.append(f"  type = {tf_type}")
        if p.get("default") is not None:
            default_val = p["default"]
            if tf_type == "list(string)":
                var_lines.append(f"  default = {default_val}")
            else:
                var_lines.append(f'  default = "{default_val}"')
        var_lines.append("}")
        var_lines.append("")
    (tf_dir / "variables.tf").write_text("\n".join(var_lines) + "\n")

    # --- terraform.tfvars ---
    tfvars_lines = ["# Auto-generated from manifest.yaml — edit as needed.", ""]
    for name, p in all_params.items():
        if name in wired_params:
            continue
        value = params.get(name, "")
        if not value and p.get("default") is not None:
            continue
        if p.get("type") == "json":
            tfvars_lines.append(f'{name} = {value or "[]"}')
        else:
            tfvars_lines.append(f'{name} = "{value}"')
    # Always include region
    if "region" not in all_params:
        tfvars_lines.append(f'region = "{params.get("region", "us-east-1")}"')
    tfvars_lines.append("")
    (tf_dir / "terraform.tfvars").write_text("\n".join(tfvars_lines) + "\n")

    return tf_dir


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



# --- Status / drift detection ---

STATUS_NO_DRIFT = "no_drift"
STATUS_DRIFT = "drift"
STATUS_UNKNOWN = "unknown"
STATUS_ERROR = "error"


def check_status_terraform(mod: str, manifest: dict, target_env: dict | None = None) -> tuple[str, str]:
    """Check Terraform module drift via terraform plan. Returns (status, detail)."""
    tf_dir = Path("generated")
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



def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py <validate|generate|deploy|status|cost> [--auto-approve]")
        sys.exit(1)

    command = sys.argv[1]
    auto_approve = "--auto-approve" in sys.argv
    manifest = load_manifest()
    manifest = resolve_params(manifest)

    if command == "validate":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        print(f"Deploy order: {' → '.join(ordered)}")
    elif command == "generate":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        # Filter to terraform modules only
        tf_modules = [m for m in ordered if load_module_config(m).get("iac_type", "terraform") == "terraform"]
        if not tf_modules:
            print("No Terraform modules selected in manifest.")
            sys.exit(0)
        tf_dir = generate_terraform(tf_modules, manifest)
        print(f"\n✓ Generated Terraform root module in {tf_dir}/")
        print(f"  - main.tf       ({len(tf_modules)} module(s))")
        print(f"  - variables.tf")
        print(f"  - terraform.tfvars")
        print(f"\nNext steps:")
        print(f"  cd {tf_dir}")
        print(f"  terraform init")
        print(f"  terraform plan")
        print(f"  terraform apply")
    elif command == "deploy":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)

        # Generate + apply Terraform modules
        tf_modules = [m for m in ordered if load_module_config(m).get("iac_type", "terraform") == "terraform"]
        if tf_modules:
            tf_dir = generate_terraform(tf_modules, manifest)
            print(f"\n=== Deploying {len(tf_modules)} Terraform module(s) ===")
            target = resolve_target(tf_modules[0], manifest)
            target_env = target.apply_to_env(dict(os.environ))
            subprocess.run(["terraform", "init"], cwd=tf_dir, check=True, env=target_env)
            if auto_approve:
                subprocess.run(["terraform", "apply", "-auto-approve"], cwd=tf_dir, check=True, env=target_env)
            else:
                subprocess.run(["terraform", "apply"], cwd=tf_dir, check=True, env=target_env)

        # Deploy external modules
        ext_modules = [m for m in ordered if load_module_config(m).get("iac_type") == "external"]
        if ext_modules:
            deploy_external(ext_modules, manifest, auto_approve)

        # Deploy config-only modules
        cfg_modules = [m for m in ordered if load_module_config(m).get("iac_type") == "config-only"]
        if cfg_modules:
            deploy_config(cfg_modules, manifest, auto_approve)

        print("\n✓ All modules deployed successfully")
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

        print("=" * 50)
        print("Summary:")
        counts: dict[str, int] = {}
        for _mod, (st, _detail) in results.items():
            counts[st] = counts.get(st, 0) + 1
        for s in [STATUS_NO_DRIFT, STATUS_DRIFT, STATUS_UNKNOWN, STATUS_ERROR]:
            if counts.get(s):
                icon = {"no_drift": "✓", "drift": "⚠", "unknown": "?", "error": "✗"}[s]
                print(f"  {icon} {s}: {counts[s]}")
    elif command == "cost":
        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        print_cost_report(manifest, ordered)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
