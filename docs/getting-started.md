# Getting Started

This guide walks you through deploying Amazon Quick Suite with [AWS IAM Identity Center](https://docs.aws.amazon.com/singlesignon/) using Terraform.

## Prerequisites

- [AWS CLI](https://docs.aws.amazon.com/cli/) configured with appropriate credentials
- [Terraform](https://developer.hashicorp.com/terraform/install) 1.5+
- Python 3.12+ with `pyyaml` installed (`pip install pyyaml`)

!!! warning "Region Restrictions"

    Amazon Quick Suite AI capabilities are only available in certain AWS regions. Check the [Quick Suite FAQs](https://aws.amazon.com/quicksuite/faqs/) for current regional availability.

## Step 1: Configure Your Deployment

Edit `manifest.yaml` to select modules and set parameters:

```yaml
project: my-quick-suite-deployment

modules:
  - governance/subscription
  - governance/permissions
  - governance/group-assignments

params:
  account_name: MyCompanyQuickSuite
  notification_email: quicksuite-admin@mycompany.com
  admin_pro_group_name: QuickSuiteAdmins
  reader_pro_group_names: '["QuickSuiteReaders"]'
  region: us-east-1
```

### Configuration Options

**account_name** (default: `QuickSuiteStarterKit`)
Display name for your Quick Suite account.

!!! danger "Important"

    - End users must type this name when signing in — choose wisely!
    - **Cannot be changed** after account creation
    - Must be **globally unique** across all AWS accounts

**notification_email** (required)
Email address for Quick Suite notifications.

**admin_pro_group_name** (required)
Name of the [AWS IAM Identity Center](https://docs.aws.amazon.com/singlesignon/) group for Quick Suite administrators. This group must already exist in your Identity Center identity store.

**reader_pro_group_names** (optional, default: `[]`)
List of Identity Center group names to assign the Reader Pro role. Example: `'["Analysts", "Viewers"]'`

### Using secret references (recommended for CI/CD)

Instead of putting sensitive values directly in `manifest.yaml`, you can reference them from external sources:

```yaml
params:
  # From SSM Parameter Store
  notification_email: "ssm:/quicksuite/notification_email"

  # From Secrets Manager
  admin_pro_group_name: "secretsmanager:quicksuite/admin-group"

  # From environment variables (useful in CI pipelines)
  region: "env:AWS_REGION"

  # Plaintext (fine for non-sensitive values)
  account_name: MyCompanyQuickSuite
```

| Prefix | Source | Use for |
|---|---|---|
| `ssm:/path` | SSM Parameter Store | ARNs, IDs, shared config |
| `secretsmanager:name` | Secrets Manager | Emails, credentials |
| `env:VAR_NAME` | Environment variable | CI pipeline values |
| (no prefix) | Plaintext in manifest | Non-sensitive defaults |

## Step 2: Generate Terraform Project

```bash
python3 core/utils/orchestrator.py generate
```

This reads your manifest, resolves dependencies, and generates a Terraform project in `templates/customer-project/tf-app/` with:

- `main.tf` — module blocks with dependency ordering
- `variables.tf` — all parameters as Terraform variables
- `terraform.tfvars` — values from your manifest

You can also review the generated files before deploying:

```bash
cat templates/customer-project/tf-app/main.tf
```

## Step 3: Deploy

```bash
cd templates/customer-project/tf-app
terraform init
terraform plan
terraform apply
```

Or use the one-shot deploy script:

```bash
./deploy.sh                  # Interactive (prompts for approval)
./deploy.sh --auto-approve   # CI mode (no prompts)
```

This deployment will:

1. Auto-discover your [AWS IAM Identity Center](https://docs.aws.amazon.com/singlesignon/) instance
2. Create the Quick Suite subscription with IAM Identity Center authentication
3. Assign your admin group to the Admin Pro role
4. Assign reader groups to the Reader Pro role (if configured)
5. Apply custom permission profiles (e.g. restrict sharing for Reader Pro)

!!! warning "Do Not Access Quick Suite Yet"

    After deployment completes, **do not** navigate to <https://us-east-1.quicksight.aws.amazon.com> yet. You must create an admin user first (Step 4), otherwise you won't be able to sign in.

## Step 4: Enable Email OTP for API-Created Users

!!! danger "CRITICAL: Required Before Creating Users"

    This is a **one-time manual step** that you must complete before creating users via the operator tools. Without this setting, users created via API will not receive the invite to sign in.

1. Open the [IAM Identity Center console](https://console.aws.amazon.com/singlesignon)
2. Choose **Settings** → **Authentication** tab
3. In **Standard authentication**, choose **Configure**
4. Check **Send email OTP** and save

## Step 5: Create Your First Admin User

Navigate to the operator tools directory:

```bash
cd core/utils
```

Create an admin user:

```bash
uv run manage-users create-user \
  --username admin \
  --email admin@example.com \
  --given-name Admin \
  --family-name User \
  --group QUICK_SUITE_ADMIN
```

The user will receive an email to verify their address and set up MFA.

## Step 6: Access Quick Suite

1. Navigate to <https://us-east-1.quicksight.aws.amazon.com> (replace region if different)
2. Enter your Quick Suite account name
3. Sign in with your admin user credentials via IAM Identity Center

!!! success "You're Ready!"

    Your Quick Suite environment is now fully configured and ready to use!

## Step 7: Verify Deployment

```bash
cd core/utils
uv run monitor account-summary
```

## Estimate Costs (Optional)

Review estimated costs for your selected modules:

```bash
./cost.sh
```

## Next Steps

- [Operator Tools](operator-tools/index.md) — manage users and monitor usage
- [Module Development Guide](module-development-guide.md) — create new modules
- [Cleanup Instructions](cleanup.md) — remove resources when done
