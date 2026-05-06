# S3 Automate Action Connector

Creates an Amazon S3 action connector for use with **Amazon Quick Automate** workflows.

## What This Does

This module provisions an S3 action connector via the `AWS::QuickSight::ActionConnector` resource (AWSCC provider). The connector allows Quick Automate workflows to perform S3 operations (upload files, manage buckets, retrieve objects) using IAM role-based authentication.

This replaces the manual admin console step: **Manage Quick Suite → AWS Actions → New Action → Amazon S3**.

## What This Does NOT Do

- **Does not create a knowledge base.** S3 knowledge bases (for Amazon Q document Q&A) are created separately through the Amazon Quick console UI — there is no API for knowledge base creation today.
- **Does not grant QuickSight data source access.** For S3 as a data source (SPICE/direct query), use the `data-sources/s3-csv` module instead.

## Architecture

```
┌─────────────────────────────────┐
│  Amazon Quick Automate          │
│  (workflows, automations)       │
└──────────────┬──────────────────┘
               │ uses
┌──────────────▼──────────────────┐
│  S3 Action Connector            │  ← this module
│  (IAM auth, AMAZON_S3 type)     │
└──────────────┬──────────────────┘
               │ assumes role
┌──────────────▼──────────────────┐
│  IAM Role (QuickSuiteS3DataAccess) │  ← from aws-resources module
│  (s3:GetObject, s3:ListBucket, etc) │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│  S3 Bucket                      │  ← from aws-resources module
└─────────────────────────────────┘
```

## Parameters

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `quicksight_role_arn` | No (wired from aws-resources) | — | IAM role ARN for S3 access |
| `action_connector_id` | No | `s3-automate` | Unique connector identifier |
| `action_connector_name` | No | `S3 Automate` | Display name in Quick Suite |

## Outputs

| Name | Description |
|------|-------------|
| `action_connector_arn` | ARN of the created action connector |

## Note on Knowledge Bases

If you need an S3 knowledge base for Amazon Q document search, you must:
1. Deploy this module (creates the S3 connector)
2. Go to Amazon Quick console → **Knowledge** → **Add** → select **Amazon S3**
3. Select files/folders and create the knowledge base

There is currently no API for step 2-3.
