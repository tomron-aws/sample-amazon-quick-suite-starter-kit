"""Tests for the orchestrator module."""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from orchestrator import (
    load_module_config,
    resolve_deploy_order,
    validate,
)


@pytest.fixture()
def tmp_project(tmp_path, monkeypatch):
    """Create a minimal project structure for testing."""
    monkeypatch.chdir(tmp_path)

    def make_module(path, config):
        mod_dir = tmp_path / path
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "config.yaml").write_text(yaml.dump(config))

    return make_module


# --- validate ---


class TestValidate:
    """Tests for manifest validation."""

    def test_valid_manifest(self, tmp_project):
        tmp_project("modA", {"name": "modA", "iac_type": "terraform", "dependencies": [], "params": []})
        manifest = {"modules": ["modA"], "params": {}}
        validate(manifest)  # should not raise

    def test_missing_module_directory(self, tmp_project):
        manifest = {"modules": ["nonexistent/mod"], "params": {}}
        with pytest.raises(SystemExit):
            validate(manifest)

    def test_missing_required_param(self, tmp_project):
        tmp_project("modA", {
            "name": "modA", "iac_type": "terraform", "dependencies": [],
            "params": [{"name": "account_id", "required": True}],
        })
        manifest = {"modules": ["modA"], "params": {}}
        with pytest.raises(SystemExit):
            validate(manifest)

    def test_required_param_provided(self, tmp_project):
        tmp_project("modA", {
            "name": "modA", "iac_type": "terraform", "dependencies": [],
            "params": [{"name": "account_id", "required": True}],
        })
        manifest = {"modules": ["modA"], "params": {"account_id": "123456789012"}}
        validate(manifest)  # should not raise

    def test_optional_param_not_required(self, tmp_project):
        tmp_project("modA", {
            "name": "modA", "iac_type": "terraform", "dependencies": [],
            "params": [{"name": "edition", "required": False, "default": "ENTERPRISE"}],
        })
        manifest = {"modules": ["modA"], "params": {}}
        validate(manifest)  # should not raise


# --- resolve_deploy_order ---


class TestResolveDependencyOrder:
    """Tests for topological sort of module dependencies."""

    def test_single_module_no_deps(self, tmp_project):
        tmp_project("modA", {"name": "modA", "iac_type": "terraform", "dependencies": []})
        manifest = {"modules": ["modA"]}
        assert resolve_deploy_order(manifest) == ["modA"]

    def test_linear_chain(self, tmp_project):
        tmp_project("core/base", {"name": "base", "iac_type": "terraform", "dependencies": []})
        tmp_project("mid", {"name": "mid", "iac_type": "terraform", "dependencies": ["core/base"]})
        tmp_project("top", {"name": "top", "iac_type": "terraform", "dependencies": ["mid"]})
        manifest = {"modules": ["top"]}
        order = resolve_deploy_order(manifest)
        assert order.index("core/base") < order.index("mid") < order.index("top")

    def test_implicit_deps_pulled_in(self, tmp_project):
        """Dependencies not in the manifest are auto-added."""
        tmp_project("core/base", {"name": "base", "iac_type": "terraform", "dependencies": []})
        tmp_project("modA", {"name": "modA", "iac_type": "terraform", "dependencies": ["core/base"]})
        manifest = {"modules": ["modA"]}  # core/base not listed
        order = resolve_deploy_order(manifest)
        assert "core/base" in order
        assert order.index("core/base") < order.index("modA")

    def test_diamond_dependency(self, tmp_project):
        """A depends on B and C, both depend on D."""
        tmp_project("D", {"name": "D", "iac_type": "terraform", "dependencies": []})
        tmp_project("B", {"name": "B", "iac_type": "terraform", "dependencies": ["D"]})
        tmp_project("C", {"name": "C", "iac_type": "terraform", "dependencies": ["D"]})
        tmp_project("A", {"name": "A", "iac_type": "terraform", "dependencies": ["B", "C"]})
        manifest = {"modules": ["A"]}
        order = resolve_deploy_order(manifest)
        assert order[0] == "D"
        assert order[-1] == "A"
        assert set(order) == {"A", "B", "C", "D"}

    def test_circular_dependency_detected(self, tmp_project):
        tmp_project("modA", {"name": "modA", "iac_type": "terraform", "dependencies": ["modB"]})
        tmp_project("modB", {"name": "modB", "iac_type": "terraform", "dependencies": ["modA"]})
        manifest = {"modules": ["modA"]}
        with pytest.raises(SystemExit):
            resolve_deploy_order(manifest)

    def test_version_pinned_module(self, tmp_project):
        """Modules with @version pins are handled correctly."""
        tmp_project("core/base", {"name": "base", "iac_type": "terraform", "dependencies": []})
        tmp_project("modA", {"name": "modA", "iac_type": "external", "dependencies": ["core/base"]})
        manifest = {"modules": ["modA@v2.1.0"]}
        order = resolve_deploy_order(manifest)
        assert order.index("core/base") < order.index("modA")

    def test_multiple_roots(self, tmp_project):
        """Independent modules with no shared deps."""
        tmp_project("modA", {"name": "modA", "iac_type": "terraform", "dependencies": []})
        tmp_project("modB", {"name": "modB", "iac_type": "config-only", "dependencies": []})
        manifest = {"modules": ["modB", "modA"]}
        order = resolve_deploy_order(manifest)
        assert set(order) == {"modA", "modB"}


