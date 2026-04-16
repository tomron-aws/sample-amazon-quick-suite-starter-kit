"""Tests for the param resolver module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from param_resolver import resolve_params


class TestPlaintextPassthrough:
    """Plaintext values should pass through unchanged."""

    def test_no_refs(self):
        manifest = {
            "project": "test",
            "params": {
                "account_name": "MyAccount",
                "region": "us-east-1",
            },
        }
        result = resolve_params(manifest)
        assert result["params"]["account_name"] == "MyAccount"
        assert result["params"]["region"] == "us-east-1"

    def test_empty_params(self):
        manifest = {"project": "test", "params": {}}
        result = resolve_params(manifest)
        assert result["params"] == {}

    def test_no_params_key(self):
        manifest = {"project": "test"}
        result = resolve_params(manifest)
        assert "params" not in result or result.get("params") is None


class TestEnvResolver:
    """env: prefix should resolve from environment variables."""

    def test_resolves_env_var(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "resolved-value")
        manifest = {
            "project": "test",
            "params": {"my_param": "env:MY_SECRET"},
        }
        result = resolve_params(manifest)
        assert result["params"]["my_param"] == "resolved-value"

    def test_missing_env_var_exits(self):
        manifest = {
            "project": "test",
            "params": {"my_param": "env:NONEXISTENT_VAR_12345"},
        }
        with pytest.raises(SystemExit):
            resolve_params(manifest)


    def test_mixed_env_and_plaintext(self, monkeypatch):
        monkeypatch.setenv("SECRET_ARN", "arn:aws:sso:::instance/ssoins-abc")
        manifest = {
            "project": "test",
            "params": {
                "arn": "env:SECRET_ARN",
                "name": "plaintext-value",
            },
        }
        result = resolve_params(manifest)
        assert result["params"]["arn"] == "arn:aws:sso:::instance/ssoins-abc"
        assert result["params"]["name"] == "plaintext-value"


class TestSsmResolver:
    """ssm: prefix should resolve from SSM Parameter Store."""

    def test_resolves_ssm_param(self):
        mock_client = MagicMock()
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "ssm-resolved-value"}
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            # Re-import to pick up the mocked boto3
            import importlib
            import param_resolver
            importlib.reload(param_resolver)

            manifest = {
                "project": "test",
                "params": {"my_param": "ssm:/quicksuite/my-param"},
            }
            result = param_resolver.resolve_params(manifest)
            assert result["params"]["my_param"] == "ssm-resolved-value"
            mock_client.get_parameter.assert_called_once_with(
                Name="/quicksuite/my-param", WithDecryption=True
            )

    def test_ssm_failure_exits(self):
        mock_client = MagicMock()
        mock_client.get_parameter.side_effect = Exception("ParameterNotFound: Not found")
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            import importlib
            import param_resolver
            importlib.reload(param_resolver)

            manifest = {
                "project": "test",
                "params": {"my_param": "ssm:/nonexistent/param"},
            }
            with pytest.raises(SystemExit):
                param_resolver.resolve_params(manifest)


class TestSecretsManagerResolver:
    """secretsmanager: prefix should resolve from Secrets Manager."""

    def test_resolves_secret(self):
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": "secret-resolved-value"
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            import importlib
            import param_resolver
            importlib.reload(param_resolver)

            manifest = {
                "project": "test",
                "params": {"my_param": "secretsmanager:quicksuite/admin-email"},
            }
            result = param_resolver.resolve_params(manifest)
            assert result["params"]["my_param"] == "secret-resolved-value"
            mock_client.get_secret_value.assert_called_once_with(
                SecretId="quicksuite/admin-email"
            )


class TestOriginalManifestUnchanged:
    """resolve_params should not mutate the original manifest dict."""

    def test_original_not_mutated(self, monkeypatch):
        monkeypatch.setenv("TEST_VAL", "resolved")
        original = {
            "project": "test",
            "params": {"key": "env:TEST_VAL"},
        }
        result = resolve_params(original)
        assert original["params"]["key"] == "env:TEST_VAL"
        assert result["params"]["key"] == "resolved"
