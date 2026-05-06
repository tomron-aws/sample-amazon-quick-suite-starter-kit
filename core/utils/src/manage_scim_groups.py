"""CLI tool for mapping SCIM-synced groups to QuickSight roles."""

import sys

import boto3
import click
from botocore.exceptions import ClientError
from common.observability import logger

identitystore = boto3.client("identitystore", region_name="us-east-1")
quicksight = boto3.client("quicksight", region_name="us-east-1")
sso_admin = boto3.client("sso-admin", region_name="us-east-1")
sts = boto3.client("sts", region_name="us-east-1")


def get_identity_store_id() -> str:
    """Get the Identity Store ID from IAM Identity Center instance."""
    try:
        paginator = sso_admin.get_paginator("list_instances")
        for page in paginator.paginate():
            instances = page.get("Instances", [])
            if instances:
                identity_store_id = instances[0]["IdentityStoreId"]
                logger.info("Found Identity Store", extra={"identity_store_id": identity_store_id})
                return identity_store_id

        logger.error("No IAM Identity Center instances found")
        sys.exit(1)
    except ClientError as e:
        logger.exception("Failed to get Identity Store ID", extra={"error": str(e)})
        sys.exit(1)


def get_group_id(identity_store_id: str, group_name: str) -> str | None:
    """Get group ID by name."""
    try:
        paginator = identitystore.get_paginator("list_groups")
        for page in paginator.paginate(
            IdentityStoreId=identity_store_id,
            Filters=[{"AttributePath": "DisplayName", "AttributeValue": group_name}],
        ):
            groups = page.get("Groups", [])
            if groups:
                return groups[0]["GroupId"]
        return None
    except ClientError as e:
        logger.exception("Failed to get group", extra={"group_name": group_name, "error": str(e)})
        return None


@click.group()
def cli() -> None:
    """Manage QuickSight group-to-role mappings for SCIM-synced groups."""
    pass


@cli.command()
@click.option("--identity-store-id", help="Identity Store ID (auto-detected if not provided)")
def list_groups(identity_store_id: str | None) -> None:
    """List all groups in the Identity Store (synced from Entra ID)."""
    if not identity_store_id:
        identity_store_id = get_identity_store_id()

    try:
        paginator = identitystore.get_paginator("list_groups")
        groups = []

        for page in paginator.paginate(IdentityStoreId=identity_store_id):
            groups.extend(page.get("Groups", []))

        if not groups:
            click.echo("No groups found")
            return

        click.echo(f"\nFound {len(groups)} group(s) synced from Entra ID:\n")
        for group in groups:
            group_id = group["GroupId"]
            display_name = group.get("DisplayName", "N/A")
            description = group.get("Description", "N/A")

            click.echo(f"Group ID: {group_id}")
            click.echo(f"  Name: {display_name}")
            click.echo(f"  Description: {description}")
            click.echo()
    except ClientError as e:
        logger.exception("Failed to list groups", extra={"error": str(e)})
        click.echo(f"✗ Failed to list groups: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--group-name", required=True, help="Identity Center group name (synced from Entra ID)")
