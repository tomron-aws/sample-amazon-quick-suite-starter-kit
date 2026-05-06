"""Deploy audit logger — writes structured JSON logs for every orchestrator run.

Log files are written to the 'logs/' directory with timestamped filenames.
Each log captures: command, user, params (secrets masked), module outcomes, and timing.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = "logs"

# Param names that should be masked in logs
_SENSITIVE_PATTERNS = {"email", "secret", "password", "token", "key", "credential"}


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive param values for logging."""
    key_lower = key.lower()
    for pattern in _SENSITIVE_PATTERNS:
        if pattern in key_lower:
            if len(value) > 4:
                return value[:4] + "***"
            return "***"
    # Also mask resolved references
    if isinstance(value, str) and any(value.startswith(p) for p in ("ssm:", "secretsmanager:", "env:")):
        return value  # Still a reference, not resolved yet — safe to log
    return value


def _safe_params(params: dict) -> dict:
    """Return a copy of params with sensitive values masked."""
    return {k: _mask_value(k, str(v)) for k, v in params.items()}


class DeployLogger:
    """Structured audit logger for orchestrator runs."""

    def __init__(self, command: str, manifest: dict):
        self.start_time = datetime.now(timezone.utc)
        self.log_entry = {
            "timestamp": self.start_time.isoformat(),
            "command": command,
            "project": manifest.get("project", ""),
            "user": _get_user_info(),
            "params": _safe_params(manifest.get("params", {})),
            "modules": [m.split("@")[0] for m in manifest.get("modules", [])],
            "events": [],
            "result": None,
        }
        self._log_path = self._create_log_path(command)

    def _create_log_path(self, command: str) -> Path:
        """Create the log file path."""
        logs_dir = Path(LOGS_DIR)
        logs_dir.mkdir(exist_ok=True)
        ts = self.start_time.strftime("%Y%m%d-%H%M%S")
        return logs_dir / f"{ts}-{command}.json"

    def log_event(self, event_type: str, module: str | None = None, **kwargs) -> None:
        """Record a timestamped event."""
        event = {
            "time": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
        }
        if module:
            event["module"] = module
        event.update(kwargs)
        self.log_entry["events"].append(event)

    def log_module_start(self, module: str, iac_type: str) -> None:
        self.log_event("module_start", module=module, iac_type=iac_type)

    def log_module_success(self, module: str) -> None:
        self.log_event("module_success", module=module)

    def log_module_failure(self, module: str, exit_code: int) -> None:
        self.log_event("module_failure", module=module, exit_code=exit_code)

    def finish(self, result: str, deployed: list[str] | None = None, failed: str | None = None) -> None:
        """Finalize the log with the overall result and write to disk."""
        end_time = datetime.now(timezone.utc)
        self.log_entry["result"] = result
        self.log_entry["duration_seconds"] = (end_time - self.start_time).total_seconds()
        if deployed is not None:
            self.log_entry["deployed"] = deployed
        if failed is not None:
            self.log_entry["failed"] = failed
        self.log_entry["finished_at"] = end_time.isoformat()
        self._write()

    def _write(self) -> None:
        """Write the log entry to disk."""
        try:
            self._log_path.write_text(json.dumps(self.log_entry, indent=2))
        except OSError as e:
            print(f"  WARNING: Failed to write deploy log: {e}", file=sys.stderr)


def _get_user_info() -> dict:
    """Gather user/environment info for the audit log."""
    return {
        "username": getpass.getuser(),
        "hostname": platform.node(),
        "cwd": os.getcwd(),
    }
