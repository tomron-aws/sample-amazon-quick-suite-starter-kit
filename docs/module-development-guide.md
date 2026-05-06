# Module Development Guide

How to add a new Terraform module to the Quick Suite Starter Kit.

For external accelerators, see the [Accelerator Integration Guide](accelerator-integration-guide.md).

## Quick Checklist

1. Create the module directory
2. Write `config.yaml`
3. Write the Terraform module
4. Add to the manifest
5. Test with `generate` + `terraform plan`

## Step-by-Step

### 1. Create the Module Directory

Pick the right parent based on what the module does:

```
governance/my-module/terraform/          # IAM, permissions, subscription
quicksight-resources/data-sources/       # Data source connectors
quicksight-resources/data-sets/          # Dataset definitions
quicksight-resources/topics/             # Q Topics
quicksight-resources/dashboards/         # Dashboards
quicksight-resources/analyses/           # Analyses
aws-resources/                           # Shared AWS infrastructure
```

### 2. Write config.yaml

```yaml
name: my-module
version: 0.1.0
status: preview              # ready | preview | planned
iac_type: terraform
dependencies:
  - governance/subscription  # modules that must deploy before this one
params:
  - name: my_required_param
    required: true
    type: string
  - name: my_optional_param
    required: false
    default: "some-default"
```

Supported param types: `string`, `arn`, `email`, `json`, `aws_region`.

### 3. Write the Terraform Module

Create `terraform/main.tf`:

```hcl
variable "my_required_param" { type = string }
variable "my_optional_param" {
  type    = string
  default = "some-default"
}

resource "aws_quicksight_..." "this" {
  # Your resources here
}

output "my_output" {
  value = aws_quicksight_....this.arn
}
```

Key conventions:

- Variable names must match the param names in `config.yaml`
- Use `output` blocks for values other modules need — the generator auto-wires outputs to dependent modules when param names match
- For resources without Terraform support (e.g. topics), use `terraform_data` with `local-exec` provisioners

### 4. Add to the Manifest

Edit `manifest.yaml`:

```yaml
modules:
  - governance/subscription
  - my-new-module                # add your module

params:
  my_required_param: "value"     # add required params
```

### 5. Test

```bash
# Validate
python3 core/utils/orchestrator.py validate

# Generate
python3 core/utils/orchestrator.py generate

# Review
cd generated && terraform plan
```

## Cross-Module Output Wiring

The generator automatically wires module outputs to dependent modules. If module B depends on module A, and module B has a param named `data_set_arn`, and module A has an `output "data_set_arn"`, the generator produces:

```hcl
module "b" {
  source       = "../path/to/b/terraform"
  data_set_arn = module.a.data_set_arn    # auto-wired
  depends_on   = [module.a]
}
```

The param is excluded from `variables.tf` and `terraform.tfvars` since it's not user-facing.

## Module Status Lifecycle

- `planned` — directory and config.yaml exist but no implementation. Orchestrator blocks deployment.
- `preview` — functional but not production-hardened. Orchestrator warns during validation.
- `ready` — fully implemented and tested. Safe for customer deployments.

## See Also

- [Accelerator Integration Guide](accelerator-integration-guide.md) — for external modules with their own deploy scripts
