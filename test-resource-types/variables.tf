variable "region" {
  type    = string
  default = "us-east-1"
}

variable "account_name" {
  description = "Unique QuickSight account name (appears at sign-in)"
  type        = string
}

variable "notification_email" {
  description = "Email for QuickSight notifications"
  type        = string
}

variable "admin_pro_group_name" {
  description = "IAM Identity Center group name to assign the ADMIN_PRO role"
  type        = string
}

variable "reader_pro_group_names" {
  description = "IAM Identity Center group names to assign the READER_PRO role"
  type        = list(string)
  default     = []
}
