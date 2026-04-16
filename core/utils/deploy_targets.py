"""Deploy targets — resolves per-module account/region/profile from manifest.

Supports an optional 'targets' section in manifest.yaml:

    targets:
      default:
        region: us-east-1
        profile: quicksuite-prod
      data-account:
        region: us-west-2
        profile: quicksuite-data
        account: "222222222222"

    module_targets:
      data-sources/redshift: data-account
      data-sources/athena: data-account
      # Everything else uses 'default' if it exists, or current CLI profile

If no targets section exists, everything deploys to the current CLI profile.
"""

from __future__ import annotations

import os


class DeployTarget:
    """Resolved deployment target for a module."""

    def __init__(self, region: str | None = None, profile: str | None = None, account: str | None = None):
        self.region = region
        self.profile = profile
        self.account = account

    def apply_to_env(self, env: dict[str, str]) -> dict[str, str]:
        """Return a copy of env with target-specific AWS variables set."""
        result = dict(env)
        if self.region:
            result["AWS_DEFAULT_REGION"] = self.region
            result["AWS_REGION"] = self.region
        if self.profile:
            result["AWS_PROFILE"] = self.profile
        if self.account:
            result["QS_TARGET_ACCOUNT"] = self.account
        return result

    def __repr__(self) -> str:
        parts = []
        if self.profile:
            parts.append(f"profile={self.profile}")
        if self.account:
            parts.append(f"account={self.account}")
        if self.region:
            parts.append(f"region={self.region}")
        return f"DeployTarget({', '.join(parts)})" if parts else "DeployTarget(current CLI)"


def resolve_target(module_path: str, manifest: dict) -> DeployTarget:
    """Resolve the deployment target for a module.

    Lookup order:
    1. module_targets mapping (explicit per-module override)
    2. 'default' target (if defined in targets section)
    3. No target (use current CLI profile)
    """
    targets = manifest.get("targets", {})
    module_targets = manifest.get("module_targets", {})

    # No targets section at all — backward-compatible, use current CLI
    if not targets:
        return DeployTarget()

    # Check for explicit module → target mapping
    target_name = module_targets.get(module_path)
    if not target_name:
        target_name = "default"

    target_config = targets.get(target_name)
    if not target_config:
        return DeployTarget()

    return DeployTarget(
        region=target_config.get("region"),
        profile=target_config.get("profile"),
        account=target_config.get("account"),
    )


def validate_targets(manifest: dict) -> list[str]:
    """Validate the targets configuration. Returns a list of errors."""
    errors = []
    targets = manifest.get("targets", {})
    module_targets = manifest.get("module_targets", {})

    if not targets and module_targets:
        errors.append("'module_targets' defined but no 'targets' section found")
        return errors

    # Check all module_targets reference valid target names
    for mod, target_name in module_targets.items():
        if target_name not in targets:
            errors.append(f"Module '{mod}' references unknown target '{target_name}'")

    # Validate target configs
    for name, config in targets.items():
        if not isinstance(config, dict):
            errors.append(f"Target '{name}' must be a mapping")
            continue
        region = config.get("region")
        if region and not isinstance(region, str):
            errors.append(f"Target '{name}': region must be a string")
        profile = config.get("profile")
        if profile and not isinstance(profile, str):
            errors.append(f"Target '{name}': profile must be a string")

    return errors
