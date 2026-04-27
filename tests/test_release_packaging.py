import os
import re


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_pyproject_version_matches_cli_version():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        pyproject = f.read()
    with open(os.path.join(ROOT, "cli", "VERSION"), encoding="utf-8") as f:
        cli_version = f.read().strip()

    assert re.search(r'^version = "{}"$'.format(re.escape(cli_version)), pyproject, re.M)


def test_build_system_supports_pep621_metadata():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        pyproject = f.read()

    assert 'requires = ["setuptools>=61.0"]' in pyproject


def test_pyproject_packages_include_core_modules():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        pyproject = f.read()

    for package_glob in ["agent*", "channel*", "models*", "plugins*", "cli*"]:
        assert f'"{package_glob}"' in pyproject


def test_python_version_metadata_allows_313():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        pyproject = f.read()

    assert 'requires-python = ">=3.7,<3.14"' in pyproject


def test_editable_install_exposes_core_namespace_packages():
    from setuptools import find_namespace_packages

    packages = set(find_namespace_packages(ROOT))
    assert {"common", "bridge", "agent.memory", "models", "voice"}.issubset(packages)
