# Cleanup and Deletion

How to remove your Quick Suite deployment.

!!! warning "Data Loss"

    Destroying the QuickSight subscription deletes all dashboards, datasets, analyses, topics, and user configurations. This cannot be undone.

## Cleanup Steps

### 1. Destroy Terraform Resources

From the `generated/` directory:

```bash
cd generated
terraform destroy
```

This removes all Terraform-managed resources in reverse dependency order:

- QuickSight dashboards, topics, datasets, data sources
- S3 bucket and IAM roles
- Custom permissions and role assignments
- QuickSight account subscription

!!! note "Topic Cleanup"

    Topics created via the AWS CLI provisioner are automatically deleted by the destroy provisioner.

### 2. Delete the QuickSight Subscription (if not managed by Terraform)

If the subscription was created outside of Terraform or the destroy didn't remove it:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws quicksight delete-account-subscription --aws-account-id "$ACCOUNT_ID"
```

### 3. Remove IAM Identity Center Groups (optional)

Groups created during setup are not managed by Terraform. Remove them if no longer needed:

```bash
IDENTITY_STORE_ID="<your-identity-store-id>"

# List groups
aws identitystore list-groups --identity-store-id "$IDENTITY_STORE_ID"

# Delete each group
aws identitystore delete-group \
  --identity-store-id "$IDENTITY_STORE_ID" \
  --group-id <group-id>
```

### 4. Clean Up Local Files

```bash
rm -rf generated/
```

## Verifying Cleanup

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Confirm subscription is gone
aws quicksight describe-account-subscription \
  --aws-account-id "$ACCOUNT_ID" 2>&1 | grep -q "ResourceNotFoundException" && \
  echo "✓ Subscription deleted" || echo "⚠ Subscription still active"

# Confirm S3 bucket is gone
aws s3 ls | grep quicksuite-data && \
  echo "⚠ Bucket still exists" || echo "✓ Bucket deleted"
```

## See Also

- [Getting Started](getting-started.md) — deployment guide
