"""CLI - Manage your agent from the command line."""

import os as _os
import sys as _sys

_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, _PROJECT_ROOT)

from common.brand import APP_NAME

def _read_version():
    version_file = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "VERSION")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"

__version__ = _read_version()
__app_name__ = APP_NAME
