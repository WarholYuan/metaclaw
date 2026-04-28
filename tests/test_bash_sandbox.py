import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.tools.bash.bash import Bash


def test_bash_uses_cwd_by_default():
    default_cwd = os.getcwd()
    bash = Bash()
    assert bash.cwd == default_cwd


def test_bash_prefers_sandbox_workspace_over_cwd():
    with tempfile.TemporaryDirectory() as sandbox:
        with tempfile.TemporaryDirectory() as workspace:
            bash = Bash(config={"cwd": workspace, "sandbox_workspace": sandbox})
            assert bash.cwd == sandbox


def test_bash_creates_sandbox_dir_if_missing():
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = os.path.join(tmp, "new_sandbox")
        assert not os.path.exists(sandbox)
        bash = Bash(config={"sandbox_workspace": sandbox})
        assert os.path.exists(sandbox)
        assert bash.cwd == sandbox
