<div align="center">

# Amazon Quick Suite Starter Kit

Modular starter kit for deploying [Amazon Quick Suite](https://aws.amazon.com/quicksuite/) with [AWS IAM Identity Center](https://aws.amazon.com/iam/identity-center/)

<div align="center">
  <a href="https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/graphs/commit-activity"><img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/aws-samples/sample-amazon-quick-suite-starter-kit"/></a>
  <a href="https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/issues"><img alt="GitHub open issues" src="https://img.shields.io/github/issues/aws-samples/sample-amazon-quick-suite-starter-kit"/></a>
  <a href="https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/pulls"><img alt="GitHub open pull requests" src="https://img.shields.io/github/issues-pr/aws-samples/sample-amazon-quick-suite-starter-kit"/></a>
  <a href="https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/aws-samples/sample-amazon-quick-suite-starter-kit"/></a>
</div>

</div>

## What is This?

A modular, composable toolkit for deploying Amazon Quick Suite. It serves as both:

- **A reusable asset library** — pick the modules you need
- **A delivery template** — clone, customize `manifest.yaml`, and deploy

## Quick Start

1. Clone the repo
2. Edit `manifest.yaml` — select modules and fill in your parameters
3. Run `./deploy.sh`

## Project Structure

```
├── manifest.yaml                  # Module selection + params (edit this)
├── deploy.sh                      # Single deploy entry point
│
├── governance/                    # Account setup and access control
│   ├── subscription/              # Quick Suite subscription (CDK)
│   ├── permissions/               # IAM Identity Center permissions
│   └── themes/                    # Quick Suite themes
│
├── data-sources/                  # Data source connectors
│   ├── redshift/
│   ├── athena/
│   └── glue/
│
├── use-case-accelerators/         # Standalone accelerators (git subtree)
│   ├── idp-accelerator/           # Intelligent Document Processing
│   └── live-meeting-assistant/
│
├── agentcore-agents/              # AI agent configurations
│   ├── agent1/
│   └── agent2/
│
├── core/                          # Shared infrastructure
│   ├── custom-resources/          # CloudFormation custom resource Lambdas
│   └── utils/                     # Operator CLI tools + orchestrator
│
├── templates/                     # Consultant starting point
│   └── customer-project/
│
└── docs/                          # Documentation
```

## How It Works

Each module has a `config.yaml` declaring its IaC type, dependencies, and parameters:

```yaml
name: subscription
version: 0.1.0
iac_type: cdk          # cdk | terraform | external | config-only
dependencies:
  - core/custom-resources
params:
  - name: identity_center_instance_arn
    required: true
```

The orchestrator reads `manifest.yaml`, groups modules by IaC type, and dispatches:

- **CDK modules** → `cdk deploy`
- **Terraform modules** → `terraform apply`
- **External modules** → module's own `deploy.sh`
- **Config-only modules** → API calls / config push

### Terraform-only customers

CDK modules ship a pre-synthesized `cfn-template.yaml` + thin Terraform wrapper. No CDK CLI needed — everything runs via `terraform apply`.

## Modules

| Module | Type | Status |
|---|---|---|
| `governance/subscription` | CDK | ✅ Implemented |
| `governance/permissions` | CDK | Placeholder |
| `governance/themes` | Config-only | Placeholder |
| `data-sources/redshift` | CDK | Placeholder |
| `data-sources/athena` | CDK | Placeholder |
| `data-sources/glue` | CDK | Placeholder |
| `use-case-accelerators/idp-accelerator` | External | Placeholder |
| `use-case-accelerators/live-meeting-assistant` | External | Placeholder |
| `agentcore-agents/agent1` | Config-only | Placeholder |
| `agentcore-agents/agent2` | Config-only | Placeholder |

## Operator Tools

CLI tools for managing users, groups, and monitoring are in `core/utils/`:

```bash
cd core/utils && make build

# User management
uv run manage-users list-users
uv run manage-users create-user --username jdoe --email jdoe@example.com --given-name John --family-name Doe

# SCIM group mapping
uv run manage-scim-groups assign-group-to-role --group-name "MyGroup" --role READER_PRO

# Monitoring
uv run monitor account-summary
```

## Documentation

- [Full Documentation](https://aws-samples.github.io/sample-amazon-quick-suite-starter-kit/)
- [Refactor Plan](docs/REFACTOR_PLAN.md) — architecture decisions and module contract

## Contributing

If you find this starter kit helpful, please ⭐ star the repository!

For feature requests or bug reports, please [open an issue](https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/issues/new).

For development and contribution guidelines, see [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

See [LICENSE](./LICENSE) file.

## Contributors

<a href="https://github.com/aws-samples/sample-amazon-quick-suite-starter-kit/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=aws-samples/sample-amazon-quick-suite-starter-kit" />
</a>