@click.option(
    "--role",
    required=True,
    type=click.Choice(["ADMIN", "AUTHOR", "READER", "ADMIN_PRO", "AUTHOR_PRO", "READER_PRO"]),
    help="QuickSight role to assign",
)
@click.option("--namespace", default="default", help="Quick Suite namespace (default: default)")
@click.option("--identity-store-id", help="Identity Store ID (auto-detected if not provided)")
def assign_group_to_role(
    group_name: str, role: str, namespace: str, identity_store_id: str | None
) -> None:
    """Assign an Identity Center group to a QuickSight role.
    
    Available roles:
    - ADMIN: Admin (legacy QuickSight)
    - AUTHOR: Author (legacy QuickSight)
    - READER: Reader (legacy QuickSight)
    - ADMIN_PRO: Admin Pro (Quick Suite with AI)
    - AUTHOR_PRO: Author Pro (Quick Suite with AI)
    - READER_PRO: Reader Pro (Quick Suite with AI)
    """
    if not identity_store_id:
        identity_store_id = get_identity_store_id()

    # Verify group exists in Identity Store
    group_id = get_group_id(identity_store_id, group_name)
    if not group_id:
        logger.error("Group not found in Identity Store", extra={"group_name": group_name})
        click.echo(
            f"✗ Group '{group_name}' not found in Identity Store. Ensure it's synced from Entra ID via SCIM.",
            err=True,
        )
        sys.exit(1)

    account_id = sts.get_caller_identity()["Account"]

    try:
        quicksight.create_role_membership(
            MemberName=group_name,
            AwsAccountId=account_id,
            Namespace=namespace,
            Role=role,
        )
        logger.info(
            "Assigned group to Quick Suite role",
            extra={"group": group_name, "role": role, "namespace": namespace},
        )
        click.echo(f"✓ Assigned '{group_name}' → {role} role")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            logger.info("Group already assigned", extra={"group": group_name, "role": role})
            click.echo(f"⚠ '{group_name}' already assigned to {role} role")
        else:
            logger.exception(
                "Failed to assign group",
                extra={"group": group_name, "role": role, "error": str(e)},
            )
            click.echo(f"✗ Failed to assign '{group_name}': {e}", err=True)
            sys.exit(1)


@cli.command()
@click.option("--namespace", default="default", help="Quick Suite namespace (default: default)")
def list_role_memberships(namespace: str) -> None:
    """List all QuickSight role memberships."""
    account_id = sts.get_caller_identity()["Account"]

    click.echo(f"\nQuickSight role memberships in namespace '{namespace}':\n")

    for role in ["ADMIN", "AUTHOR", "READER", "ADMIN_PRO", "AUTHOR_PRO", "READER_PRO"]:
        try:
            paginator = quicksight.get_paginator("list_role_memberships")
            members = []

            for page in paginator.paginate(AwsAccountId=account_id, Namespace=namespace, Role=role):
                members.extend(page.get("MembersList", []))

            if members:
                click.echo(f"{role}:")
                for member in members:
                    click.echo(f"  - {member}")
            else:
                click.echo(f"{role}: (none)")
            click.echo()
        except ClientError as e:
            logger.exception("Failed to list role memberships", extra={"role": role, "error": str(e)})
            click.echo(f"✗ Failed to list {role} memberships: {e}", err=True)


@cli.command()
@click.option("--group-name", required=True, help="Identity Center group name to remove")
@click.option("--namespace", default="default", help="Quick Suite namespace (default: default)")
def remove_group_from_role(group_name: str, namespace: str) -> None:
    """Remove an Identity Center group from its QuickSight role."""
    account_id = sts.get_caller_identity()["Account"]

    # Find which role the group is assigned to
    found_role = None
    for role in ["ADMIN", "AUTHOR", "READER", "ADMIN_PRO", "AUTHOR_PRO", "READER_PRO"]:
        try:
            paginator = quicksight.get_paginator("list_role_memberships")
            for page in paginator.paginate(AwsAccountId=account_id, Namespace=namespace, Role=role):
                members = page.get("MembersList", [])
                if group_name in members:
                    found_role = role
                    break
            if found_role:
                break
        except ClientError:
            continue

    if not found_role:
        click.echo(f"⚠ Group '{group_name}' is not assigned to any role")
        return

    try:
        quicksight.delete_role_membership(
            MemberName=group_name,
            AwsAccountId=account_id,
            Namespace=namespace,
            Role=found_role,
        )
        logger.info(
            "Removed group from Quick Suite role",
            extra={"group": group_name, "role": found_role, "namespace": namespace},
        )
        click.echo(f"✓ Removed '{group_name}' from {found_role} role")
    except ClientError as e:
        logger.exception(
            "Failed to remove group",
            extra={"group": group_name, "role": found_role, "error": str(e)},
        )
        click.echo(f"✗ Failed to remove '{group_name}': {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
