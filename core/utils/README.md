# Core: Utils (Operator Tools)

CLI tools for managing Quick Suite users, groups, and monitoring usage.

## Tools

- `manage-users` — Create, update, delete IAM Identity Center users and assign to Quick Suite groups
- `manage-scim-groups` — Map SCIM-synced groups (from Entra ID) to QuickSight roles
- `monitor` — List Quick Suite users, groups, and account summary

## Setup

```bash
cd core/utils
make build
```

## Usage

```bash
# User management
uv run manage-users setup-groups
uv run manage-users create-user --username jdoe --email jdoe@example.com --given-name John --family-name Doe
uv run manage-users list-users

# SCIM group mapping
uv run manage-scim-groups assign-group-to-role --group-name "MyEntraGroup" --role READER_PRO

# Monitoring
uv run monitor account-summary
uv run monitor list-users
```
