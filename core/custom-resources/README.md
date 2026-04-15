# Core: Custom Resources

Shared CloudFormation custom resource Lambda handlers used by CDK modules.

## Contents

- `lambdas/src/custom_resource_handler_for_quick_suite_setup.py` — Quick Suite subscription setup (used by `governance/subscription`)

## For module authors

Place new custom resource handlers here. Each handler should:
1. Use `crhelper` for CloudFormation lifecycle management
2. Include observability via `common/observability.py`
3. Be referenced from your module's CDK construct via `Code.fromAsset('core/custom-resources/lambdas', ...)`
