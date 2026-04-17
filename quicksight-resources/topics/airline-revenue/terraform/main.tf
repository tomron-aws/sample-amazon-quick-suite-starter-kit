variable "data_set_arn" { type = string }
variable "topic_id" {
  type    = string
  default = "airline-revenue-topic"
}
variable "topic_name" {
  type    = string
  default = "Airline Revenue Analysis"
}
variable "topic_description" {
  type    = string
  default = "Analyze SkyLine Airways route revenue by fare class, booking channel, and time period"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "terraform_data" "topic" {
  input = {
    account_id = data.aws_caller_identity.current.account_id
    region     = data.aws_region.current.name
    topic_id   = var.topic_id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws quicksight create-topic \
        --aws-account-id ${data.aws_caller_identity.current.account_id} \
        --topic-id ${var.topic_id} \
        --topic '{
          "Name": "${var.topic_name}",
          "Description": "${var.topic_description}",
          "DataSets": [{
            "DatasetArn": "${var.data_set_arn}",
            "DatasetName": "airline-revenue",
            "DatasetDescription": "${var.topic_description}",
            "DataAggregation": {
              "DatasetRowDateGranularity": "DAY",
              "DefaultDateColumnName": "flight_date"
            },
            "Columns": [
              {"ColumnName": "flight_date", "ColumnFriendlyName": "Flight Date", "ColumnDescription": "Date of the flight", "ColumnDataRole": "DIMENSION", "TimeGranularity": "DAY", "IsIncludedInTopic": true},
              {"ColumnName": "origin", "ColumnFriendlyName": "Origin Airport", "ColumnDescription": "Departure airport code", "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": true, "ColumnSynonyms": ["departure", "from"]},
              {"ColumnName": "destination", "ColumnFriendlyName": "Destination Airport", "ColumnDescription": "Arrival airport code", "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": true, "ColumnSynonyms": ["arrival", "to"]},
              {"ColumnName": "fare_class", "ColumnFriendlyName": "Fare Class", "ColumnDescription": "Ticket fare class", "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": true, "ColumnSynonyms": ["cabin", "class"]},
              {"ColumnName": "booking_channel", "ColumnFriendlyName": "Booking Channel", "ColumnDescription": "How the ticket was booked", "ColumnDataRole": "DIMENSION", "IsIncludedInTopic": true, "ColumnSynonyms": ["channel", "source"]},
              {"ColumnName": "passengers", "ColumnFriendlyName": "Passengers", "ColumnDescription": "Number of passengers", "ColumnDataRole": "MEASURE", "IsIncludedInTopic": true, "Aggregation": "SUM", "AllowedAggregations": ["SUM", "AVERAGE", "COUNT", "MAX", "MIN"]},
              {"ColumnName": "avg_fare", "ColumnFriendlyName": "Average Fare", "ColumnDescription": "Average ticket price", "ColumnDataRole": "MEASURE", "IsIncludedInTopic": true, "Aggregation": "AVERAGE", "DefaultFormatting": {"DisplayFormat": "CURRENCY", "DisplayFormatOptions": {"CurrencySymbol": "$", "FractionDigits": 2}}},
              {"ColumnName": "revenue", "ColumnFriendlyName": "Revenue", "ColumnDescription": "Total revenue", "ColumnDataRole": "MEASURE", "IsIncludedInTopic": true, "Aggregation": "SUM", "DefaultFormatting": {"DisplayFormat": "CURRENCY", "DisplayFormatOptions": {"CurrencySymbol": "$", "FractionDigits": 2}}, "ColumnSynonyms": ["sales", "income"]},
              {"ColumnName": "load_factor", "ColumnFriendlyName": "Load Factor", "ColumnDescription": "Seat occupancy rate", "ColumnDataRole": "MEASURE", "IsIncludedInTopic": true, "Aggregation": "AVERAGE", "DefaultFormatting": {"DisplayFormat": "PERCENT", "DisplayFormatOptions": {"FractionDigits": 1}}}
            ]
          }],
          "UserExperienceVersion": "NEW_READER_EXPERIENCE"
        }' \
        --region ${data.aws_region.current.name}
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      aws quicksight delete-topic \
        --aws-account-id ${self.input.account_id} \
        --topic-id ${self.input.topic_id} \
        --region ${self.input.region} || true
    EOT
  }
}

output "topic_id" {
  value = var.topic_id
}
