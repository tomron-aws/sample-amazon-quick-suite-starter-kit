"""Integration tests for the full orchestrator deploy pipeline.

These tests validate the end-to-end flow:
  manifest → validate → resolve_deploy_order → run_deploy → deploy.sh execution

No AWS account needed — uses mock accelerators with deploy scripts that
write marker files to prove they ran and received the correct env vars.
"""

import json
import os
import stat
import textwrap
from pathlib import Path

import pytest
import yaml

from orchestrator import (
    DEPLOY_STATE_FILE,
    clear_deploy_state,
    load_deploy_state,
    resolve_deploy_order,
    run_deploy,
    validate,
)


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """Set up a temporary project directory with helper methods."""
    monkeypatch.chdir(tmp_path)

    class ProjectHelper:
        root = tmp_path

        def make_module(self, path, config, deploy_script=None, deploy_py=None):
            """Create a module with config.yaml and optional deploy.sh / deploy.py."""
            mod_dir = tmp_path / path
            mod_dir.mkdir(parents=True, exist_ok=True)
            (mod_dir / "config.yaml").write_text(yaml.dump(config))
            if deploy_script is not None:
                script_path = mod_dir / "deploy.sh"
                script_path.write_text(deploy_script)
                script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
            if deploy_py is not None:
                (mod_dir / "deploy.py").write_text(deploy_py)

        def write_manifest(self, manifest):
            (tmp_path / "manifest.yaml").write_text(yaml.dump(manifest))

        def marker_path(self, name):
            return tmp_path / f".marker-{name}"

    return ProjectHelper()


def _deploy_script_that_writes_marker(marker_path: Path) -> str:
    """Generate a deploy.sh that writes env vars to a marker file."""
    return textwrap.dedent(f"""\
        #!/bin/bash
        set -euo pipefail
        # Write all QS_ env vars to marker file as JSON
        python3 -c "
import json, os
qs_vars = {{k: v for k, v in os.environ.items() if k.startswith('QS_')}}
with open('{marker_path}', 'w') as f:
    json.dump(qs_vars, f)
"
    """)


def _deploy_py_that_writes_marker(marker_path: Path) -> str:
    """Generate a deploy.py that writes a marker file."""
    return textwrap.dedent(f"""\
        import json
        from pathlib import Path
        Path("{marker_path}").write_text("deployed")
    """)


def _deploy_script_that_fails() -> str:
    """Generate a deploy.sh that exits with error."""
    return textwrap.dedent("""\
        #!/bin/bash
        echo "Simulated failure" >&2
        exit 1
    """)


# ---------------------------------------------------------------
# Test 1: Full pipeline — external module receives env vars
# ---------------------------------------------------------------

class TestExternalModuleEnvVars:
    """Verify deploy.sh receives manifest params as QS_PARAM_* env vars."""

    def test_params_passed_as_env_vars(self, project):
        marker = project.marker_path("accel")

        project.make_module("accel", {
            "name": "accel", "iac_type": "external",
            "dependencies": [], "params": [],
        }, deploy_script=_deploy_script_that_writes_marker(marker))

        manifest = {
            "project": "test-project",
            "modules": ["accel"],
            "params": {
                "region": "us-west-2",
                "my_bucket": "test-bucket-123",
            },
        }
        project.write_manifest(manifest)

        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        run_deploy(ordered, manifest, auto_approve=True)

        assert marker.exists(), "deploy.sh did not run"
        env_vars = json.loads(marker.read_text())
        assert env_vars["QS_PARAM_REGION"] == "us-west-2"
        assert env_vars["QS_PARAM_MY_BUCKET"] == "test-bucket-123"
        assert env_vars["QS_PROJECT"] == "test-project"
        assert env_vars["QS_AUTO_APPROVE"] == "1"

    def test_auto_approve_not_set_when_false(self, project):
        marker = project.marker_path("accel2")

        project.make_module("accel", {
            "name": "accel", "iac_type": "external",
            "dependencies": [], "params": [],
        }, deploy_script=_deploy_script_that_writes_marker(marker))

        manifest = {
            "project": "test-project",
            "modules": ["accel"],
            "params": {"region": "us-east-1"},
        }
        project.write_manifest(manifest)

        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        run_deploy(ordered, manifest, auto_approve=False)

        env_vars = json.loads(marker.read_text())
        assert "QS_AUTO_APPROVE" not in env_vars


# ---------------------------------------------------------------
# Test 2: Cross-tier dependency ordering
# ---------------------------------------------------------------

