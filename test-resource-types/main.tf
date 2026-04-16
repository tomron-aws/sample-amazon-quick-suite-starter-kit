terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# Look up the IAM Identity Center instance in this account
data "aws_ssoadmin_instances" "this" {}

locals {
  identity_center_instance_arn = tolist(data.aws_ssoadmin_instances.this.arns)[0]
}

# @secure_recommendation: Use IAM_IDENTITY_CENTER auth to leverage centralized workforce identity management
resource "aws_quicksight_account_subscription" "this" {
  account_name                    = var.account_name
  authentication_method           = "IAM_IDENTITY_CENTER"
  edition                         = "ENTERPRISE"
  notification_email              = var.notification_email
  iam_identity_center_instance_arn = local.identity_center_instance_arn
  admin_pro_group                  = [var.admin_pro_group_name]
}

# @secure_recommendation: Explicit role membership ensures group-to-role mapping is tracked in state and auditable
resource "aws_quicksight_role_membership" "admin_pro" {
  member_name = var.admin_pro_group_name
  role        = "ADMIN_PRO"
  namespace   = "default"

  depends_on = [aws_quicksight_account_subscription.this]
}

resource "aws_quicksight_role_membership" "reader_pro" {
  for_each    = toset(var.reader_pro_group_names)
  member_name = each.value
  role        = "READER_PRO"
  namespace   = "default"

  depends_on = [aws_quicksight_account_subscription.this]
}

# @secure_recommendation: Deny all sharing capabilities for READER_PRO to enforce least-privilege data access
resource "aws_quicksight_custom_permissions" "reader_pro_no_sharing" {
  custom_permissions_name = "reader-pro-no-sharing"

  capabilities {
    share_analyses        = "DENY"
    share_dashboards      = "DENY"
    share_datasets        = "DENY"
    share_data_sources    = "DENY"
    create_shared_folders = "DENY"
    rename_shared_folders = "DENY"
  }

  depends_on = [aws_quicksight_account_subscription.this]
}

resource "aws_quicksight_role_custom_permission" "reader_pro" {
  role                    = "READER_PRO"
  custom_permissions_name = aws_quicksight_custom_permissions.reader_pro_no_sharing.custom_permissions_name
}
