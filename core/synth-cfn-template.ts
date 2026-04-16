#!/usr/bin/env npx ts-node
/**
 * Synthesizes a single CDK module into a standalone CloudFormation template.
 *
 * Usage:
 *   npx ts-node core/synth-cfn-template.ts governance/subscription
 *
 * Outputs:
 *   governance/subscription/cfn-template.yaml
 *
 * The template uses CloudFormation Parameters so Terraform wrappers can
 * pass values in without needing the CDK CLI.
 */
import { App, CfnParameter, Stack } from 'aws-cdk-lib';
import { readFileSync, writeFileSync } from 'fs';
import { load } from 'js-yaml';
import { resolve } from 'path';

// --- Module registry ---
// Each CDK module must be registered here with its construct and param mapping.
import { QuickSuiteSubscription } from '../governance/subscription/cdk';
import { QuickSuitePermissions } from '../governance/permissions/cdk';
import { RedshiftDataSource } from '../data-sources/redshift/cdk';
import { AthenaDataSource } from '../data-sources/athena/cdk';
import { GlueDataSource } from '../data-sources/glue/cdk';

interface ModuleConfig {
  name: string;
  params: { name: string; required?: boolean; default?: string }[];
}

function loadModuleConfig(modulePath: string): ModuleConfig {
  const raw = readFileSync(resolve(modulePath, 'config.yaml'), 'utf8');
  return load(raw) as ModuleConfig;
}

function synthModule(modulePath: string): void {
  const config = loadModuleConfig(modulePath);
  const app = new App();
  const stack = new Stack(app, `${config.name}-stack`);

  // Create CFN Parameters from the module's config.yaml params
  const cfnParams: Record<string, CfnParameter> = {};
  for (const p of config.params || []) {
    cfnParams[p.name] = new CfnParameter(stack, p.name, {
      type: 'String',
      ...(p.default != null ? { default: p.default } : {}),
    });
  }

  // --- Module-specific wiring ---
  // Add a case for each CDK module that needs cfn-template.yaml.
  const base = modulePath.replace(/\/$/, '');
  switch (base) {
    case 'governance/subscription':
      new QuickSuiteSubscription(stack, 'Subscription', {
        identityCenterInstanceArn: cfnParams['identity_center_instance_arn'].valueAsString,
        identityStoreId: cfnParams['identity_store_id'].valueAsString,
        accountName: cfnParams['account_name']?.valueAsString,
        adminUserEmail: cfnParams['admin_user_email'].valueAsString,
        adminProGroupName: cfnParams['admin_pro_group'].valueAsString,
        groupRoleMappings: [], // Passed as JSON string via CFN parameter
      });
      break;
    case 'governance/permissions':
      new QuickSuitePermissions(stack, 'Permissions', {
        identityStoreId: cfnParams['identity_store_id'].valueAsString,
      });
      break;
    case 'data-sources/redshift':
      new RedshiftDataSource(stack, 'RedshiftDataSource', {
        redshiftClusterId: cfnParams['redshift_cluster_id'].valueAsString,
      });
      break;
    case 'data-sources/athena':
      new AthenaDataSource(stack, 'AthenaDataSource', {
        athenaWorkgroup: cfnParams['athena_workgroup']?.valueAsString,
      });
      break;
    case 'data-sources/glue':
      new GlueDataSource(stack, 'GlueDataSource', {
        glueDatabase: cfnParams['glue_database'].valueAsString,
      });
      break;
    default:
      console.error(`ERROR: No synth mapping for module '${base}'`);
      console.error('Register it in core/synth-cfn-template.ts');
      process.exit(1);
  }

  // Synthesize and write the template
  const assembly = app.synth();
  const template = assembly.getStackByName(`${config.name}-stack`).template;
  const yaml = JSON.stringify(template, null, 2);
  const outPath = resolve(base, 'cfn-template.yaml');
  writeFileSync(outPath, yaml);
  console.log(`✓ Wrote ${outPath}`);
}

// --- CLI ---
const modulePath = process.argv[2];
if (!modulePath) {
  console.error('Usage: npx ts-node core/synth-cfn-template.ts <module-path>');
  console.error('Example: npx ts-node core/synth-cfn-template.ts governance/subscription');
  process.exit(1);
}
synthModule(modulePath);
