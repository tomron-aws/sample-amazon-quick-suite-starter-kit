# Terraform Module: Amazon Bedrock Knowledge Base Action Connector for Amazon Quick Suite
# Purpose: Provisions a Bedrock Knowledge Base action connector enabling Quick Flows/Automate
#          to query and retrieve information from an existing Bedrock Knowledge Base.
# Pattern: Same structure as the s3-knowledge-base connector module (IAM auth).
#
# PREREQUISITE: An Amazon Bedrock Knowledge Base must already exist. This module
# references an existing KB by ID — it does not create one. The IAM role passed as
# quicksight_role_arn must have permissions to invoke bedrock-agent-runtime:Retrieve
# and bedrock-agent-runtime:RetrieveAndGenerate on the target Knowledge Base.

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

variable "knowledge_base_id" {
  description = "ID of the existing Amazon Bedrock Knowledge Base (e.g., ABCDEF1234)"
  type        = string
  validation {
    condition     = length(var.knowledge_base_id) > 0
    error_message = "Knowledge base ID must not be empty."
  }
}

variable "quicksight_role_arn" {
  description = "ARN of the IAM role that QuickSight assumes to invoke Bedrock Knowledge Base APIs"
  type        = string
  validation {
    condition     = can(regex("^arn:aws:iam::", var.quicksight_role_arn))
    error_message = "Must be a valid IAM role ARN."
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

locals {
  account_id   = data.aws_caller_identity.current.account_id
  region       = data.aws_region.current.name
  connector_id = "bedrock-kb-connector"
}

# ==============================================================================
# Bedrock Knowledge Base Action Connector
# ==============================================================================

resource "awscc_quicksight_action_connector" "bedrock_kb" {
  aws_account_id      = local.account_id
  action_connector_id = local.connector_id
  name                = "Bedrock Knowledge Base"
  type                = "AMAZON_BEDROCK_AGENT_RUNTIME"
  description         = "Amazon Bedrock Knowledge Base action connector for RAG queries via Quick Flows and Automate (KB ID: ${var.knowledge_base_id})"

  authentication_config = {
    authentication_type = "IAM"

    authentication_metadata = {
      iam_connection_metadata = {
        role_arn = var.quicksight_role_arn
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
    value = "bedrock-kb-action-connector"
  }, {
    key   = "ManagedBy"
    value = "Terraform"
  }, {
    key   = "KnowledgeBaseId"
    value = var.knowledge_base_id
  }]
}

# ==============================================================================
# IAM Policy: Permissions for the QuickSight role to invoke Bedrock KB
# ==============================================================================

resource "aws_iam_role_policy" "quicksight_bedrock_kb_access" {
  name = "quick-bedrock-kb-connector-access"
  role = element(split("/", var.quicksight_role_arn), length(split("/", var.quicksight_role_arn)) - 1)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowBedrockKBRetrieval"
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = "arn:aws:bedrock:${local.region}:${local.account_id}:knowledge-base/${var.knowledge_base_id}"
      },
      {
        Sid    = "AllowBedrockModelInvocation"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${local.region}::foundation-model/*"
      }
    ]
  })
}

# ==============================================================================
# Outputs
# ==============================================================================

output "action_connector_arn" {
  description = "ARN of the Bedrock Knowledge Base action connector"
  value       = awscc_quicksight_action_connector.bedrock_kb.arn
}
