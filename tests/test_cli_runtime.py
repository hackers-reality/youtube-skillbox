from pathlib import Path
from types import SimpleNamespace

import importlib.metadata

from youtube_skillbox import cli


def test_find_skills_dir_uses_wheel_record_location(tmp_path, monkeypatch):
    engine_dir = tmp_path / "relocated" / "share" / "youtube-skillbox" / "skills" / "youtube" / "scripts"
    engine_dir.mkdir(parents=True)
    (engine_dir / "ytdata.py").write_text("def main(): pass\n", encoding="utf-8")

    record_entry = Path(
        "youtube_skillbox-0.4.5.data/data/share/youtube-skillbox/"
        "skills/youtube/scripts/ytdata.py"
    )
    fake_dist = SimpleNamespace(
        files=[record_entry],
        locate_file=lambda entry: engine_dir / "ytdata.py",
    )
    monkeypatch.setattr(importlib.metadata, "distribution", lambda name: fake_dist)
    monkeypatch.setattr(cli.sysconfig, "get_path", lambda *args, **kwargs: str(tmp_path / "wrong"))
    monkeypatch.setattr(cli.sysconfig, "get_preferred_scheme", lambda name: "user")

    assert cli.find_skills_dir() == str(engine_dir)


def test_find_skills_dir_falls_back_to_source_checkout(tmp_path, monkeypatch):
    package_dir = tmp_path / "repo" / "youtube_skillbox"
    package_dir.mkdir(parents=True)
    engine_dir = tmp_path / "repo" / "skills" / "youtube" / "scripts"
    engine_dir.mkdir(parents=True)
    (engine_dir / "ytdata.py").write_text("def main(): pass\n", encoding="utf-8")

    fake_dist = SimpleNamespace(files=None, locate_file=lambda entry: entry)
    monkeypatch.setattr(importlib.metadata, "distribution", lambda name: fake_dist)
    monkeypatch.setattr(cli, "__file__", str(package_dir / "cli.py"))
    monkeypatch.setattr(cli.sysconfig, "get_path", lambda *args, **kwargs: str(tmp_path / "wrong"))
    monkeypatch.setattr(cli.sysconfig, "get_preferred_scheme", lambda name: "user")

    assert cli.find_skills_dir() == str(engine_dir)
