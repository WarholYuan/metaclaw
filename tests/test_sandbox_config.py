import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import available_setting


def test_sandbox_keys_exist():
    assert "sandbox_enabled" in available_setting
    assert "sandbox_workspace" in available_setting


def test_sandbox_defaults():
    assert available_setting["sandbox_enabled"] is False
    assert available_setting["sandbox_workspace"] == "~/metaclaw-sandbox"
