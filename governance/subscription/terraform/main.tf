variable "identity_center_instance_arn" { type = string }
variable "identity_store_id" { type = string }
variable "account_name" { type = string; default = "QuickSuiteStarterKit" }
variable "admin_user_email" { type = string }
variable "admin_pro_group" { type = string }
variable "group_role_mappings" { type = string; default = "[]" }

resource "aws_cloudformation_stack" "quick_suite_subscription" {
  name          = "quick-suite-subscription"
  template_body = file("${path.module}/../cfn-template.yaml")
  capabilities  = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]

  parameters = {
    IdentityCenterInstanceArn = var.identity_center_instance_arn
    IdentityStoreId           = var.identity_store_id
    AccountName               = var.account_name
    AdminUserEmail            = var.admin_user_email
    AdminProGroupName         = var.admin_pro_group
    GroupRoleMappings         = var.group_role_mappings
  }
}
