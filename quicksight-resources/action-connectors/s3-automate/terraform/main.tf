terraform {
  required_providers {
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
  }
}

variable "quicksight_role_arn" { type = string }
variable "action_connector_id" {
  type    = string
  default = "s3-automate"
}
variable "action_connector_name" {
  type    = string
  default = "S3 Automate"
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

resource "awscc_quicksight_action_connector" "s3_knowledge_base" {
  action_connector_id = var.action_connector_id
  aws_account_id      = local.account_id
  name                = var.action_connector_name
  type                = "AMAZON_S3"

  authentication_config = {
    authentication_type = "IAM"
    authentication_metadata = {
      iam_connection_metadata = {
        role_arn = var.quicksight_role_arn
      }
    }
  }
}

output "action_connector_arn" {
  value = awscc_quicksight_action_connector.s3_knowledge_base.arn
}
