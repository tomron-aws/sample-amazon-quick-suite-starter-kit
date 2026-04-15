# Governance: Subscription

Deploys an Amazon Quick Suite (QuickSight) Enterprise subscription with IAM Identity Center authentication.

## What it does

- Creates a QuickSight account subscription with IAM Identity Center
- Verifies admin group exists in Identity Store (synced from external IdP)
- Assigns groups to QuickSight roles based on configured mappings

## Usage

Include in your `manifest.yaml`:

```yaml
modules:
  - governance/subscription
params:
  identity_center_instance_arn: "arn:aws:sso:::instance/ssoins-XXXXX"
  identity_store_id: "d-XXXXX"
  admin_user_email: "admin@example.com"
  admin_pro_group: "QuickSuiteAdminPro"
```

## CDK Construct

```typescript
import { QuickSuiteSubscription } from './governance/subscription/cdk';

new QuickSuiteSubscription(stack, 'Subscription', {
  identityCenterInstanceArn: '...',
  identityStoreId: '...',
  accountName: 'MyAccount',
  adminUserEmail: 'admin@example.com',
  adminProGroupName: 'QuickSuiteAdminPro',
});
```
