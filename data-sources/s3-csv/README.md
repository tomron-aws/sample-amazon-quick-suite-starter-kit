# S3 CSV Data Source

Creates a QuickSight data source and SPICE dataset from a CSV file in S3.

## Resources

- S3 manifest object (auto-generated, points to the CSV)
- `aws_quicksight_data_source` (S3 type with IAM role)
- `aws_quicksight_data_set` (SPICE import with column definitions)

## Prerequisites

- CSV file must already exist in the S3 bucket
- Bucket and IAM role from `aws-resources` module
