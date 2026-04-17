# Operator Tools

Tools for managing your Quick Suite deployment.

## Managing Your Deployment

### The Manifest File

The `manifest.yaml` at the repo root is the single source of truth for your deployment. It controls which modules are deployed and their configuration.

```yaml
modules:
  - governance/subscription
  - governance/permissions
  - governance/group-assignments
  - aws-resources
  - quicksight-resources/data-sources/s3-csv
  - quicksight-resources/data-sets/airline-revenue
  - quicksight-resources/topics/airline-revenue
  - quicksight-resources/dashboards/airline-revenue

params:
  account_name: MyCompanyQuickSuite
  notification_email: admin@example.com
  admin_pro_group_name: QuickSuiteAdmins
  # ...
```

### Adding or Removing Modules

1. Edit `manifest.yaml` — comment/uncomment modules, update params
2. Regenerate: `python3 core/utils/orchestrator.py generate`
3. Review: `cd generated && terraform plan`
4. Apply: `terraform apply`

### Validating Your Configuration

```bash
python3 core/utils/orchestrator.py validate
```

Checks that all selected modules exist, required params are set, and values match expected types/patterns.

### Estimating Costs

```bash
./cost.sh
```

Shows QuickSight per-user licensing costs and infrastructure costs per module.

## Post-Deployment Management

### [User Management Runbook](user-management-runbook.md)

Manage IAM Identity Center users and groups, and assign them to Quick Suite roles.

### [Monitoring Runbook](monitoring-runbook.md)

Monitor Quick Suite usage, users, and account status.

### [Cleanup and Deletion](../cleanup.md)

Safely remove your Quick Suite deployment.
