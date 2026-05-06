"""Tests for the Quick Suite setup custom resource handler."""

from unittest.mock import MagicMock, patch

import pytest

from custom_resource_handler_for_quick_suite_setup import (
    check_quicksight_subscription_exists,
    get_existing_group_id,
)


@pytest.fixture()
def mock_quicksight():
    """Mock the QuickSight boto3 client."""
    with patch("custom_resource_handler_for_quick_suite_setup.quicksight") as mock:
        yield mock


@pytest.fixture()
def mock_identitystore():
    """Mock the Identity Store boto3 client."""
    with patch("custom_resource_handler_for_quick_suite_setup.identitystore") as mock:
        yield mock


class TestCheckQuickSightSubscription:
    """Tests for subscription existence check."""

    def test_returns_true_when_active(self, mock_quicksight):
        mock_quicksight.describe_account_subscription.return_value = {
            "AccountInfo": {"AccountSubscriptionStatus": "ACCOUNT_CREATED"}
        }
        assert check_quicksight_subscription_exists("123456789012") is True

    def test_returns_false_when_unsubscribed(self, mock_quicksight):
        mock_quicksight.describe_account_subscription.return_value = {
            "AccountInfo": {"AccountSubscriptionStatus": "UNSUBSCRIBED"}
        }
        assert check_quicksight_subscription_exists("123456789012") is False

    def test_returns_false_when_not_found(self, mock_quicksight):
        from botocore.exceptions import ClientError

        mock_quicksight.describe_account_subscription.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DescribeAccountSubscription",
        )
        assert check_quicksight_subscription_exists("123456789012") is False


class TestGetExistingGroupId:
    """Tests for Identity Store group lookup."""

    def test_returns_group_id_when_found(self, mock_identitystore):
        paginator = MagicMock()
        mock_identitystore.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Groups": [{"GroupId": "group-123"}]}
        ]
        result = get_existing_group_id("d-test", "AdminGroup")
        assert result == "group-123"

    def test_returns_none_when_not_found(self, mock_identitystore):
        paginator = MagicMock()
        mock_identitystore.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"Groups": []}]
        result = get_existing_group_id("d-test", "NonExistent")
        assert result is None
