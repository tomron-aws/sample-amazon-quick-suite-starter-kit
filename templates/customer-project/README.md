# Customer Project Template

Use this as a starting point for a new Quick Suite engagement.

## Getting Started

1. Clone the repo
2. Copy `manifest.yaml` to the repo root (or edit the root `manifest.yaml`)
3. Fill in your customer's parameters
4. Uncomment the modules you need
5. Run `./deploy.sh`

## Structure

```
manifest.yaml          # Your module selections and params
deploy.sh              # Single entry point
governance/            # Subscription, permissions, themes
data-sources/          # Redshift, Athena, Glue connectors
use-case-accelerators/ # IDP, Live Meeting Assistant, etc.
agentcore-agents/      # AI agent configurations
core/                  # Shared custom resources and utilities
```

## Adding modules

Edit `manifest.yaml` to include additional modules:

```yaml
modules:
  - governance/subscription
  - data-sources/redshift
  - use-case-accelerators/idp-accelerator@v2.1.0
```

Then re-run `./deploy.sh`.
