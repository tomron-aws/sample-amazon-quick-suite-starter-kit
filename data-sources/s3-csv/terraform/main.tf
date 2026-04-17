variable "bucket_name" { type = string }
variable "quicksight_role_arn" { type = string }
variable "csv_key" { type = string }
variable "admin_pro_group_name" { type = string }
variable "dataset_name" {
  type    = string
  default = "airline-revenue"
}

data "aws_caller_identity" "current" {}

locals {
  admin_group_arn = "arn:aws:quicksight:us-east-1:${data.aws_caller_identity.current.account_id}:group/default/${var.admin_pro_group_name}"
}

# QuickSight needs a manifest.json that points to the CSV
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
  data_source_id = "${var.dataset_name}-s3"
  name           = "${var.dataset_name}-s3-source"
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
    actions   = [
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

resource "aws_quicksight_data_set" "this" {
  data_set_id = var.dataset_name
  name        = var.dataset_name
  import_mode = "SPICE"

  permissions {
    actions = [
      "quicksight:DescribeDataSet",
      "quicksight:DescribeDataSetPermissions",
      "quicksight:PassDataSet",
      "quicksight:DescribeIngestion",
      "quicksight:ListIngestions",
      "quicksight:UpdateDataSet",
      "quicksight:DeleteDataSet",
      "quicksight:CreateIngestion",
      "quicksight:CancelIngestion",
      "quicksight:UpdateDataSetPermissions",
    ]
    principal = local.admin_group_arn
  }

  physical_table_map {
    physical_table_map_id = "s3-source"
    s3_source {
      data_source_arn = aws_quicksight_data_source.s3.arn
      input_columns {
        name = "flight_date"
        type = "STRING"
      }
      input_columns {
        name = "origin"
        type = "STRING"
      }
      input_columns {
        name = "destination"
        type = "STRING"
      }
      input_columns {
        name = "fare_class"
        type = "STRING"
      }
      input_columns {
        name = "booking_channel"
        type = "STRING"
      }
      input_columns {
        name = "passengers"
        type = "STRING"
      }
      input_columns {
        name = "avg_fare"
        type = "STRING"
      }
      input_columns {
        name = "revenue"
        type = "STRING"
      }
      input_columns {
        name = "load_factor"
        type = "STRING"
      }
      upload_settings {
        format           = "CSV"
        delimiter        = ","
        contains_header  = true
        text_qualifier   = "DOUBLE_QUOTE"
      }
    }
  }

  logical_table_map {
    logical_table_map_id = "s3-source-logical"
    alias                = var.dataset_name
    source {
      physical_table_id = "s3-source"
    }
    data_transforms {
      cast_column_type_operation {
        column_name     = "flight_date"
        new_column_type = "DATETIME"
        format          = "yyyy-MM-dd"
      }
    }
    data_transforms {
      cast_column_type_operation {
        column_name     = "passengers"
        new_column_type = "INTEGER"
      }
    }
    data_transforms {
      cast_column_type_operation {
        column_name     = "avg_fare"
        new_column_type = "DECIMAL"
      }
    }
    data_transforms {
      cast_column_type_operation {
        column_name     = "revenue"
        new_column_type = "DECIMAL"
      }
    }
    data_transforms {
      cast_column_type_operation {
        column_name     = "load_factor"
        new_column_type = "DECIMAL"
      }
    }
  }
}

output "data_source_arn" {
  value = aws_quicksight_data_source.s3.arn
}

output "data_set_arn" {
  value = aws_quicksight_data_set.this.arn
}
