"""Custom resource handler for Quick Suite setup with IAM Identity Center and external IdP."""

from typing import Any

import boto3
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from crhelper import CfnResource

from common.observability import logger

helper = CfnResource()
quicksight = boto3.client("quicksight")
identitystore = boto3.client("identitystore")


def get_existing_group_id(identity_store_id: str, group_name: str) -> str | None:
    """Get group ID by name from Identity Store."""
    try:
        paginator = identitystore.get_paginator("list_groups")
        page_iterator = paginator.paginate(
            IdentityStoreId=identity_store_id,
            Filters=[{"AttributePath": "DisplayName", "AttributeValue": group_name}],
        )

        for page in page_iterator:
            if page["Groups"]:
                return page["Groups"][0]["GroupId"]
        return None
    except ClientError as e:
        logger.exception("Failed to get group", extra={"group_name": group_name, "error": str(e)})
        return None


def check_quicksight_subscription_exists(account_id: str) -> bool:
    """Check if QuickSight subscription already exists."""
    try:
        response = quicksight.describe_account_subscription(AwsAccountId=account_id)
        status = response["AccountInfo"]["AccountSubscriptionStatus"]
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise
    else:
        return status not in ["UNSUBSCRIBED", "UNSUBSCRIBE_IN_PROGRESS"]


def create_quicksight_subscription(
    account_id: str, account_name: str, admin_email: str, identity_center_arn: str, admin_group_name: str
) -> None:
    """Create QuickSight Enterprise subscription with IAM Identity Center."""
    quicksight.create_account_subscription(
        Edition="ENTERPRISE",
        AuthenticationMethod="IAM_IDENTITY_CENTER",
        AwsAccountId=account_id,
        AccountName=account_name,
        NotificationEmail=admin_email,
        IAMIdentityCenterInstanceArn=identity_center_arn,
        AdminProGroup=[admin_group_name],
    )
    logger.info("Quick Suite account subscription created")


def ensure_quicksight_subscription(
    account_id: str, account_name: str, admin_email: str, identity_center_arn: str, admin_group_name: str
) -> None:
    """Ensure QuickSight subscription exists (idempotent)."""
    if check_quicksight_subscription_exists(account_id):
        logger.info("Quick Suite account subscription already exists")
        return

    create_quicksight_subscription(account_id, account_name, admin_email, identity_center_arn, admin_group_name)


@helper.create
def create(event: dict[str, Any], _context: LambdaContext) -> str:
    """Create Quick Suite resources."""
    logger.info("Creating Quick Suite resources")
    props = event["ResourceProperties"]
    account_id = event["StackId"].split(":")[4]
    identity_center_arn = props["IdentityCenterInstanceArn"]
    identity_store_id = props["IdentityStoreId"]
    account_name = props["AccountName"]
    admin_user_email = props["AdminUserEmail"]
    admin_group_name = props["AdminProGroupName"]
    group_role_mappings_str = props.get("GroupRoleMappings", "[]")
    
    import json
    group_role_mappings = json.loads(group_role_mappings_str) if group_role_mappings_str else []

    # Verify admin group exists in Identity Store (synced from Entra ID)
    group_id = get_existing_group_id(identity_store_id, admin_group_name)
    if not group_id:
        error_msg = f"Admin group '{admin_group_name}' not found in Identity Store. Ensure it's synced from Entra ID via SCIM."
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"Found admin group '{admin_group_name}' in Identity Store", extra={"group_id": group_id})

    # Create QuickSight subscription
    ensure_quicksight_subscription(account_id, account_name, admin_user_email, identity_center_arn, admin_group_name)

    # Assign additional groups to roles
    for mapping in group_role_mappings:
        group_name = mapping.get("groupName")
        role = mapping.get("role")
        
        if not group_name or not role:
            logger.warning("Invalid group mapping", extra={"mapping": mapping})
            continue
            
        # Verify group exists
        if not get_existing_group_id(identity_store_id, group_name):
            logger.warning(f"Group '{group_name}' not found in Identity Store, skipping", extra={"group": group_name})
            continue
        
        # Remove group from all other roles first
        all_roles = ["ADMIN", "AUTHOR", "READER", "ADMIN_PRO", "AUTHOR_PRO", "READER_PRO"]
        for existing_role in all_roles:
            if existing_role == role:
                continue  # Skip the target role
            try:
                quicksight.delete_role_membership(
                    MemberName=group_name,
                    AwsAccountId=account_id,
                    Namespace="default",
                    Role=existing_role,
                )
                logger.info(f"Removed group '{group_name}' from role {existing_role}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    pass  # Group wasn't in this role, that's fine
                else:
                    logger.warning(f"Failed to remove group '{group_name}' from role {existing_role}", extra={"error": str(e)})
        
        # Now assign to the target role
        try:
            quicksight.create_role_membership(
                MemberName=group_name,
                AwsAccountId=account_id,
                Namespace="default",
                Role=role,
            )
            logger.info(f"Assigned group '{group_name}' to role {role}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                logger.info(f"Group '{group_name}' already assigned to role {role}")
            else:
                logger.warning(f"Failed to assign group '{group_name}' to role {role}", extra={"error": str(e)})

    return account_id


@helper.update
def update(event: dict[str, Any], _context: LambdaContext) -> str:
    """Update called - ensuring resources exist."""
    logger.info("Update called - ensuring resources exist")
    return create(event, _context)


@helper.delete
def delete(_event: dict[str, Any], _context: LambdaContext) -> None:
    """Delete called - Quick Suite subscription must be deleted manually."""
    logger.info("Delete called - Quick Suite subscription must be deleted manually")
    logger.info("See documentation for manual deletion instructions")


@logger.inject_lambda_context
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Lambda handler for Quick Suite setup custom resource."""
    logger.info("Received event", extra={"event": event})
    return helper(event, context)
