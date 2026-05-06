# Asana Action Connector for Amazon Quick Suite
# Uses the hashicorp/awscc provider to create a native ASANA action connector.

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

variable "secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing the Asana Personal Access Token (JSON: {\"pat\": \"<token>\"})"
  type        = string
}

variable "workspace_id" {
  description = "Asana workspace ID to scope connector actions (optional)"
  type        = string
  default     = ""
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

data "aws_secretsmanager_secret_version" "asana_pat" {
  secret_id = var.secret_arn
}

locals {
  account_id     = data.aws_caller_identity.current.account_id
  region         = data.aws_region.current.name
  connector_id   = "asana-connector"
  asana_base_url = "https://app.asana.com/api/1.0"

  # Expects secret JSON: {"pat": "<asana_personal_access_token>"}
  secret_value = jsondecode(data.aws_secretsmanager_secret_version.asana_pat.secret_string)
  asana_pat    = local.secret_value["pat"]
}

# ==============================================================================
# Asana Action Connector
# ==============================================================================

resource "awscc_quicksight_action_connector" "asana" {
  aws_account_id      = local.account_id
  action_connector_id = local.connector_id
  name                = "Asana"
  type                = "ASANA"
  description         = "Asana action connector for task and project management via Quick Flows and Automate"

  authentication_config = {
    authentication_type = "API_KEY"

    authentication_metadata = {
      api_key_connection_metadata = {
        base_endpoint = local.asana_base_url
        api_key       = local.asana_pat
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
    value = "asana-action-connector"
  }, {
    key   = "ManagedBy"
    value = "Terraform"
  }]
}

# ==============================================================================
# IAM Policy: Allow Quick Suite to read the Asana PAT secret
# ==============================================================================

resource "aws_iam_policy" "quicksight_read_asana_secret" {
  name        = "quick-asana-connector-secret-access"
  description = "Allows Amazon Quick Suite to read the Asana PAT from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowQuickSightReadAsanaSecret"
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
  description = "ARN of the Asana action connector"
  value       = awscc_quicksight_action_connector.asana.arn
}
