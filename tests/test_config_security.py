from config import _format_env_override_log, _parse_env_override_value


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