# --- load_module_config ---


class TestLoadModuleConfig:
    """Tests for module config loading."""

    def test_loads_valid_config(self, tmp_project):
        tmp_project("modA", {"name": "modA", "iac_type": "terraform", "dependencies": [], "params": []})
        config = load_module_config("modA")
        assert config["name"] == "modA"
        assert config["iac_type"] == "terraform"

    def test_strips_version_pin(self, tmp_project):
        tmp_project("modA", {"name": "modA", "iac_type": "external", "dependencies": []})
        config = load_module_config("modA@v1.0.0")
        assert config["name"] == "modA"

    def test_missing_config_exits(self, tmp_project):
        with pytest.raises(SystemExit):
            load_module_config("nonexistent/mod")


# --- validate_param_value ---

from orchestrator import validate_param_value


class TestParamValidation:
    """Tests for param type and format validation."""

    def test_string_valid(self):
        ok, _ = validate_param_value({"type": "string"}, "hello")
        assert ok

    def test_string_empty_fails(self):
        ok, _ = validate_param_value({"type": "string"}, "")
        assert not ok

    def test_string_pattern_valid(self):
        ok, _ = validate_param_value({"type": "string", "pattern": "^d-[a-zA-Z0-9]+$"}, "d-abc123")
        assert ok

    def test_string_pattern_invalid(self):
        ok, msg = validate_param_value({"type": "string", "pattern": "^d-[a-zA-Z0-9]+$"}, "x-bad")
        assert not ok
        assert "pattern" in msg

    def test_arn_valid(self):
        ok, _ = validate_param_value(
            {"type": "arn", "pattern": "^arn:aws:sso:::instance/ssoins-.+$"},
            "arn:aws:sso:::instance/ssoins-abc123",
        )
        assert ok

    def test_arn_missing_prefix(self):
        ok, _ = validate_param_value({"type": "arn"}, "not-an-arn")
        assert not ok

    def test_arn_wrong_pattern(self):
        ok, _ = validate_param_value(
            {"type": "arn", "pattern": "^arn:aws:sso:::instance/ssoins-.+$"},
            "arn:aws:s3:::my-bucket",
        )
        assert not ok

    def test_email_valid(self):
        ok, _ = validate_param_value({"type": "email"}, "user@example.com")
        assert ok

    def test_email_invalid(self):
        ok, _ = validate_param_value({"type": "email"}, "not-an-email")
        assert not ok

    def test_json_valid(self):
        ok, _ = validate_param_value({"type": "json"}, '[{"groupName": "Readers", "role": "READER"}]')
        assert ok

    def test_json_invalid(self):
        ok, _ = validate_param_value({"type": "json"}, "not json {")
        assert not ok

    def test_aws_region_valid(self):
        ok, _ = validate_param_value({"type": "aws_region"}, "us-east-1")
        assert ok

    def test_aws_region_invalid(self):
        ok, _ = validate_param_value({"type": "aws_region"}, "invalid-region")
        assert not ok

    def test_no_type_skips_validation(self):
        ok, _ = validate_param_value({}, "anything")
        assert ok

    def test_unknown_type_skips_validation(self):
        ok, _ = validate_param_value({"type": "future_type"}, "anything")
        assert ok


class TestValidateParamFormats:
    """Integration tests for param format validation in the validate function."""

    def test_invalid_arn_format_rejected(self, tmp_project):
        tmp_project("modA", {
            "name": "modA", "iac_type": "terraform", "dependencies": [],
            "params": [{"name": "my_arn", "required": True, "type": "arn"}],
        })
        manifest = {"modules": ["modA"], "params": {"my_arn": "not-an-arn"}}
        with pytest.raises(SystemExit):
            validate(manifest)

    def test_invalid_email_rejected(self, tmp_project):
        tmp_project("modA", {
            "name": "modA", "iac_type": "terraform", "dependencies": [],
            "params": [{"name": "email", "required": True, "type": "email"}],
        })
        manifest = {"modules": ["modA"], "params": {"email": "bad-email"}}
        with pytest.raises(SystemExit):
            validate(manifest)

    def test_valid_params_pass(self, tmp_project):
        tmp_project("modA", {
            "name": "modA", "iac_type": "terraform", "dependencies": [],
            "params": [
                {"name": "my_arn", "required": True, "type": "arn", "pattern": "^arn:aws:.*$"},
                {"name": "email", "required": True, "type": "email"},
            ],
        })
        manifest = {"modules": ["modA"], "params": {
            "my_arn": "arn:aws:sso:::instance/ssoins-abc",
            "email": "admin@example.com",
        }}
        validate(manifest)  # should not raise
