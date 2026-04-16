# Infrastructure

Shared infrastructure for Quick Suite data ingestion.

## Resources

- S3 bucket for data files (versioned, encrypted, public access blocked, SSL enforced)
- IAM role for QuickSight to read from the bucket (least-privilege, scoped to this bucket)

## Usage

Upload CSV/JSON data files to the bucket. Reference the bucket name and IAM role ARN in data source modules.
