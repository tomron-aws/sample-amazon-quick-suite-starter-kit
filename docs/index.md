# Amazon Quick Suite Starter Kit

Automated deployment of [Amazon Quick Suite](https://aws.amazon.com/quicksuite/) using [AWS IAM Identity Center](https://aws.amazon.com/iam/identity-center/) as an identity provider.

## What is Amazon Quick Suite?

[Amazon Quick Suite](https://aws.amazon.com/quicksuite/) is an agentic AI-powered digital workspace that answers your questions and turns those answers into actions using agentic teammates for research, business insights, and automation.

Quick Suite helps you make better decisions faster by unifying AI agents for research, business insights, and automation. You can connect to diverse data sources, create interactive dashboards, build intelligent automations, and get immediate insights through natural language conversations with AI agents.

!!! note "QuickSight Service Name"

    Amazon Quick Suite is the new name for Amazon QuickSight. The underlying AWS service still uses QuickSight APIs, service principals, and console pages. This is why you'll see `quicksight` in IAM policies, CLI commands, and Terraform resources. See the [Amazon Quick Suite documentation](https://docs.aws.amazon.com/quicksight/) for API references.

## What This Starter Kit Provides

This starter kit automates the deployment and management of Quick Suite with:

- **Manifest-driven deployment** — edit `manifest.yaml` to select modules and set parameters, then generate and apply Terraform
- **Modular Terraform modules** — pick the governance, data source, and accelerator modules you need
- **User management** — CLI tools for managing users and groups
- **Monitoring** — tools to track usage and costs
- **Best practices** — pre-configured security and governance settings

## How It Works

```
manifest.yaml          ← Select modules, fill in params
       │
       ▼
  orchestrator.py generate
       │
       ▼
templates/customer-project/tf-app/
  ├── main.tf           ← Module blocks with dependencies
  ├── variables.tf      ← Union of all module params
  └── terraform.tfvars  ← Values from manifest
       │
       ▼
  terraform init → plan → apply
```

Each module lives in its own directory with a `config.yaml` declaring its parameters and dependencies. The orchestrator reads the manifest, resolves dependencies, and generates a standard Terraform project you can plan and apply with normal Terraform workflows.

## Quick Start

1. **[Getting Started](getting-started.md)** — deploy Quick Suite in ~15 minutes
2. **[Cleanup](cleanup.md)** — remove resources when done

## Available Modules

| Module | Description | Status |
|---|---|---|
| `governance/subscription` | QuickSight account subscription with IAM Identity Center | ✅ Ready |
| `governance/permissions` | Custom permission profiles (e.g. restrict sharing for Reader Pro) | ✅ Ready |
| `governance/group-assignments` | Map Identity Center groups to QuickSight roles | ✅ Ready |
| `data-sources/redshift` | Redshift data source connector | 🔧 Preview |
| `data-sources/athena` | Athena data source connector | 🔧 Preview |
| `data-sources/glue` | Glue data source connector | 🔧 Preview |
| `use-case-accelerators/idp-accelerator` | Intelligent Document Processing | 🔧 Preview |

## Role Mappings

This starter kit uses [AWS IAM Identity Center](https://docs.aws.amazon.com/singlesignon/) groups mapped to Quick Suite roles:

| Identity Center Group | Quick Suite Role | Notes |
|---|---|---|
| Configured via `admin_pro_group_name` | Admin Pro | Set during subscription creation |
| Configured via `reader_pro_group_names` | Reader Pro | Assigned via group-assignments module |

For role capabilities and pricing, see [Amazon Quick Suite Pricing](https://aws.amazon.com/quicksuite/pricing/).

## Documentation

- [Getting Started](getting-started.md) — deployment guide
- [Cleanup Instructions](cleanup.md) — remove resources
- [Module Development Guide](module-development-guide.md) — creating new modules
- [Accelerator Integration Guide](accelerator-integration-guide.md) — adding external accelerators

## Support

For issues or questions, please [open an issue](https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/issues) on GitHub.
