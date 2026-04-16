variable "bucket_name" { type = string }
variable "csv_key" { type = string }
variable "dataset_name" {
  type    = string
  default = "airline-revenue"
}

data "aws_caller_identity" "current" {}

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
    }
  }
}

resource "aws_quicksight_data_set" "this" {
  data_set_id = var.dataset_name
  name        = var.dataset_name
  import_mode = "SPICE"

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
        type = "INTEGER"
      }
      input_columns {
        name = "avg_fare"
        type = "DECIMAL"
      }
      input_columns {
        name = "revenue"
        type = "DECIMAL"
      }
      input_columns {
        name = "load_factor"
        type = "DECIMAL"
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
        column_name    = "flight_date"
        new_column_type = "DATETIME"
        format         = "yyyy-MM-dd"
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
