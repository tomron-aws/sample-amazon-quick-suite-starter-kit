"""Cost estimator — provides deployment cost estimates for selected modules.

Uses a combination of:
1. Known QuickSight pricing tiers (the primary cost driver)
2. Infrastructure cost notes per module (most are free-tier or negligible)
3. Optional infracost integration for detailed IaC cost breakdowns
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# QuickSight pricing (us-east-1, monthly, per user)
# Source: https://aws.amazon.com/quicksight/pricing/
QUICKSIGHT_PRICING = {
    "READER": {"monthly": 5.0, "annual_monthly": 3.0},
    "READER_PRO": {"monthly": 10.0, "annual_monthly": 8.0},
    "AUTHOR": {"monthly": 24.0, "annual_monthly": 18.0},
    "AUTHOR_PRO": {"monthly": 35.0, "annual_monthly": 25.0},
    "ADMIN": {"monthly": 24.0, "annual_monthly": 18.0},
    "ADMIN_PRO": {"monthly": 35.0, "annual_monthly": 25.0},
}

# Per-module infrastructure cost notes
MODULE_COST_NOTES: dict[str, dict] = {
    "governance/subscription": {
        "resources": "Lambda function, IAM roles, CloudFormation custom resource",
        "estimated_monthly": 0.0,
        "note": "Lambda runs only during deploy/update. No ongoing compute cost.",
    },
    "governance/permissions": {
        "resources": "IAM Identity Center permission sets",
        "estimated_monthly": 0.0,
        "note": "IAM Identity Center permission sets are free.",
    },
    "data-sources/redshift": {
        "resources": "QuickSight data source configuration",
        "estimated_monthly": 0.0,
        "note": "Data source config only. Redshift cluster cost is separate.",
    },
    "data-sources/athena": {
        "resources": "QuickSight data source, S3 results bucket",
        "estimated_monthly": 0.0,
        "note": "Athena charges per query ($5/TB scanned). S3 storage is minimal.",
    },
    "data-sources/glue": {
        "resources": "QuickSight data source configuration",
        "estimated_monthly": 0.0,
        "note": "Data source config only. Glue catalog is free for first 1M objects.",
    },
    "core/custom-resources": {
        "resources": "Lambda function (shared)",
        "estimated_monthly": 0.0,
        "note": "Runs only during deploy. Covered by Lambda free tier.",
    },
}


def estimate_quicksight_cost(manifest: dict) -> dict:
    """Estimate QuickSight licensing cost based on manifest params."""
    edition = manifest.get("params", {}).get("edition", "ENTERPRISE").upper()
    is_pro = "PRO" in edition or edition == "ENTERPRISE"

    return {
        "edition": edition,
        "pricing_note": "QuickSight is the primary cost driver. Infrastructure costs are negligible.",
        "per_user_monthly": {
            role: pricing["monthly"]
            for role, pricing in QUICKSIGHT_PRICING.items()
            if (is_pro and "PRO" in role) or (not is_pro and "PRO" not in role)
        },
        "tip": "Use annual commitment pricing for 20-30% savings.",
    }


def estimate_module_costs(modules: list[str]) -> list[dict]:
    """Return cost notes for each selected module."""
    results = []
    for mod in modules:
        info = MODULE_COST_NOTES.get(mod)
        if info:
            results.append({"module": mod, **info})
        else:
            results.append({
                "module": mod,
                "resources": "Unknown",
                "estimated_monthly": None,
                "note": "No cost estimate available for this module.",
            })
    return results


def try_infracost(manifest: dict) -> str | None:
    """Run infracost if available. Returns output or None."""
    if not shutil.which("infracost"):
        return None

    tf_dir = Path("generated")
    if not tf_dir.exists():
        return None

    try:
        result = subprocess.run(
            ["infracost", "breakdown", "--path", str(tf_dir), "--format", "table"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def print_cost_report(manifest: dict, ordered: list[str]) -> None:
    """Print a cost estimation report for the selected modules."""
    print("\n=== Cost Estimation ===\n")

    # QuickSight licensing
    qs = estimate_quicksight_cost(manifest)
    print(f"QuickSight Edition: {qs['edition']}")
    print(f"\n  {qs['pricing_note']}\n")
    print("  Per-user monthly pricing:")
    for role, price in qs["per_user_monthly"].items():
        print(f"    {role:15s}  ${price:.2f}/month")
    print(f"\n  Tip: {qs['tip']}\n")

    # Module infrastructure costs
    print("Module infrastructure costs:\n")
    module_costs = estimate_module_costs(ordered)
    total_infra = 0.0
    for mc in module_costs:
        cost_str = f"${mc['estimated_monthly']:.2f}/mo" if mc["estimated_monthly"] is not None else "unknown"
        print(f"  [{mc['module']}]")
        print(f"    Resources: {mc['resources']}")
        print(f"    Cost: {cost_str}")
        print(f"    Note: {mc['note']}\n")
        if mc["estimated_monthly"] is not None:
            total_infra += mc["estimated_monthly"]

    print(f"  Total infrastructure: ${total_infra:.2f}/month")
    print(f"  (QuickSight user licensing is additional — see per-user pricing above)\n")

    # Try infracost for detailed breakdown
    print("Checking for infracost...")
    infracost_output = try_infracost(manifest)
    if infracost_output:
        print(f"\n  Infracost detailed breakdown:\n")
        for line in infracost_output.split("\n"):
            print(f"    {line}")
    else:
        print("  infracost not found — install it for detailed IaC cost breakdowns:")
        print("  https://www.infracost.io/docs/")

    print("\n" + "=" * 50)
    print("Note: This is an estimate. Actual costs depend on usage patterns,")
    print("data volumes, and QuickSight user count. Review AWS pricing pages")
    print("for current rates: https://aws.amazon.com/quicksight/pricing/")
