# Use Case Accelerator: Live Meeting Assistant

Live Meeting Assistant accelerator integrated with Quick Suite.

## Integration tier

Standard (deploy-script). See [Accelerator Integration Guide](../../docs/accelerator-integration-guide.md).

## Prerequisites

- No Quick Suite module dependencies

## Manifest configuration

```yaml
modules:
  - use-case-accelerators/live-meeting-assistant@v1.0.0
```

## How it deploys

The orchestrator calls `deploy.sh` with manifest params as `QS_PARAM_*` environment variables.

## Source

Managed as a git subtree from the upstream Live Meeting Assistant repository. Run `bootstrap.sh` to pull or update.
