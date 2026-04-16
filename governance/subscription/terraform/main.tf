variable "account_name" {
  type    = string
  default = "QuickSuiteStarterKit"
}

variable "notification_email" { type = string }

variable "admin_pro_group_name" { type = string }

# Look up the IAM Identity Center instance in this account
data "aws_ssoadmin_instances" "this" {}

locals {
  identity_center_instance_arn = tolist(data.aws_ssoadmin_instances.this.arns)[0]
}

# @secure_recommendation: Use IAM_IDENTITY_CENTER auth to leverage centralized workforce identity management
resource "aws_quicksight_account_subscription" "this" {
  account_name                     = var.account_name
  authentication_method            = "IAM_IDENTITY_CENTER"
  edition                          = "ENTERPRISE"
  notification_email               = var.notification_email
  iam_identity_center_instance_arn = local.identity_center_instance_arn
  admin_pro_group                  = [var.admin_pro_group_name]
}

output "identity_center_instance_arn" {
  value = local.identity_center_instance_arn
}

output "account_subscription_status" {
  value = aws_quicksight_account_subscription.this.account_subscription_status
}
