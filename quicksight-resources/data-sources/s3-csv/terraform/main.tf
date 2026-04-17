variable "bucket_name" { type = string }
variable "quicksight_role_arn" { type = string }
variable "csv_key" { type = string }
variable "admin_pro_group_name" { type = string }
variable "data_source_name" {
  type    = string
  default = "s3-csv"
}

data "aws_caller_identity" "current" {}

locals {
  admin_group_arn = "arn:aws:quicksight:us-east-1:${data.aws_caller_identity.current.account_id}:group/default/${var.admin_pro_group_name}"
}

resource "aws_s3_object" "manifest" {
  bucket = var.bucket_name
  key    = "${var.csv_key}.manifest.json"
  content = jsonencode({
    fileLocations = [{ URIs = ["s3://${var.bucket_name}/${var.csv_key}"] }]
    globalUploadSettings = {
      format         = "CSV"
      delimiter      = ","
      textqualifier  = "\""
      containsHeader = true
    }
  })
  content_type = "application/json"
}

resource "aws_quicksight_data_source" "s3" {
  data_source_id = "${var.data_source_name}-s3"
  name           = "${var.data_source_name}-s3-source"
  type           = "S3"

  parameters {
    s3 {
      manifest_file_location {
        bucket = var.bucket_name
        key    = aws_s3_object.manifest.key
      }
      role_arn = var.quicksight_role_arn
    }
  }

  permission {
    actions = [
      "quicksight:DescribeDataSource",
      "quicksight:DescribeDataSourcePermissions",
      "quicksight:PassDataSource",
      "quicksight:UpdateDataSource",
      "quicksight:DeleteDataSource",
      "quicksight:UpdateDataSourcePermissions",
    ]
    principal = local.admin_group_arn
  }
}

output "data_source_arn" {
  value = aws_quicksight_data_source.s3.arn
}
