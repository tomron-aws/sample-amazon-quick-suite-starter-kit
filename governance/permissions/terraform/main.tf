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
}

resource "aws_quicksight_role_custom_permission" "reader_pro" {
  role                    = "READER_PRO"
  custom_permissions_name = aws_quicksight_custom_permissions.reader_pro_no_sharing.custom_permissions_name
}
