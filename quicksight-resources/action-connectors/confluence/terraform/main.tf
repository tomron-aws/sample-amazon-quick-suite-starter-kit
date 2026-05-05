# Terraform Module: Confluence Action Connector for Amazon Quick Suite
# Purpose: Provisions an Atlassian Confluence action connector enabling Quick Flows/Automate
#          to search, create, and update pages and spaces in Confluence.
# Pattern: Same structure as the Asana and s3-knowledge-base connector modules.

terraform {
  required_version = ">= 1.0"
  required_providers {
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ==============================================================================
# Variables (passed from manifest.yaml via orchestrator)
# ==============================================================================

variable "confluence_url" {
  description = "Base URL of the Confluence instance (e.g., https://yoursite.atlassian.net/wiki)"
  type        = string
  validation {
    condition     = can(regex("^https://", var.confluence_url))
    error_message = "Confluence URL must start with https://."
  }
}

variable "secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing Confluence API token or OAuth credentials"
  type        = string
  sensitive   = true
  validation {
    condition     = can(regex("^arn:aws:secretsmanager:", var.secret_arn))
    error_message = "Must be a valid Secrets Manager ARN."
  }
}

variable "admin_pro_group" {
  description = "IAM Identity Center group name granted full access to this connector"
  type        = string
}

# Manifest-level params that the orchestrator always passes
variable "identity_center_instance_arn" {
  type    = string
  default = ""
}

variable "identity_store_id" {
  type    = string
  default = ""
}

variable "account_name" {
  type    = string
  default = "QuickSuiteStarterKit"
}

variable "admin_user_email" {
  type    = string
  default = ""
}

variable "region" {
  type    = string
  default = "us-east-1"
}

# ==============================================================================
# Data Sources
# ==============================================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_secretsmanager_secret_version" "confluence_creds" {
  secret_id = var.secret_arn
}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  region       = data.aws_region.current.name
  connector_id = "confluence-connector"

  # Expects secret JSON: {"email": "<user@domain.com>", "api_token": "<token>"}
  secret_value = jsondecode(data.aws_secretsmanager_secret_version.confluence_creds.secret_string)
  api_token    = local.secret_value["api_token"]
  email        = local.secret_value["email"]
}

# ==============================================================================
# Confluence Action Connector
# ==============================================================================

resource "awscc_quicksight_action_connector" "confluence" {
  aws_account_id      = local.account_id
  action_connector_id = local.connector_id
  name                = "Confluence"
  type                = "ATLASSIAN_CONFLUENCE"
  description         = "Atlassian Confluence action connector for page and space management via Quick Flows and Automate"

  authentication_config = {
    authentication_type = "API_KEY"

    authentication_metadata = {
      api_key_connection_metadata = {
        base_endpoint = var.confluence_url
        api_key       = local.api_token
        email         = local.email
      }
    }
  }

  permissions = [{
    principal = "arn:aws:quicksight:${local.region}:${local.account_id}:group/default/${var.admin_pro_group}"
    actions = [
      "quicksight:DescribeActionConnector",
      "quicksight:ListActionConnectorActions",
      "quicksight:InvokeActionConnector",
      "quicksight:UpdateActionConnector",
      "quicksight:DeleteActionConnector"
    ]
  }]

  tags = [{
    key   = "Service"
    value = "Amazon-Quick"
  }, {
    key   = "Module"
    value = "confluence-action-connector"
  }, {
    key   = "ManagedBy"
    value = "Terraform"
  }]
}

# ==============================================================================
# IAM Policy: Allow Quick Suite service to read the Confluence credentials secret
# ==============================================================================

resource "aws_iam_policy" "quicksight_read_confluence_secret" {
  name        = "quick-confluence-connector-secret-access"
  description = "Allows Amazon Quick Suite to read the Confluence credentials from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowQuickSightReadConfluenceSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.secret_arn
      }
    ]
  })
}

# ==============================================================================
# Outputs
# ==============================================================================

output "action_connector_arn" {
  description = "ARN of the Confluence action connector"
  value       = awscc_quicksight_action_connector.confluence.arn
}
