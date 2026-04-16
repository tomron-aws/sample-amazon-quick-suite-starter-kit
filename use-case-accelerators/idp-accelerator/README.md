# Use Case Accelerator: IDP Accelerator

Intelligent Document Processing accelerator integrated with Quick Suite dashboards.

## Integration tier

Standard (deploy-script). See [Accelerator Integration Guide](../../docs/accelerator-integration-guide.md).

## Prerequisites

- `governance/subscription` module deployed (declared as dependency)
- An S3 bucket for document ingestion (`document_bucket` param)

## Manifest configuration

```yaml
modules:
  - use-case-accelerators/idp-accelerator@v1.0.0

params:
  document_bucket: my-documents-bucket
```

## How it deploys

The orchestrator calls `deploy.sh` with manifest params as `QS_PARAM_*` environment variables. The script handles all IDP-specific infrastructure using the accelerator's native tooling.

## Source

Managed as a git subtree from the upstream IDP accelerator repository. Run `bootstrap.sh` to pull or update.
