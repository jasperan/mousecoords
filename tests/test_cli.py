"""Tests for CLI argument parsing and command dispatch."""

import os
import json
import subprocess
import sys

import pytest
from unittest.mock import patch

from mousecoords.automator import main
from mousecoords.bundles import create_bundle


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
        assert "demo" in result.stdout


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

    def test_doctor_json_subprocess_headless(self):
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "mousecoords", "doctor", "--json"],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["total"] >= 1
        assert payload["ok"] is False
        assert any(check["name"] == "display" for check in payload["checks"])


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

    def test_profile_validate_default(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "validate"]):
            main()
        captured = capsys.readouterr()
        assert "is valid" in captured.out

    def test_profile_validate_json(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "validate", "--json"]):
            main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["profile_name"] == "antimatter_dimensions"
        assert payload["ok"] is True

    def test_profile_validate_invalid_exits_nonzero(self, capsys, tmp_path):
        invalid = tmp_path / "invalid.yaml"
        invalid.write_text(
            "name: broken\n"
            "resolution: [1280]\n"
            "poll_interval: 0\n"
            "buttons: []\n"
            "states: []\n"
        )
        with patch("sys.argv", ["mousecoords", "profile", "validate", str(invalid), "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exc_info.value.code == 1
        assert payload["ok"] is False

    def test_profile_validate_missing_profile_exits_cleanly(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "validate", "missing-profile.yaml"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "could not be loaded" in captured.out.lower()

    def test_profile_validate_malformed_yaml_exits_cleanly(self, capsys, tmp_path):
        malformed = tmp_path / "broken.yaml"
        malformed.write_text("name: [unterminated\n")
        with patch("sys.argv", ["mousecoords", "profile", "validate", str(malformed), "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exc_info.value.code == 1
        assert payload["ok"] is False
        assert payload["issues"][0]["code"] == "profile_load_failed"

    def test_profile_inspect_json(self, capsys):
        payload = {
            "profile_name": "demo",
            "source": "demo",
            "button_count": 1,
            "detected_count": 1,
            "ok": True,
            "buttons": [],
            "ocr": {},
        }
        with patch("mousecoords.automator._load_pyautogui"):
            with patch("mousecoords.automator._resolve_profile") as mock_resolve:
                mock_resolve.return_value = (object(), "demo.yaml")
                with patch("mousecoords.inspector.inspect_profile", return_value=payload):
                    with patch("sys.argv", ["mousecoords", "profile", "inspect", "demo", "--json"]):
                        main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["ok"] is True
        assert result["detected_count"] == 1

    def test_profile_inspect_missing_profile_exits_cleanly(self, capsys):
        with patch("sys.argv", ["mousecoords", "profile", "inspect", "missing-profile.yaml", "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exc_info.value.code == 1
        assert payload["issues"][0]["code"] == "profile_load_failed"


class TestRunCommand:
    def test_run_dispatches_to_shared_command(self):
        with patch("mousecoords.automator._run_command") as mock_run:
            with patch("sys.argv", ["mousecoords", "run", "--dry-run", "--once", "--json"]):
                main()
        assert mock_run.call_count == 1
        args = mock_run.call_args.kwargs
        assert args["command_name"] == "run"
        assert args["mode_label"] == "Automation Run"

    def test_automate_dispatches_to_shared_command(self):
        with patch("mousecoords.automator._run_command") as mock_run:
            with patch("sys.argv", ["mousecoords", "automate", "--dry-run", "--once"]):
                main()
        assert mock_run.call_count == 1
        args = mock_run.call_args.kwargs
        assert args["command_name"] == "automate"
        assert args["mode_label"] == "Game Automation"

    def test_run_missing_profile_exits_cleanly(self):
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "mousecoords", "run", "-p", "missing_profile_xyz", "--once", "--json"],
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "missing_profile_xyz" in result.stdout
        assert "Traceback" not in result.stderr


class TestBundleCommand:
    def test_bundle_inspect_json(self, capsys, tmp_path):
        bundle = create_bundle(tmp_path / "sample.zip", {"profile": "demo"})
        with patch("sys.argv", ["mousecoords", "bundle", "inspect", str(bundle), "--json"]):
            main()
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["manifest"]["profile"] == "demo"

    def test_bundle_inspect_missing_exits_cleanly(self, capsys):
        with patch("sys.argv", ["mousecoords", "bundle", "inspect", "missing.zip"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "Bundle not found" in captured.out


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
