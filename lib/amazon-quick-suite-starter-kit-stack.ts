import { Stack, StackProps, CustomResource, Duration } from 'aws-cdk-lib';
import {
  Runtime,
  Code,
  Function as LambdaFunction,
} from 'aws-cdk-lib/aws-lambda';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import { CfnInstance } from 'aws-cdk-lib/aws-sso';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

const RESOURCE_PREFIX = 'QuickSuiteStarterKit';

export class AmazonQuickSuiteStarterKitStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const identityCenterInstanceArn = this.node.tryGetContext(
      'IDENTITY_CENTER_INSTANCE_ARN',
    );
    const identityStoreId = this.node.tryGetContext('IDENTITY_STORE_ID');
    const accountName =
      this.node.tryGetContext('QUICK_SUITE_ACCOUNT_NAME') ||
      'QuickSuiteStarterKit';
    const adminUserEmail =
      this.node.tryGetContext('QUICK_SUITE_ADMIN_USER_EMAIL') ||
      'admin@example.com';
    const adminProGroupName =
      this.node.tryGetContext('QUICK_SUITE_ADMIN_PRO_GROUP') ||
      'QuickSuiteAdminPro';
    const groupRoleMappings =
      this.node.tryGetContext('QUICK_SUITE_GROUP_ROLE_MAPPINGS') || [];

    if (!identityCenterInstanceArn || !identityStoreId) {
      throw new Error(
        'IDENTITY_CENTER_INSTANCE_ARN and IDENTITY_STORE_ID must be provided in cdk.json context when using external identity provider',
      );
    }

    const quickSuiteSetupFunction = new LambdaFunction(
      this,
      `${RESOURCE_PREFIX}QuickSuiteSetupFunction`,
      {
        runtime: Runtime.PYTHON_3_12,
        handler: 'custom_resource_handler_for_quick_suite_setup.handler',
        code: Code.fromAsset('lambdas', {
          bundling: {
            image: Runtime.PYTHON_3_12.bundlingImage,
            command: [
              'bash',
              '-c',
              'echo "Installing dependencies..." && pip install -q -r /asset-input/src/requirements.txt -t /asset-output && echo "Copying source files..." && cp -r /asset-input/src/* /asset-output && echo "Build complete!"',
            ],
          },
        }),
        functionName: `${RESOURCE_PREFIX}QuickSuiteSetupFunction`,
        timeout: Duration.minutes(15),
      },
    );

    // IAM policies for Quick Suite setup
    // Reference: https://docs.aws.amazon.com/quicksuite/latest/userguide/iam.html
    // Policy examples: https://docs.aws.amazon.com/quicksuite/latest/userguide/iam-policy-examples.html

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'quicksight:CreateAccountSubscription',
          'quicksight:DescribeAccountSubscription',
          'quicksight:DeleteAccountSubscription',
          'quicksight:Subscribe',
        ],
        resources: [`arn:aws:quicksight:${this.region}:${this.account}:*`],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'quicksight:CreateNamespace',
          'quicksight:DescribeNamespace',
          'quicksight:DeleteNamespace',
        ],
        resources: [
          `arn:aws:quicksight:${this.region}:${this.account}:namespace/*`,
        ],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['sso:DescribeInstance', 'sso:ListInstances'],
        resources: [identityCenterInstanceArn],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'sso:CreateApplication',
          'sso:DeleteApplication',
          'sso:DescribeApplication',
          'sso:CreateApplicationAssignment',
          'sso:DeleteApplicationAssignment',
          'sso:PutApplicationGrant',
          'sso:DeleteApplicationGrant',
          'sso:PutApplicationAuthenticationMethod',
          'sso:PutApplicationAccessScope',
        ],
        resources: ['*'],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'iam:CreateRole',
          'iam:AttachRolePolicy',
          'iam:DetachRolePolicy',
          'iam:GetRole',
          'iam:PassRole',
          'iam:ListAttachedRolePolicies',
          'iam:GetPolicy',
          'iam:CreatePolicyVersion',
          'iam:DeletePolicyVersion',
          'iam:GetPolicyVersion',
          'iam:ListPolicyVersions',
          'iam:DeleteRole',
          'iam:ListRoles',
          'iam:CreatePolicy',
          'iam:ListEntitiesForPolicy',
          'iam:listPolicies',
          'iam:CreateServiceLinkedRole',
        ],
        resources: ['*'],
      }),
    );

    // Organizations permissions: https://docs.aws.amazon.com/quicksight/latest/user/iam-policy-examples.html#security_iam_id-based-policy-examples-all-access-enterprise-edition-sso
    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'organizations:DescribeOrganization',
          'organizations:ListAWSServiceAccessForOrganization',
          's3:ListAllMyBuckets',
          'athena:ListDataCatalogs',
          'athena:GetDataCatalog',
          'ds:AuthorizeApplication',
          'ds:UnauthorizeApplication',
          'ds:CheckAlias',
          'ds:CreateAlias',
          'ds:DescribeDirectories',
          'ds:DescribeTrusts',
          'ds:DeleteDirectory',
          'ds:CreateIdentityPoolDirectory',
        ],
        resources: ['*'],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'identitystore:DescribeUser',
          'identitystore:ListUsers',
          'identitystore:CreateUser',
          'identitystore:CreateGroup',
          'identitystore:DescribeGroup',
          'identitystore:CreateGroupMembership',
          'identitystore:ListGroupMemberships',
        ],
        resources: [
          `arn:aws:identitystore::${this.account}:identitystore/${identityStoreId}`,
          `arn:aws:identitystore:::user/*`,
          `arn:aws:identitystore:::group/*`,
          `arn:aws:identitystore:::membership/*`,
        ],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'quicksight:CreateRoleMembership',
          'quicksight:DeleteRoleMembership',
          'quicksight:ListRoleMemberships',
        ],
        resources: ['*'],
      }),
    );

    quickSuiteSetupFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'identitystore:ListGroups',
          'sso-directory:DescribeUser',
          'sso-directory:DescribeGroup',
          'sso:ListApplicationAssignments',
          'organizations:ListAWSServiceAccessForOrganization',
          'user-subscriptions:CreateClaim',
          'user-subscriptions:UpdateClaim',
        ],
        resources: ['*'],
      }),
    );

    const provider = new Provider(
      this,
      `${RESOURCE_PREFIX}QuickSuiteSetupProvider`,
      {
        onEventHandler: quickSuiteSetupFunction,
      },
    );

    new CustomResource(this, `${RESOURCE_PREFIX}QuickSuiteSetup`, {
      serviceToken: provider.serviceToken,
      properties: {
        IdentityCenterInstanceArn: identityCenterInstanceArn,
        IdentityStoreId: identityStoreId,
        AccountName: accountName,
        AdminUserEmail: adminUserEmail,
        AdminProGroupName: adminProGroupName,
        GroupRoleMappings: JSON.stringify(groupRoleMappings),
        ForceUpdate: Date.now().toString(),
      },
    });
  }
}
