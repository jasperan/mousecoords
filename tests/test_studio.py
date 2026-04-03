"""Tests for minimal studio profile-pack scaffolding."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mousecoords.automator import main
from mousecoords.config import load_profile
from mousecoords.studio import create_studio_project


def test_create_studio_project_blank(tmp_path):
    project = create_studio_project(tmp_path / "blank_pack")

    assert project.output_dir == tmp_path / "blank_pack"
    assert project.profile_path == tmp_path / "blank_pack" / "profile.yaml"
    assert project.profile_path.exists()
    assert (tmp_path / "blank_pack" / "assets" / "templates" / ".gitkeep").exists()
    assert (tmp_path / "blank_pack" / "assets" / "reference" / ".gitkeep").exists()

    profile = load_profile(str(project.profile_path))
    assert profile.name == "blank_pack"
    assert profile.buttons == []


def test_create_studio_project_from_profile(tmp_path, sample_profile):
    source = tmp_path / "source.yaml"
    from mousecoords.config import save_profile

    save_profile(sample_profile, str(source))
    project = create_studio_project(
        tmp_path / "copied_pack",
        name="copied_name",
        from_profile=str(source),
    )

    profile = load_profile(str(project.profile_path))
    assert profile.name == "copied_name"
    assert len(profile.buttons) == len(sample_profile.buttons)
    assert project.source.endswith("source.yaml")


def test_create_studio_project_refuses_nonempty_dir_without_force(tmp_path):
    output_dir = tmp_path / "occupied"
    output_dir.mkdir()
    (output_dir / "note.txt").write_text("busy")

    with pytest.raises(FileExistsError):
        create_studio_project(output_dir)


def test_studio_new_cli_creates_scaffold(tmp_path, capsys):
    output_dir = tmp_path / "cli_pack"

    with patch(
        "sys.argv",
        ["mousecoords", "studio", "new", "--output", str(output_dir), "--name", "cli_pack"],
    ):
        main()

    captured = capsys.readouterr()
    assert "Created studio scaffold" in captured.out
    assert (output_dir / "profile.yaml").exists()


def test_studio_new_cli_rejects_nonempty_dir(tmp_path, capsys):
    output_dir = tmp_path / "occupied"
    output_dir.mkdir()
    (output_dir / "note.txt").write_text("busy")

    with patch("sys.argv", ["mousecoords", "studio", "new", "--output", str(output_dir)]):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "already exists and is not empty" in captured.out
