import os

from cli.commands import process


def test_release_zip_url_uses_custom_base(monkeypatch):
    monkeypatch.setenv("METACLAW_RELEASE_BASE_URL", "https://downloads.example.com/metaclaw/")

    assert process._release_zip_url("v2.0.10") == "https://downloads.example.com/metaclaw/2.0.10.zip"


def test_release_zip_url_defaults_to_github_tag_archive(monkeypatch):
    monkeypatch.delenv("METACLAW_RELEASE_BASE_URL", raising=False)

    assert process._release_zip_url("2.0.10").endswith("/archive/refs/tags/2.0.10.zip")


def test_find_extracted_project_dir(tmp_path):
    extracted = tmp_path / "metaclaw-2.0.10"
    extracted.mkdir()
    (extracted / "app.py").write_text("# app", encoding="utf-8")

    assert process._find_extracted_project_dir(str(tmp_path)) == str(extracted)


def test_replace_app_from_dir_preserves_local_config_and_runtime(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    (source / "app.py").write_text("new", encoding="utf-8")
    (source / "config-template.json").write_text("template", encoding="utf-8")
    (target / "app.py").write_text("old", encoding="utf-8")
    (target / "config.json").write_text("local", encoding="utf-8")
    (target / "nohup.out").write_text("log", encoding="utf-8")

    backup_dir = process._replace_app_from_dir(str(source), str(target))

    assert (target / "app.py").read_text(encoding="utf-8") == "new"
    assert (target / "config.json").read_text(encoding="utf-8") == "local"
    assert (target / "nohup.out").read_text(encoding="utf-8") == "log"
    assert os.path.isdir(backup_dir)
    assert os.path.exists(os.path.join(backup_dir, "app.py"))
