# Accelerator Integration Guide

How to integrate an external accelerator with the Quick Suite Starter Kit.

## Overview

External accelerators are standalone projects (their own repos, their own IaC) that integrate with Quick Suite through a lightweight contract. You do not need to rewrite your accelerator in CDK or Terraform to integrate — you just need to provide a deploy script and a config file.

There are two integration tiers:

| Tier | Effort | What you provide | IaC parity? |
|---|---|---|---|
| Standard (deploy-script) | Low | `config.yaml` + `deploy.sh` | No — you use whatever IaC you already have |
| Deep (CDK shim) | Medium | Standard + `cdk/` construct | Yes — enables CFN bridge for Terraform customers |

Start with Standard. Upgrade to Deep only if your accelerator needs to share CloudFormation outputs with other Quick Suite modules or if Terraform-only customers need to deploy it without your native tooling.

## Standard integration (deploy-script)

This is the default and recommended path. The Quick Suite orchestrator calls your `deploy.sh` and passes manifest params as environment variables.

### What you provide

```
use-case-accelerators/my-accelerator/
├── config.yaml       # Module metadata (required)
├── deploy.sh         # Your deployment entry point (required)
├── README.md         # What it does, prerequisites (required)
└── ...               # Your accelerator's own code, IaC, etc.
```

### config.yaml

```yaml
name: my-accelerator
version: 1.0.0
iac_type: external
dependencies:
  - governance/subscription    # List Quick Suite modules you depend on
params:
  - name: my_custom_param
    required: true
    type: string
  - name: optional_param
    required: false
    default: "some-default"
    type: string
```

Key fields:

- `iac_type: external` — tells the orchestrator to call your `deploy.sh` instead of CDK or Terraform
- `dependencies` — modules that must be deployed before yours. The orchestrator handles ordering automatically.
- `params` — parameters your accelerator needs. Consultants set these in `manifest.yaml`. Supported types: `string`, `arn`, `email`, `json`, `aws_region`.

### deploy.sh

The orchestrator calls your script with manifest params injected as environment variables:

| Manifest param | Environment variable |
|---|---|
| `region` | `QS_PARAM_REGION` |
| `document_bucket` | `QS_PARAM_DOCUMENT_BUCKET` |
| `identity_store_id` | `QS_PARAM_IDENTITY_STORE_ID` |
| (any param) | `QS_PARAM_<UPPER_SNAKE_CASE>` |

Additional variables:

| Variable | Description |
|---|---|
| `QS_PROJECT` | Project name from manifest |
| `QS_AUTO_APPROVE` | Set to `1` if running in non-interactive mode |

Example `deploy.sh`:

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying My Accelerator..."

REGION="${QS_PARAM_REGION:-us-east-1}"
BUCKET="${QS_PARAM_MY_CUSTOM_PARAM:?'my_custom_param is required in manifest.yaml'}"

# Use whatever deployment tool your accelerator already uses:

# Option A: Your accelerator uses CDK
cd "$SCRIPT_DIR" && npx cdk deploy --all --require-approval never

# Option B: Your accelerator uses Terraform
cd "$SCRIPT_DIR/terraform" && terraform init && terraform apply -auto-approve

# Option C: Your accelerator uses SAM
cd "$SCRIPT_DIR" && sam build && sam deploy --no-confirm-changeset

# Option D: Your accelerator uses plain CloudFormation
aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/template.yaml" \
  --stack-name "my-accelerator" \
  --parameter-overrides Bucket="$BUCKET" \
  --capabilities CAPABILITY_IAM

