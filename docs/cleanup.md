# Cleanup and Deletion

This guide explains how to properly remove your Amazon Quick Suite deployment to avoid ongoing costs and orphaned resources.

## Why manual cleanup is required

The CloudFormation custom resource handler intentionally does **not** delete the QuickSight subscription during stack deletion. QuickSight subscriptions contain dashboards, datasets, analyses, and user configurations that cannot be recovered once deleted. This is a safety measure to prevent accidental data loss.

When you run `cdk destroy`, the Lambda handler will log a warning with the exact cleanup steps. You can find these in CloudWatch Logs under the `/aws/lambda/QuickSuiteStarterKitQuickSuiteSetupFunction` log group.

## Cleanup steps

### 1. Delete the QuickSight subscription

This must be done **before** destroying the CDK stack (the stack's IAM roles are needed for the API call).

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Delete the subscription
aws quicksight delete-account-subscription --aws-account-id "$ACCOUNT_ID"
```

Alternatively, use the [QuickSight console](https://console.aws.amazon.com/quicksight/) to unsubscribe.

### 2. Destroy the CDK stack

```bash
npx cdk destroy --all
```

This removes the Lambda function, IAM roles, custom resource provider, and other infrastructure.

### 3. Remove IAM Identity Center groups (optional)

Groups created during setup are not automatically deleted. Remove them if no longer needed:

```bash
# List groups to find IDs
aws identitystore list-groups --identity-store-id <your-identity-store-id>

# Delete each group
aws identitystore delete-group \
  --identity-store-id <your-identity-store-id> \
  --group-id <group-id>
```

### 4. Clean up CloudWatch log groups (optional)

```bash
aws logs delete-log-group \
  --log-group-name /aws/lambda/QuickSuiteStarterKitQuickSuiteSetupFunction
```

## Verifying cleanup

After completing all steps, verify no resources remain:

```bash
# Confirm subscription is gone
aws quicksight describe-account-subscription \
  --aws-account-id "$ACCOUNT_ID" 2>&1 | grep -q "ResourceNotFoundException" && \
  echo "✓ Subscription deleted" || echo "⚠ Subscription still active"

# Confirm stack is gone
aws cloudformation describe-stacks \
  --stack-name "my-quick-suite-deployment-stack" 2>&1 | grep -q "does not exist" && \
  echo "✓ Stack deleted" || echo "⚠ Stack still exists"
```

## See also

- [Monitoring Runbook](operator-tools/monitoring-runbook.md) — check account status before cleanup
- [User Management Runbook](operator-tools/user-management-runbook.md) — manage users before deletion
