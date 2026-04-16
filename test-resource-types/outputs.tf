output "account_subscription_status" {
  value = aws_quicksight_account_subscription.this.account_subscription_status
}

output "identity_center_instance_arn" {
  value = local.identity_center_instance_arn
}
