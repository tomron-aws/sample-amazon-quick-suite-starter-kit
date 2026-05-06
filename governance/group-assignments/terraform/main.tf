variable "admin_pro_group_name" { type = string }

variable "reader_pro_group_names" {
  type    = list(string)
  default = []
}

# @secure_recommendation: Explicit role membership ensures group-to-role mapping is tracked in state and auditable
resource "aws_quicksight_role_membership" "admin_pro" {
  member_name = var.admin_pro_group_name
  role        = "ADMIN_PRO"
  namespace   = "default"
}

resource "aws_quicksight_role_membership" "reader_pro" {
  for_each    = toset(var.reader_pro_group_names)
  member_name = each.value
  role        = "READER_PRO"
  namespace   = "default"
}
