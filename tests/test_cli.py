"""Tests for CLI argument parsing and command dispatch."""

import os
import subprocess
import sys

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from mousecoords.automator import main


class TestCLIHelp:
    def test_no_args_shows_help(self, capsys):
        """Running with no args prints help and exits cleanly."""
        with patch("sys.argv", ["mousecoords"]):
            main()
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "GUI automation" in captured.out

    def test_help_flag(self):
        """--help exits with code 0."""
        with patch("sys.argv", ["mousecoords", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_help_subprocess_headless(self):
        """The top-level CLI should show help without requiring a display."""
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "mousecoords", "--help"],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()


class TestDoctorCommand:
    def test_doctor_runs(self, capsys):
        """Doctor command runs and produces output."""
        with patch("sys.argv", ["mousecoords", "doctor"]):
            main()
        captured = capsys.readouterr()
        assert "System Diagnostics" in captured.out
        assert "pyautogui" in captured.out

    def test_doctor_shows_pass_fail(self, capsys):
        with patch("sys.argv", ["mousecoords", "doctor"]):
            main()
        captured = capsys.readouterr()
        # Should have at least some PASS results
        assert "PASS" in captured.out

    def test_doctor_subprocess_headless(self):
        """Doctor should report display issues instead of crashing headless."""
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "mousecoords", "doctor"],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert "System Diagnostics" in result.stdout
        assert "display" in result.stdout.lower()
        assert "unexpected error" not in result.stdout
        assert "requires an active DISPLAY/GUI session" in result.stdout


class TestProfileCommand:
    def test_profile_list(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "list"]):
            main()
        captured = capsys.readouterr()
        assert "antimatter_dimensions" in captured.out

    def test_profile_show(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "show"]):
            main()
        captured = capsys.readouterr()
        assert "antimatter_dimensions" in captured.out.lower() or "Antimatter" in captured.out

    def test_profile_show_builtin_default_without_profiles_dir(self, capsys, tmp_path):
        with patch("mousecoords.config.get_profiles_dir", return_value=tmp_path):
            with patch("sys.argv", ["mousecoords", "profile", "show"]):
                main()
        captured = capsys.readouterr()
        assert "antimatter_dimensions" in captured.out.lower()

    def test_profile_show_missing(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "show", "-n", "nonexistent_xyz"]):
            main()
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_profile_create(self, capsys, tmp_path):
        with patch("mousecoords.config.get_profiles_dir", return_value=tmp_path):
            with patch("sys.argv", ["mousecoords", "profile", "create"]):
                main()
        captured = capsys.readouterr()
        assert "Created" in captured.out


class TestWatchCommand:
    def test_watch_no_coords_exits(self, capsys):
        """Watch without coordinates or --pick gives helpful error."""
        with patch("sys.argv", ["mousecoords", "watch"]):
            with pytest.raises(SystemExit):
                main()

    def test_watch_no_coords_subprocess_headless(self):
        """Watch should validate arguments before importing GUI code."""
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "mousecoords", "watch"],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Specify coordinates" in result.stdout
        assert "Traceback" not in result.stderr

    def test_watch_with_coords_subprocess_headless(self):
        """GUI-dependent watch mode should fail cleanly when no display is available."""
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "mousecoords", "watch", "-x", "0", "-y", "0"],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "requires an active graphical session" in result.stdout
        assert "Traceback" not in result.stderr


class TestMainModuleEntry:
    def test_python_m_entry(self):
        """mousecoords/__main__.py exists and is importable."""
        import importlib
        spec = importlib.util.find_spec("mousecoords.__main__")
        assert spec is not None
