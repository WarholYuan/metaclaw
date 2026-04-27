import os

from config import _format_env_override_log, _parse_env_override_value, get_appdata_dir, get_config_path, config


def test_parse_env_override_value_bool():
    assert _parse_env_override_value("true", False) is True
    assert _parse_env_override_value("0", True) is False


def test_parse_env_override_value_list_and_int():
    assert _parse_env_override_value("[\"a\", \"b\"]", []) == ["a", "b"]
    assert _parse_env_override_value("8080", 9899) == 8080


def test_parse_env_override_value_string_preserved():
    assert _parse_env_override_value("true", "") == "true"
    assert _parse_env_override_value("deepseek-v4-pro", "gpt-4o") == "deepseek-v4-pro"


def test_format_env_override_log_masks_sensitive_values():
    msg = _format_env_override_log("open_ai_api_key", "sk-secret-value")
    assert "sk-secret-value" not in msg
    assert "*****" in msg


def test_default_appdata_dir_is_workspace_data():
    old_value = config.get("appdata_dir")
    try:
        config["appdata_dir"] = "~/metaclaw/data"
        assert get_appdata_dir().endswith(os.path.join("metaclaw", "data"))
        assert os.path.isabs(get_appdata_dir())
    finally:
        if old_value is None:
            config.pop("appdata_dir", None)
        else:
            config["appdata_dir"] = old_value


def test_config_path_env_override(monkeypatch, tmp_path):
    path = tmp_path / "custom-config.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("METACLAW_CONFIG_FILE", str(path))

    assert get_config_path() == str(path)
