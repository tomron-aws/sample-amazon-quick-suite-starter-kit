variable "data_set_arn" { type = string }
variable "admin_pro_group_name" { type = string }
variable "dashboard_id" {
  type    = string
  default = "airline-revenue-dashboard"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  admin_group_arn = "arn:aws:quicksight:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:group/default/${var.admin_pro_group_name}"
  ds_id           = "airline-ds"
}

resource "aws_quicksight_dashboard" "this" {
  dashboard_id        = var.dashboard_id
  name                = "Airline Revenue Dashboard"
  version_description = "v1"

  permissions {
    actions = [
      "quicksight:DescribeDashboard",
      "quicksight:ListDashboardVersions",
      "quicksight:UpdateDashboardPermissions",
      "quicksight:QueryDashboard",
      "quicksight:UpdateDashboard",
      "quicksight:DeleteDashboard",
      "quicksight:DescribeDashboardPermissions",
      "quicksight:UpdateDashboardPublishedVersion",
    ]
    principal = local.admin_group_arn
  }

  definition {
    data_set_identifiers_declarations {
      data_set_arn = var.data_set_arn
      identifier   = local.ds_id
    }

    sheets {
      title    = "Revenue Overview"
      sheet_id = "revenue-overview"

      # Revenue over time — line chart
      visuals {
        line_chart_visual {
          visual_id = "revenue-over-time"
          title {
            format_text { plain_text = "Revenue Over Time" }
          }
          chart_configuration {
            field_wells {
              line_chart_aggregated_field_wells {
                category {
                  date_dimension_field {
                    field_id = "date-cat"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "flight_date"
                    }
                    date_granularity = "MONTH"
                  }
                }
                values {
                  numerical_measure_field {
                    field_id = "revenue-val"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "revenue"
                    }
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # Revenue by fare class — bar chart
      visuals {
        bar_chart_visual {
          visual_id = "revenue-by-fare-class"
          title {
            format_text { plain_text = "Revenue by Fare Class" }
          }
          chart_configuration {
            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "fare-cat"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "fare_class"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    field_id = "fare-rev"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "revenue"
                    }
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # Revenue by route — table
      visuals {
        table_visual {
          visual_id = "revenue-by-route"
          title {
            format_text { plain_text = "Revenue by Route" }
          }
          chart_configuration {
            field_wells {
              table_aggregated_field_wells {
                group_by {
                  categorical_dimension_field {
                    field_id = "origin-dim"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "origin"
                    }
                  }
                }
                group_by {
                  categorical_dimension_field {
                    field_id = "dest-dim"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "destination"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    field_id = "route-rev"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "revenue"
                    }
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
                values {
                  numerical_measure_field {
                    field_id = "route-pax"
                    column {
                      data_set_identifier = local.ds_id
                      column_name         = "passengers"
                    }
                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

output "dashboard_arn" {
  value = aws_quicksight_dashboard.this.arn
}