class TestCrossTierDependencyOrdering:
    """Verify external modules deploy after their CDK/config-only dependencies."""

    def test_external_deploys_after_config_only_dependency(self, project):
        """config-only dep → external accelerator, in correct order."""
        marker_dep = project.marker_path("dep")
        marker_accel = project.marker_path("accel")

        project.make_module("core/base", {
            "name": "base", "iac_type": "config-only",
            "dependencies": [], "params": [],
        }, deploy_py=_deploy_py_that_writes_marker(marker_dep))

        project.make_module("accel/idp", {
            "name": "idp", "iac_type": "external",
            "dependencies": ["core/base"], "params": [],
        }, deploy_script=_deploy_script_that_writes_marker(marker_accel))

        manifest = {
            "project": "ordering-test",
            "modules": ["accel/idp"],  # core/base not listed — should be auto-added
            "params": {},
        }
        project.write_manifest(manifest)

        validate(manifest)
        ordered = resolve_deploy_order(manifest)

        # Verify ordering
        assert ordered.index("core/base") < ordered.index("accel/idp")

        # Run deploy and verify both ran
        run_deploy(ordered, manifest, auto_approve=True)
        assert marker_dep.exists(), "Dependency deploy.sh did not run"
        assert marker_accel.exists(), "Accelerator deploy.sh did not run"

    def test_three_tier_chain(self, project):
        """core → governance → accelerator, all different iac_types."""
        markers = {}
        for name in ["core/infra", "gov/sub", "accel/thing"]:
            markers[name] = project.marker_path(name.replace("/", "-"))

        project.make_module("core/infra", {
            "name": "infra", "iac_type": "config-only",
            "dependencies": [], "params": [],
        }, deploy_py=_deploy_py_that_writes_marker(markers["core/infra"]))

        project.make_module("gov/sub", {
            "name": "sub", "iac_type": "config-only",
            "dependencies": ["core/infra"], "params": [],
        }, deploy_py=_deploy_py_that_writes_marker(markers["gov/sub"]))

        project.make_module("accel/thing", {
            "name": "thing", "iac_type": "external",
            "dependencies": ["gov/sub"], "params": [],
        }, deploy_script=_deploy_script_that_writes_marker(markers["accel/thing"]))

        manifest = {
            "project": "chain-test",
            "modules": ["accel/thing"],
            "params": {},
        }
        project.write_manifest(manifest)

        ordered = resolve_deploy_order(manifest)
        assert ordered == ["core/infra", "gov/sub", "accel/thing"]

        run_deploy(ordered, manifest, auto_approve=True)
        for m in markers.values():
            assert m.exists()


# ---------------------------------------------------------------
# Test 3: Failure and state tracking
# ---------------------------------------------------------------

class TestFailureAndStateTracking:
    """Verify the orchestrator handles deploy failures correctly."""

    def test_failure_writes_state_file(self, project):
        """When deploy.sh fails, state file records what succeeded and what failed."""
        marker_ok = project.marker_path("ok")

        project.make_module("mod-ok", {
            "name": "mod-ok", "iac_type": "config-only",
            "dependencies": [], "params": [],
        }, deploy_py=_deploy_py_that_writes_marker(marker_ok))

        project.make_module("mod-fail", {
            "name": "mod-fail", "iac_type": "external",
            "dependencies": ["mod-ok"], "params": [],
        }, deploy_script=_deploy_script_that_fails())

        project.make_module("mod-skipped", {
            "name": "mod-skipped", "iac_type": "config-only",
            "dependencies": ["mod-fail"], "params": [],
        })

        manifest = {
            "project": "fail-test",
            "modules": ["mod-skipped"],
            "params": {},
        }
        project.write_manifest(manifest)

        ordered = resolve_deploy_order(manifest)
        assert ordered == ["mod-ok", "mod-fail", "mod-skipped"]

        with pytest.raises(SystemExit):
            run_deploy(ordered, manifest, auto_approve=True)

        # mod-ok should have run
        assert marker_ok.exists()

        # State file should exist with correct data
        state = load_deploy_state()
        assert state is not None
        assert state["deployed"] == ["mod-ok"]
        assert state["failed"] == "mod-fail"
        assert "mod-fail" in state["remaining"]
        assert "mod-skipped" in state["remaining"]

    def test_resume_skips_already_deployed(self, project):
        """Resume picks up after the last successfully deployed module."""
        marker_ok = project.marker_path("ok")
        marker_resumed = project.marker_path("resumed")

        project.make_module("mod-ok", {
            "name": "mod-ok", "iac_type": "config-only",
            "dependencies": [], "params": [],
        }, deploy_py=_deploy_py_that_writes_marker(marker_ok))

        project.make_module("mod-resumed", {
            "name": "mod-resumed", "iac_type": "external",
            "dependencies": ["mod-ok"], "params": [],
        }, deploy_script=_deploy_script_that_writes_marker(marker_resumed))

        manifest = {
            "project": "resume-test",
            "modules": ["mod-resumed"],
            "params": {"region": "eu-west-1"},
        }
        project.write_manifest(manifest)

        ordered = resolve_deploy_order(manifest)

        # Simulate: mod-ok already deployed, resume from there
        run_deploy(ordered, manifest, auto_approve=True, resume_after="mod-ok")

        # mod-ok's marker should NOT exist (it was skipped)
        assert not marker_ok.exists()
        # mod-resumed should have run
        assert marker_resumed.exists()

        # State file should be cleaned up on success
        assert load_deploy_state() is None