echo "✓ My Accelerator deployed"
```

### What the orchestrator guarantees

1. Your dependencies are deployed before your script runs
2. Manifest params are validated (required, type, pattern) before your script runs
3. If your script exits non-zero, the orchestrator stops and reports the failure with recovery instructions
4. The `QS_AUTO_APPROVE` flag tells you whether the operator wants interactive prompts

### status.sh (optional)

If you provide a `status.sh` script, the orchestrator's `status` command will call it to check for drift. The same `QS_PARAM_*` environment variables are available.

- Exit code 0 → no drift detected
- Exit code non-zero → drift detected (stdout is shown to the operator)

```bash
#!/bin/bash
set -euo pipefail
# Check if our resources still exist and match expected state
aws cloudformation describe-stacks --stack-name "my-accelerator" > /dev/null 2>&1 || {
  echo "Stack not found — needs redeployment"
  exit 1
}
echo "Stack exists and is healthy"
```

If no `status.sh` is provided, the module shows as "unknown" in the status report.

## Deep integration (CDK shim) — upgrade path

Use this when:

- Terraform-only customers need to deploy your accelerator without your native tooling
- Your accelerator needs to export CloudFormation outputs that other Quick Suite modules consume
- You want your accelerator to appear in the CDK app alongside governance and data-source modules

### What changes

```
use-case-accelerators/my-accelerator/
├── config.yaml                # iac_type changes to 'cdk'
├── deploy.sh                  # Kept as fallback for non-CDK deployments
├── cdk/
│   └── index.ts               # Thin CDK construct wrapping your deployment
├── cfn-template.yaml          # Auto-generated by CI from cdk/
├── terraform/
│   └── main.tf                # Thin HCL wrapper around cfn-template.yaml
├── README.md
└── ...
```

### config.yaml changes

```yaml
name: my-accelerator
version: 1.0.0
iac_type: cdk                  # Changed from 'external'
dependencies:
  - governance/subscription
params:
  - name: my_custom_param
    required: true
    type: string
artifacts:
  - cfn-template.yaml          # Added
  - terraform/main.tf          # Added
```

### The CDK shim

The shim is a thin CDK construct that wraps your accelerator's deployment. It doesn't rewrite your IaC — it calls it:

```typescript
import { Construct } from 'constructs';
import { PythonCustomResource } from '../../../core/constructs';

export class MyAccelerator extends Construct {
  constructor(scope: Construct, id: string, props: { bucket: string }) {
    super(scope, id);

    // Option A: Wrap an existing CFN template
    new CfnInclude(this, 'Upstream', {
      templateFile: 'use-case-accelerators/my-accelerator/upstream-template.yaml',
      parameters: { Bucket: props.bucket },
    });

    // Option B: Use a custom resource to call your deploy logic
    new PythonCustomResource(this, 'Deploy', {
      resourcePrefix: 'MyAccelerator',
      handler: 'deploy_handler.handler',
      codePath: 'use-case-accelerators/my-accelerator/lambdas',
      resourceProperties: { Bucket: props.bucket },
    });
  }
}
```

### CI generates the CFN bridge

Once you have a CDK shim, the existing CI pipeline (`synth-cfn.sh`) synthesizes `cfn-template.yaml` and the thin Terraform wrapper lets Terraform-only customers deploy via `aws_cloudformation_stack`.

### When NOT to upgrade

- Your accelerator has complex multi-stack deployments that don't fit in a single CFN template
- Your accelerator uses a deployment tool that manages its own state (e.g., Terraform with remote state)
- The integration overhead isn't justified by the number of Terraform-only customers

In these cases, stay with Standard integration. The `deploy.sh` approach is production-ready and fully supported.

## Adding your accelerator to the starter kit

1. Create your module directory under `use-case-accelerators/`
2. Add `config.yaml`, `deploy.sh`, and `README.md`
3. Register the git remote in `bootstrap.sh` (the `ACCELERATOR_REPOS` array)
4. Add your module to the manifest template in `templates/customer-project/manifest.yaml` (commented out)
5. Test: uncomment your module in `manifest.yaml`, set params, run `./deploy.sh`

## Responsibility model

| Concern | Your responsibility | Starter kit responsibility |
|---|---|---|
| Deployment logic | You own `deploy.sh` and all IaC | Orchestrator calls it with params |
| Param validation | Define types/patterns in `config.yaml` | Orchestrator validates before calling you |
| Dependency ordering | Declare dependencies in `config.yaml` | Orchestrator deploys deps first |
| Versioning | Tag releases in your repo | `bootstrap.sh` pulls by version tag |
| Testing | You test your accelerator | Starter kit tests the integration contract |
| CDK/TF parity | Only if you choose Deep integration | CFN bridge CI handles synthesis |
