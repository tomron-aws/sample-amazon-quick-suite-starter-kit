import { CustomResource, Duration } from 'aws-cdk-lib';
import { Runtime, Code, Function as LambdaFunction } from 'aws-cdk-lib/aws-lambda';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import { Provider } from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

const RESOURCE_PREFIX = 'QuickSuiteStarterKit';

export interface QuickSuiteSubscriptionProps {
  identityCenterInstanceArn: string;
  identityStoreId: string;
  accountName?: string;
  adminUserEmail: string;
  adminProGroupName: string;
  groupRoleMappings?: { groupName: string; role: string }[];
}

export class QuickSuiteSubscription extends Construct {
  constructor(scope: Construct, id: string, props: QuickSuiteSubscriptionProps) {
    super(scope, id);

    const {
      identityCenterInstanceArn,
      identityStoreId,
      accountName = 'QuickSuiteStarterKit',
      adminUserEmail,
      adminProGroupName,
      groupRoleMappings = [],
    } = props;

    const setupFunction = new LambdaFunction(this, `${RESOURCE_PREFIX}SetupFunction`, {
      runtime: Runtime.PYTHON_3_12,
      handler: 'custom_resource_handler_for_quick_suite_setup.handler',
      code: Code.fromAsset('core/custom-resources/lambdas', {
        bundling: {
          image: Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -q -r /asset-input/src/requirements.txt -t /asset-output && cp -r /asset-input/src/* /asset-output',
          ],
        },
      }),
      functionName: `${RESOURCE_PREFIX}QuickSuiteSetupFunction`,
      timeout: Duration.minutes(15),
    });

    const account = scope.node.tryGetContext('aws:cdk:account') || '*';
    const region = scope.node.tryGetContext('aws:cdk:region') || '*';

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'quicksight:CreateAccountSubscription',
        'quicksight:DescribeAccountSubscription',
        'quicksight:DeleteAccountSubscription',
        'quicksight:Subscribe',
      ],
      resources: [`arn:aws:quicksight:*:*:*`],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'quicksight:CreateNamespace',
        'quicksight:DescribeNamespace',
        'quicksight:DeleteNamespace',
      ],
      resources: [`arn:aws:quicksight:*:*:namespace/*`],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: ['sso:DescribeInstance', 'sso:ListInstances'],
      resources: [identityCenterInstanceArn],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'sso:CreateApplication', 'sso:DeleteApplication', 'sso:DescribeApplication',
        'sso:CreateApplicationAssignment', 'sso:DeleteApplicationAssignment',
        'sso:PutApplicationGrant', 'sso:DeleteApplicationGrant',
        'sso:PutApplicationAuthenticationMethod', 'sso:PutApplicationAccessScope',
      ],
      resources: ['*'],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'iam:CreateRole', 'iam:AttachRolePolicy', 'iam:DetachRolePolicy',
        'iam:GetRole', 'iam:PassRole', 'iam:ListAttachedRolePolicies',
        'iam:GetPolicy', 'iam:CreatePolicyVersion', 'iam:DeletePolicyVersion',
        'iam:GetPolicyVersion', 'iam:ListPolicyVersions', 'iam:DeleteRole',
        'iam:ListRoles', 'iam:CreatePolicy', 'iam:ListEntitiesForPolicy',
        'iam:listPolicies', 'iam:CreateServiceLinkedRole',
      ],
      resources: ['*'],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'organizations:DescribeOrganization', 'organizations:ListAWSServiceAccessForOrganization',
        's3:ListAllMyBuckets', 'athena:ListDataCatalogs', 'athena:GetDataCatalog',
        'ds:AuthorizeApplication', 'ds:UnauthorizeApplication', 'ds:CheckAlias',
        'ds:CreateAlias', 'ds:DescribeDirectories', 'ds:DescribeTrusts',
        'ds:DeleteDirectory', 'ds:CreateIdentityPoolDirectory',
      ],
      resources: ['*'],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'identitystore:DescribeUser', 'identitystore:ListUsers',
        'identitystore:CreateUser', 'identitystore:CreateGroup',
        'identitystore:DescribeGroup', 'identitystore:CreateGroupMembership',
        'identitystore:ListGroupMemberships',
      ],
      resources: [
        `arn:aws:identitystore::*:identitystore/${identityStoreId}`,
        'arn:aws:identitystore:::user/*',
        'arn:aws:identitystore:::group/*',
        'arn:aws:identitystore:::membership/*',
      ],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'quicksight:CreateRoleMembership', 'quicksight:DeleteRoleMembership',
        'quicksight:ListRoleMemberships',
      ],
      resources: ['*'],
    }));

    setupFunction.addToRolePolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        'identitystore:ListGroups', 'sso-directory:DescribeUser',
        'sso-directory:DescribeGroup', 'sso:ListApplicationAssignments',
        'organizations:ListAWSServiceAccessForOrganization',
        'user-subscriptions:CreateClaim', 'user-subscriptions:UpdateClaim',
      ],
      resources: ['*'],
    }));

    const provider = new Provider(this, `${RESOURCE_PREFIX}Provider`, {
      onEventHandler: setupFunction,
    });

    new CustomResource(this, `${RESOURCE_PREFIX}Setup`, {
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