# ---------------------------------------------------------------
# Test 4: Missing deploy.sh handled gracefully
# ---------------------------------------------------------------

class TestMissingDeployScript:
    """Verify external modules without deploy.sh are skipped with a warning."""

    def test_missing_deploy_sh_skips_module(self, project):
        project.make_module("accel/no-script", {
            "name": "no-script", "iac_type": "external",
            "dependencies": [], "params": [],
        })  # No deploy_script argument

        manifest = {
            "project": "skip-test",
            "modules": ["accel/no-script"],
            "params": {},
        }
        project.write_manifest(manifest)

        ordered = resolve_deploy_order(manifest)
        # Should not raise — just prints a warning
        run_deploy(ordered, manifest, auto_approve=True)


# ---------------------------------------------------------------
# Test 5: Param validation blocks deploy before scripts run
# ---------------------------------------------------------------

class TestParamValidationBlocksDeploy:
    """Verify invalid params are caught before any deploy.sh runs."""

    def test_invalid_param_prevents_deploy(self, project):
        marker = project.marker_path("should-not-run")

        project.make_module("accel/strict", {
            "name": "strict", "iac_type": "external",
            "dependencies": [],
            "params": [{
                "name": "my_arn",
                "required": True,
                "type": "arn",
                "pattern": "^arn:aws:.*$",
            }],
        }, deploy_script=_deploy_script_that_writes_marker(marker))

        manifest = {
            "project": "validation-test",
            "modules": ["accel/strict"],
            "params": {"my_arn": "not-an-arn"},
        }
        project.write_manifest(manifest)

        with pytest.raises(SystemExit):
            validate(manifest)

        # deploy.sh should never have run
        assert not marker.exists()


# ---------------------------------------------------------------
# Test 6: Version-pinned external module
# ---------------------------------------------------------------

class TestVersionPinnedModule:
    """Verify modules with @version pins work through the full pipeline."""

    def test_version_pin_stripped_for_path_resolution(self, project):
        marker = project.marker_path("versioned")

        project.make_module("accel/versioned", {
            "name": "versioned", "iac_type": "external",
            "dependencies": [], "params": [],
        }, deploy_script=_deploy_script_that_writes_marker(marker))

        manifest = {
            "project": "version-test",
            "modules": ["accel/versioned@v2.1.0"],
            "params": {},
        }
        project.write_manifest(manifest)

        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        assert "accel/versioned" in ordered

        run_deploy(ordered, manifest, auto_approve=True)
        assert marker.exists()


# ---------------------------------------------------------------
# Test 7: Config-only module receives env vars
# ---------------------------------------------------------------

class TestConfigOnlyModuleEnvVars:
    """Verify deploy.py for config-only modules receives QS_PARAM_* env vars."""

    def test_params_passed_to_deploy_py(self, project):
        marker = project.marker_path("config-mod")

        deploy_py = textwrap.dedent(f"""\
            import json, os
            from pathlib import Path
            qs_vars = {{k: v for k, v in os.environ.items() if k.startswith("QS_")}}
            Path("{marker}").write_text(json.dumps(qs_vars))
        """)

        project.make_module("agents/a1", {
            "name": "a1", "iac_type": "config-only",
            "dependencies": [], "params": [],
        }, deploy_py=deploy_py)

        manifest = {
            "project": "config-test",
            "modules": ["agents/a1"],
            "params": {
                "region": "ap-southeast-1",
                "api_key": "test-key-123",
            },
        }
        project.write_manifest(manifest)

        validate(manifest)
        ordered = resolve_deploy_order(manifest)
        run_deploy(ordered, manifest, auto_approve=True)

        assert marker.exists(), "deploy.py did not run"
        env_vars = json.loads(marker.read_text())
        assert env_vars["QS_PARAM_REGION"] == "ap-southeast-1"
        assert env_vars["QS_PARAM_API_KEY"] == "test-key-123"
        assert env_vars["QS_PROJECT"] == "config-test"
        assert env_vars["QS_AUTO_APPROVE"] == "1"
