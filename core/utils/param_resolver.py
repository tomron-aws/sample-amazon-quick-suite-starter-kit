"""Param resolver — fetches secret/config values from external sources.

Supports three reference prefixes in manifest param values:
  ssm:/path/to/param          → AWS SSM Parameter Store
  secretsmanager:secret-name  → AWS Secrets Manager
  env:VARIABLE_NAME           → Environment variable

Plaintext values (no prefix) pass through unchanged.
"""

from __future__ import annotations

import os
import sys


def _resolve_ssm(ref: str) -> str:
    """Fetch a value from SSM Parameter Store."""
    import boto3

    path = ref[len("ssm:"):]
    try:
        client = boto3.client("ssm")
        response = client.get_parameter(Name=path, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"ERROR: Failed to resolve SSM param '{path}': {e}")
        sys.exit(1)


def _resolve_secretsmanager(ref: str) -> str:
    """Fetch a value from Secrets Manager."""
    import boto3

    secret_id = ref[len("secretsmanager:"):]
    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_id)
        return response["SecretString"]
    except Exception as e:
        print(f"ERROR: Failed to resolve secret '{secret_id}': {e}")
        sys.exit(1)


def _resolve_env(ref: str) -> str:
    """Fetch a value from an environment variable."""
    var_name = ref[len("env:"):]
    value = os.environ.get(var_name)
    if value is None:
        print(f"ERROR: Environment variable '{var_name}' not set (referenced in manifest)")
        sys.exit(1)
    return value


# Resolver registry: prefix → resolver function
_RESOLVERS = {
    "ssm:": _resolve_ssm,
    "secretsmanager:": _resolve_secretsmanager,
    "env:": _resolve_env,
}


def resolve_params(manifest: dict) -> dict:
    """Resolve all param references in a manifest, returning a new manifest with resolved values.

    Plaintext values pass through unchanged. Reference values (ssm:, secretsmanager:, env:)
    are fetched from their respective sources.
    """
    params = manifest.get("params", {})
    if not params:
        return manifest

    resolved = dict(manifest)
    resolved["params"] = dict(params)
    refs_found = False

    for key, value in params.items():
        if not isinstance(value, str):
            continue
        for prefix, resolver in _RESOLVERS.items():
            if value.startswith(prefix):
                if not refs_found:
                    print("Resolving param references...")
                    refs_found = True
                resolved_value = resolver(value)
                resolved["params"][key] = resolved_value
                # Mask the value in output for security
                display = resolved_value[:4] + "***" if len(resolved_value) > 4 else "***"
                print(f"  ✓ {key}: {prefix}... → {display}")
                break

    if refs_found:
        print("")
    return resolved
