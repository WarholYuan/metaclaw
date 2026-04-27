"""Shared utilities for CLI."""

import os
import sys
import json

from pathlib import Path

from common.brand import DEFAULT_AGENT_WORKSPACE, DEFAULT_SERVICE_LOG_FILE, DEFAULT_PID_FILE


def get_project_root() -> str:
    """Get the project root directory."""
    # cli/ is directly under the project root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_workspace_dir() -> str:
    """Get the agent workspace directory from config."""
    config = load_config_json()
    workspace = config.get("agent_workspace", DEFAULT_AGENT_WORKSPACE)
    return os.path.expanduser(workspace)


def ensure_dir(path: str) -> str:
    """Create and return a directory path."""
    os.makedirs(path, exist_ok=True)
    return path


def get_runtime_dir() -> str:
    """Get the directory for process state files and service logs."""
    return ensure_dir(os.path.join(get_workspace_dir(), "logs"))


def get_pid_file() -> str:
    """Get the service PID file path."""
    return os.path.join(get_runtime_dir(), DEFAULT_PID_FILE)


def get_service_log_file() -> str:
    """Get the service stdout/stderr log file path."""
    config = load_config_json()
    log_file = config.get("service_log_file", DEFAULT_SERVICE_LOG_FILE)
    return str(Path(os.path.expanduser(log_file)))


def get_skills_dir() -> str:
    """Get the custom skills directory."""
    return os.path.join(get_workspace_dir(), "skills")


def get_builtin_skills_dir() -> str:
    """Get the builtin skills directory."""
    return os.path.join(get_project_root(), "skills")


def load_config_json() -> dict:
    """Load config.json from the active config location."""
    env_path = os.environ.get("METACLAW_CONFIG_FILE", "").strip()
    candidates = []
    if env_path:
        candidates.append(os.path.expanduser(env_path))
    candidates.extend([
        os.path.expanduser(os.path.join(DEFAULT_AGENT_WORKSPACE, "config.json")),
        os.path.join(get_project_root(), "config.json"),
    ])
    config_path = next((path for path in candidates if os.path.exists(path)), "")
    if not config_path:
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_skills_config() -> dict:
    """Load skills_config.json from the custom skills directory."""
    path = os.path.join(get_skills_dir(), "skills_config.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ensure_sys_path():
    """Add project root to sys.path so we can import agent modules."""
    root = get_project_root()
    if root not in sys.path:
        sys.path.insert(0, root)
