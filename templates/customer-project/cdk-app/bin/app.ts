#!/usr/bin/env node
import { App, Stack } from 'aws-cdk-lib/core';
import { readFileSync } from 'fs';
import { load } from 'js-yaml';
import { QuickSuiteSubscription } from '../../governance/subscription/cdk';

interface Manifest {
  project: string;
  modules: string[];
  params: Record<string, string>;
}

const manifest = load(readFileSync('manifest.yaml', 'utf8')) as Manifest;
const app = new App();
const stack = new Stack(app, `${manifest.project}-stack`, {});

for (const mod of manifest.modules) {
  const base = mod.split('@')[0];

  if (base === 'governance/subscription') {
    new QuickSuiteSubscription(stack, 'Subscription', {
      identityCenterInstanceArn: manifest.params.identity_center_instance_arn,
      identityStoreId: manifest.params.identity_store_id,
      accountName: manifest.params.account_name,
      adminUserEmail: manifest.params.admin_user_email,
      adminProGroupName: manifest.params.admin_pro_group,
    });
  }

  // Add additional module imports here as they are built
}
