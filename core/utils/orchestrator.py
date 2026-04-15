"""Orchestrator — reads manifest.yaml, validates modules, and dispatches to IaC engines."""

import subprocess
import sys
from pathlib import Path

import yaml


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
    """Validate manifest: check all modules exist and required params are set."""
    errors = []
    for mod in manifest.get("modules", []):
        base = mod.split("@")[0]
        if not Path(base).exists():
            errors.append(f"Module directory not found: {base}")
            continue
        config = load_module_config(mod)
        for param in config.get("params", []):
            if param.get("required") and not manifest.get("params", {}).get(param["name"]):
                errors.append(f"Module '{mod}' requires param '{param['name']}'")
    if errors:
        print("Validation errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("✓ Manifest validated successfully")


def group_by_iac_type(manifest: dict) -> dict[str, list[str]]:
    """Group modules by their iac_type."""
    groups: dict[str, list[str]] = {}
    for mod in manifest.get("modules", []):
        config = load_module_config(mod)
        iac_type = config.get("iac_type", "cdk")
        groups.setdefault(iac_type, []).append(mod)
    return groups


def deploy_cdk(modules: list[str], manifest: dict) -> None:
    """Deploy CDK modules via cdk deploy."""
    print(f"\n=== Deploying {len(modules)} CDK module(s) ===")
    for mod in modules:
        print(f"  - {mod}")
    subprocess.run(["npx", "cdk", "deploy", "--all", "--require-approval", "never"], check=True)


def deploy_terraform(modules: list[str], manifest: dict) -> None:
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
    subprocess.run(["terraform", "init"], cwd=tf_dir, check=True)
    subprocess.run(["terraform", "apply", "-auto-approve"], cwd=tf_dir, check=True)


def deploy_external(modules: list[str], manifest: dict) -> None:
    """Deploy external modules via their own deploy scripts."""
    print(f"\n=== Deploying {len(modules)} external module(s) ===")
    for mod in modules:
        base = mod.split("@")[0]
        deploy_script = Path(base) / "deploy.sh"
        if deploy_script.exists():
            subprocess.run(["bash", str(deploy_script)], check=True)
        else:
            print(f"  WARNING: No deploy.sh found for {mod}, skipping")


def deploy_config(modules: list[str], manifest: dict) -> None:
    """Deploy config-only modules via their deploy scripts."""
    print(f"\n=== Deploying {len(modules)} config-only module(s) ===")
    for mod in modules:
        base = mod.split("@")[0]
        deploy_py = Path(base) / "deploy.py"
        if deploy_py.exists():
            subprocess.run([sys.executable, str(deploy_py)], check=True)
        else:
            print(f"  WARNING: No deploy.py found for {mod}, skipping")


DEPLOYERS = {
    "cdk": deploy_cdk,
    "terraform": deploy_terraform,
    "external": deploy_external,
    "config-only": deploy_config,
}


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: orchestrator.py <validate|deploy>")
        sys.exit(1)

    command = sys.argv[1]
    manifest = load_manifest()

    if command == "validate":
        validate(manifest)
    elif command == "deploy":
        validate(manifest)
        groups = group_by_iac_type(manifest)
        for iac_type in ["cdk", "terraform", "external", "config-only"]:
            modules = groups.get(iac_type, [])
            if modules:
                DEPLOYERS[iac_type](modules, manifest)
        print("\n✓ All modules deployed successfully")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
