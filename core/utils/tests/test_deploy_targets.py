"""Tests for the deploy targets module."""

from __future__ import annotations

from deploy_targets import DeployTarget, resolve_target, validate_targets


class TestDeployTarget:
    """Tests for the DeployTarget class."""

    def test_apply_to_env_sets_region(self):
        target = DeployTarget(region="eu-west-1")
        env = target.apply_to_env({"PATH": "/usr/bin"})
        assert env["AWS_DEFAULT_REGION"] == "eu-west-1"
        assert env["AWS_REGION"] == "eu-west-1"
        assert env["PATH"] == "/usr/bin"

    def test_apply_to_env_sets_profile(self):
        target = DeployTarget(profile="prod-account")
        env = target.apply_to_env({})
        assert env["AWS_PROFILE"] == "prod-account"

    def test_apply_to_env_sets_account(self):
        target = DeployTarget(account="123456789012")
        env = target.apply_to_env({})
        assert env["QS_TARGET_ACCOUNT"] == "123456789012"

    def test_apply_to_env_no_overrides(self):
        target = DeployTarget()
        env = target.apply_to_env({"EXISTING": "value"})
        assert env == {"EXISTING": "value"}

    def test_apply_does_not_mutate_original(self):
        target = DeployTarget(region="us-west-2")
        original = {"PATH": "/usr/bin"}
        result = target.apply_to_env(original)
        assert "AWS_DEFAULT_REGION" not in original
        assert "AWS_DEFAULT_REGION" in result


class TestResolveTarget:
    """Tests for target resolution from manifest."""

    def test_no_targets_section(self):
        manifest = {"modules": ["modA"], "params": {}}
        target = resolve_target("modA", manifest)
        assert target.region is None
        assert target.profile is None

    def test_default_target_used(self):
        manifest = {
            "targets": {"default": {"region": "us-east-1", "profile": "prod"}},
            "modules": ["modA"],
        }
        target = resolve_target("modA", manifest)
        assert target.region == "us-east-1"
        assert target.profile == "prod"

    def test_explicit_module_target(self):
        manifest = {
            "targets": {
                "default": {"region": "us-east-1"},
                "data-account": {"region": "us-west-2", "profile": "data", "account": "222222222222"},
            },
            "module_targets": {
                "data-sources/redshift": "data-account",
            },
            "modules": ["governance/subscription", "data-sources/redshift"],
        }
        # Subscription gets default
        sub_target = resolve_target("governance/subscription", manifest)
        assert sub_target.region == "us-east-1"
        assert sub_target.profile is None

        # Redshift gets data-account
        rs_target = resolve_target("data-sources/redshift", manifest)
        assert rs_target.region == "us-west-2"
        assert rs_target.profile == "data"
        assert rs_target.account == "222222222222"

    def test_unknown_module_gets_default(self):
        manifest = {
            "targets": {"default": {"region": "ap-southeast-1"}},
            "modules": ["some/new-module"],
        }
        target = resolve_target("some/new-module", manifest)
        assert target.region == "ap-southeast-1"

    def test_no_default_no_mapping_returns_empty(self):
        manifest = {
            "targets": {"special": {"region": "eu-central-1"}},
            "modules": ["modA"],
        }
        target = resolve_target("modA", manifest)
        assert target.region is None


class TestValidateTargets:
    """Tests for target configuration validation."""

    def test_no_targets_no_errors(self):
        assert validate_targets({"modules": []}) == []

    def test_module_targets_without_targets_section(self):
        errors = validate_targets({"module_targets": {"modA": "prod"}})
        assert len(errors) == 1
        assert "no 'targets' section" in errors[0]

    def test_unknown_target_reference(self):
        errors = validate_targets({
            "targets": {"prod": {"region": "us-east-1"}},
            "module_targets": {"modA": "nonexistent"},
        })
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_valid_config_no_errors(self):
        errors = validate_targets({
            "targets": {
                "default": {"region": "us-east-1", "profile": "prod"},
                "data": {"region": "us-west-2", "account": "222222222222"},
            },
            "module_targets": {"data-sources/redshift": "data"},
        })
        assert errors == []
